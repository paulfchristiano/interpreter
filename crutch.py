import datum
from datum import Datum as D
from ipdb import set_trace as debug
import computation as c
import difflib
import ask
import utilities
import re
import explore

in_list_Q = "does [list] contain an item equal to [item]?"
remove_binding_Q = "what are the bindings obtained by removing [key] from [bindings]?"

context_sensitive_view = D("the response to this view is sensitive to the user's current state")
context_sensitive_question = D("the response to this question is sensitive to the user's current state")

get_starting_view_Q = ("what view should the user see when beginning to answer [question]?")
debug_view_Q = "what view should the user see when debugging [target]?"

what_would_user_do_Q = ("what input would the user provide when faced with the view [view]?")
update_view_on_input_Q = ("what view should [view] become after processing [input]?")
predict_interaction_Q = "what will the user ultimately output after an interaction with [view]?"
eval_str_Q = ("what does [string] refer to when entered in response to [view]?")
is_action_Q = "is [x] an action?"
is_Q_Q = "is [x] a question?"
take_action_Q = "what is the view that results if we take action [action] in view [view]?"
cancel_input_H = "the user did not intend to enter [input]"

format_as_string_Q = "how should [x] be represented as a string for printing in [view]?"

debug_Q = "the user is unhappy with the value of [target] and wants to correct the process that produced it"
debug_view_H = "was generated in order to debug [target]"
view_hint_H = "is best answered by presenting the user with [view]"

view_H = "the view with lines [lines] and bindings [bindings]"
invoked_for_H = "invoked to handle [question]"
modified_H = "has been modified on the basis of user input or predicted user input"

asking_about_H = "was asked about the string [template] with arguments [arguments]"

annotate_Q = ("[child] was posed as a subquestion of [parent]; "
              "what is an appropriately annotated version of [child] for this context?")

remove_from_history_Q = "remove [prompt] from history"
add_head_Q = "add [head] to the list of headers that have been entered"

in_list_C = ("the computation that tests whether the result of running [item] is an element "
             "of the result of running [list]")

crutch_answer_Q = ("what is the value of crutch([question])?")

#TODO this could be implemented (much) more nicely as one function per question,
#with a decorator that appends those methods to the database of things to try for crutch
#and also handles extracting arguments
#this would also make it easier to have functions from other modules register themselves
#and it would allow me to interleave the ridiculous definitions above with the relevant methods

