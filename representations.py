from ipdb import set_trace as debug
import term
from memoization import memoize
import properties
import fields
from frozendict import frozendict
import askers
import termtypes

#Representing terms--------------------------------

#TODO I could probably make Representation a function,
#then make a decorator that turns any such function into a "held"
#version...


quoted_term = term.simple("a term with head [head] head and bindings [bindings]",
        'head', 'bindings')
term_type = termtypes.new_type("the type of terms")
termtypes.set_type(term_type, quoted_term)

head = fields.named_binding(
    "the function that maps a term to its head",
    quoted_term.head,
    'head'
)

bindings = fields.named_binding(
    "the function that maps a term to its bindings",
    quoted_term.head,
    'bindings'
)

#referent_of = term.simple("the function that maps a term to the referent of [s] in that term's head", "s")
#FIXME this is a dumb hack to cut down on computational time
#(though I think that in the real thing these changes would propagate back to the computations)
@term.as_head("the function that maps a term to the referent of [s] in that term's head")
def referent_of(s):
    import dictionaries
    return fields.compose(bindings(), dictionaries.image(s))

#FIXME these seem awkward, given that we can just reduce
#I had to write them because accessing referent of is done during reductions...
@fields.getter(referent_of.head)
def get_referent(asker, rep, s):
    import dictionaries
    return asker.ask_tail(fields.get_field(
        fields.compose(bindings(), dictionaries.image(s)),
        rep
    ))

@fields.setter(referent_of.head)
def set_referent(asker, rep, new_value, s):
    import updates, dictionaries
    return asker.ask_tail(updates.apply_update(
        updates.set_field(
            fields.compose(bindings(), dictionaries.image(s)),
            new_value
        ),
        rep
    ))

#Note: automatically memoized (with weak values) because it inherits the Memoizer metaclass from Term
class Representation(term.Term):

    def __init__(self, represents, source=None):
        assert(isinstance(represents, term.Term))
        self._head = quoted_term.head
        self.represents = represents
        self._hash = hash(("representation", self.represents))
        self._id = hash(("representation", self.represents.id))
        self._source = source

    def change_source(self, new_source):
        return Representation(self.represents, new_source)

    @property
    @memoize
    def source(self):
        if self._source is None:
            return term.explain(
                quoting(self.represents),
                term.construction(self.head, bindings=self.bindings)
            )
        else:
            return self._source

    @property
    @memoize
    def bindings(self):
        return frozendict(
             head=quote(self.represents.head),
             bindings=quote(self.represents.bindings),
             _modifier=properties.both(
                has_id(quote(self.represents.id)),
                has_source(quote(self.represents.source))
            )
        )


has_id = term.simple("has id [id] and is identical to all other terms with that id", "id")
has_source = term.simple("is the result of performing [operation]", "source")

def make(head, bindings=None, **kwargs):
    if bindings is None:
        bindings = {}
    bindings = frozendict(bindings, **kwargs)
    return quoted_term(
        head=quote(head),
        #can't use quote because the values of bindings are already quotations
        bindings=term.Term.from_dict_of_str(bindings)
    )

#Representing metaterms----------------------------

#TODO I should somehow improve the inheritance hierarchy...
#it seems like Term should probably inherit from MetaTerm,
#and Representation should inherit from this,
#and all of the doubled up code should be removed.
class MetaRepresentation(term.Term):
    def __init__(self, represents, source=None):
        assert(isinstance(represents, term.MetaTerm))
        self.represents = represents
        self._head = represents.head
        self._source = source
        self._hash = hash(("metarepresentation", self.represents))
        self._id = self._hash

    def change_source(self, new_source):
        return MetaRepresentation(self.represents, new_source)

    @property
    @memoize
    def source(self):
        if self._source is None:
            return term.explain(
                quoting(self.represents),
                term.construction(self.head, self.bindings)
            )
        else:
            return self.source

    @property
    @memoize
    def bindings(self):
        return quote(self.represents.bindings)

#Quoting------------------------------------------

def quote(x):
    if isinstance(x, term.Term):
        return Representation(x)
    elif isinstance(x, term.MetaTerm):
        return MetaRepresentation(x)
    elif isinstance(x, str) or isinstance(x, unicode):
        return term.Term.from_str(x)
    elif isinstance(x, int) or isinstance(x, long):
        return term.Term.from_int(x)
    elif isinstance(x, dict) or isinstance(x, frozendict):
        return term.Term.from_dict({quote(k):quote(v) for k, v in x.iteritems()})
    elif isinstance(x, list) or isinstance(x, tuple):
        return term.Term.from_list([quote(y) for y in x])
    elif isinstance(x, askers.Wrapper):
        return quote(x.value)
    elif isinstance(x, askers.Query):
        return x.quote()
    elif isinstance(x, askers.Asker):
        return term.Term("an asker with query [Q]", Q=x.Q)
    elif hasattr(x, 'func_name'):
        return term.Term("a function with name [name]", name=quote(x.func_name))
    raise ValueError("failed to quote")

def quoting(d):
    return term.MetaTerm(quoting.head, term=d)
quoting.head = "computing a quoted representation of [term]"
