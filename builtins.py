from dispatch import Dispatcher
import term
from term import Term as T
from ipdb import set_trace as debug

builtin = Dispatcher("builtin", ("question",))

#FIXME this should probably get taken over by dictionaries...
@builtin("what is a value bound to the key [key] in the bindings [bindings]?")
def lookup(asker,bindings,key):
    return searcher.dispatch(asker,bindings,key)

searcher = Dispatcher("searcher", ("bindings", "key"))

@searcher(T.dict_cons.head)
def simple_lookup(asker, search_key, key, value, other):
    are_equal = asker.ask(equal(key, search_key)).answer
    #FIXME should avoid these cyclic imports
    import convert
    if are_equal is not None and convert.to_bool(asker, are_equal):
        return asker.reply(answer=value)
    else:
        return asker.ask_tail(lookup(other, search_key))

equal = term.simple("are [a] and [b] equal?", "a", "b")
