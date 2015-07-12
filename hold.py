import convert
from dispatch import Dispatcher
from builtins import builtin
import fields

raw_unholder = Dispatcher("unholder", ("value",))

held_heads = set()

#TODO should modifier moving be done here, or in conversion, or both?
def unholder(name, hides_modifiers=True):
    def unhold_f(f):
        @convert.converter(name, False)
        def convert_held(asker, value, req):
            #FIXME in the long run, shouldn't be firm_answer,
            #need to think about what to do when you don't get an answer
            result = asker.ask(unhold(value)).firm_answer
            return asker.ask_tail(convert.convert(result, req))
        maker = raw_unholder(name)(f)
        convert.is_reducible(maker)
        held_heads.add(name)
        if hides_modifiers:
            convert.hides_modifiers(maker)
        return maker
    return unhold_f

@builtin("what is the value of [object]? the result should be explicitly "
    "represented, rather than implicitly represented as the result of running "
    "some computation.")
def unhold(asker, object):
    result = object
    while result.head in held_heads:
        result= asker.ask(unhold_once(result)).firm_answer
    return asker.reply(answer=result)

@builtin("what is a value equal to [object]? it's better for the result to be "
    "closer to being explicitly represented")
def unhold_once(asker, object):
    return raw_unholder.dispatch(asker, object)

@unholder("the value of [field] in [object]")
def get(asker, field, object):
    return asker.ask_tail(fields.get_field(field, object))

@unholder("the answer to [Q]")
def answer(asker, Q):
    return asker.ask_tail(Q)
