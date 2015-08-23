import term
from term import Term as T
from dispatch import Dispatcher
import updates
from updates import updater
import convert
from convert import converter
import termtypes
from termtypes import is_type

int_type = termtypes.new_type("the type of integers")

#Canonicalization---------------------------------

#TODO convert other things
def to_int(asker, k):
    if k.to_int() is not None:
        return k.to_int()
    return literalizer.dispatch(asker, k)

literalizer = Dispatcher("int literalizer", ('integer',))

@is_type(int_type)
@literalizer(T.negative.head)
def literalize_negative(asker, x):
    return -to_int(asker, x)

@is_type(int_type)
@literalizer(T.double.head)
def literalize_double(asker, x):
    return 2*to_int(asker, x)

@is_type(int_type)
@literalizer(T.double_plus_one.head)
def literalize_double_plus_one(asker, x):
    return 2*to_int(asker, x) + 1

@is_type(int_type)
@literalizer(T.zero.head)
def literalize_zero(asker):
    return 0

#Incrementer--------------------------------------

incrementer = Dispatcher("incrementer", ('x',))

@updater("the update that increases the updated number by 1")
def increment(asker, object):
    return incrementer.dispatch(asker, object)

@incrementer(T.zero.head)
def increment_zero(asker):
    return asker.reply(answer=T.double_plus_one(T.zero()))

@incrementer(T.double.head)
def increment_even(asker, x):
    return asker.reply(answer=T.double_plus_one(x))

@incrementer(T.double_plus_one.head)
def increment_odd(asker, x):
    return asker.reply(answer=T.double(updates.update(increment(), x)))

def plus_one(x):
    return updates.update(increment(), x)

#TODO decrement, increemnt negative numbers, larger increments?
#TODO think about representations etc.
