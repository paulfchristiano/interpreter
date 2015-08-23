[Everything in this repository is likely to be changed without regard for consistency or compatability.]


term.py:Term -- the type of almost all data, consists of a 'head', which is a string
describing some object in natural language (or whatever other language).
This string maye contain some expressions of the form [x].
Each such expression is a link to another Term;
the mapping from name to referent is stored in the bindings field.
We consider all heads to end with the implicit suffix "which satisfies [_modifier]"
so that the referent of '_modifier' in any Term's bindings is a property which that
term satisfies.

Terms are rendered as T(head).

term.py:MetaTerm -- a convenience class. See the discussion of representations.py below.


dispatch.py:Dispatcher -- the main control structure. There are a bunch of dispatchers,
one for answering questions, one for running computations, one for getting and setting fields, etc.
A dispatcher takes a sequence of terms as arguments. It picks a function to invoke based on the heads
of those terms.
If X is a dispatcher, then the decorator...

@X(name_1, name_2, ..., name_k)
def f(...)

...registers f as the function to be invoked when X.dispatch is called
with a first argument with head == name_1, a second argument with head == name_2, etc.
Ommitted names (either equal to None or left out of the list) match anything.

The bindings of each matched argument are passed to f as kwargs.
Each unmatched argument is passed as a positional argument.
A tuple of booleans may also be given, indicating that some matched arguments should not be expanded.

@X also rebinds f to produce a term with head name_1,
as does @term.py:as_head.



askers.py:Query -- a query Q is basically a pair, Q.question is a question to be answered,
and Q.other is a list of desiderata that apply to the representation of the question.

askers.py:Reply -- a reply is returned as the answer to a Query. 
Formally it is a property that applies to the representation of the query.
For example, it might be the property "has answer [A]" for some term A.




ask.py:ask -- takes as input a query, and outputs a best reply

ask.py:Asker -- many functions depend on global state, for example
on the record of everything the user has ever typed (which is used
to make predictions about how to respond to similar questions in the future).
Ideally this global state is all encapsulated by an asker 
(though right now there are a few unfortunate pieces of mutable global state for performance reasons).
ask spawns a new Asker to answer a top-level question, which sets up some default state.
Whenever a subquestion is asked, a new Asker is created which inherits its parent's state
(and propagates changes back to the parent).
Dispatched functions always have an asker as their first argument.

The Asker class mixes together functionality from askers.py:BaseAsker,
counters.py:Counter, relayers.py:Relayer, context.py:ContextUpdater,
and state.py:StatefulAsker.
Each of these classes passes a bit of additional information up and down
between questions and subquestions, or maintains a bit of additional state.



database.py:Database -- global state is stored in a mongo instance.
The data is loaded lazily as accessed.
(This was necessary in previous implementations for performance reasons,
but is very unneccessary in the current implementation.)



representations.py:Representation -- for a term X, Representation(X) is a new term that refers to T.
For example, if X = T(zero), then Representation(X) = T(a term with head [h]), where h is a term referring to 'zero.'
Representation is its own class because computing the representation takes time linear
in the number of terms reachable by following links, so we want to compte it lazily.

term.py:MetaTerm -- a metaterm with head H and bindings B is the thing referred to by a term with
head H and bindings B; roughly an inverse operation to Representation.
So MetaTerm(an empty list) is semantically equivalent to [];
both are the referent of Term(an empty list).
MetaTerm isn't ontologically necessary, it's just more convenient
than ensuring that Python has enough objects to mirror all of the operations we want
to perform using terms.
