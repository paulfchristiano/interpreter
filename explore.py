import datum
from datum import Datum as D
import utilities
import textwrap
import ask
from ask import both, as_answer, no_answer
from ipdb import set_trace as debug
import crutch

#TODO it seems like I should probably be passing around an asker rather than a state

def headline(n,prefix=None,state=None):
    if prefix is None:
        prefix = D.from_str("")
    base = None
    new_n = n
    m = n.modifier_find(lambda m : m.head == headline_is_H and m['pre'] == prefix)
    if m is not None:
        return as_answer(m['headline'])
    elif n.head == node_H:
        base = D.from_str(n['D'].head)
    else:
        new_Q = D(
            "what should we display as the headline of [node] "
               "for rendering in an interactive session?",
            node=n
        )
        interim_response, base = ask.ask_and_extract(Q,state)
        n = update_given_response(n,interim_response)
    key = get_key(n)
    if key is not None:
        key_str = key.str_concat(D.from_str(": "))
        base = key_str.str_concat(base)
    result = prefix.str_concat(base)
    n = n.update(D(headline_is_H,headline=result,pre=prefix))
    return both(as_answer(result), D(updated_H,new=n))

def update_given_response(n, response):
    class context:
        node = n
    def update_node(d):
        if d.head == updated_H:
            context.node = d['new']
    ask.process_answer(response, update_node)
    return context.node

#TODO there is no caching for the representation of parents right now, though there could be
def represent_parents(parents,state):
    if parents is None:
        parents = datum.empty_list
    lines = []
    for node in reversed(parents.to_list()):
        lines.append(D(single_line_H,text=represent_node_as_parent(node,state)))
    if parents != datum.empty_list:
        lines.append(empty_line)
    return D(concat_H, sequence=D.from_list(lines))

def concat(l):
    return D(concat_H,sequence=D.from_list(l))

concat_H = "the concatenation of the printable objects in [sequence]"
indent_H = "the printable object formed by indenting every line of [x]"
single_line_H = "the line with text [text]"

def represent_node(n,state=None,parents=None):
    original_n = n
    m = n.modifier_find(has_representation_H)
    if m is not None:
        return m['lines']
    response = headline(n,prefix=D.from_str("* " if is_pointer(n) else "  "),state=state)
    header = D(single_line_H, text=ask.extract_answer_firmly(response))
    n = update_given_response(n, response)
    children = expanded_children(n,state)
    new_children = []
    changed_children = False
    subsections = []
    for node in children.to_list():
        response = represent_node(node,state)
        subsections.append(ask.extract_answer(response))
        new_node = update_given_response(node,response)
        changed_children = changed_children or new_node is not node
        new_children.append(new_node)
    result = header
    if subsections:
        sublines = concat(subsections)
        footer = D(indent_H, x=sublines)
        result = concat([header,footer])
    #TODO this will have to wait until we have a better mechanism
    #for transferring properties across updates
    #n = n.update(D(has_representation_H,lines=result))
    if is_expanded(n) and changed_children:
        n = n.update(children=D.from_list(new_children))
    answer = as_answer(result)
    if n is not original_n:
        answer = both(answer,D(updated_H,new=n))
    return answer

def represent_datum(d, key=None,levels=3):
    representation = D(single_line_H,text=D.from_str("".join([
        "{}: ".format(key) if key is not None else "",
        d.head
    ])))
    if levels > 0:
        subsections = [represent_datum(d[k],key=k,levels=levels-1) for k in d]
        footer = D(indent_H,x=concat(subsections))
        representation = concat([representation,footer])
    return representation

def show(d,levels=3):
    print('\n'.join(render_lines(represent_datum(d,levels=levels))))

def represent_node_as_parent(n,state):
    response = headline(n, state=state,prefix=D.from_str("> "))
    return ask.extract_answer_firmly(response)

empty_line = D("an empty line")