def crutch(Q,state):

    asker = ask.QuestionContext(Q,state)
    def annotater(subQ):
        return ask.ask_firmly(annotate_Q,state,parent=Q,child=subQ)
    #asker.preprocessing = annotater
    
    if Q.head == annotate_Q:
        child = Q['child']
        parent = Q['parent']
        return asker.as_answer(child)

    if Q.head == get_starting_view_Q:
        question = Q['question']
        bindings = {}
        invoked_for_modifier = D(invoked_for_H,question=question)
        modifiers = [invoked_for_modifier]
        for m in Q['question'].modifiers.to_list():
            if m.head == view_hint_H:
                return asker.as_answer(m['view'].update(invoked_for_modifier))
            if m == context_sensitive_question:
                modifiers.append(context_sensitive_view)
        if question.head == debug_Q:
            return asker.ask_tail(debug_view_Q, target=question['target'])
        return asker.as_answer(D(view_H, modifiers,lines=D.from_list_of_str(['---',question.head]),
            bindings=D.from_dict_of_str(question.bindings)))

    if Q.head == debug_view_Q:
        target = Q['target']
        lines = []
        bindings = {}
        lines.append("Debug: {}".format(target.head))
        lines.append("BINDINGS")
        for k, v in sorted(target.bindings.items()):
            line = "{}: {}".format(k,v.head)
            bindings[k] = v
            lines.append(line)
        lines.append("MODIFIERS")
        n = 0
        modifier_name = "mod{}".format(n)
        for m in target.modifiers.to_list():
            while modifier_name in bindings:
                n += 1
                modifier_name = "mod{}".format(n)
            line = "({}) {}".format(modifier_name,m.head)
            lines.append(line)
            bindings[modifier_name] = m
        return asker.as_answer(D(
            view_H,
            [D(debug_view_H,target=target)],
            lines=D.from_list_of_str(reversed(lines)),
            bindings=D.from_dict_of_str(bindings)
        ))


    if Q.head == what_would_user_do_Q:
        view = Q['view']
        prompt = get_prompt(view)
        question = None
        use_prediction = True
        for m in view.modifiers.to_list():
            if m.head == invoked_for_H:
                question = m['question']
            if m.head == debug_view_H or m == context_sensitive_view:
                use_prediction = False
        alternatives = []
        suggestions = []
        if use_prediction:
            new_Q = D(c.lookup_Q,bindings=state.get_history(),key=D.from_str(prompt))
            response, answer = asker.ask_and_extract(new_Q)
            if answer is not None:
                return asker.as_answer(answer)
            fresh = True
            for m in view.modifiers.to_list():
                if m.head == modified_H:
                    fresh = False
            if fresh:
                q = asked_about(view)
                if q is not None:
                    question_head = q['template'].to_str()
                    l = state.get_historical_heads().to_list_of_str()
                    scored_l = sorted(
                        [(h,string_similarity(h,question_head)) for h in l], 
                        key=lambda x : -x[1])
                    alternatives = []
                    for h, score in scored_l:
                        if score > 0 and h!=question_head and len(alternatives) < 5:
                            alternatives.append(h)
        utilities.clear()
        print(prompt)
        for i, option in enumerate(alternatives):
            print("Did you mean {}:{}".format(i,option))
        input = raw_input()
        try:
            k = int(input)
            if k < len(alternatives):
                input = "return {}".format(alternatives[k])
        except ValueError:
            pass
        state.set_history(prompt, input)
        return asker.as_answer(D.from_str(input))

    if Q.head == add_head_Q:
        head = Q['head']
        heads = state.get_historical_heads()
        already_there = asker.ask_firmly(in_list_Q,item=head,list=heads)
        if not already_there:
            state.add_head(head)
        return asker.no_answer()


    if Q.head == format_as_string_Q:
        x = Q['x']
        try:
            k = x.to_int()
            return asker.as_answer(D.from_str(str(k)))
        except ValueError:
            pass
        try:
            char = x.to_char()
            return asker.as_answer(D.from_str(char))
        except ValueError:
            pass
        try:
            s = x.to_str()
            return asker.as_answer(x)
        except ValueError:
            pass

    if Q.head == c.eval_Q:
        comp = Q['computation']
        if comp.head == in_list_C:
            l = asker.ask_firmly(c.run_Q(comp['list']))
            ql = c.quote(l)
            item = asker.ask_firmly(c.run_Q(comp['item']))
            qi = c.quote(item)
            return asker.ask_tail(c.run_Q(c.branch(
                c.eq(ql,c.quote(datum.empty_list)),
                c.quote(datum.no),
                c.branch(
                    c.eq(c.referent_str('head',ql),qi),
                    c.quote(datum.yes),
                    D(in_list_C,list=c.referent_str('tail',ql),item=qi)
                )
            )))

    if Q.head == in_list_Q:
        item = Q['item']
        l = Q['list']
        return asker.ask_tail(c.run_Q(D(in_list_C,item=c.quote(item),list=c.quote(l))))

    #XXX now that crutch is dealing with things from other packages this seems like a mess...
    #I should fix it, either by killing crutch earlier or by writing module specific additions
    #e.g. explore could have an explore_crutch, which gets called in this process and either returns or None
    response = explore.explore_crutch(Q,asker)
    if response is not None: return response

    if Q.head == update_view_on_input_Q:
        view = Q['view']
        input = Q['input'].to_str()
        lines = view['lines'].to_list_of_str()
        bindings = view['bindings']
        debugging = False
        for m in view.modifiers.to_list():
            if m.head == invoked_for_H:
                question = m['question']
            if m.head == debug_view_H:
                debugging = True

        if debugging:
            try:
                target = asker.ask_firmly(c.lookup_Q,key=Q['input'],bindings=bindings)
                asker.ask(debug_Q,target=target)
                return asker.as_answer(view)
            except:
                pass

        def set_answer_and_return(a):
            return ask.as_answer(question,a)

        def update_view(view,*args,**kwargs):
            new_view = view.update(*args,**kwargs)
            fresh = True
            for m in new_view.modifiers.to_list():
                if m.head == modified_H:
                    fresh = False
            if fresh:
                new_view = new_view.update(D(modified_H))
            return new_view

        if input=="return":
            return asker.no_answer()

        if input=="pdb":
            debug()
            return asker.as_answer(update_view(view,lines=D.make_list(D.from_str(input),view['lines'])))

        def print_answer(answer):
            new_lines = [asker.ask_firmly(format_as_string_Q, x=answer,view=view).to_str(),input]+lines
            return asker.as_answer(update_view(view,lines=D.from_list_of_str(new_lines)))
        def debug_answer(answer):
            explore.explore(answer)
            asker.no_answer()

        def say_answer(a):
            return a

        builtins = [
                ("return {}", set_answer_and_return),
                ("say {}", say_answer),
                ("print {}", print_answer),
                ("debug {}", debug_answer)
            ]
        for template,fn in builtins:
            arg = utilities.unformat(input,template)
            if arg is not None:
                arg = D.from_str(arg)
                response,answer = asker.ask_and_extract(eval_str_Q,view=view,string=arg)
                if answer is not None:
                    return fn(answer)
                elif response.head == cancel_input_H and response['input'] == arg:
                    prompt = D.from_str(prompt_from_view(view))
                    asker.ask(remove_from_history_Q,prompt=prompt)
                    return asker.as_answer(view)

        response,answer = asker.ask_and_extract(eval_str_Q,view=view,string=D.from_str(input))
        if answer is not None:
            if asker.ask_firmly(is_action_Q,x=answer):
                view = update_view(view,lines=D.from_list_of_str([input] + lines))
                return asker.ask_tail(take_action_Q,action=answer,view=view)
            else:
                var_name = "out{}".format(len(lines))
                new_bindings = None
                new_lines = None
                if asker.ask_firmly(is_Q_Q,x=answer):
                    response,answer_to_answer = asker.ask_and_extract(answer)
                    if answer_to_answer is not None:
                        new_bindings = D.make_dict(D.from_str(var_name), answer_to_answer, bindings)
                        new_lines = D.from_list_of_str([ "A: {}".format(var_name), "Q: {}".format(input)]+lines)
                    else:
                        new_bindings = D.make_dict(D.from_str(var_name), response, bindings)
                        new_lines = D.from_list_of_str([ "{} = {}".format(var_name, response.head), 
                                                         "Q: {}".format(input)]+lines)
                else:
                    new_bindings = D.make_dict(D.from_str(var_name), answer, bindings)
                    new_lines = D.from_list_of_str([ "{} = {}".format(var_name, input)]+lines)
                return asker.as_answer(update_view(view,lines=new_lines, bindings=new_bindings))
        else:
            if response.head == cancel_input_H:
                prompt = prompt_from_view(view)
                question = asked_about(view)
                input = response['input']
                if input == Q['input']:
                    asker.ask(remove_from_history_Q,prompt=D.from_str(prompt))
                    return asker.as_answer(view)
                if question is not None and input == question['template']:
                    asker.ask(remove_from_history_Q,prompt=D.from_str(prompt))
                    return response
                if input == view['lines'].list_head():
                    asker.ask(remove_from_history_Q,prompt=D.from_str(prompt))
                    new_view = update_view(view,lines = view['lines'].list_tail())
                    new_prompt = prompt_from_view(new_view)
                    asker.ask(remove_from_history_Q,prompt=D.from_str(new_prompt))
                    return asker.as_answer(new_view)
            debug()

    if Q.head == remove_from_history_Q:
        prompt = Q['prompt']
        history = state.get_history()
        new_history = asker.ask_firmly(remove_binding_Q, bindings=history,key=prompt)
        state.replace_history(new_history)
        return asker.no_answer()

    if Q.head == remove_binding_Q:
        key = Q['key']
        bindings = Q['bindings']
        if bindings == datum.empty_dict:
            return asker.as_answer(bindings)
        elif bindings.is_dict():
            if bindings.dict_key() == key:
                return asker.as_answer(bindings.dict_other())
            else:
                return asker.as_answer(D.make_dict(bindings.dict_key(),bindings.dict_value(),
                    asker.ask_firmly(remove_binding_Q,bindings=bindings.dict_other(), key=key)))


    if Q.head == eval_str_Q:
        #should factor out these 'test for literal' steps...
        #should somehow allow things to be recognized as nouns, which would subsume the empty list etc. stuff
        #may also need to put in more explicit handling of the empty list case and so on,
        #since right now that might be literally impossible to deal with
        view = Q['view']
        string_d = Q['string']
        string = string_d.to_str()
        if 'bindings' in view:
            result,answer = asker.ask_and_extract(c.lookup_Q,key=string_d,bindings=view['bindings'])
            if answer is not None:
                return asker.as_answer(answer)
        if string in ["undo","cancel","nevermind","never mind"]:
            to_cancel = string_d
            question = asked_about(view)
            if len(view['lines'].to_list())>2:
                to_cancel = view['lines'].list_head()
            elif question is not None:
                to_cancel = question['template']
            return D(cancel_input_H,input=to_cancel)
        try:
            k = int(string)
            return asker.as_answer(D.from_int(k))
        except ValueError:
            pass
        #if string == "this view":
        #    return asker.as_answer(view.explain(
        #        "returning the view in which [string] was typed, because [string] == 'this view'",
        #        string=string_d
        #    ))
        if string == "the question":
            for m in view.modifiers.to_list():
                if m.head == invoked_for_H:
                    question = m['question']
            return asker.as_answer(question.explain(
                "returning the question that [view] was invoked to handle, because [string] == 'the question'",
                string = string_d,
                view=view
            ))
        if string == "itself":
            about = asked_about(view)
            if about is not None:
                answer = D(about['template'].to_str(), [], about['arguments'].to_dict_of_str())
                return asker.as_answer(answer)
        s = utilities.unformat(string, "'{}'")
        if s is None:
            s = utilities.unformat(string, '"{}"')
        if s is not None:
            return asker.as_answer(D.from_str(s))
        s = string.strip().lower()
        literals = {"none":datum.none,
                   "true":datum.yes,
                   "false":datum.no,
                   "yes":datum.yes,
                   "no":datum.no,
                   "[]":datum.empty_list,
                   "{}":datum.empty_dict}
        if s in literals:
            return asker.as_answer(literals[s])
        if s == 'globals':
            return state.state.explain("retrieving global state")

        def subeval(s):
            s = D.from_str(s)
            response,answer = asker.ask_and_extract(eval_str_Q, string=s, view=view)
            if answer is not None:
                return answer, None
            elif response.head == cancel_input_H and response['input'] == s:
                return None, D(cancel_input_H,input=string_d)
            else:
                raise Exception("Can't yet handle subexpressions evaluating to neither answer nor 'cancel'")

        #XXX this would work moderately better if we did the parentheses extraction first
        #we could then do the matching, and sub back in if there was a match
        #this way, the patterns could count on having simple expressions, especially for the a=b,c=d,... one
        vr = r"[a-zA-Z_][a-zA-Z_0-9]*"
        m = re.search(r'^(.*)\[({})\]\s*$'.format(vr), string)
        if m:
            d,response = subeval(m.group(1))
            if d is not None and m.group(2) in d:
                return asker.as_answer(d[m.group(2)])
            elif response is not None:
                return response
        m = re.search(r'^\s*({})\s*:=\s*(.*)\s*$'.format(vr), string)
        if m:
            name = D.from_str(m.group(1))
            result,response = subeval(m.group(2))
            if result is not None:
                return asker.as_answer(D("the action that assigns [result] to [name] in the view "
                         "where it is taken", name=name, result=result))
            elif response is not None:
                return response 
        eq_expr = r'\s*({})\s*=\s*([^=]*)\s*'.format(vr)
        m = re.search(r'^(?:{},{},{}|{},{}|{})$'.format(*(6*[eq_expr])),string)
        if m:
            groups = m.groups()
            result = {}
            for i in range(len(groups)/2):
                if groups[2*i] is not None:
                    val,response = subeval(groups[2*i+1])
                    if val is not None:
                        result[groups[2*i]] = val
                    elif response is not None:
                        return response
            return asker.as_answer(D.from_dict_of_str(result))
        #the parsing should probably bp seperated out as well
        head, args = parenthesize_top_level(string)
        arg_names = ["arg"] if len(args) == 1 else ["arg{}".format(i) for i in range(len(args))]
        arg_values = []
        for arg in args:
            arg_value, response = subeval(arg)
            if arg_value is not None:
                arg_values.append(arg_value)
            elif response is not None:
                return response
        formatted_head = head.format(*arg_names)
        asker.ask(add_head_Q,head=D.from_str(formatted_head))

        if head == "head({})":
            return asker.as_answer(D.from_str(arg_values[0].head))
        if head == "bindings({})":
            return asker.as_answer(D.from_dict_of_str(arg_values[0].bindings))
        if head == "modifiers({})":
            return asker.as_answer(arg_values[0].modifiers)
        if head == "update ({}) by making ({}) refer to ({})":
            return asker.as_answer(arg_values[0].update(_bindings={arg_values[1]:arg_values[2]}))
        if head == "D ({}) ({})":
            return asker.as_answer(D(arg_values[0].to_str(), 
                               _bindings=arg_values[1].to_dict_of_str()))
        if head == "({}):({})":
            return asker.as_answer(D.make_list(arg_values[0],arg_values[1]))
        if head == "{{({}):({})}}:({})":
            return asker.as_answer(D.make_dict(arg_values[0],arg_values[1],arg_values[2]))
        if head == "str({})":
            return asker.as_answer(D.make_str(arg_values[0]))
        if head == "ask({})":
            return asker.ask_tail(arg_values[0])
        if head == "({}) is identical to ({})":
            return asker.ask_tail(c.eq_Q, a=arg_values[0], b=arg_values[1])

        arg_bindings = dict(zip(arg_names,arg_values))
        about = D(asking_about_H, template = D.from_str(formatted_head), arguments =D.from_dict_of_str(arg_bindings))
        return asker.ask_tail('what is the value of "{}" in [view]?'.format(formatted_head), [about],view=view, **arg_bindings)

    if Q.head == predict_interaction_Q:
        view = Q['view']
        while True:
            input = asker.ask_firmly(what_would_user_do_Q,view=view)
            response,new_view = asker.ask_and_extract(update_view_on_input_Q,view=view,input=input)
            if new_view is not None:
                view = new_view
            else:
                return response
    #default
    view = asker.ask_firmly(get_starting_view_Q,question=Q)
    return asker.ask_tail(predict_interaction_Q, view=view)

