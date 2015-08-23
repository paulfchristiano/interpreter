import term
from dispatch import Dispatcher
import builtins

typesetter = Dispatcher("typesetter", ("object",))

#TODO add types for computations, functions, updates, fields, properties, questions...
#TODO add type checks, subtyping...
#TODO add parametrized types

#FIXME should maybe ask more specifically for some kind of brute type
#overall this is starting to lean on abstractions that are a bit heavier than I would like
#but I don't have the time to do things more properly
@builtins.builtin("what is a type of which [x] is an instance?")
def type(asker, x):
    return typesetter.dispatch(asker, x)

def is_type(t):
    def set_by_head(f):
        set_type(t, f)
        return f
    return set_by_head

#NOTE using t() so that I can have parametrized types later
#but for this function it would be more natural to just pass in the constructed type
#I think this may bite me at some point
def set_type(t, head):
    if hasattr(head, 'head'):
        head = head.head
    @typesetter(head)
    def return_type(asker):
        return asker.reply(answer=t())
    return head

def set_types(t, *heads):
    return [set_type(t, head) for head in heads]

known_types = set()

def new_type(head, *args):
    result = term.simple(head, *args)
    set_type(meta_type, result)
    known_types.add(result)
    return result

meta_type = term.simple("the type of types")
new_type(meta_type.head)
