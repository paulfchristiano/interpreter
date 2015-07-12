import term
from term import Term as T
from term import as_head
from itertools import chain
from dispatch import Dispatcher
from ipdb import set_trace as debug
from memoization import memoize
import builtins
import booleans

#TODO setters for properties
#TODO cut the simple iterator in atomic property, use the field inferrer
#TODO in general, unify fields and properties

checker = Dispatcher("checker", ("property", "object"))
#object: the object on which the property is being tested

def atomic_property(name):
    custom_checker = Dispatcher("check {}".format(name), ("property",))

    @custom_checker(name)
    def direct_inference(asker):
        return T.from_bool(True)

    @custom_checker(both.head)
    def infer_from_both(asker, a, b):
        from_a = custom_checker.dispatch(asker, a)
        from_b = custom_checker.dispatch(asker, b)
        return booleans.either(from_a, from_b)

    @custom_checker()
    def give_up(asker, m):
        return T.from_bool(False)

    @checker(name)
    def easy_check(asker, object):
        #FIXME seems pretty awkward
        import fields
        m = fields.get(asker, fields.modifier(), object)
        return asker.reply(answer=custom_checker.dispatch(asker, m))

    return easy_check

@as_head("satisfies both [a] and [b]")
def both(a, b):
    if a == b:
        return a
    elif a.head == T.trivial.head:
        return b
    elif b.head == T.trivial.head:
        return a
    else:
        return T(both.head, a=a, b=b)

@checker(T.trivial.head)
def trivial(asker, object):
    return asker.reply(answer=T.from_bool(True))

@checker("is satisfied by all objects")
def is_trivial(asker, property):
    return trivial_checker.dispatch(asker, property)

trivial_checker = Dispatcher("tester for triviality", ("property",))

#FIXME should have better tests for triviality...
@trivial_checker(T.trivial.head)
def trivial_is_trivial(asker):
    return asker.reply(answer=T.from_bool(True))

def simple_iterator(p):
    if p.head == T.trivial.head:
        return
    elif p.head == both.head:
        for x in simple_iterator(p['a']):
            yield x
        for y in simple_iterator(p['b']):
            yield y
    else:
        yield p

#TODO want support for multiple evaluation strategies, e.g. lookup in modifiers or compute
#TODO want to have property caching, where a property that checks out gets added
#TODO in order to do that need to have strategic reasoning about what properties are worth including 
#(if you include too many, then the cost of iterating over them will be prohibitive)

@builtins.builtin("does [object] satisfy property [p]?")
def check(asker, p, object):
    return checker.dispatch(asker, p, object)

def combine(properties, *args):
    if len(args) > 0:
        properties = (properties,)+args
    n = len(properties)
    if n == 0:
        return trivial()
    elif n == 1:
        return properties[0]
    else:
        return both(combine(properties[:n/2]),combine(properties[n/2:]))

def simple_add_modifier(object, new):
    if new.head == trivial.head:
        return object
    old_modifier = object.modifier
    return object.simple_update(_modifier=both(old_modifier, new))

#FIXME this shouldn't exist
def modifier_map(object, f):
    def g(m):
        result = f(m)
        return m if result is None else result
    return combine(f(x) for x in simple_iterator(object.modifier))

def check_firmly(asker, p, object):
    return booleans.ask_firmly(asker, check(p, object))