#TODO this is pretty slow, it's fine because it's all done in python but it could/should be made faster
def render_lines(lines,num_tabs=0,width=115):
    tab = "    "
    #partial_tab is a string that is concatenated to the beginning of any lines that were
    #wrapped by textwrap.
    #XXX this way of coping with wrapped lines is not very elegant, 
    #it would be better to have two indentation levels
    partial_tab = "    "
    if lines == empty_line:
        return [""]
    elif lines.head == single_line_H:
        initial_tabs = num_tabs * tab
        hanging_tabs = initial_tabs + partial_tab
        reduced_width = width - len(hanging_tabs)
        wrapped_lines = textwrap.wrap(lines['text'].to_str(),width=reduced_width)
        return [initial_tabs + x if i == 0 else hanging_tabs + x for i, x in enumerate(wrapped_lines)]
    elif lines.head == concat_H:
        result = []
        for x in lines['sequence'].to_list():
            result.extend(render_lines(x,num_tabs=num_tabs,width=width))
        return result
    elif lines.head == indent_H:
        return [x for x in render_lines(lines['x'],num_tabs=num_tabs+1,width=width)]

#XXX move to crutch module
elicit_replacement_Q = "What does the user want to replace the value stored in [node] with?"
def elicit_replacement(n,state):
    response = represent_node(n,state)
    n = update_given_response(n, response)
    node_repr = ask.extract_answer_firmly(response)
    lines = D.from_list_of_str(
        ["-----"] + 
        list(reversed(render_lines(node_repr))) + 
        [elicit_replacement_Q]
    )
    view = D(crutch.view_H, [crutch.context_sensitive_view],bindings=D.from_dict_of_str({'node':n}),lines=lines)
    Q = D(elicit_replacement_Q,[D(crutch.view_hint_H,view=view)],node=n)
    result = ask.ask_firmly(Q,state)
    return both(as_answer(result), D(updated_H,new=n))

def explore_node(root,state=None,parents=None,starter=None):
    if parents is None:
        parents = datum.empty_list
    class context:
        node=root
        node_updated=False
        datum_updated=False
        datum = None
    while True:
        if starter is None:
            response = represent_node(context.node,state)
            node_repr = ask.extract_answer_firmly(response)
            context.node = update_given_response(context.node,response)
            parent_repr = represent_parents(parents,state)
            lines = concat([parent_repr,node_repr])
            view = '\n'.join(render_lines(lines))
            utilities.clear()
            print(view)
        c = starter if starter is not None else utilities.getch()
        starter = None
        result = process_char(c,context.node,state,parents=parents)

        def process_result(m):
            if m.head == updated_H:
                context.node= m['new']
                context.node_updated=True
            elif m.head == changed_underlying_H:
                context.datum = m['new']
                context.datum_updated=True
            elif m.head == moved_H and m['direction'] == left:
                if parents != datum.empty_list:
                    return True,m
            elif m.head == quits_H:
                return True,m
            elif m.head == ask.and_H:
                quita, a = process_result(m['a'])
                quitb, b = process_result(m['b'])
                return quita or quitb, both(a,b)
            elif m.head == sends_message_H:
                return False,m
            return False,noop

        quit,result = process_result(result)
        if quit:
            if context.datum_updated:
                result = both(result,D(changed_underlying_H,new=context.datum))
            if context.node_updated:
                result = both(result,D(updated_H,new=context.node))
            return result

def explore(d,state=None):
    root = add_pointer(make_node(d,state=state),state)
    return explore_node(root,state)

is_expanded_H = "is expanded"
is_not_expanded_H = "is not expanded"
has_pointer_H = "the pointer is in one of this node's chidren"
is_pointer_H = "the pointer is pointing at this node"
def toggle_expanded(n,state):
    def toggle(m):
        if m.head == is_expanded_H:
            return D(is_not_expanded_H)
        elif m.head == is_not_expanded_H:
            return D(is_expanded_H)
    if n.head == node_H:
        if n['children'] == datum.empty_list:
            new_children = datum.empty_list
            d = n['D']
            for k in d:
                new_children = D.make_list(make_node(d[k],state,key=k),new_children)
            if new_children != datum.empty_list:
                n = n.update(children=new_children)
    return n.modifier_map(toggle)

