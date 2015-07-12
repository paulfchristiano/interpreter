from dispatch import Dispatcher
import term
from term import Term as T
from term import as_head
from ipdb import set_trace as debug

import functions
import convert
from convert import converter, is_reducible
import builtins
from builtins import builtin
import fields
from fields import getter, setter
import properties
from properties import checker
import updates
from updates import updater
import types
from types import is_type

list_type = types.new_type("the type of lists")

@is_type(list_type)
@as_head(T.empty_list.head)
def empty():
    return T.empty_list()

@is_type(list_type)
@converter(T.cons.head)
def cons(asker, req, head, tail):
    return asker.ask_tail(make_list(req, empty(), T.cons(head, tail), empty()))

@is_type(list_type)
@as_head("the list with last element [last] and first elements [init]")
def snoc(init, last):
    return T(snoc.head, init=init, last=last)

@is_type(list_type)
@as_head("the list formed by concatenating [a] to [b]")
def concat(a, b):
    return T(concat.head, a=a, b=b)

@builtins.builtin("what is the list that starts with [a] and ends with [b]?"
                  "the output should be a canonical representation of a list, if [b] is")
def make_list(asker, a, b):
    return list_maker.dispatch(asker, a, b)

list_maker = Dispatcher("list maker", ("prefix", "suffix",))

@list_maker(empty.head)
def make_from_empty(asker, suffix):
    return asker.reply(answer=suffix)

@list_maker(concat.head)
def make_from_concat(asker, suffix, a, b):
    new_suffix = asker.ask(make_list(b, suffix)).firm_answer
    return asker.ask_tail(make_list(a, new_suffix))

@list_maker(snoc.head)
def make_from_snoc(asker, suffix, init, last):
    new_suffix = cons(suffix, last)
    return asker.ask_tail(make_list(init, new_suffix))

@list_maker(cons.head)
def make_from_cons(asker, suffix, head, tail):
    new_suffix = asker.ask(make_list(tail, suffix)).firm_answer
    return asker.reply(answer=cons(head, new_suffix))

def singleton(x):
    return cons(x, empty())

#Dictionaries-------------------------------------

@is_type(list_type)
@convert.reducer("a list of pairs (key, [map](key)) where key ranges over the range of [map]")
def from_dict(asker, map):
    return dict_to_list.dispatch(asker, map)

dict_to_list = Dispatcher("dictionary to list", ("map",))

@dict_to_list(T.dict_cons.head)
def dict_cons_to_list(asker, key, value, other):
    return asker.reply(answer=cons(T.pair(key, value), from_dict(other)))

@dict_to_list(T.empty_dict)
def empty_dict_to_list(asker):
    return asker.reply(answer=empty())

#Conversion---------------------------------------

def to_list(asker, l):
    return list(iterator(asker, l))

def iterator(asker, l):
    return list_iterator.dispatch(asker, l)

list_iterator = Dispatcher("list iterator", ("list",))

@list_iterator(cons.head)
def iterate_cons(asker, head, tail):
    yield head
    for y in iterator(asker, tail):
        yield y

@list_iterator(empty.head)
def iterate_empty(asker):
    return iter(())

#FIXME this keeps all of the iterators on the stack,
#with quadratic cost and a stack overflow if the list is long
@list_iterator(snoc.head)
def iterate_snoc(asker, init, last):
    for x in iterator(asker, init):
        yield x
    yield last

@list_iterator(concat.head)
def iterate_concat(asker, a, b):
    for x in iterator(asker, a):
        yield x
    for y in iterator(asker, b):
        yield y

first = fields.named_binding(
    "the function that maps a list to its first element",
    cons.head,
    'head'
)

#FIXME should probably assert that the length is 1 or something?
#also maybe there should be a singleton type?
only = first

tail = fields.named_binding(
    "the function that maps a list to all but its first element",
    cons.head,
    'tail'
)

#Properties---------------------------------------

@as_head("is an empty list")
def is_empty():
    return T(is_empty.head)

