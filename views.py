import term
from term import as_head
from term import Term as T
import builtins
from builtins import builtin
import parsing
import termtypes
import pairs
import ints
import strings
import representations
import fields
import properties
import dispatch
from dispatch import Dispatcher
import relayer
import utilities
from utilities import clear
import convert
import lists
import dictionaries
import updates
import strings
import state
import computations
import functions

from ipdb import set_trace as debug
import inspect
from decorator import decorator
import string

@as_head("an interactive environment with sequence of lines [lines] and variable bindings [binding]")
def view(lines, bindings):
    return T(view.head, lines=lines, bindings=bindings)

lines_field = fields.named_binding(
    "the function that maps a view to the sequence of lines rendered in that view",
    view.head,
    'lines'
)

bindings_field = fields.named_binding(
    "the function that maps a view to the variable bindings that should be applied in that view",
    view.head,
    'bindings'
)

@builtin("what value will ultimately be returned if the user interacts with [view]?")
def predict_output(asker, view):
    input = asker.ask(predict_input(view)).firm_answer
    class context:
        result = None

    handler = dispatch.SimpleDispatcher(None, ("property",))
    @handler(should_return.head)
    def handle(x):
        context.result = x
        return properties.trivial()

    asker.ask(update_view(view, input), handler=handler)
    if context.result is not None:
        #FIXME this is an awkward jump between meta levels,
        #I think that I'm doing something wrong
        return asker.reply(answer=context.result)
    else:
        return asker.ask_tail(predict_output(asker.refresh(view)))

def shell(asker):
    current_view = view(T.from_list_of_str(["(Home)"]), T.from_dict({}))
    asker.tag(T("the current view"), current_view)
    while True:
        input = asker.ask_firmly(elicit(current_view))
        asker.ask(update_view(current_view, input))
        current_view = asker.refresh(current_view)

@builtin("prompt the user by displaying the lines of [view]")
def print_view(asker, view):
    clear()
    lines = fields.get(asker, lines_field(), view)
    for line in lists.iterator(asker, lines):
        s = strings.to_str(asker, line)
        print(s)
    return asker.reply()

@builtin("prompt the user with [view] and get their input")
def elicit(asker, view):
    asker.ask(print_view(view))
    return asker.ask_tail(prompt())

@builtin("what would the user type when prompted with [view]?")
def predict_input(asker, view):
    lines = fields.get(asker, lines_field(), view)
    h = asker.ask(state.get_history()).firm_answer
    response = asker.ask(fields.get_field(dictionaries.image(lines), h))
    if response.has_answer():
        return asker.reply(answer=response.answer)
    else:
        input = asker.ask_firmly(elicit(view))
        asker.ask(state.update_state(updates.apply_to_field(
            state.history(),
            updates.set_field(
                dictionaries.image(lines),
                input
            )
        )))
        return asker.reply(answer=input)

@builtin("what would the user type if prompted right now?")
def prompt(asker):
    return asker.reply(answer=T.from_str(raw_input("")))


#TODO: I'm equivocating between questions and queries here...
#I'll need to sort this out, and the logic here will end up being very much
#more complicated
@builtin("what view should be presented to the user to answer [query]?")
def get_starting_view(asker, query):
    head = fields.get(asker, representations.head(), query)
    bindings = fields.get(asker, representations.bindings(), query)
    initial_lines = T.from_list([head, T.from_str("---")])
    return asker.reply(answer=view(initial_lines, bindings))

#TODO should probably just have a "should take [action]" item that gets passed through?
@builtin("what does [input] refer to if entered in response to [view]?")
def interpret_input(asker, view, input):
    parsed_input = asker.ask(parse_string(input)).firm_answer
    return asker.ask_tail(interpret_expression(view, parsed_input),
            handler=asker.pass_through(
                should_return.head, 
                should_print.head, 
                should_dispatch.head,
                should_assign.head
            ))

@builtin("what expression corresponds to the string [s]?")
def parse_string(asker, s):
    return asker.reply(answer=parsing.parse(strings.to_str(asker,s)))

@builtin("what term is [expr] equivalent to when entered in response to [view]?")
def interpret_expression(asker, view, expr):
    return interpreter.dispatch(asker, expr, view)

interpreter = Dispatcher("interpreter", ("expr", "context"))