def is_expanded(n):
    for m in n.modifiers.to_list():
        if m.head == is_expanded_H:
            return True
    else:
        return False

def expanded_children(n,state):
    children = None
    if not is_expanded(n):
        return datum.empty_list
    elif n.head == node_H:
        return n['children']
    else:
        return ask.ask_firmly("what are the children of the node [node]?",
                state,
                node=n
            )

node_H = "a node in an interactive visualization corresponding to [D], which has children [children]"
node_is_modifier_H = "represents a datum which is the [index]th modifier of the parent node's datum"
node_has_key_H = "represents a datum which is stored as the referent of [key] in the parent node's datum"
headline_is_H = "should be represented by the headline [headline] when prefix is [pre]"
has_representation_H = "should be represented by the list of lines [lines]"
get_node_Q = "what node should be used to represent [datum] in an interactive exploration?"

def make_node(d, state,key=None):
    new_modifiers = [D(is_not_expanded_H)]
    if key is not None:
        new_modifiers.append(D(node_has_key_H,key=D.from_str(key)))
    node = None
    if state is not None:
        response,answer = ask.ask_and_extract(D(get_node_Q,datum=d))
        if answer is not None:
            node = answer
    if node is None: 
        node = D(node_H,D=d,children=datum.empty_list)
    return node.update(_modifiers=new_modifiers,append_modifiers=True)

moved_H = "the user tried to move [direction] out of the movable area"
updated_H = "the referenced node should be replaced by [new]"
changed_underlying_H = ("after an interactive session, the user replaced the datum with [new]")
quits_H = "the user wanted to end the interactive exploration session"
sends_message_H = "the user entered the message [message]"
noop = no_answer()

up = D("the direction up")
down = D("the direction down")
left = D("the direction left")

user_entered_input_H = "the user entered [string] in response to [view]"

def explore_crutch(Q,asker):
    if Q.head == user_entered_input_H:
        view = Q['view']
        string = Q['string']
        response, answer = asker.ask_and_extract(crutch.eval_str_Q,view=view,string=string)
        if answer is not None:
            asker.ask_tail("the user entered a string that refers to [x] in view [view]",x=answer,view=view)
        else:
            return response
    return None

