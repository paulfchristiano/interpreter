import greenlet
import sys
from decorator import decorator
from ipdb import set_trace as debug

UP = "up"
DOWN = "down"
sentinel = object()

#FIXME this can lead to really weird stuff if you don't clear out the greenlets
#I should definitely have a more robust system in some way 

@decorator
def stackless(f, *args, **kwargs):
    if sys.gettrace() is not None:
        return f(*args, **kwargs)
    elif not getattr(f,'greenlets',[]):
        return start_greenlet(f, *args, **kwargs)
    else:
        return f.core_greenlet.switch((DOWN, (args, kwargs)))

def start_greenlet(f, *args, **kwargs):
    try:
        QorA = (args, kwargs)
        direction = DOWN
        #FIXME I think that we can do this more elegantly without a sentinel
        #but I've debugged this and know it works, so I don't think changing it is wortwhile
        f.greenlets = [sentinel]
        f.Qs = [QorA]
        f.core_greenlet = greenlet.getcurrent()
        while True:
            if direction == DOWN:
                g = greenlet.greenlet(lambda (args, kwargs) : (UP, f(*args, **kwargs)))
            elif direction == UP:
                g = f.greenlets.pop()
                if g is sentinel:
                    return QorA
                else:
                    f.Qs.pop()
            else:
                raise ValueError("direction must be either UP or DOWN")

            direction, QorA = g.switch(QorA)
            if direction == DOWN:
                f.greenlets.append(g)
                f.Qs.append(QorA)
    finally:
        f.greenlets = []
        f.Qs = []


def stack(f):
    return f.__wrapped__.Qs
