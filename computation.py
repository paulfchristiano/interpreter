import datum
from datum import Datum as D
from utilities import clear
import crutch
import ask

eval_Q = "what is the result of running [computation] with bindings [bindings]?"

#-----Computation headers------------------------

#Turing completeness----------

quote_C =   ("the computation that returns [value]")
branch_C =  ("the computation that runs [cond] and then runs [branch1] "
             "if [cond] returns yes and [branch2] otherwise (returning the result)")
getvar_C =  ("the computation that runs [variable], then looks up the result in the current scope and returns it")
apply_C =   ("the computation that returns the result of running [f] in the new scope "
            "formed by adding the results of running [bindings] to the current scope")
askQ_C =     ("the computation that runs [Q], then returns the answer to the resulting question.")
datum_C =   ("the computation that outputs the datum with head the result of running [head], "
            "bindings the result of running [bindings], and modifiers the result of running [modifiers]")
assoc_C =   ("the computation that runs [key] and [bindings], then searches for the result of [key] in "
             "the result of [bindings]. If there is an associated value it is returned, "
             "otherwise [default] is run and the result returned.")
eq_C =      ("the computation that runs [a] and [b], and returns whether they are equal")

#Fundamental questions------

eq_Q =          "are [a] and [b] identical, i.e. do they have the same head and identical non-property bindings?"
referent_Q =    "what does [name] refer to in the head of [datum]?"
lookup_Q =      "what is a value bound to the key [key] in the bindings [bindings]?"
not_found_H =   "[key] was not found in [bindings]"

#Other primitives------------

get_global_C =  ("the computation that returns a representation of the interpreter's current state")
set_global_C =  ("the computation that runs [new_global] "
                 "and then sets the interpreter's global state to the result")
prompt_C =      ("the computation that prompts the user by displaying the result of running [prompt] "
                 "and then returns their input")
get_bindings_C =("the computation that runs [datum], then returns the bindings of the result")
get_head_C =    ("the computation that runs [datum], then returns the head of the result")
#TODO I would like to have a computation that holds its argument and evaluates it lazily
#this is not straightforward because calling d.explain() will typically force evaluation

#Conveniences---------------

datum_literal_C = ("The computation that returns a copy of [datum], in which each "
                   "the referent of each key that doesn't start with _ has been run "
                   "and replaced by the result")
bindings_C =    ("The computation that runs [key], then [value], then [other], "
                 "then returns the dictionary that "
                 "maps [key] to the result of [value] in addition to the bindings output by [other]")
referent_C =("the computation that runs [name], then returns the referent of the result in "
                 "the datum that results from running [datum]")

#Computation builders-----------------------------

def quote(X):
    return D(quote_C, value=X)

def branch(cond, branch1,branch2):
    return D(branch_C,cond=cond,branch1=branch1,branch2=branch2)

def getvar(variable):
    return D(getvar_C,variable=variable)

def apply(f,bindings):
    return D(apply_C,f=f,bindings=bindings)

def let(var,val,f):
    return apply(f, literal_datum(D.from_dict({var:val})))

def literal_datum(d):
    return D(datum_literal_C, datum=d)

def askQ(Q):
    return D(askQ_C,Q=Q)

def make_datum(head,modifiers,bindings):
    return D(datum_C,head=head,modifiers=modifiers,bindings=bindings)

def assoc(key,bindings,default=None):
    if default is None:
        default = quote(datum.none)
    return D(assoc_C,key=key,bindings=bindings,default=default)

def eq(a,b):
    return D(eq_C,a=a,b=b)

def get_global():
    return D(get_global_C)

def set_global(state):
    return D(set_global_C,state=state)

def prompt(x):
    return D(prompt_C,prompt=x)

def get_bindings(datum):
    return D(get_bindings_C,datum=datum)

def get_head(datum):
    return D(get_head_C,datum=datum)

def bindings(key,value,other):
    return D(bindings_C,key=key,value=value,other=other)

def referent(name,datum):
    return D(referent_C,name=name,datum=datum)


def run_Q(computation,bindings=None):
    if bindings is None:
        bindings = {}
    if type(bindings) is dict:
        bindings = D.from_dict(bindings)
    return D(eval_Q,computation=computation,bindings=bindings)

#shortcuts--------------------

def quote_str(s):
    return quote(D.from_str(s))

def referent_str(name,datum):
    return D(referent_C,name=quote_str(name),datum=datum)

def make_complex_bindings(**kwargs):
    result = quote(datum.empty_dict)
    for name, value in kwargs.items():
        result = bindings(key=quote_str(name), value=value, other=result)
    return result

#Default handler----------------------------------

def simple_handler(): 
    return askQ(literal_datum(D(
                crutch.crutch_answer_Q,
                question=getvar(quote(ask.question_var))
           )))
                        

#The evaluator------------------------------------


