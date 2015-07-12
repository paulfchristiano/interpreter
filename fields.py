from dispatch import Dispatcher
from ipdb import set_trace as debug
import term
from term import Term as T, as_head
import properties
import builtins
from builtins import builtin
import booleans

getter = Dispatcher("getter", ("field", "object",))
#object: the object on which we are getting the field

setter = Dispatcher("setter", ("field", "object", "new_value"))
#object: the object on which we are setting the field
#new_value: the new value to which we are setting the field

#TODO think about properties affecting field retrieval...
#(e.g. we might be counting accesses, or have normative properties true of children...)

#TODO I should probably implement properties as boolean-valued fields

#FIXME if an object is in a reducible form, like an update or held question,
#then an access to its modifiers may not return the "real" modifiers.
#It seems worth thinking more about avoiding errors that that could cause.

field_not_found = term.simple("the referenced field wasn't found on the referenced object")

#TODO should call .explain more often...
#FIXME should cache the values of fields probably? Either as properties or by id.
#FIXME it seems like their should really just be a "cached" decorator?
#that operates at the meta level...
@builtin("what is the value of [field] of [object]?")
def get_field(asker, field, object):
    reply = getter.dispatch(asker, field, object)
    if reply is None:
        reply = asker.reply()
    if not reply.has_answer():
        reply.add(field_not_found())
    return reply

def get(asker, field, object):
    return asker.ask(get_field(field, object)).firm_answer

def getting(field, object):
    return term.MetaTerm(getting.head, field=field, object=object)
getting.head = "accessing field [field] of [object]"

#Atomic fields------------------------------------

def field_value(field, value):
    return T(field_value.head, field=field, value=value)
field_value.head = "[value] is the value of [field] at this object"

def atomic_field(name):
    field = T(name)
    @getter(name)
    def easy_get(asker, object):
        return asker.ask_tail(
                get_field(
                    implication_about(field), 
                    get(asker, modifier(), object)
                )
            )
    @setter(name)
    def easy_set(asker, object, new_value):
        #FIXME the cyclic import again, would be nice to do better
        import updates
        return asker.reply(answer=updates.update(
            updates.apply_to_field(
                modifier(), 
                updates.set_field(implication_about(field), new_value)
            ),
            object
        ))
    return easy_get

def named_binding(name, head, key):
    @getter((name, head), (True, False))
    def easy_get(asker, object):
        return asker.reply(answer=object[key])

    @setter((name, head), (True, False))
    def easy_set(asker, object, new_value):
        return asker.reply(answer=object.simple_update(**{key:new_value}))
        return this_setter.dispatch(asker, object)

    return easy_get

#Inference from properties------------------------

@getter("the function that maps a property to the value of [field] for any object satisfying it")
def implication_about(asker, object, field):
    return inferrer.dispatch(asker, field, object)

@setter(implication_about.head)
def set_implication_about(asker, object, new_value, field):
    result = asker.ask(soft_set_implication(object, field, new_value))
    if result.has_answer():
        return result
    else:
        return asker.reply(answer=properties.both(field_value(field, new_value), object))

@builtin("if [property] pins down the value of [field], return the new property "
        "that is as similar as possible but instead implies that [field] has value [new_value]")
def soft_set_implication(asker, property, field, new_value):
    return implier.dispatch(asker, property, field, new_value)

implier = Dispatcher("implication setter", ("property", "field", "new_value"))

#FIXME it feels like removing things etc. should somehow be slicker than it is

@implier(properties.both.head)
def set_both_implication(asker, field, new_value, a, b):
    for x, y in [(a, b), (b, a)]:
        r = asker.ask(soft_set_implication(x, field, new_value))
        if r.has_answer():
            return asker.reply(answer=properties.both(r.answer, y))
    return asker.reply(value=unknown())

@implier(properties.trivial.head)
def set_trivial_implication(asker, field, new_value):
    return asker.reply(value=unknown())

@implier(field_value.head)
def set_implication(asker, to_set, new_value, field):
    if booleans.ask_firmly(asker, builtins.equal(to_set, field)):
        return asker.reply(answer=field_value(to_set, new_value))
    else:
        return asker.reply(value=unknown())

#Inference from modifier--------------------------

#TODO better handle the "couldn't tell" signal
#(send it at all...)

inferrer = Dispatcher("inferrer", ("field", "modifier"))

#TODO this should probably just apply in every case
@builtin("what is the value of [field] for an object satisfying [property]?")
def infer_from_property(asker, field, property):
    return inferrer.dispatch(asker, field, property)

@inferrer((None, properties.both.head))
def infer_from_conjunction(asker, field, a, b):
    result = asker.ask(infer_from_property(field, a)).answer
    if result is not None:
        return asker.reply(answer=result)
    result = asker.ask(infer_from_property(field, b)).answer
    if result is not None:
        return asker.reply(answer=result)
    return asker.reply(value=unknown())


#FIXME in some cases you can infer one field from another...
#so this will need to be more careful in the long run
@inferrer((None, field_value.head))
def infer_from_field_value(asker, to_infer, field, value):
    if booleans.ask_firmly(asker, builtins.equal(to_infer, field)):
        return asker.reply(answer=value)
    else:
        return asker.reply(value=unknown())

@as_head("the value of the referenced field "
    "was not inferred from the referenced property")
def unknown():
    return T(unknown.head)

#Properties---------------------------------------

#Dictionary lookups---------------------

@getter("the function that maps a dictionary to the image of [key] in that dictionary")
def lookup(asker, key, object):
    return asker.ask_tail(dictionaries.lookup(key, object))

@setter(lookup.head)
def set_value(asker, key, object, new_value):
    return asker.ask_tail(dictionies.set_value(key, value, object))

#Composites-----------------------------

@getter("the function that applies [f] then applies [g] to the result")
def compose(asker, object, f, g):
    handler = asker.pass_through(field_not_found.head)
    intermediate = asker.ask(get_field(f, object), handler=handler).answer
    if intermediate is None:
        return asker.reply()
    else:
        return asker.ask_tail(get_field(g, intermediate), handler=handler)

#Modifiers------------------------------

#FIXME this should actually work in a more complicated way?
#or rather, I would like to have a simple modifier access, but I would also like to have
#a way to access all properties that I know to be true about a term,
#which is a more subtle operation
@term.as_head("the function that maps an object to the most stringest property we know to be true about it")
def modifier():
    return T(modifier.head)

#Orthogonality------------------------------------

@builtin("if we change [field1], can we guarantee that it won't affect the value of [field2]?")
def orthogonal(asker, field1, field2):
    if booleans.ask_firmly(asker, builtins.equal(field1, field2)):
        return asker.reply(answer=T.no())
    result = orthogonality_tester.dispatch(asker, field1, field2)
    if result is not None: return result
    result = orthogonality_tester.dispatch(asker, field2, field1)
    if result is not None: return result

orthogonality_tester = Dispatcher("orthogonality tester", ("field1", "field2"))

def are_orthogonal(head1, head2):
    @orthogonality_tester(head1, head2)
    def return_yes(asker):
        return asker.reply(answer=T.yes())
