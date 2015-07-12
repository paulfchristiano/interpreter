import pyparsing
from pyparsing import Word, Forward, Keyword, OneOrMore, ZeroOrMore, Optional, Literal, Combine
from pyparsing import alphas, nums, alphanums
from term import Term as T
from term import as_head
from ipdb import set_trace as debug


def raw(s):
    return Literal(s).suppress()
def list_of(term):
    return Optional(term) + ZeroOrMore(raw(",") + term)
def parse_action(term):
    def add_parse_action(f):
        #The first two arguments are random stuff I don't care about that pyparsing makes
        #available
        def action(x, y, t):
            return f(list(t))
        term.addParseAction(action)
        return f
    return add_parse_action

#Expressions--------------------------------------

expr = Forward()
literal_expr = Forward()

prose = Word(" ,!?+-/*.;:_<>=&%#@$" + alphas).leaveWhitespace()
argument = (raw("(") + expr + raw(")")).leaveWhitespace()
raw_expr = OneOrMore(literal_expr | argument | prose).leaveWhitespace()

integer_expr = Word(nums).setParseAction(lambda t : int(t[0]))
string_expr = pyparsing.quotedString.setParseAction(pyparsing.removeQuotes)
list_expr = raw('[') + list_of(expr) + raw(']')
dict_expr = raw('{') + list_of(expr + raw(':') + expr) + raw('}')
literal_expr << (integer_expr ^ string_expr ^ list_expr ^ dict_expr)

expr << (literal_expr ^ raw_expr)

#Parse actions------------------------------------

@parse_action(integer_expr)
@as_head("an expression referring to the integer [k]")
def make_int_expr(k):
    return T(make_int_expr.head, k=T.from_int(k[0]))

@parse_action(string_expr)
@as_head("an expression referring to the string [s]")
def make_str_expr(s):
    return T(make_str_expr.head, s=T.from_str(s[0]))

@parse_action(list_expr)
@as_head("an expression referring to the list of terms "
        "referred to by the expressions in [list]")
def make_list_expr(l):
    return T(make_list_expr.head, l=T.from_list(l))

@parse_action(dict_expr)
@as_head("an expression referring to the dictionary that maps the referent of k "
        "to the referent of [map](k), for any expression k in the range of [map]")
def make_dict_expr(ms):
    d = {ms[i]:ms[i+1] for i in range(0, len(ms), 2)}
    return T(make_dict_expr.head, map=T.from_dict(d))

@as_head("an expression with text [text] in which variables refer to the referents "
        "of the images of their name in [bindings]")
@parse_action(raw_expr)
def make_raw_expr(xs):
    text = ""
    args = {}
    for x in xs:
        if type(x) is str:
            text += x
        else:
            arg_name = ("xyzw"+alphas)[len(args)]
            text += "[{}]".format(arg_name)
            args[arg_name] = x
    return T(make_raw_expr.head, text=T.from_str(text), bindings=T.from_dict_of_str(args))

#Actions------------------------------------------

def keyed(s):
    return Keyword(s).suppress() + expr

ask_action = keyed('ask')
return_action = keyed('return')
print_action = keyed('print')
dispatch_action = keyed('dispatch')

variable = Word(alphas, alphanums + "_")
assign_action = variable + Optional(raw(":")) + raw("=") + expr
action = ask_action | return_action | print_action | assign_action | dispatch_action

input = pyparsing.stringStart + (action ^ expr) + pyparsing.stringEnd

@parse_action(ask_action)
@as_head("an imperative to ask the question referred to by [Q]")
def make_ask(Q):
    return T(make_ask.head, Q=Q[0])

@parse_action(return_action)
@as_head("an imperative to return the referent of [x]")
def make_return(x):
    return T(make_return.head, x=x[0])

@parse_action(print_action)
@as_head("an imperative to print the string referred to by [s]")
def make_print(s):
    return T(make_print.head, s=s[0])

@parse_action(dispatch_action)
@as_head("an imperative to display the head of [x] and make its bindings accessible")
def make_dispatch(x):
    return T(make_dispatch.head, x=x[0])

@parse_action(assign_action)
@as_head("the imperative to assign the referent of "
        "[value] to the variable with name [name]")
def make_assignment(ins):
    return T(make_assignment.head, name=T.from_str(ins[0]), value=ins[1])

#Interface----------------------------------------

def parse(s):
    return input.parseString(s)[0]