def builtin_eval(Q,state):
    """
    Answers Q if it is a simple questions about the result of running a computation.

    Checks to see if Q is about the result of running a computation.
    If so, it looks against a fixed list of primitive computations.
    If Q asks about one of them, it computes the result and returns it.

    Also answers questions about equality, references, and lookups in bindings.

    Otherwise, return None, allowing the default handler to take over.
    """
    asker = ask.QuestionContext(Q,state)

    if Q.head == lookup_Q and 'bindings' in Q and 'key' in Q:
        bindings = Q['bindings']
        key = Q['key']

        if bindings == datum.empty_dict:
            return D(not_found_H, key=key).explain("checking that [bindings] is empty",bindings=bindings)

        test = asker.ask_firmly(eq_Q,a=key,b=bindings.dict_key())
        if test:
            return asker.as_answer(bindings.dict_value().explain("looking up value in [bindings] because [test]",
                    bindings=bindings,
                    test=test
                ))
        else:
            new_Q = Q.update(bindings=bindings.dict_other()).explain("asking because not [test]",test=test)
            response,answer = asker.ask_and_extract(new_Q)
            if answer is not None:
                return asker.as_answer(answer)
            elif response.head == not_found_H:
                return response.update(bindings=bindings)
            else:
                return response

    if Q.head == eq_Q and 'a' in Q and 'b' in Q:
        return asker.as_answer(D.from_bool(Q['a'] == Q['b']))

    if Q.head == referent_Q:
        return asker.as_answer(Q['datum'][Q['name']])

    if Q.head == eval_Q and 'bindings' in Q and 'computation' in Q:
        bindings = Q['bindings']
        c = Q['computation']
        def run(new_c,additional_bindings=None,firmly=False,tail=False):
            new_bindings = bindings
            if additional_bindings is not None:
                new_bindings = new_bindings.dict_update(additional_bindings)
            new_Q = run_Q(new_c,new_bindings)
            if firmly:
                return asker.ask_firmly(new_Q)
            elif tail:
                return asker.ask_tail(new_Q)
            else:
                return asker.ask(new_Q)
        head = c.head
        if head == quote_C:
            return asker.as_answer(c['value'])
        if head == apply_C:
            f = run(c['f'],firmly=True)
            new_bindings = run(c['bindings'],firmly=True)
            return run(f, additional_bindings = new_bindings, tail=True)
        if head == branch_C:
            cond = run(c['cond'],firmly=True)
            branch_name = (
                D.from_str('branch1').explain("choosing branch1 because [cond]",cond=cond) 
                if cond else
                D.from_str('branch2').explain("choosing branch2 because not [cond]",cond=cond)
            )
            return run(c[branch_name],tail=True)
        if head == askQ_C:
            new_Q = run(c['Q'],firmly=True)
            return asker.ask_tail(new_Q)
        if head == datum_literal_C:
            new_bindings = {}
            d = c['datum']
            for k in d:
                if k[0] != '_':
                    new_bindings[k] = run(d[k],firmly=True)
            return asker.as_answer(D(d.head,_bindings=new_bindings))
        if head == bindings_C:
            key = run(c['key'],firmly=True)
            value = run(c['value'],firmly=True)
            tail = run(c['other'],firmly=True)
            return asker.as_answer(D.make_dict(key,value,tail))
        if head == prompt_C:
            clear()
            prompt = run(c['prompt'],firmly=True).to_str()
            print(prompt)
            input = raw_input()
            return asker.as_answer(D.from_str(input))
        if head == datum_C:
            head = run(c['head'],firmly=True)
            bindings = run(c['bindings'],firmly=True)
            #XXX I should be able to cut this modifiers business once I finish transitioning away from them...
            modifiers = run(c['modifiers'],firmly=True)
            return asker.as_answer(D(head.to_str(),modifiers,bindings.to_dict_of_str()).explain(
                    "contructing a datum with head [head], bindings [bindings], and modifiers [modifiers]",
                    head=head,
                    bindings=bindings,
                    modifiers=modifiers
                ))
        if head == getvar_C:
            variable = run(c['variable'],firmly=True)
            return asker.ask_tail(lookup_Q,key=variable,bindings=bindings)
        if head == eq_C:
            a = run(c['a'],firmly=True)
            b = run(c['b'],firmly=True)
            return asker.ask_tail(eq_Q,a=a,b=b)
        if head == assoc_C:
            key = run(c['key'],firmly=True)
            searching_in = run(c['bindings'],firmly=True)
            return asker.ask_tail(lookup_Q,key=key,bindings=searching_in)
        if head == referent_C:
            d = run(c['datum'],firmly=True)
            name = run(c['name'],firmly=True)
            return asker.as_answer(d[name])
        if head == get_bindings_C:
            d = run(c['datum'],firmly=True)
            return asker.as_answer(D.from_dict(d.bindings).explain(D(
                "accessing the bindings of [datum]",datum=d
            )))
        if head == get_head_C:
            d = run(c['datum'],firmly=True)
            return asker.as_answer(D.from_str(d.head).explain(D(
                "acessing the head of [datum]",datum=d
            )))

        if head == get_global_C:
            return asker.as_answer(state.state.explain(D('accessing the global state')))
        if head == set_global_C:
            new_global = run(c['new_global'],firmly=True)
            state.state = new_global
            return D("the global state was set to [state]",state=new_global)

    return None
