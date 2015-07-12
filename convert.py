from dispatch import Dispatcher
import term
from term import Term as T
from collections import defaultdict
import properties
from properties import checker
import builtins
from builtins import builtin
import fields
import representations
from ipdb import set_trace as debug
try:
    from pytest import set_trace as test_debug
except ImportError:
    pass
from frozendict import frozendict
import booleans
import strings

converter = Dispatcher("converter", ('value', 'requirement'))
#req: a desired property for the post-conversion representation

#FIXME I would prefer incorporate this into the interpreter state rather than using global state
#it seems somewhat plausible that the interpeter state should be a MetaTerm rather than a Term?
#that would make this significantly easier
#at the very least I can construct it by making a metaterm and then quoting it

#maps id --> a set of equivalent forms that have been produced by conversions
synonyms = defaultdict(set)
#maps (id, req.id) --> a satisfying form
conversion_cache = {}

#FIXME I think that something is wrong here with respect to quoting
#FIXME I want to be able to take small diffs from things that heve ids
@builtin("what is [value]? the representation of the result should satisfy [req]")
def convert(asker, value, req):
    starting_cost = asker.cost
    def check(x):
        return properties.check_firmly(asker, req, representations.quote(x))

    if check(value):
        return asker.reply(answer=value)

    #TODO in the long run we might want to leave properties in if they can simplify the conversion
    old_modifier = value.modifier
    stripped = value.simple_update(_modifier=properties.trivial())
    id = stripped.id
    result = None
    if (id, req.id) in conversion_cache:
        result = conversion_cache[(id, req.id)]
    if result is None:
        for form in synonyms[id]:
            if check(form):
                result = form
    if result is None:
        response = asker.ask(raw_convert(value, req))
        if response.has_answer():
            result = response.answer
        else:
            return asker.reply()
    synonyms[id].add(result)
    conversion_cache[(id, req.id)] = result
    #FIXME what an ugly hack; this sort of thing will hopefully be done automatically
    if (asker.cost - starting_cost > 30 and
            booleans.ask_firmly(asker, nicer_representation(
                representations.quote(value),
                representations.quote(result),
                req
            ))):
        asker.set_repr(value, representations.quote(result))
    return asker.reply(answer=properties.simple_add_modifier(result, old_modifier))

#FIXME the real semantics here is that "_modifier" is missing, not "missing some properties"
#I don't know how to express that right now...
@builtin("what is an object that is the same as [value], but potentially missing "
        "some of the properties of [value]? "
        "the representation of the result should satisfy [req]")
def raw_convert(asker, value, req):
    return converter.dispatch(asker, value, req)

@builtin("is [repr2] a better representation to us than [repr1], "
    "given [repr2] satisfies [req] but [repr1] does not?")
def nicer_representation(asker, repr1, repr2, req):
    if (booleans.ask_firmly(asker, builtins.equal(req, irreducible())) or 
        booleans.ask_firmly(asker, builtins.equal(req, exposed_modifier()))):
        return asker.affirm()
    else:
        #FIXME I should do something much more sophisticated here
        return asker.deny()


#Conversion to literal types----------------------

#FIXME these have been superseded by real conversions in the appropriate files

def is_literal_term():
    return T(is_literal_term.head)
is_literal_term.head = "is a canonical representation of a term"

#FIXME I think that this belongs in representations area probably?
def unquote(asker, value):
    #FIXME more circular dependencies
    import dictionaries, strings
    if isinstance(value, representations.Representation):
        return value.represents
    #FIXME all of this should be done with requirements embedded in questions
    #rather than asking and then converting
    bindings = asker.ask(fields.get_field(representations.bindings(), value)).firm_answer
    proto_literal_bindings = dictionaries.to_dict(asker, bindings)
    literal_bindings = frozendict({strings.to_str(asker, k):unquote(asker, v) 
            for k, v in proto_literal_bindings.iteritems()})
    head = asker.ask(fields.get_field(representations.head(), value)).firm_answer
    literal_head = strings.to_str(asker, head)
    return T(literal_head, literal_bindings)

reducible_heads = set()
def is_reducible(f):
    if type(f) is str:
        reducible_heads.add(f)
    else:
        reducible_heads.add(f.head)
    return f

@checker("can probably be reduced to a simpler form")
def reducible(asker, rep):
    head = asker.ask(fields.get_field(representations.head(), rep)).firm_answer
    result = strings.to_str(asker, head) in reducible_heads
    return asker.reply(answer=T.from_bool(result))

