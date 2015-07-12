from ipdb import set_trace as debug
import term
from term import as_head, Term as T
import database
import askers
from dispatch import Dispatcher
import handlers
import properties
from builtins import builtin
import fields
import relayer
import updates
import context

state = term.simple("a state of the interpeter where [history] maps "
    "strings to the user's historical response to those strings, "
    "and where [computation] is invoked to handle computations",
    'history', 'computation')

history = fields.named_binding(
    "the function that maps an interpreter state to the history of commands that "
    "have been entered in that state",
    state.head,
    'history'
)

handler = fields.named_binding(
    "the function that maps an interpreter state to the computation invoked "
    "to handle questions in that state",
    state.head,
    'computation'
)

def starting_state():
    return state(T.from_dict({}), handlers.view_handler())

#TODO it seems like somehow history should be a composite resource locator
#(almost a composite field, but there is no object you are accessing it on...)
#I could make it a field that you typically apply to a dummy object
#that seems pretty ugly though

@builtin("what is the current state of the interpreter?")
def get_state(asker):
    return asker.reply(answer=asker.state)

@builtin("what computation should handle questions?")
def get_handler(asker):
    state = asker.ask(get_state()).firm_answer
    return asker.ask_tail(fields.get_field(handler(), state))

@builtin("apply [update] to the interpreter's state")
def update_state(asker, update):
    asker.update(update, asker.state)
    return asker.reply()

@builtin("what is the history of commands that have been entered?")
def get_history(asker):
    state = asker.ask(get_state()).firm_answer
    return asker.ask_tail(fields.get_field(history(), state))

@builtin("apply [update] to the history of commands that have been entered")
def update_history(asker, update):
    asker.ask(update_state(updates.apply_to_field(history(), update)))
    asker.reply()

use_state = term.simple("should be computed using interpreter state [state]", "state")
is_state = term.simple("the state of the interpreter used to answer the referenced question")

#FIXME the implementation of state changes seems very awkward
#there are several levels of aberaction where a change occurs, and I don't know if I believe that it will
#all work out...
class StatefulAsker(context.ContextUpdater):

    def __init__(self, Q, name="rootv5", db=None, collection=None, *args, **kwargs):
        super(StatefulAsker, self).__init__(Q, *args, **kwargs)
        self.db = None
        self.name = None
        if not hasattr(self, 'state'):
            if isinstance(db, database.Termsbase):
                self.db = database
            else:
                self.db = database.Termsbase(db=db, collection=collection)
            self.name = name
            try:
                self.state = database.load_pointer(self.db, name)
            except KeyError:
                self.state = starting_state()
        self.state_changed = False
        self.tag(is_state(), self.state)

    #FIXME decide between this and the dispatcher...
    def process_query(self, other):
        if other.head == use_state.head:
            self.state = other['state']
            return properties.trivial()
        else:
            return super(StatefulAsker, self).process_query(other)

    def incoming_update(self, source, Q, update, repr_change=None):
        if source.head == is_state.head:
            self.update(update, self.state, repr_change)
        else:
            super(StatefulAsker, self).incoming_update(source, Q, update, repr_change)

    def update(self, update, v, *args, **kwargs):
        super(StatefulAsker, self).update(update, v, *args, **kwargs)
        if v.id in self.internal:
            internal = self.internal[v.id]
            source = self.source[internal]
            if source.head == is_state.head:
                self.state = self.refresh(self.state)

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, new_value):
        self.state_changed = True
        assert(isinstance(new_value, T))
        self._state = new_value

    def ask(self, new_Q, **kwargs):
        new_Q = new_Q.add(use_state(self.state))
        reply = super(StatefulAsker, self).ask(new_Q, **kwargs)
        if self.db is not None and self.state_changed:
            database.save_as(self.db, self.name, self.state)
            self.state_changed = False
        return reply
