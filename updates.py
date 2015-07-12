import term
from term import Term as T
from term import as_head
from dispatch import Dispatcher
import hold
import convert
from convert import converter
import fields
import properties
import builtins
import booleans
import builtins
from builtins import builtin
from ipdb import set_trace as debug
import representations

#Applying updates---------------------------------

updater = Dispatcher("updater", ("update", "object"))
#object: the object being updated

#TODO when you convert something to a nicer form, you should probably just propagate that
#(i.e., tell the parent to make the substitution)
#TODO some updates should leave modifiers on (if the update itself can handle them)
#but right now they always have to be stripped

#TODO we should evaluate in place if it's cheap...
#(when asked to hold an update)
@hold.unholder("the result of applying update [update] to [object]")
def update(asker, update, object):
    return asker.ask_tail(apply_update(update, object))

#FIXME this is stupid, but I keep having name conflicts...
held_update = update

@builtin("what is the result of applying [update] to [object]?")
def apply_update(asker, update, object):
    fast_result = fast_updater.dispatch(asker, update, object)
    if fast_result is not None:
        return fast_result
    exposed_object = asker.ask(convert.convert(object, convert.exposed_modifier())).firm_answer
    old_modifier = exposed_object.modifier
    #FIXME these forms seems more correct but are way too slow...
    #if properties.check_firmly(asker, properties.is_trivial(),  old_modifier):
    #if booleans.ask_firmly(asker, builtins.equal(properties.trivial(), old_modifier)):
    if properties.trivial.head == old_modifier.head:
        return asker.ask_tail(apply_update_raw(update, exposed_object))
    keep_or_strip = asker.ask(modifiers_to_strip(update, old_modifier, exposed_object)).value
    kept_modifier = fields.get(asker, fields.implication_about(to_keep()), keep_or_strip)
    stripped_modifier = fields.get(asker, fields.implication_about(to_strip()), keep_or_strip)
    stripped_object = exposed_object.simple_update(_modifier=kept_modifier)
    stripped_result = asker.ask(apply_update_raw(update, stripped_object)).firm_answer
    return asker.ask_tail(reintroduce_modifier(
        stripped_modifier,
        update,
        stripped_object,
        stripped_result
    ))

@builtin("what is the result of applying [update] to [object]? "
        "it is not worth trying to simplify [object] by "
        "removing properties")
def apply_update_raw(asker, update, object):
    return updater.dispatch(asker, update, object)

#Basic updates------------------------------------

@as_head("the update that applies [a] then applies [b]")
def compose(a,b):
    if a.head == trivial.head:
        return b
    elif b.head == trivial.head:
        return a
    else:
        return T(compose.head, a=a, b=b)

@updater(compose.head)
def compose_updater(asker, object, a, b):
    return asker.ask_tail(apply_update(b, update(a, object)))

@updater("the update that doesn't affect anything")
def trivial(asker, object):
    return asker.reply(answer=object)

@updater("transformation into [target]")
def become(asker, object, target):
    return asker.reply(answer=target)

#Fast results-------------------------------------

fast_updater = Dispatcher("fast updater", ("update", "object"))

@fast_updater(trivial.head)
def trivial_update(asker, object):
    return asker.reply(answer=object)

@fast_updater(become.head)
def become_update(asker, object, target):
    return asker.reply(answer=target)

#Reintroducing modifiers--------------------------

@builtin("of [property], what property should be removed from [object] before applying [update] (and restored after), "
    "and which should be kept during the update?")
def modifiers_to_strip(asker, update, property, object):
    return modifier_stripper.dispatch(asker, update, property, object)

modifier_stripper = Dispatcher("modifier stripper", ("update", "property", "object"))

to_keep = fields.atomic_field("the function that sends a question to the property that should be retained in the referenced situation")
to_strip = fields.atomic_field("the function that sends a question to the property "
        "that should be restored later in the referenced situation")

def keep_strip(keep=None, strip=None):
    if keep is None:
        keep = properties.trivial()
    if strip is None:
        strip = properties.trivial()
    return properties.both(
            fields.field_value(to_keep(), keep),
            fields.field_value(to_strip(), strip)
    )

#TODO in the long run we should do something more sophisticated
@modifier_stripper()
def generic_stripper(asker, update, property, object):
    if properties.check_firmly(asker, convert.irreducible(), representations.quote(property)):
        return asker.reply(value=keep_strip(strip=property))

