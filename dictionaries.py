import builtins
import relayer
import hold
import fields
from fields import getter, setter
import properties
import pairs
import term
from term import as_head, Term as T
import updates
from dispatch import Dispatcher
#FIXME this is an awkward dependence, I don't know where else to put to_term_bindings though
import strings
import booleans
from frozendict import frozendict
import functions
import lists
import termtypes
from termtypes import is_type

from ipdb import set_trace as debug


cons = T.dict_cons
empty = T.empty_dict

dict_type = termtypes.new_type("the type of dictionaries")
termtypes.set_types(dict_type, cons, empty)

image = term.simple("the function that maps a dictionary to the image of [k] in that dictionary", "k")

@getter(image.head, cons.head)
def cons_image(asker, k, key, value, other):
    if booleans.ask_firmly(asker, builtins.equal(k, key)):
        return asker.reply(answer=value)
    else:
        return asker.ask_tail(
            fields.get_field(image(k), other), 
            handler=asker.pass_through(not_found.head)
        )

@getter(image.head, empty.head)
def image_empty(asker, k):
    return asker.reply(value=not_found())

@as_head("the referenced key was not found in the referenced dictionary")
def not_found():
    return T(not_found.head)

@setter(image.head, cons.head)
def set_image(asker, new_value, k, key, value, other):
    if booleans.ask_firmly(asker, builtins.equal(k, key)):
        return asker.reply(answer=cons(key=key, value=new_value, other=other))
    else:
        return asker.reply(answer=cons(key=key, value=value,
            other=updates.update(updates.set_field(image(k), new_value), other)
        ))

@setter(image.head, empty.head)
def set_empty_dict_image(asker, new_value, k):
    return asker.reply(answer=cons(key=k, value=new_value, other=empty()))

def to_dict(asker, d):
    return literalizer.dispatch(asker, d)

literalizer = Dispatcher("dict literalizer", ('dictionary',))

#FIXME using mutable state here is a little bit scary...

@literalizer(cons.head)
def literalize_cons(asker, key, value, other):
    result = to_dict(asker, other)
    result[key] = value
    return result

@literalizer(empty.head)
def literalize_empty(asker):
    return {}

def to_term_bindings(asker, d):
    return frozendict({
        strings.to_str(asker, k):v
        for k, v in to_dict(asker, d).iteritems()
    })

#Mapping------------------------------------------

@functions.applier("the function that maps [d] to the dictionary which maps "
        "each x to the value of [f] at [d](x)")
def map(asker, d, f):
    return mapper.dispatch(asker, d, f)

mapper = Dispatcher("dictionary mapper", ("dictionary", "function"))

@mapper(empty.head)
def map_empty(asker, f):
    return asker.reply(answer=empty())

@mapper(cons.head)
def map_cons(asker, f, key, value, other):
    return asker.reply(answer=cons(
        key,
        functions.apply(f, value),
        functions.apply(map(f), other)
    ))

#From items---------------------------------------

@is_type(dict_type)
@hold.unholder("the dictionary that maps a to b for each pair (a, b) in the list [l]", False)
def from_items(asker, l):
    return itemizer.dispatch(asker, l)

itemizer = Dispatcher("dictionary itemizer", ("list",))

#FIXME remember the explanations
@itemizer(lists.cons.head)
def itemize_cons(asker, head, tail):
    a = fields.get(asker, pairs.first(), head)
    b = fields.get(asker, pairs.second(), head)
    return asker.reply(answer=cons(a, b, from_items(tail)))

@itemizer(lists.empty.head)
def itemize_empty(asker):
    return asker.reply(answer=empty())

def item_iterator(asker, d):
    return lists.iterator(asker, lists.from_dict(d))
