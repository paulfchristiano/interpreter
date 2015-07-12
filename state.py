from ipdb import set_trace as debug
import weakref
import db as database
from datum import Datum as D
import computation

history_H = "represents a state with history of commands [history]"
handler_H = "represents a state where questions are handled by [handler]"
head_list_H = "represents a state which has seen expressions [heads]"

class State(object):
    """
    Stores the state of an interpreter

    This includes the log of what has been typed, the list of commands that have been entered,
    and the handler which processes new questions.
    The state can be extended with new information as needed.

    An instance of State stores a datum representing the state.
    It also stores information about an element in the database where the state should be stored

    State includes methods for translating data for storage in the database.
    """


    def __init__(self, 
            db=None,
            handle="current_interpreter_state", 
            db_name="tooldb",collection_name="data",
            state=None):

        if db is None and db_name is not None and collection_name is not None:
            db = database.Database(db_name,collection_name)

        self.db = db
        self.handle = db.make_id(handle) if self.db else None

        if state is None and db is None:
            raise Exception("Must provide either a starting strate or a database!")

        self.state = state
        if state is None: self.load_state()

    #Loading and saving-----------------

    def load_state(self):
        if self.db is None:
            raise Exception("Cannot load a state that is not associated with a database!")
        self.state = self.db.load(self.handle)

    def save_state(self):
        if self.db is None:
            raise Exception("Cannot save a state that is not associated with a database!")
        self.db.save_as(self.state,self.handle)

    def mockup(self):
        """
        Creates a copy of self which will be written to a different place in the database.
        Invoked when we want a state, but don't want to save changes to that state.
        """
        return State(
                handle = self.db.make_id(),
                db = self.db,
                state=self.state
            )

    #Getters and setters-----------------

    def get_historical_heads(self):
        for m in self.state.modifiers.to_list():
            if m.head == head_list_H:
                return m['heads']

    def get_history(self):
        for m in self.state.modifiers.to_list():
            if m.head == history_H:
                return m['history']
        return None

    def get_handler(self):
        for m in self.state.modifiers.to_list():
            if m.head == handler_H:
                return m['handler']

    def add_head(self,head):
        def add_head_to_list(m):
            if m.head == head_list_H:
                l = m['heads']
                return m.update(heads=D.make_list(head,l))
            return None
        self.state = self.state.modifier_map(add_head_to_list)

    def replace_history(self,new_history):
        def replace_history(m):
            if m.head == history_H:
                return m.update(history=new_history)
            else:
                return m
        self.state = self.state.modifier_map(replace_history)

    def set_history(self,a, b):
        def set_history(m):
            if m.head == history_H:
                new_history = D.make_dict(D.from_str(a),D.from_str(b),m['history'])
                return m.update(history=new_history)
        self.state = self.state.modifier_map(set_history)

def starting_state():
    """
    Return the starting state for a new interpreter
    """

    return D(
            "a representation of a possible state of the interpreter",
            [D(history_H, history=D.from_dict({})),
             D(handler_H,handler=computation.simple_handler()),
             D(head_list_H,heads=D.from_list([]))]
        )
