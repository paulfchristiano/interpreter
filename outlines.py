import term
from term import Term as T
from dispatch import Dispatcher
import fields
from fields import getter, setter
import updates
from updates import updater
import convert
import properties
import lists
import strings
import builtins
from builtins import builtin
import representations
import utilities
import textwrap
import ints

from ipdb import set_trace as debug


#Making outlines----------------------------------

def node(headline, children):
    return T(node.head, headline=headline, children=children)
node.head = "an outline node with headline [headline] and children [children]"

#TODO I want nodes to have children and so on
#which I think can be done by having a translator that pulls "will have children"
#across the toggl expanded update
@builtin("what is the outline, collapsed to its root, that best expresses [quoted_term]?")
def node_from_term(asker, quoted_term):
    head = asker.ask(fields.get_field(representations.head(), quoted_term)).firm_answer
    bindings = asker.ask(fields.get_field(representations.bindings(), quoted_term)).firm_answer
    return asker.reply(answer=properties.simple_add_modifier(
        node(head, T.empty_list()),
        children_on_expanded(bindings)
    ))

#Outlines to lines--------------------------------

#TODO I should implement caching in a generic way...
cached_lines = fields.atomic_field(
    "the function that maps a node to a sequence of lines that represents it"
)

to_lines_Q = "what sequence of lines should represent the outline with root [root]"
@builtin(to_lines_Q)
def outline_to_lines(asker, root):
    debug()
    result = asker.ask(fields.get_field(cached_lines(), root)).answer
    if result is not None:
        return asker.reply(answer=result)
    base_headline = asker.ask(fields.get_field(headline(), root)).firm_answer
    root = asker.refresh(root)
    prefix = "* " if convert.check_hard(asker, is_pointer(), root) else "  "
    full_headline = strings.string_concat(T.from_str(prefix), base_headline)
    root = asker.refresh(root)
    children = asker.ask(fields.get_field(visible_children(), root)).firm_answer
    body = empty_lines()
    for child in lists.iterator(asker, children):
        section = asker.ask(outline_to_lines(child)).firm_answer
        body = concat_lines(body, section)
    result = concat_lines(one_line(full_headline), indent_lines(body))
    asker.update(updates.set_field(cached_lines(), result), root)
    return asker.reply(answer=result)

is_pointer = properties.atomic_property("the cursor is currently positioned in this node")

#TODO this isn't really an atomic property, the caching infrastructure
#should eventually be good enough that we can be honest about that
#(it can be defined in the normal way, we can cache the result,
#and we can define a translator for the cache to make it so that this all works...)
has_pointer = properties.atomic_property("the cursor is currently positioned in a child of this node")

is_expanded = properties.atomic_property("this node is currently expanded")

@getter("the function that maps a node of an outline "
    "to the list of children visible beneath that node")
def visible_children(asker, object):
    expanded = convert.check_hard(asker, is_expanded(), object)
    object = asker.refresh(object)
    if not expanded:
        return asker.reply(answer=T.from_list([]))
    else:
        children = asker.ask(fields.get_field(all_children(), object)).firm_answer
        return asker.reply(answer=children)

@setter(visible_children.head)
def set_visibile_children(asker, object, new_value):
    return asker.ask_tail(fields.set_field(all_children(), object, new_value))

all_children = fields.named_binding(
    "the function that maps a node of an outline to the list of nodes which are its children",
    node.head,
    'children'
)


#Printing lines-----------------------------------

#FIXME this should probably emit a string or list of strings rather than just print them...
#FIXME this should probably use the conversions machinery
line_printer = Dispatcher("line printer", ("lines", "k", "tab"))
#tab: the string to use for a tab
#k: the number of tabs to use for the outermost line

@builtin("print the lines [lines]")
def print_lines_simple(asker, lines):
    return asker.ask_tail(print_lines(lines, T.from_int(0), T.from_str("  ")))

@builtin("print the lines [lines], with a starting indentation of [k], and a tab of [tab]")
def print_lines(asker, lines, k, tab):
    line_printer.dispatch(asker, lines, k, tab)

