import term
from term import Term as T
import properties
from ipdb import set_trace as debug
import computations
import state
import context
from counter import Counter
import relayer
from builtins import builtin
import handlers
import representations
import stackless
from askers import Querier
import convert

debug_mode = False

@stackless.stackless
@term.term_arg('Q')
def ask(Q, parent=None, **kwargs):
    try:
        asker = Asker(Q, ask, parent=parent)
        debug_Q(asker, "Asking")
        result = builtin.dispatch(asker,Q.question)
        if result is not None:
            debug_Q(asker, "Answered", result=result, answer=result.answer)
            #FIXME include the rest of the query?
            return result
        else:
            debug_Q(asker, "Failed to answer")
            meta_answer = asker.ask(meta(representations.quote(Q.question), Q.other)).answer
            response = convert.unquote(asker, meta_answer)
            response = response.explain("going meta to answer [Q]", Q=Q).because("could not answer [Q] directly", Q=Q)
            return asker.reply(value=response)
    except KeyboardInterrupt:
        global debug_mode
        if not debug_mode:
            debug_mode = True
            print("Entering debug mode!")
            return ask(Q, parent=parent, **kwargs)
        else:
            raise

class Asker(Querier, Counter, state.StatefulAsker, context.ContextUpdater, relayer.Relayer):
    def __init__(self, Q=None, ask_func=ask, *args, **kwargs):
        super(Asker, self).__init__(Q=Q, ask_func=ask_func, *args, **kwargs)

#TODO some day I want to move things over into a handler which is an explicit computation
#(it used to be like that, but I eventually had to backtrack)

@builtin("what should be the representation of the response to "
"a question with representation [quoted_Q]? the response should satisfy [properties]")
def meta(asker, quoted_Q, properties):
    handler = asker.ask(state.get_handler()).answer
    #FIXME I need to transfer results
    result = asker.ask(computations.run(
        handler, 
        T.from_dict({handlers.question_var:quoted_Q})
    )).answer
    return asker.reply(answer=result)

def debug_Q(asker, s, result=None, answer=None):
    global debug_mode

    if result is None:
        def skip(asker):
            global debug_mode
            asker.trip = True
            debug_mode = False
    if getattr(asker, "trip", False):
        asker.trip = False
        debug_mode = True

    if debug_mode:
        def show(asker, d):
            tabs = -1
            result = {}
            for x in reversed(asker.ancestors()):
                if x.Q is not None:
                    print("{}Q:{}".format(tabs * "  ", x.Q.question.head))
                    for y in x.Q.question:
                        d[y] = x.Q.question[y]
            if answer is not None:
                print("{}A:{}".format(tabs * "  ", answer.head))
                for x in answer:
                    d[x] = answer[x]
            print "{}({})".format(tabs * "  ", s)
            for x in asker.Q.question:
                if x == 'asker':
                    raise Exception("overwrote asker...")
                d[x] = asker.Q.question[x]
        show(asker, locals())
        debug()
        pass

def no_debug():
    global debug_mode
    debug_mode = False