@modifier_stripper(become.head)
def become_stripper(asker, property, object, target):
    return asker.reply(value=keep_strip(keep=property))

@modifier_stripper((None, properties.both.head))
def both_stripper(asker, update, object, a, b):
    keeps = properties.trivial()
    strips = properties.trivial()
    for x in [a, b]:
        keep_or_strip = asker.ask(modifiers_to_strip(update, x, object)).value
        new_keeps = fields.get(asker, fields.implication_about(to_keep()), keep_or_strip)
        keeps = properties.both(keeps, new_keeps)
        new_strips = fields.get(asker, fields.implication_about(to_strip()), keep_or_strip)
        strips = properties.both(strips, new_strips)
    return asker.reply(value=keep_strip(keep=keeps, strip=strips))

translator = Dispatcher("translator", ("property", "update", "input", "output"))

@builtin("if [input] became [output] after applying [update], "
         "what would [input] have become if it had satisfied [property]?")
def reintroduce_modifier(asker, property, update, input, output):
    result = translator.dispatch(asker, property, update, input, output)
    if result is None:
        debug()
    return result

@translator(fields.field_value.head)
def reintroduce_field_value(asker, update, input, output, field, value):
    new_value = asker.ask(translate_field(field, value, update, input, output))
    if new_value.has_answer():
        return asker.reply(answer=held_update(
            apply_to_field(
                fields.modifier(),
                set_field(fields.implication_about(field),new_value.answer)
            ),
            output
        ))
    else:
        return output

@translator(None, trivial.head)
def translate_trivial(asker, property, input, output):
    return asker.reply(answer=output)

@translator(properties.trivial.head)
def translate_trivial_property(asker, update, input, output):
    return asker.reply(answer=output)

@translator((None, compose.head, None, update.head), (False, False, False, True))
def translate_composite_held_arg(asker, property, transferring_across, input, object, update):
    if convert.ask_firmly(asker, builtins.equal(update, transferring_across)):
        if convert.ask_firmly(asker, builtins.equal(input, object)):
            return asker.reply(answer=held_update(update, properties.simple_add_modifier(object, property)))

@translator(None, compose.head, None, update.head)
def translate_composite(asker, property, input, object, update, a, b):
    if convert.ask_firmly(asker, builtins.equal(update, b)):
        intermediate = asker.ask(reintroduce_modifier(
            property, 
            a, 
            input, 
            object
        )).firm_answer
        return asker.reply(answer=held_update(update, intermediate))
    #FIXME should I do something if that's not what happened? e.g. if the evaluation got pushed further?

@translator(properties.both.head)
def translate_both(asker, update, input, output, a, b):
    intermediate = asker.ask(reintroduce_modifier(a, update, input, output)).firm_answer
    with_a = properties.simple_add_modifier(input, a)
    return asker.ask_tail(reintroduce_modifier(b, update, with_a, intermediate))

def translate_simply(name, exclude=None):
    exclude = exclude + [compose.head]
    @translator(name, False)
    def simple_translate(asker, property, update, input, output):
        reduced_update = convert.reduce(asker, update)
        if reduced_update.head not in exclude:
            return asker.reply(answer=properties.simple_add_modifier(output, property))

#translate_simply(properties.trivial.head) #(slower than the above, but basically equivalent)

#Setters and fields-------------------------------

#TODO now that I have a "become" update, I can make set_field a special case of apply_update...
@updater("the update that sets field [field] to [new_value]")
def set_field(asker, object, field, new_value):
    return fields.setter.dispatch(asker,field,object,new_value)

#TODO some day it would be nice to retain the option of doing these rewrites stepwise
#(but it doesn't seem worth it for now)
@fields.setter(fields.compose.head)
def set_composite(asker, object, new_value, f, g):
    return asker.ask_tail(apply_update(
        apply_to_field(f, set_field(g, new_value)),
        object
    ))

@updater("the update that applies update [update] to field [field]")
def apply_to_field(asker, object, field, update):
    value = fields.get(asker, field=field, object=object)
    #FIXME this update should sometimes be held
    #but for now, I have no way to make good tradeoffs about the costs of doing that
    new_value = asker.ask_firmly(apply_update(update, value))
    return asker.ask_tail(apply_update(set_field(field, new_value), object))