@checker("cannot be reduced to a manifestly simpler form by computing")
def irreducible(asker, rep):
    head = asker.ask(fields.get_field(representations.head(), rep)).firm_answer
    result = strings.to_str(asker, head) not in reducible_heads
    return asker.reply(answer=T.from_bool(result))
    #FIXME this is much cleaner, but too slow; at any rate could remove duplicate code
    return asker.ask_tail(properties.check(opposite(reducible()), rep))

#FIXME I should somehow handle a conversion fail gracefully
def reduce(asker, object):
    return asker.ask(convert(object, irreducible())).firm_answer

makermaker = Dispatcher("dummy", ("thing",))

def reducer(name):
    is_reducible(name)
    def simplify(f):
        converter((name, irreducible.head))(f)
        return makermaker(name)(f)
    return simplify

#Applications of reduction--------------

#TODO I can probably do the equality tests in a more intelligent way...
@builtins.builtin(builtins.equal.head)
def equal(asker, a, b):
    #FIXME wrong place to call this!
    #but given that this function is willing to say no, nothing else can get priority
    #in the long run I hope to have a better system...
    if a.id == b.id:
        return asker.affirm()
    a, b = [reduce(asker, x) for x in [a, b]]
    if a.id == b.id:
        return asker.affirm()
    else:
        return asker.deny()

@properties.trivial_checker()
def check_trivial_default(asker, property):
    if properties.check_firmly(asker, irreducible(), property):
        return asker.reply(answer=T.from_bool(False))
    

#Properties---------------------------------------

hidden_modifier_heads = set()
def hides_modifiers(f):
    hidden_modifier_heads.add(f.head)
    return f

#TODO in the long run I want to be able to just define what a property is...
#and then have the conversions be handled for me
@checker("is a representation with most easily accessible properties of the represented object in '_modifier'")
def exposed_modifier(asker, rep):
    head = asker.ask(fields.get_field(representations.head(), rep)).answer
    if head is None:
        return asker.reply(answer=T.no())
    else:
        result = strings.to_str(asker, head) not in hidden_modifier_heads
        return asker.reply(answer=T.from_bool(result))

@converter((None, exposed_modifier.head))
def expose_modifier(asker, object):
    rep = representations.quote(object)
    head = strings.to_str(asker, fields.get(asker, representations.head(), rep))
    if head not in hidden_modifier_heads:
        new_modifier = convert.reduce(asker, object.modifier)
        return asker.reply(answer=object.simple_update(_modifier=new_modifier))

#FIXME in general things seem to live in really awkward places because of dependency issues
#there is no way this belongs in conversions...
@fields.getter(fields.modifier.head)
def get_modifier(asker, object):
    reduced_object = asker.ask(convert(object, exposed_modifier())).firm_answer
    return asker.reply(answer=reduced_object.modifier)

@fields.setter(fields.modifier.head)
def set_modifier(asker, object, new_value):
    reduced_object = asker.ask(convert(object, exposed_modifier())).firm_answer
    return asker.reply(answer=reduced_object.simple_update(_modifier=new_value))


#Booleans-----------------------------------------

@checker(properties.both.head)
def check_both(asker, object, a, b):
    replies = [asker.ask(check(x, object)) for x in [a, b]]
    for reply in replies:
        if not reply.has_answer():
            return asker.reply()
    return asker.reply(answer=both(*[reply.answer for reply in replies]))

@checker("does not satisfy [x]")
def opposite(asker, object, x):
    underlying = asker.ask(properties.check(x, object)).firm_answer
    return asker.reply(answer=booleans.opposite(underlying))

@reducer(booleans.either.head)
def either(asker, a, b):
    for x in [a, b]:
        if to_bool(asker, x):
            return asker.reply(answer=T.from_bool(True))
    return asker.reply(answer=T.from_bool(False))

@reducer(booleans.both.head)
def both(asker, a, b):
    for x in [a, b]:
        if not to_bool(asker, x):
            return asker.reply(answer=T.from_bool(False))
    return asker.reply(answer=T.from_bool(True))

@reducer(booleans.opposite.head)
def convert_opposite(asker, a):
    return opposite_converter.dispatch(asker, a)

opposite_converter = Dispatcher("opposite converter", ('x',))

@opposite_converter(T.yes.head)
def yes_to_no(asker):
    return asker.reply(answer=T.no())

@opposite_converter(T.no.head)
def no_to_yes(asker):
    return asker.reply(answer=T.yes())

#Fields-------------------------------------------

#FIXME in a terrible place...
#maybe I should just merge representations and convert?
#TODO should irreducible use the same format? I need to think about that
@reducer(representations.referent_of.head)
def reduce_referent_of(asker, s):
    import dictionaries
    return asker.reply(answer=fields.compose(representations.bindings(), dictionaries.image(s)))
