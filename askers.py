import properties
from memoization import memoize, memoize_constructor
import term
from term import Term as T
import dispatch
from ipdb import set_trace as debug

class BaseAsker(object):

    def __init__(self, Q, ask_func, parent=None):
        if Q is None:
            #top-level asker
            self.Q = None
        else:
            self.Q = Query(question=Q.question, other=self.process_query(Q.other))
        self.children = []
        self.parent = parent
        if parent is not None:
            parent.children.append(self)
        self.ask_func = ask_func

    @term.term_arg('Q')
    def ask(self, Q, handler=None, **kwargs):
        response = self.ask_func(Q, parent=self)
        if getattr(self, "slow", False):
            debug()
        return response.set(self.process_response(response.value, Q=Q, handler=handler))

    def process_query(self, other):
        processor = dispatch.SimpleDispatcher("processor", ("other",))
        @processor(properties.both.head)
        def process_both(a, b):
            return properties.both(*[self.process_query(x) for x in (a, b)])
        @processor()
        def process_generic(q):
            return q
        return processor.dispatch(other)

    def process_response(self, response, Q, handler=None):
        result = None
        if handler is not None:
            result = handler.dispatch(response)
        if result is None:
            processor = dispatch.SimpleDispatcher("processor", ("response",))
            @processor(properties.both.head)
            def process_both(a, b):
                return properties.both(*[self.process_response(x, Q=Q, handler=handler) for x in (a, b)])
            @processor()
            def process_generic(p):
                return p
            result = processor.dispatch(response)
        return result

    #FIXME I should probably use Q to refer only to questions
    #and use something different to refer to queries...
    def reply(self, **kwargs):
        return Reply(question=self.Q.question, **kwargs)

    def ancestors(self):
        p = self
        result = []
        while p is not None:
            result.append(p)
            p = p.parent
        return result

    def ask_tail(self, *args, **kwargs):
        answer = self.ask(*args, **kwargs).answer
        return self.reply() if answer is None else self.reply(answer=answer)

    def ask_firmly(self, *args, **kwargs):
        return self.ask(*args, **kwargs).firm_answer

    def affirm(self):
        return self.reply(answer=T.from_bool(True))

    def deny(self):
        return self.reply(answer=T.from_bool(False))

class Querier(BaseAsker):

    def __init__(self, Q, *args, **kwargs):
        super(Querier, self).__init__(self.to_query(Q), *args, **kwargs)

    def ask(self, Q, *args, **kwargs):
        return super(Querier, self).ask(self.to_query(Q), *args, **kwargs)

    @staticmethod
    def to_query(Q):
        if Q is None:
            return None
        elif isinstance(Q, Query):
            return Q
        else:
            return Query(question=Q)

#Queries----------------------

class Query():

    def __init__(self, question, other=None):
        if other is None:
            other = properties.trivial()
        self.other = other
        self.question = question

    def add(self, property):
        return Query(question=self.question, other=properties.both(property, self.other))

    def quote(self):
        return T("a query with question [question] and requested properties [properties]",
                  question=self.question, properties=self.other)

#Replies----------------------

answer_is = term.simple("the requested answer is [A]", "A")

@term.as_head("answering question [Q]")
def answering(Q):
    return term.MetaTerm(answering.head, Q=Q)

class Reply():

    def __init__(self, value=None, answer=None, question=None):
        self.question = question
        if value is None:
            value = properties.trivial()
        if answer is not None:
            value = properties.both(answer_is(answer), value)
        self.value = value

    @property
    @memoize
    def answer(self):
        for m in properties.simple_iterator(self.value):
            if m.head == answer_is.head:
                return m['A'].explain(answering(self.question))

    @property
    def firm_answer(self):
        assert self.has_answer()
        return self.answer

    def has_answer(self):
        return self.answer is not None

    def set(self, new_value):
        return self.__class__(value=new_value, question=self.question)

    def add(self, new_value):
        return self.set(properties.both(new_value, self.value))
