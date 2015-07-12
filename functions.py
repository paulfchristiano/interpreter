from dispatch import Dispatcher
import convert
import pairs
import hold

applier = Dispatcher("applier", ("function", "arguments"))

@hold.unholder("the result of applying [fn] to [arg]")
def apply(asker, fn, arg):
    return applier.dispatch(asker, fn, arg)

@applier("the function that maps everything to itself")
def id(asker, arg):
    return asker.reply(answer=arg)

@applier("the function that maps everything to [x]")
def const(asker, arg, x):
    return asker.reply(answer=x)

@applier("the function that applies [g], then applies [f] to the result")
def compose(asker, arg, f, g):
    return asker.reply(answer=apply(f, apply(g, arg)))
