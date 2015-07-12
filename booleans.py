import term
from term import Term as T
from term import as_head
from dispatch import Dispatcher

@as_head("yes iff both [a] and [b] are yes")
def both(a, b):
    for x, y in [(a, b), (b, a)]:
        if x.head == T.yes.head:
            return y
        if x.head == T.no.head:
            return x
    return T(both.head, a=a, b=b)

@as_head("yes iff either [a] and [b] are yes")
def either(a, b):
    for x, y in [(a, b), (b, a)]:
        if x.head == T.yes.head:
            return x
        if x.head == T.no.head:
            return y
    return T(either.head, a=a, b=b)

@as_head("the opposite of [a]")
def opposite(a):
    if a.head == T.yes.head:
        return T.no()
    elif a.head == T.no.head:
        return T.yes()
    return T(opposite.head, a=a)

def to_bool(asker, a):
    return literalizer.dispatch(asker, a)

literalizer = Dispatcher("literalize bool", ("a",))

@literalizer(T.yes.head)
def literalize_yes(asker):
    return True

@literalizer(T.no.head)
def literalize_no(asker):
    return False

#FIXME these seem nice, but may actually be destructive...
#if you use conversions the results are cached, but these are not
@literalizer(either.head)
def literalize_either(asker, a, b):
    return to_bool(asker, a) or to_bool(asker, b)

@literalizer(both.head)
def literalize_both(asker, a, b):
    return to_bool(asker, a) and to_bool(asker, b)

@literalizer(opposite.head)
def literalize_opposite(asker, a):
    return not to_bool(asker, a)

def ask_firmly(asker, Q):
    return to_bool(asker, asker.ask(Q).firm_answer)