def process_char(c, n, state=None,parents=None,recursive=False):
    if parents is None:
        parents=datum.empty_list
    if is_pointer(n):
        if c == 'q':
            return D(quits_H)
        elif c == ':':
            view  = D("the view of an interactive exploration of node [node]",node=n)
            s = raw_input(":")
            response = ask.ask(user_entered_input_H, state=state,string=D.from_str(s),view=view)
            new_response,answer = ask.ask_and_extract(
                    "in light of [response], what value should [node] be replaced by, if any?",
                    state,
                    response=response,
                    node=n
                )
            if answer is not None:
                new_n = add_pointer(answer)
                return D(updated_H,new=new_n)
            return both(D(quits_H),D(sends_message_H,message=D.from_str(s)))
        elif c == 'j':
            children = expanded_children(n,state)
            if children == datum.empty_list:
                return D(moved_H,direction=down)
            else:
                new_children = D.make_list(add_pointer(children.list_head(),state),children.list_tail())
                new_n = change_pointer(n)
                return D(updated_H,new=new_n.update(children=new_children))
        elif c == 'k':
            return D(moved_H,direction=up)
        elif c == 'z':
            return D(updated_H,new=toggle_expanded(n,state=state))
        elif c == 'h':
            return D(moved_H,direction=left)
        elif c == 'l':
            result = explore_node(n,state,parents=parents)
            return both(D(moved_H,direction=left),result)
        elif c == 'r' and state is not None:
            #XXX elicit_replacement should use the parents list to provide additional context
            new_value = elicit_replacement(n,state)
            new_n = n.update(D=new_value)
            return both(D(changed_underlying_H,new=new_value),D(updated_H,new=new_n))
    elif has_pointer(n):
        if c == 'l' and recursive:
            result = explore_node(n,state,parents=parents,starter='l')
            return both(D(moved_H,direction=left),result)
        children = expanded_children(n,state).to_list()
        new_children = []
        results = []
        results = ([None] + 
                   [process_char(c,child,state,D.make_list(n,parents),recursive=True) for child in children] + 
                   [None])
        class context:
            point_to_parent = False
            remove_pointer = False
            new_value = None
            new_child = None
        result = noop
        for x, y, z, child in zip(results,results[1:],results[2:],children):
            context.new_child = child
            context.remove_pointer = False

            def process_y(m):
                if m.head==updated_H:
                    context.new_child = m['new']
                elif m.head == sends_message_H:
                    return m
                elif m.head == moved_H:
                    direction = m['direction']
                    moved_to = {up:x,down:z,left:n}[direction]
                    if moved_to is None:
                        if direction == down:
                            return m
                        elif direction == up:
                            context.new_child = remove_pointer(child)
                            context.point_to_parent = True
                    else:
                        if direction == left:
                            context.point_to_parent = True
                        context.remove_pointer=True
                elif m.head == ask.and_H:
                    return both(process_y(m['a']),process_y(m['b']))
                elif m.head == changed_underlying_H:
                    context.new_value = n['D']
                    key = get_key(context.new_child)
                    if key is not None:
                        context.new_value = new_value.update(**{key.to_str():m['new']})
                elif m.head == quits_H:
                    return m
                return noop

            def process_x(m):
                if m is None:
                    pass
                elif m.head == moved_H and m['direction'] == down:
                    context.new_child = add_pointer(context.new_child,state)
                elif m.head == ask.and_H:
                    process_x(m['a'])
                    process_x(m['b'])
                return noop

            def process_z(m):
                if m is None:
                    pass
                elif m.head == moved_H and m['direction'] == up:
                    context.new_child = add_pointer_at_end(context.new_child,state)
                elif m.head == ask.and_H:
                    process_z(m['a'])
                    process_z(m['b'])
                return noop

            #order is important---we want to update b before adding the pointer
            result = both(process_y(y),result)
            #these two updates shouldn't do anything, but someday they might
            result = both(process_x(x),result)
            result = both(process_z(z),result)

            if context.remove_pointer:
                context.new_child = remove_pointer(context.new_child)

            new_children.append(context.new_child)

        new_n = n.update(children = D.from_list(new_children))

        if context.point_to_parent:
            new_n = change_pointer(new_n)

        if context.new_value is not None:
            new_n = new_n.update(D=context.new_value)
            result = both(result,D(changed_underlying_H,new=context.new_value))

        result = both(result,D(updated_H,new=new_n))
        return result
    return noop

def add_pointer(n,state):
    return n.update(D(is_pointer_H))

def add_pointer_at_end(n,state):
    children = expanded_children(n,state).to_list()
    if not children:
        return add_pointer(n,state)
    else:
        children[-1] = add_pointer_at_end(children[-1],state)
        return n.update(D(has_pointer_H),children=D.from_list(children))

def change_pointer(n):
    def toggl(m):
        if m.head == is_pointer_H:
            return D(has_pointer_H)
        if m.head == has_pointer_H:
            return D(is_pointer_H)

    return n.modifier_map(toggl)
                

def remove_pointer(n):
    def cut(m):
        return m.head not in [has_pointer_H,is_pointer_H]
    new_n = n.modifier_filter(cut)
    if new_n.head == node_H:
        new_n = new_n.update(children=n['children'].list_map(remove_pointer))
    return new_n


def is_pointer(n):
    for m in n.modifiers.to_list():
        if m.head == is_pointer_H:
            return True
    return False

def has_pointer(n):
    for m in n.modifiers.to_list():
        if m.head == has_pointer_H:
            return True
    return False

def get_key(n):
    for m in n.modifiers.to_list():
        if m.head == node_has_key_H:
            return m['key']
    return None

def get_modifier_index(n):
    for m in n.modifiers.to_list():
        if m.head == node_is_modifier_H:
            return m['index']
    return None