#Manipulating views---------------------

def asked_about(view):
    for m in view.modifiers.to_list():
        if m.head == invoked_for_H:
            question = m['question']
            for n in question.modifiers.to_list():
                if n.head == asking_about_H:
                    return n

def prompt_from_view(view):
    return '\n'.join(reversed(view['lines'].to_list_of_str()))

def get_prompt(view):
    return "\n".join(reversed(view['lines'].to_list_of_str()))

def add_line(view,line):
    lines = view['lines']
    return view.update(lines=D.make_list(D.from_str(line),lines))

#Pattern matching-----------------------

def string_similarity(a,b):
    """
    Returns a measure of the similarity of a and b

    Currently uses the Levensstein distance, rescaled.
    0 is the cutoff at which a match is barely worth displaying (if there is nothing else to display
    """

    x = difflib.SequenceMatcher(None,a,b).ratio()
    return x-0.5

#String manipulation--------------------

def escape_braces(s):
    """
    escape_braces(s).format() = s

    Replace { with {{ and replace } with }}
    """

    def escape_char(c):
        if c == '{':
            return '{{'
        if c == '}':
            return '}}'
        return c
    return ''.join(escape_char(c) for c in s) 


def parenthesize_top_level(expr):
    """
    Replace each parenthesized expression with {}, and returns a list of parenthesized expressions
    """
    expr = escape_braces(expr)
    paren_count = 0
    template = ""
    current_arg = ""
    arg_list = []
    for c in expr:
        if c == '(':
            if paren_count > 0:
                current_arg += c
            paren_count += 1
        elif c == ')':
            paren_count -= 1
            if paren_count > 0:
                current_arg += c
            elif paren_count == 0:
                arg_list.append(current_arg.format())
                current_arg = ""
                template += "({})"
            elif paren_count < 0:
                return expr, []
        else:
            if paren_count > 0:
                current_arg += c
            elif paren_count == 0:
                template += c
    if paren_count == 0:
        return template, arg_list
    else:
        return expr, []