@interpreter(parsing.make_raw_expr.head)
def interpret_raw(asker, view, text, bindings):
    #FIXME I think that most field lookups should be done implicitly
    variable_bindings = fields.get(asker, bindings_field(), view)
    lookup_value = asker.ask(fields.get_field(
        dictionaries.image(text), 
        variable_bindings
    ))
    if lookup_value.has_answer():
        return asker.reply(answer=lookup_value.answer)
    update_bindings = dictionaries.map(
        computations.apply_to_single(
            computations.askQ_literal(interpret_expression(
                computations.quote(view),
                computations.getvar(computations.quote(computations.x_var))
            )),
            computations.x_var
        )
    )
    return asker.reply(answer=representations.quoted_term(
        text, 
        functions.apply(update_bindings, bindings)
    ))
    #FIXME should have other answers soon, not everything should be held...
    return elicit_meaning(text, view, functions.apply(update_bindings, bindings))

@as_head("what term represents the same thing as [text] entered in [view], "
    "if variables should refer to the same objects as their images in [bindings]?")
def elicit_meaning(text, view, bindings):
    return T(elicit_meaning.head, text=text, view=view, bindings=bindings)

@interpreter(parsing.make_int_expr.head)
def interpret_int(asker, view, k):
    return asker.reply(answer=representations.quote(k))

@interpreter(parsing.make_str_expr.head)
def interpret_str(asker, view, s):
    return asker.reply(answer=representations.quote(s))

@interpreter(parsing.make_list_expr.head)
def interpret_list(asker, view, l):
    #TODO if I had better mapping, this would be fine...
    #for now I have to do it in this terrible way...
    result = representations.make(T.empty_list.head)
    for x in reversed(list(lists.iterator(asker, l))):
        result = representations.make(T.cons.head, head=x, tail=result)
    return asker.reply(answer=result)

should_print = term.simple("the referent of [s] should be printed in the referenced view", "s")
should_dispatch = term.simple("the head of [x] should be printed and its bindings promoted "
        "in the referenced view", "x")
should_return = term.simple("[x] should be returned "
        "if the user interacts with the referenced view", "x")
should_assign = term.simple("[s] should refer to [x] in future interactions with the "
        "referenced view", "s", "x")

#TODO this is a duplicate of run_arg, I should generalize them
def interpret_arg(name):

    def make_interpreted_arg(f):

        arg_names = inspect.getargspec(f).args
        run_index = arg_names.index(name)

        def with_run_arg(f, *args, **kwargs):
            args = list(args)
            asker = args[0]
            view = args[1]
            def run_arg(x):
                return asker.ask_firmly(interpret_expression(view, x))
            if len(args) > run_index:
                args[run_index] = run_arg(args[run_index])
            else:
                kwargs[name] = run_arg(kwargs[name])
            return f(*args, **kwargs)

        return decorator(with_run_arg, f)

    return make_interpreted_arg

#FIXME this probably doesn't play nicely with unquoting and the current print routine
@interpreter(parsing.make_print.head)
@interpret_arg('s')
def interpret_print(asker, view, s):
    return asker.reply(value=should_print(s))

#FIXME consistency in use of x vs. x.head in dispatches
@interpreter(parsing.make_dispatch.head)
@interpret_arg('x')
def interpret_dispatch(asker, view, x):
    return asker.reply(value=should_dispatch(x))

@interpreter(parsing.make_return.head)
@interpret_arg('x')
def interpret_return(asker, view, x):
    return asker.reply(value=should_return(x))

@interpreter(parsing.make_assignment)
@interpret_arg('value')
def interpret_assign(asker, view, name, value):
    return asker.reply(value=should_assign(name, value))

