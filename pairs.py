import term
from term import Term as T
import fields
import types

pair_type = types.new_type("the type of pairs")

types.set_type(pair_type, T.pair)

def to_pair(asker, p):
    return (fields.get(asker, first(), p), fields.get(asker, second(), p))

first = fields.named_binding(
    "the function that maps a pair to its first element",
    T.pair.head,
    'a'
)

second = fields.named_binding(
    "the function that maps a pair to its second element",
    T.pair.head,
    'b'
)
