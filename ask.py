from datum import Datum as D
from ipdb import set_trace as debug
import sys
import re
from greenlet import greenlet
from utilities import unformat, clear
import explore
import computation as c

has_answer_H = "has answer [A]"
vacuous_H = "the assertion that doesn't imply anything"
and_H = "[a] and [b] are both true"
vacuous = D(vacuous_H)
is_answer_H = "answering [Q]"
question_var = D("a variable referring to the question currently being answered")

#The main affair------------------------

def answer(Q,state):

    asker = ask.QuestionContext(Q,state)

    #First: if the question is about a computation, run it
    result = builtin_eval(Q,state)

    #For now, we just go straight to crutch to save effort.
    #(This preempts the next two conditions.)
    #In the medium term this will probably get taken out so that we can build up the handler
    #and crutch only has to handle stuff the handler doesn't want to.
    #In the long term there will be no crutch.
    if result is None:
        result = crutch.crutch(Q,state)

    #Second: if the question is about crutch(Q), call crutch
    #this is a stopgap that should be absorbed into the default handler
    if result is None and Q.head == crutch_answer_Q:
        #XXX this is wrong. The answer is taken as an answer to Q, but it's an answer to Q['question'].
        #"has answer [Q]" should get replaced with "the referent of 'question' has answer [A]"
        #this should then be unwound within the crutch computation, which should extract that...
        #for now the two errors can cancel out, and I'll just leave it as is
        result = crutch.crutch(Q['question'],state)

    #Finally: apply the default handler
    if result is None:
        result = asker.ask_tail(c.run_Q(state.get_handler(),{c.question_var:Q}))

    return result.explain(is_answer_H,Q=Q)



#Extracting answers---------------------

class NoAnswerError(Exception):
    pass

def extract_answer_firmly(d):
    A = extract_answer(d)
    if A is None:
        raise NoAnswerError("Firmly extracted an answer, but no answer was present")
    else:
        return A

def process_answer(d,f):
    if d.head == and_H:
        a = process_answer(d['a'], f)
        b = process_answer(d['b'], f)
        if a is None:
            return b
        if b is None:
            return a
        return both(a, b)
    else:
        return f(d)


def extract_answer(d):
    if d.head == has_answer_H:
        return d['A']
    elif d.head == and_H:
        A = extract_answer(d['a'])
        return A if A is not None else extract_answer(d['b'])
    else:
        return None

#XXX having to keep doing this extraction is a bit awkward
#I should either write a decorator or use askers more extensively
def ask_and_extract(Q,state,*args,**kwargs):
    Q = Q_from_args(Q,*args,**kwargs)
    response = ask(Q,state)
    answer = extract_answer(response)
    return response,answer

def ask_firmly(Q,state,*args,**kwargs):
    Q = Q_from_args(Q,*args,**kwargs)
    d = ask(Q,state)
    return extract_answer_firmly(d)

def both(a,b):
    if a == vacuous:
        return b
    elif b == vacuous:
        return a
    else:
        return D(and_H,a=a,b=b)

def pass_through(A):
    A = extract_answer(A)
    return as_answer(A) if A is not None else no_answer()

def as_answer(A):
    return D(has_answer_H,A=A)

def no_answer():
    return vacuous

#Preparing questions--------------------

def Q_from_args(Q,*args,**kwargs):
    if type(Q) is str:
        return D(Q,*args,**kwargs)
    else:
        return Q

def needs_preprocessing(f):
    def preprocessed_f(self,Q,*args,**kwargs):
        Q = Q_from_args(Q,*args,**kwargs)
        Q = self.preprocess(Q)
        return f(self,Q)
    return preprocessed_f

class QuestionContext(object):

    def __init__(self,Q,state,preprocessing=None):
        self.state = state
        self.Q = Q
        self.preprocessing = preprocessing

    def preprocess(self,Q):
        return Q if self.preprocessing is None else self.preprocessing(Q) 

    @needs_preprocessing
    def ask_firmly(self,Q):
        return ask_firmly(Q,self.state)

    @needs_preprocessing
    def ask_tail(self,Q):
        A = pass_through(ask(Q,self.state))
        return A

    @needs_preprocessing
    def ask(self,Q):
        return ask(Q,self.state)

    @needs_preprocessing
    def ask_and_extract(self,Q):
        return ask_and_extract(Q,self.state)

    def as_answer(self,A):
        return as_answer(A)

    def no_answer(self):
        return vacuous



#Ask------------------------------------

def start_greenlets_and_ask(Q,state):
    greenlets = []
    QorA = Q
    is_question = True
    class context:
        threshold = None
    while True:

        """
        if context.threshold is None or len(greenlets) <= context.threshold:
            context.threshold = None
            if len(greenlets) < context.threshold:
                debug()
            m = explore.explore(QorA,state)
            if is_question:
                def process_m(m):
                    if m.head == explore.sends_message_H:
                        if m['message'].to_str() == 'return':
                            context.threshold = len(greenlets)
                    elif m.head == explore.conjunction_H:
                        process_m(m['a'])
                        process_m(m['b'])
                process_m(m)
        """

        if is_question:
            g = greenlet(lambda Q : (False,answer(Q,state)))
        else:
            if greenlets:
                g = greenlets.pop()
            else:
                return QorA
        is_question, QorA = g.switch(QorA)
        if is_question:
            greenlets.append(g)

def ask(Q,state,*args, **kwargs):

    Q = Q_from_args(Q,*args,**kwargs)
    parent = greenlet.getcurrent().parent
    if parent is None:
        #if parent is none we are running in the main greenlet
        #in this case we need to set up the stackless machinery and start it
        return start_greenlets_and_ask(Q,state)
    elif sys.gettrace() is not None:
        #if we are debugging, we don't want to switch control
        return answer(Q,state)
    else:
        #in this case we are running in a non-main greenlet
        #we want to pass control back to the main greenlet
        #it should find the answer to Q, and give it back to us with another switch
        #we then return the answer to Q
        #the (True,Q) value indicates that we want the value of Q, rather than Q being our answer
        return parent.switch((True,Q))
