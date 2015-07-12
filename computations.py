import term
from term import Term as T
from utilities import clear
from decorator import decorator
from dispatch import Dispatcher
from builtins import builtin
import representations
import inspect
from ipdb import set_trace as debug
import strings
from frozendict import frozendict
import builtins
import dictionaries
import fields
import functions
import hold
import lists

#Running computations-----------------------------

computer = Dispatcher("computer", ("computation", "bindings"))
#bindings: the scope in which the computation is to be run

@builtin("what is the result of running [computation] with bindings [bindings]?")
def run(asker, computation, bindings):
    return computer.dispatch(asker, computation, bindings)

def run_arg(name):

    def make_run_arg(f):

        arg_names = inspect.getargspec(f).args
        run_index = arg_names.index(name)

        def with_run_arg(f, *args, **kwargs):
            args = list(args)
            asker = args[0]
            bindings = args[1]
            def run_arg(x):
                return asker.ask(run(x, bindings)).firm_answer
            if len(args) > run_index:
                args[run_index] = run_arg(args[run_index])
            else:
                kwargs[name] = run_arg(kwargs[name])
            return f(*args, **kwargs)

        return decorator(with_run_arg, f)

    return make_run_arg


#Computations-------------------------------------

#Quotations-----------------------------

@computer("the computation that returns [value]")
def quote(asker, bindings, value):
    return asker.reply(answer=value)

def quote_str(s):
    return quote(T.from_str(s))

def quote_quote(d):
    return quote(representations.quote(d))

#Applications and bindings--------------

@computer("the computation that returns the result of running [f] in the new scope "
           "formed by adding the results of running [new_bindings] to the current scope")
@run_arg('new_bindings')
@run_arg('f')
def apply(asker, bindings, f, new_bindings):
    combined_bindings = dictionaries.dict_union(bindings, new_bindings)
    asker.ask_tail(run(f, combined_bindings))

def let(var, val, f):
    return apply(quote(f), literal_term(T.from_dict({var:val})))

@computer("the computation that runs [variable], "
  "then looks up the result in the current scope and returns it")
@run_arg('variable')
def getvar(asker, bindings, variable):
    return asker.ask_tail(fields.get_field(dictionaries.image(variable), bindings))

#Conditionals---------------------------

@computer("the computation that runs [cond] and then runs [branch1] "
        "if [cond] returns yes and [branch2] otherwise (returning the result)")
@run_arg('cond')
def branch(asker, bindings, cond, branch1, branch2):
    cond = asker.ask(convert.convert(cond, convert.to_bool()))
    return asker.ask_tail(run(
        branch1 if cond else branch2,
        bindings
    ))

#Questions------------------------------

#FIXME the level of indirection mentioned below appears here as well,
#and is equally unsatisfying.
@computer("the computation that runs [head], then runs [bindings], "
 "then answers the question with that head and those bindings")
@run_arg('bindings')
@run_arg('head')
def askQ(asker, computation_bindings, head, bindings):
    return asker.ask_tail(T(strings.to_str(asker, head), dictionaries.to_term_bindings(asker,bindings)))

@term.term_arg('d')
def askQ_literal(d):
    return askQ(quote_str(d.head), complex_dict(d.bindings)) 

#Constructing terms----------------------

#FIXME this description isn't quite right; there is an important level of indirection here 
#in representations.Representation(d), the bindings map to representations
#here they map straight to objects
@computer("the computation that outputs the term with head the result of running [head], "
            "bindings the result of running [bindings]")
@run_arg('head')
@run_arg('bindings')
def make_term(asker, computation_bindings, head, bindings):
    return asker.reply(answer=representations.make(
        strings.to_str(asker, head),
        dictionaries.to_term_bindings(asker, bindings)
    ))

@term.term_arg("d")
def make_literal_term(d):
    bindings = complex_dict(d.bindings)
    head = quote_str(d.head)
    return make_term(head=head, bindings=bindings)

@computer("the computation that runs [key], [value], and [other], and returns the binding "
        "that maps the result of running [key] to the result of running [value], "
        "and maps other inputs using the result of mapping [other]")
@run_arg('key')
@run_arg('value')
@run_arg('other')
def dict_cons(asker, computation_bindings, key, value, other):
    return asker.reply(answer=T.dict_cons(key, value, other))

def complex_dict(base=None, **kwargs):
    if base is None:
        base = {}
    to_make = dict(base, **kwargs)
    result = quote(T.empty_dict())
    for name, value in to_make.items():
        result = dict_cons(quote_str(name), value, result)
    return result

#Turning into functions---------------------------

x_var = T("the first of several anonymous variables")
y_var = T("the second of several anonymous variables")

@functions.applier("the function that maps a sequence of arguments "
    "to the result of running [comp] with the arguments bound to the corresponding "
    "variables in [vars]")
def apply_to(asker, arg, comp, vars):
    bindings = dictionaries.from_items(lists.zip(vars, arg))
    return asker.ask_tail(run(comp, bindings))

def apply_to_single(comp, var):
    return functions.compose(
            apply_to(comp, lists.singleton(var)), 
            lists.make_singleton()
    )

#Holding------------------------------------------

#FIXME seems like there should be some general way to give nice names/descriptions
#to holding things...
@hold.unholder("the result of running [computation] with bindings [bindings]")
def result(asker, computation, bindings):
    return asker.ask_tail(run(computation, bindings))
