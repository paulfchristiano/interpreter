import fields
from dispatch import Dispatcher
import convert
import term
from term import Term as T
import ints
import builtins
import types
from types import is_type

string_type = types.new_type("the type of strings")
char_type = types.new_type("the type of characters")

#Converting to strings----------------------------

#TODO the default representations of characters, lists, strings, etc.
#have a distinguished place, because they can be quickly manipulated
#there needs to be some way for that to come through (eventually)

#FIXME I'd like to memoize this, but it's hard because of the dependence on the asker
#in reality I'm basically happy to ignore that, as with convert
#I could write another cache here...
#maybe best is to make a new asker-ignoring id-based cache
def to_str(asker, s):
    if s.to_str() is not None:
        return s.to_str()
    result = literalizer.dispatch(asker, s)
    if result is not None:
        return result
    else:
        chars = fields.get(asker, list_of_chars(), s)
        return ''.join(to_char(c) for c in lists.iterator(asker, chars))

literalizer = Dispatcher("string literalizer", ("string",))

#FIXME characters might not be literal, should probably have a character literalizer as well
@is_type(string_type)
@literalizer(T.simple_string.head)
def literalize_simple(asker, list):
    import lists
    return ''.join(to_char(asker, c) for c in lists.to_list(asker, list))

list_of_chars = fields.named_binding(
    "the function that maps a string to its list of characters",
    T.simple_string.head,
    'list'
)

@is_type(string_type)
@literalizer("the string formed by concatenating [a] with [b]")
def concat(asker, a, b):
    return to_str(asker, a) + to_str(asker, b)


#Converting to chars------------------------------

def to_char(asker, c):
    if c.to_char() is not None:
        return c.to_char()
    result = char_literalizer.dispatch(asker, c)
    if result is not None:
        return result
    else:
        k = asker.ask_firmly(ascii_code(c))
        return chr(ints.to_int(k))

char_literalizer = Dispatcher("character literalizer", ("char",))

@is_type(char_type)
@char_literalizer(T.simple_char.head)
def literalize_simple_char(asker, x):
    return chr(ints.to_int(asker, x))

ascii_code = term.simple("what is the ascii code of the character [c]?", "c")