@line_printer("an empty sequence of lines")
def empty_lines(asker, k, tab):
    return asker.reply()

@line_printer("the sequence of lines formed by concatenating [a] to [b]")
def concat_lines(asker, k, tab, a, b):
    asker.ask(print_lines(a, k, tab))
    asker.ask(print_lines(b, k, tab))
    return asker.reply()

@line_printer("the sequence of lines formed by indenting [x] once")
def indent_lines(asker, k, tab, x):
    asker.ask(print_lines(x, ints.plus_one(k), tab))
    return asker.reply()

@line_printer("the sequence of lines consisting of the line whose text is the string [line]")
def one_line(asker, k, tab, line):
    tab = convert.to_str(asker, tab)
    k = convert.to_int(asker, k)
    line = convert.to_str(asker, line)
    initial_tabs = k * tab
    hanging_tabs = initial_tabs + tab + tab
    reduced_width = 115 - len(hanging_tabs)
    wrapped_lines = textwrap.wrap(line,width=reduced_width)
    for i, wrapped_line in enumerate(wrapped_lines):
        print("{}{}".format(initial_tabs if i == 0 else hanging_tabs, wrapped_line))

#Manipulating outlines----------------------------

#Signals and updates--------------------

def moved(d):
    return T(moved.head, direction=d)
moved.head = "the user tried to move [direction] out of the movable area"


up = T("the direction up")
down = T("the direction down")
left = T("the direction left")

quit = T("the current interactive exploration should end")

@updater("the update that toggles whether the updated node is expanded")
def toggle_expanded(asker, object):
    if convert.check_hard(asker, is_expanded(), object):
        result = updates.update(updates.remove_modifier(is_expanded()), object)
    else:
        result = properties.simple_add_modifier(object, is_expanded())
    return asker.reply(answer=result)

@updater("the update that introduces a cursor positioned on the updated node")
def is_pointer_now(asker, object):
    result = updates.update(updates.remove_modifier(has_pointer()), object)
    result = properties.simple_add_modifier(result, is_pointer())
    return asker.reply(answer=result)

@updater("the update that implies that a cursor is positioned beneath the updated node")
def has_pointer_now(asker, object):
    if convert.check_hard(asker, has_pointer(), object):
        result = updates.update(updates.remove_modifier(is_pointer()), object)
    else:
        result = properties.simple_add_modifier(result, has_pointer())
    return asker.reply(answer=result)

@updater("the update that removes all cursors positioned on or in a descendant of the updated node")
def remove_pointer(asker, object):
    result = updates.update(updates.remove_modifier(is_pointer()), object)
    result = updates.update(updates.remove_modifier(has_pointer()), object)
    result = updates.update(
        updates.apply_to(
            all_children(),
            lists.update_map(remove_pointer())
        ), 
        result
    )
    return asker.reply(answer=result)

@updater("the update that adds a pointer to the descendant of the updated node "
    "which is rendered furthest from node (if the node has no descendants, this updates the node itself)")
def add_pointer_to_bottom(asker, object):
    visible_children = asker.ask(fields.get_field(visible_children()), object).firm_answer
    if convert.check_hard(asker, lists.is_empty(), visible_children):
        return asker.reply(answer=updates.update(is_pointer_now(), object))
    else:
        result = updates.update(has_pointer_now(), object)
    result = updates.update(
        updates.apply_to(
            fields.compose(visible_children(), lists.last_element()),
            add_pointer_to_bottom()
        ), 
        result
    )
    return asker.reply(answer=result)

#Adding children------------------------

children_on_expanded = term.simple("when expanded, should be given children from [bindings]", "bindings")

