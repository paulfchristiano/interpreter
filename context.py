import askers
import relayer
import updates
import convert
import fields
import properties
import representations
import term
from term import Term as T
from ipdb import set_trace as debug
import dispatch
import strings

#TODO I should be allowed to have representation changes interleaved with updates?

#FIXME the explicit references to 'bindings' probably aren't kosher...
#FIXME I'm still not handling the references vs. object level on questions well
#(I think that everything is kosher, but I am just equivocating on where to put the conversions)
#FIXME There is a serious risk that I'm making some call to a dispatcher directly,
#and that I'm ending up using a dirty asker rather than a fresh one
#I don't know what I should do to track that better,
#but I think that I should probably do something

#FIXME I want the variables to be represented literally I think
#needing to unquote them continues to drive home the awkwardness of the current arrangement

#TODO this can easily take quadratic time in cases where it could be done in linear time,
#because you could pool up several updates and just turn them into replacements

#TODO should I throw an error if the user gets two updates without refreshing in the middle?


class ContextUpdater(relayer.Relayer):

    def __init__(self, *args, **kwargs):
        super(ContextUpdater, self).__init__(*args, **kwargs)
        self.internal = {}
        self.changed = {}
        self.original = {}
        self.current = {}
        self.updates = {}
        self.source = {}
        if self.Q is not None:
            self.question_bindings = self.Q.question.bindings
            for k, v in self.question_bindings.iteritems():
                self.tag(in_question(T.from_str(k)), v)
        #FIXME I think that I need to think more about simple updates vs. proper updates

    def tag(self, source, v):
        internal = len(self.internal)
        self.internal[v.id] = internal
        self.original[internal] = v
        self.changed[internal] = False
        self.current[internal] = v
        self.updates[internal] = updates.trivial()
        self.source[internal] = source


    #FIXME this should work even if v is a child, or whatever...
    #I should also use a better system for tracking these things
    #(and for deciding whether updates should propagate)
    def refresh(self, v):
        if v.id in self.internal:
            internal = self.internal[v.id]
            result = self.current[internal]
            #FIXME this can cause terrible trouble if two different things being tracked
            #have the same id...
            #my current approach will probably have a hard time dealing with that
            self.internal[result.id] = internal
            return result
        else:
            raise ValueError("refreshing an untagged value")

    #TODO check for items that were made out of things you care about
    #if one of them is updated, see if it implies an update to something you care about
    #TODO if B is a field of A and A is updated, propagate the change to B
    def update(self, change, v, repr_change=None):
        if repr_change is None:
            repr_change = updates.lift(change)
            default_repr_change = True
        else:
            default_repr_change = False
        if v.id in self.internal:
            internal = self.internal[v.id]
            #if we are updating stale information...
            #apply the update, but not any representation change
            #(if info is stale, probably just a representation change...)
            if v.id != self.current[internal].id:
                if change.head == updates.trivial.head:
                    return True
                else:
                    repr_change = updates.lift(change)
            self.updates[internal] = updates.compose(self.updates[internal], change)
            self.current[internal] = convert.unquote(
                    self, 
                    self.ask_firmly(updates.apply_update(
                        repr_change, 
                        representations.quote(self.current[internal])
                    ))
                )
            self.changed[internal] = True
            return True
        else:
            #FIXME think more about how this propagation ought to work
            #it seems like something is going oddly w.r.t levels of abstraction
            #also should I propagate back across field accesses? I don't know...
            #also this whole thing seems kind of like a mess, I don't expect it to work consistently
            def propagate_back(s):
                if s.head == term.because.head:
                    return propagate_back(s['operation'])
                elif s.head == term.explain.head:
                    return propagate_back(s['operation']) or propagate_back(s['prior'])
                elif s.head == term.accessing.head:
                    if change.head == updates.trivial.head:
                        parent = s['term']
                        binding = s['binding']
                        return self.update(
                            updates.trivial(),
                            parent,
                            repr_change=updates.apply_to_field(
                                representations.referent_of(T.from_str(binding)),
                                repr_change
                            ).explain("tracing backwards from [v]", v=v)
                        )
                    else:
                        return False
                elif s.head == askers.answering.head:
                    Q = s['Q']
                    if Q.head == fields.get_field.head:
                        parent = Q['object']
                        field = Q['field']
                        return self.update(
                            updates.apply_to_field(field, change), 
                            parent, 
                            repr_change=updates.apply_to_field(updates.lift_field(field), repr_change)
                        )
                    elif Q.head == convert.convert.head:
                        previous = Q['value']
                        return self.update(
                            change,
                            previous,
                            repr_change=None
                        )
                return False
            return propagate_back(v.source)


    def incoming_update(self, source, Q, update, repr_change=None):
        if source.head == in_question.head:
            referenced = Q.question[strings.to_str(self, source['s'])]
            self.update(update, referenced, repr_change)

    def process_response(self, response, Q, *args, **kwargs):
        #FIXME seems bad to redefine the dispatcher each time...
        update_handler = dispatch.SimpleDispatcher("contextual response processor", ("response",))
        @update_handler(context_update.head)
        def process_update(source, update, repr):
            repr_change = updates.become(repr)
            self.incoming_update(source, Q, update, repr_change=repr_change)
            return properties.trivial()

        result = update_handler.dispatch(response)
        if result is None:
            result = super(ContextUpdater, self).process_response(response, Q, *args, **kwargs)
        return result

    def set_repr(self, v, new_repr):
        self.update(updates.trivial(), v, repr_change=updates.become(new_repr))

    def reply(self, *args, **kwargs):
        reply = super(ContextUpdater, self).reply(*args, **kwargs)
        if self.Q is None:
            return reply
        responses = []
        for internal in self.internal.values():
            if self.changed[internal]:
                update = self.updates[internal]
                source = self.source[internal]
                responses.append(context_update(
                    source, 
                    update, 
                    representations.quote(self.current[internal])
                ))
        return reply.add(properties.combine(responses))

class UntaggedUpdateError(ValueError):
    pass

context_update = term.simple(
    "the value of [source] at the referenced question should be updated by applying [update], "
    "and the result should be represented as [repr]",
    "source", "update", "repr"
)
in_question = term.simple("the object referred to as [s] in the referenced question", "s")