@modifier_stripper(apply_to_field.head)
def application_stripper(asker, property, object, update, field):
    if booleans.ask_firmly(asker, builtins.equal(field, fields.modifier())):
        return asker.reply(value=keep_strip(keep=property))

@modifier_stripper((apply_to_field.head, fields.field_value.head), (True, False))
def strip_field_value(asker, property, object, update, field):
    property_field = property['field']
    if booleans.ask_firmly(asker, builtins.equal(field, property_field)):
        return asker.reply(value=keep_strip(keep=property))

#FIXME we keep mirroring code for setting and applying to, there should really be some way to see both as the same thing
@modifier_stripper(set_field.head)
def setter_stripper(asker, property, object, field, new_value):
    if booleans.ask_firmly(asker, builtins.equal(field, fields.modifier())):
        return asker.reply(value=keep_strip(keep=property))

#Translating field values-------------------------

#FIXME not quite the right description, since these field annotations may actually change
#the semantics of an item, and not merely be 'saying what we already know'
@builtin("if the value of [field] at [input] was [value], and [input] is transformed "
        "into [output] by [update], then what is the value of [field] at [output]?")
def translate_field(asker, field, value, update, input, output):
    return field_translator.dispatch(asker, field, update, value, input, output)

field_translator = Dispatcher("field translator", ("field", "update", "old_value", "old", "new"))

@field_translator(None, apply_to_field.head)
def translate_field_across_application(asker, to_translate, old_value, old, new, field, update):
    if booleans.ask_firmly(asker, fields.orthogonal(to_translate, field)):
        return asker.reply(answer=old_value)
    elif booleans.ask_firmly(asker, builtins.equal(to_translate, field)):
        return asker.reply(answer=updates.update(update, field))

@field_translator(None, set_field.head)
def translate_field_across_setting(asker, to_translate, old_value, old, new, field, new_value):
    if booleans.ask_firmly(asker, fields.orthogonal(to_translate, field)):
        return asker.reply(answer=old_value)
    elif booleans.ask_firmly(asker, builtins.equal(to_translate, field)):
        return asker.reply(answer=new_value)

#Modifiers----------------------------------------

@updater("the update that removes all properties equal to [to_cut]")
def remove_modifier(asker, object, to_cut):
    return asker.reply(answer=object)

@updater("the update that adds the property [modifier]")
def add_modifier(asker, object, modifier):
    return asker.reply(answer=object.simple_update(_modifier=modifier))

#FIXME this seems really brittle, relying on the translator for both to go first
#I may need to make moderately large changes to fix this
@translator((None, remove_modifier.head))
def translate_removal(asker, property, old, new, to_cut):
    if convert.to_bool(asker.ask(builtins.equal(to_cut, object)).firm_answer):
        return asker.reply(answer=new)
    else:
        return asker.reply(answer=properties.simple_add_modifier(new, property))

#Strings------------------------------------------

#FIXME this is only here because the strings file has to be very low level so that to_str can be called...
@updater("the update that prepends [s] to the updated string")
def prepend_str(asker, object, s):
    return asker.reply(answer=strings.concat(s, object))

#Lifting------------------------------------------

@updater("the update that transforms the representation of an object "
        "to the representation of the result of applying [update] to that object")
def lift(asker, repr, update):
    return asker.reply(answer=representations.make(
        held_update.head, 
        update=representations.quote(update), 
        object=repr
    ))

#FIXME these are stopgaps, in the long run I should really deal with these modifiers

@translator(representations.has_id.head)
def translate_id(asker, update, old, new, id):
    return asker.reply(answer=new)

@translator(representations.has_source.head)
def translate_source(asker, update, old, new, source):
    return asker.reply(answer=new)

@fields.getter("the function that maps a term to the representation of the value of [field] "
     "at the referent of that term")
def lift_field(asker, object, field):
    response = asker.ask(fields.get_field(field, convert.unquote(asker, object)))
    if response.has_answer():
        return asker.reply(answer=representations.quote(response.answer))
    else:
        return asker.reply()
    
#FIXME this is a very unnatural way of lifting things
#I don't think it will generally produce very good answers (representations might get totally unchanged during setting)
#but doing it more carefully is a ways away
@fields.setter(lift_field.head)
def set_lifted_field(asker, object, new_value, field):
    raw_result = asker.ask(apply_update(
        set_field(field, convert.unquote(asker, new_value)), 
        convert.unquote(asker, object)
    )).firm_answer
    return asker.reply(answer=representations.quote(raw_result))