@updates.translator(children_on_expanded.head, toggle_expanded.head)
def add_children_on_expanded(asker, old, new, bindings):
    children = []
    for p in lists.iterator(asker, lists.from_dict(bindings)):
        k = asker.ask(fields.get_field(first(), p)).firm_answer
        v = asker.ask(fields.get_field(second(), p)).firm_answer
        prefix = strings.string_concat(k, T.from_str(": "))
        new_node = node_from_term(asker, v)
        new_node = updates.update(
            updates.apply_to(headline(), strings.prepend_str(prefix)),
            new_node
        )
        children.append(new_node)
    return asker.reply(answer=updates.update(
        fields.set_field(all_children(), T.from_list(children)), 
        new
    ))

updates.translate_simply(children_on_expanded.head, exclude=[toggle_expanded.head])

headline = fields.named_binding(
    "the function that maps a node in an outline to its headline",
    node.head, 
    'headline'
)


#Processing input-----------------------

process_char_Q = ("what should [root] transform into if the user types [c] while exploring it, "
    "given that it has parents [parents]?")
@builtin(process_char_Q)
def process_char(asker, root, c, parents):
    c = convert.to_char(asker, c)
    if convert.check_hard(asker, is_pointer(), root):
        if c == 'q':
            return asker.reply(value=quit)
        elif c == 'j':
            children = asker.ask(fields.get_field(visible_children(), root)).firm_answer
            if convert.check_hard(asker, lists.is_empty(), children):
                asker.pass_through(moved(down))
            else:
                children = asker.refresh(children)
                first_child = asker.ask(fields.get_fields(lists.first(), children)).firm_answer
                asker.update(has_pointer_now(), root)
                asker.update(is_pointer_now(), first_child)
            return asker.reply()
        elif c == 'k':
            return asker.reply(value=moved(up))
        elif c == 'z':
            asker.update(toggle_expanded(), root)
            return asker.reply()
        elif c == 'h':
            return asker.reply(value=moved(left))
        elif c == 'l':
            #FIXME zoom out one by one instead of all of the way...
            #this is pretty straightforward if we are willing to go into and out of python
            #but it would surely be nicer to do it the 'right' way
            #I'm also pretty happy to wait
            asker.ask(explore_outline(root, parents)) 
            return asker.reply(value=moved(left))
    elif convert.check_hard(asker, has_pointer(), root):
        children = asker.ask(field.get_field(visible_children(), root)).firm_answer
        def make_handler(above, below):
            handler = Dispatcher("exploration child handler", ("question",))
            @handler(moved.head)
            def move(asker, question, direction):
                if direction.head == down.head:
                    if below is None:
                        asker.pass_through(moved(direction))
                    else:
                        asker.update(now_is_pointer(), below)
                        asker.update(remove_pointer(), child)
                if direction.head == up.head:
                    if above is None:
                        asker.update(now_is_pointer(), root)
                        asker.update(remove_pointer(), child)
                    else:
                        asker.update(add_pointer_to_bottom(), above)
                        asker.update(remove_pointer(), child)
                elif direction.head == left.head:
                    asker.update(remove_pointer(), child)
                    asker.update(now_is_pointer(), root)
                return properties.trivial()
            #TODO insert a handler for changing underlying terms *etc*
            #I think that this is going to require some thought,
            #but I can wait
            return handler
        child_list = list(lists.iterator(asker, children))
        new_parents = lists.snoc(parents, root)
        for i in range(len(child_list)):
            child = child_list[i]
            if i > 0:
                below = child_list[i-1]
            else:
                below = None
            if i < len(child_list) - 1:
                above = child_list[i+1]
            else:
                above = None
            asker.ask(process_char(child, c, new_parents), handler=make_handler(above, below))
        return asker.reply()

@builtin("the user wants to interact with the outline [root], in the context of parents [parents]")
def explore_node(asker, root, parents):
    asker.update(is_pointer_now(), root)
    while True:
        #TODO print the parents
        root = asker.refresh(root)
        lines = asker.ask(outline_to_lines(root)).firm_answer
        utilities.clear()
        asker.ask(print_lines_simple(lines))
        c = utilities.getch()
        if c == 'q':
            return asker.reply()
        else:
            root = asker.refresh(root)
            asker.ask(process_char(root, T.from_char(c), parents))