@builtin("what view should [view] become if the user enters [input]?")
def update_view(asker, view, input):
    relayer = asker.pass_through(should_return.head)
    #FIXME using the name view_in is a hack to keep view from being locally scoped...
    @relayer(should_print.head)
    def print_string(s):
        view_in = asker.refresh(view)
        asker.update(add_line(input), view_in)
        #FIXME more things going wrong with representation levels...
        s = convert.unquote(asker, s)
        line = asker.ask_firmly(render(s))
        asker.update(add_line(line), view_in)
        return properties.trivial()
    @relayer(should_dispatch.head)
    def dispatch(x):
        view_in = asker.refresh(view)
        asker.update(add_line(input), view_in)
        head = fields.get(asker, representations.head(), x)
        bindings = fields.get(asker, representations.bindings(), x)
        view_in = asker.refresh(view_in)
        asker.update(add_line(head), view_in)
        for p in dictionaries.item_iterator(asker, bindings):
            var, val = pairs.to_pair(asker, p)
            view_in = asker.refresh(view_in)
            asker.update(bind_variable(var, val), view_in)
        return properties.trivial()
    @relayer(should_assign.head)
    def assign(s, x):
        view_in = asker.refresh(view)
        asker.update(add_line(input), view_in)
        view_in = asker.refresh(view_in)
        asker.update(bind_variable(s, x), view_in)
        return properties.trivial()

    interpret_response = asker.ask(interpret_input(view, input), handler=relayer)
    if interpret_response.has_answer():
        bindings = dictionaries.to_dict(asker, fields.get(asker, bindings_field(), view))
        bindings_str = {strings.to_str(asker, k):v for k, v in bindings.items()}
        for char in "xyzw" + string.letters:
            if char not in bindings_str:
                break
        asker.update(bind_variable(T.from_str(char), interpret_response.answer), view)
        new_line = strings.concat(
            T.from_str("{} = ".format(char)),
            input
        )
        asker.update(add_line(new_line), view)
    return asker.reply()

#Rendering----------------------------------------

#FIXME rendering probably belongs in another module...
#TODO add support for more rendering strategies?
@builtins.builtin("what string should be used to render [x] for printing?")
def render(asker, x):
    t = asker.ask(termtypes.type(x))
    if t.has_answer():
        return typed_renderer.dispatch(asker, t.answer, x)

typed_renderer = Dispatcher("renderer with types", ("type", "object"))
renderer = Dispatcher("renderer", ("object",))

@typed_renderer(representations.term_type)
def render_term(asker, term):
    return asker.reply(answer=strings.concat(
        strings.concat(
            T.from_str("T("), 
            field.get(asker, representations.head(), term)),
        T.from_str(")")
    ))

@typed_renderer(ints.int_type)
def render_int(asker, x):
    return asker.reply(answer=T.from_str(str(ints.to_int(asker, x))))

@typed_renderer(strings.char_type)
def render_char(asker, x):
    return asker.reply(answer=T.simple_str(T.from_list([c])))

@typed_renderer(strings.string_type)
def render_str(asker, x):
    return asker.reply(answer=x)

#FIXME in reality need more flexibility
@typed_renderer(lists.list_type)
def render_list(asker, x):
    result = T.from_str("[")
    first = True
    for item in lists.iterator(asker, x):
        item_printed = asker.ask_firmly(render(item))
        if not first:
            item_printed = strings.concat(T.from_str(", "), item_printed)
        first = False
        result = strings.concat(result, item_printed)
    result = strings.concat(result, T.from_str("]"))
    return asker.reply(answer=result)

#TODO better answer
@typed_renderer(dictionaries.dict_type)
def render_dict(asker, x):
    return asker.reply(answer=strings.concat(
        T.from_str("D"),
        lists.from_dict(x)
    ))

#TODO something better than concat... maybe formatting?
@typed_renderer(pairs.pair_type)
def render_pair(asker, x):
    return asker.reply(answer=strings.concat(
        strings.concat(
            T.from_str("("),
            asker.ask_firmly(render(fields.get(pairs.first(), x))),
        ),
        strings.concat(
            T.from_str(", "),
            strings.concat(
                asker.ask_firmly(render(fields.get(pairs.first(), x))),
                T.from_str(")")
            )
        )
    ))

@updates.updater("the update that binds [name] to [value] in the updated view")
def bind_variable(asker, view, name, value):
    return asker.reply(answer=updates.update(
        updates.apply_to_field(
            bindings_field(),
            updates.set_field(
                dictionaries.image(name),
                value
            )
        ),
        view
    ))

@updates.updater("the update that adds [new_line] to the updated view")
def add_line(asker, view, new_line):
    return asker.reply(answer=updates.update(
        updates.apply_to_field(
            lines_field(),
            lists.append(new_line)
        ),
        view
    ))
