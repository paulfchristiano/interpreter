from datum import Datum as D
import ask
import crutch
import state

home = D("Home",[crutch.context_sensitive_question])
default_state = state.State()

def run(state=default_state):
    ask.ask(home,state)