@checker(is_empty.head, empty.head)
def empty_is_empty(asker):
    return asker.reply(answer=T.yes())

@checker(is_empty.head, cons.head)
def cons_isnt_empty(asker):
    return asker.reply(answer=T.no())

@checker(is_empty.head, snoc.head)
def snoc_isnt_empty(asker):
    return asker.reply(answer=T.no())

#FIXME should probably cache length and so on, since this is a ridiculously slow approach
@checker(is_empty.head, concat.head)
def test_concat_empty(asker, a, b):
    return booleans.both(
        convert.hold(properties.check(is_empty(), a)),
        convert.hold(properties.check(is_empty(), b))
    )

#Map and filter-----------------------------------

@as_head("the update that applies [to_apply] to each element of the updated list")
def update_map(update):
    return T(update_map.head, to_apply=update)

@updater(update_map.head, cons.head)
def map_simple(asker, to_apply, head, tail):
    return asker.reply(answer=T.cons(
        updates.update(to_apply, head), 
        updates.update(update_map(to_apply), tail)
    ))

@updater(update_map.head, concat.head)
def map_concat(asker, to_apply, a, b):
    return asker.reply(answer=concat(
       updates.update(update_map(to_apply), a), 
       updates.update(update_map(to_apply), b)
    ))

@updater(update_map.head, snoc.head)
def map_last(asker, to_apply, init, last):
    return asker.reply(answer=snoc(
        updates.update(update_map(to_apply), init),
        updates.update(to_apply, last)
    ))

@updater(update_map.head, empty.head)
def map_empty(asker, to_apply):
    return asker.reply(answer=empty())

#TODO I should probably have a notion of functions (which fields specialize)
#and can use this to implement maps, filters, and so on

#TODO also the framework for conversions / accesses / etc. is not yet good enough
#that writing these feels worthwhile...


#Dealing with the last element--------------------

last = fields.named_binding(
    "the function that maps a list to its last element",
    snoc.head,
    'last'
)

@getter(last.head, cons.head)
def get_last_simple(asker, head, tail):
    return asker.ask_tail(field.get_field(last(), tail))

@setter((last.head, cons.head), (True, False))
def set_last_simple(asker, l, new_value):
    return asker.reply(answer=l.simple_update(tail=updates.update(
        updates.set_field(last(), new_value), 
        l['tail']
    )))

@getter(last.head, concat.head)
def get_last_concat(asker, a, b):
    #FIXME deal with the case where b is empty
    return asker.ask_tail(fields.get_field(last_element(), b))

@setter((last.head, concat.head), (True, False))
def set_last_concat(asker, l, new_value):
    #FIXME deal with the case where b is empty
    return asker.reply(answer=l.simple_update(b=updates.update(
        updates.set_field(last(), new_value), 
        l['b']
    )))

@updater("the update that appends [last] to the updated list")
def append(asker, l, last):
    return asker.reply(answer=snoc(l, last))

#Zipping------------------------------------------

#FIXME should do conversions more strategically!
#FIXME I should have a better way of indicating "this seems always solid..."
#also seems plausible I should call it something like WHNF
#and also seems plausible it should play a different role from other conversions?
#TODO I should propagate error signals, like zips are mismatched,
#when they are mismatched
@is_reducible
@is_type(list_type)
@converter("the list whose ith entry is the pair of the ith entry from [a] and the ith entry "
        "from [b]")
def zip(asker, req, a, b):
    if (properties.check_firmly(asker, is_empty(), a) or 
            properties.check_firmly(asker, is_empty(), b)):
        return asker.reply(answer=empty())
    zipped_first = T.pair(fields.get(asker, first(), a), fields.get(asker, first(), b))
    zipped_tail = zip(fields.get(asker, tail(), a), fields.get(asker, tail(), b))
    return asker.ask_tail(convert.convert(cons(zipped_first, zipped_tail), req))

#Functions----------------------------------------

@functions.applier("the function that maps anything to a list containing only that thing")
def make_singleton(asker, arg):
    return asker.reply(answer=singleton(arg))
