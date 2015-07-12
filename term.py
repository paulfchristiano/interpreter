from ipdb import set_trace as debug
from memoization import memoize, memoize_constructor, weak_memoize, weak_memoize_constructor
from inspect import getargspec
from decorator import decorator
from frozendict import frozendict
import functools

#FIXME right now the hash consing uses a strong key
#this is kind of healed by saving to the DB periodically,
#but probably we should just make memoize constructor use weakkeys.
#(which requires changing memoize to have that option, but that seems straightforward)
#(alternative constructors also need to use weak memoization)

#used to set attributes of class methods...
def as_head(name):
    def set_head(f):
        f.head = name
        return f
    return set_head

#Sources------------------------------------------

#FIXME this seems really awkward! reconsider the whole idea of MetaTerm
#TODO factor out the base class

@weak_memoize_constructor
class MetaTerm(object):
    def __init__(self, _head, _bindings={}, **kwargs):
        self._head = _head
        self._bindings = frozendict(_bindings, **kwargs)
        self._hash = hash((self.head, self.bindings))

    @property
    def head(self):
        return self._head

    @property
    def bindings(self):
        return self._bindings

    def __repr__(self):
        return "M({})".format(self.head)

    def __hash__(self):
        return self._hash

    def __getitem__(self, key):
        return self.bindings[key]

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __ne__(self, other):
        return not (self == other)

@as_head("constructing a term with head [head] and bindings [bindings]")
def construction(head, bindings):
    return MetaTerm(construction.head, head=head, bindings=bindings)

@as_head("accessing the referent of [binding] in [term]")
def accessing(term, binding):
    return MetaTerm(accessing.head, term=term, binding=binding)

@as_head("applying [operation], whose result was produced by [prior]")
def explain(operation, prior):
    return MetaTerm(explain.head, operation=operation, prior=prior)

@as_head("applying [operation] because of [cause]")
def because(cause, operation):
    return MetaTerm(because.head, cause=cause, operation=operation)


#Terms arguments-----------------------------------

def prepare_arg(constructor, raw_name):

    def make_raw_arg(f):
        f_args = getargspec(f).args
        raw_index = f_args.index(raw_name)

        def with_raw_arg(f, *args, **kwargs):

            raw_value = None
            from_list = False
            args = list(args)
            if len(args) > raw_index:
                raw_value = args[raw_index]
                from_list = True
            elif raw_name in kwargs:
                raw_value = kwargs[raw_name]
            else:
                return f(*args, **kwargs)

            if type(raw_value) is str:
                other_raw_args = {}
                for k in kwargs.keys():
                    if k not in f_args:
                        other_raw_args[k] = kwargs[k]
                        del kwargs[k]
                raw_value = constructor(raw_value, **other_raw_args)

            if from_list:
                args[raw_index] = raw_value
            else:
                kwargs[raw_name] = raw_value

            return f(*args, **kwargs)

        return decorator(with_raw_arg, f)

    return make_raw_arg


metaterm_arg = functools.partial(prepare_arg, MetaTerm)

#Main definitions---------------------------------

@weak_memoize_constructor
class Term(object):

    def __init__(self, _head, _bindings={}, _source=None, _id=None, **kwargs):
        self._head = _head
        assert isinstance(_head, str) or isinstance(_head, unicode)
        self._bindings = frozendict(_bindings, **kwargs)
        for v in self._bindings.values():
            assert(isinstance(v, Term))

        if _source is None:
            self._source = construction(self._head, self._bindings)
        else:
            self._source = _source

        if _id is None:
            self._id = hash((
                self._head, 
                frozendict({k:v.id for k, v in self._bindings.iteritems()})
            ))
        else:
            self._id = _id

        #TODO fix hash and id collisions (right now we just count on not running into any)
        #this is non-trivial, since something might collide with a DB entry
        #but it's also quite unlikely to cause trouble
        self._hash = hash((
            self._head,
            self._bindings,
            self._source
        ))

    #Basic methods--------------------------------

    @property
    def modifier(self):
        #FIXME if I subclass Term I'll still make Terms for things without _modifiers...
        return self.bindings.get('_modifier', Term.trivial()).explain(accessing(self, "_modifier"))

    def __repr__(self):
        
        return str(self)

        #I stopped using the version below because accidentally
        # printing repr(...) was too destructive, and very rarely needed.
        return "T({}, bindings={})".format(self.head, self.bindings)

    def __str__(self):
        return "T({})".format(self.head)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return self._hash

    @property
    def id(self):
        return self._id

    @property
    def head(self):
        return self._head

    @property
    def bindings(self):
        return self._bindings

    @property
    def source(self):
        return self._source

    #Explanations---------------------------------

    def change_source(self, new_source):
        return Term(self.head, self.bindings, _source=new_source, _id=self.id)

    @metaterm_arg('operation')
    def explain(self, operation, **kwargs):
        return self.change_source(explain(operation, self.source))

    @metaterm_arg('cause')
    def because(self, cause, **kwargs):
        return self.change_source(because(cause, self.source))

    #Operations-----------------------------------

    @memoize
    @as_head("applying the assignments in [bindings] to [term]")
    def simple_update(self, **kwargs):
        return Term(self.head, self.bindings, **kwargs).explain(Term(
            self.simple_update.head, 
            bindings=Term.from_dict_of_str(kwargs),
            term=self
        ))

    @memoize
    def __getitem__(self, key):
        return self.bindings[key].explain(accessing(self, key))

    def __contains__(self, key):
        return key in self.bindings

    def __iter__(self):
        return self.bindings.__iter__()

    #Conversions and operations on special types---------------------

    #Strings and chars-----------------

    @classmethod
    @as_head("a string with list of characters [list]")
    def simple_string(cls, list):
        return cls(cls.simple_string.head, list=list)

    @classmethod
    @weak_memoize
    def from_str(cls, s):
        assert type(s) is str
        return cls.simple_string(cls.from_list([cls.from_char(x) for x in s]))

    @memoize
    def to_str(self):
        if self.head != self.simple_string.head:
            return None
        l = self['list'].to_list()
        if l is None:
            return None
        chars = [c.to_char() for c in l]
        if any(c is None for c in chars):
            return None
        return ''.join(chars)

    def is_simple_str(self):
        return self.to_str() is not None

    @classmethod
    @as_head("the character with ASCII code [x]")
    def simple_char(cls, x):
        return cls(cls.simple_char.head, x=x)

    @classmethod
    @memoize
    def from_char(cls, c):
        assert type(c) is str
        assert len(c) == 1
        return cls.simple_char(cls.from_int(ord(c)))

    @memoize
    def to_char(self):
        if self.head != self.simple_char.head:
            return None
        x = self['x'].to_int()
        if x is None:
            return None
        return chr(x)

    def is_simple_char(self):
        assert self.to_char() is not None

    #Booleans---------------------------

    @classmethod
    @as_head("yes")
    def yes(cls):
        return cls(cls.yes.head)

    @classmethod
    @as_head("no")
    def no(cls):
        return cls(cls.no.head)


    @classmethod
    def from_bool(cls, b):
        assert type(b) is bool
        return (cls.yes() if b else cls.no())

    def to_bool(self):
        if self.head == self.yes.head:
            return True
        elif self.head == self.no.head:
            return False
        else:
            return None

    def is_simple_bool(self):
        return self.to_bool() is not None

    def __bool__(self):
        b = self.to_bool()
        if b is None:
            raise ValueError("Can't implicitly convert non-bool Term to bool")
        else:
            return b

    __nonzero__ = __bool__

    #Integers---------------------------

    @classmethod
    @as_head("two times [x]")
    def double(cls, x):
        return cls(cls.double.head, x=x)

    @classmethod
    @as_head("two times [x] plus one")
    def double_plus_one(cls, x):
        return cls(cls.double_plus_one.head, x=x)

    @classmethod
    @as_head("the additive inverse of [x]")
    def negative(cls, x):
        return cls(cls.negative.head, x=x)

    @classmethod
    @as_head("the number zero")
    def zero(cls):
        return cls(cls.zero.head)

    @classmethod
    @weak_memoize
    def from_int(cls, k):
            result = None
            if k == 0:
                result = cls.zero()
            elif k < 0:
                result = cls.negative(cls.from_int(-k))
            elif k % 2 == 0:
                result = cls.double(cls.from_int(k/2))
            elif k % 2 == 1:
                result = cls.double_plus_one(cls.from_int(k/2))
            else:
                raise TypeError("Cannot convert non-integer to an integer Term")
            return result


    @memoize
    def to_int(self):
        if self.head == self.zero.head:
            return 0
        elif self.head == self.negative.head:
            x = self.bindings['x'].to_int()
            return None if x is None else -1*x
        elif self.head == self.double.head:
            x = self.bindings['x'].to_int()
            return None if x is None else 2*x
        elif self.head == self.double_plus_one.head:
            x = self.bindings['x'].to_int()
            return None if x is None else 2*x+1
        else:
            return None

    def is_simple_int(self):
        return self.to_int() is not None

    #Lists------------------------------

    #TODO almost all of the list manipulation here should be pulled out into a another library
    #I suspect that map and filter should also work with properties and fields / updates instead...
    #And all of it should be able to handle complex lists as well as simple ones

    @classmethod
    @as_head("a list with first element [head] and following elements [tail]")
    def cons(cls, head, tail):
        return cls(cls.cons.head, head=head, tail=tail)

    @classmethod
    @as_head("an empty list")
    def empty_list(cls):
        return cls(cls.empty_list.head)


    @classmethod
    def from_list(cls, xs):
        if type(xs) != list:
            raise TypeError("Cannot convert non-list to a list Term")
        result = cls.empty_list()
        for x in reversed(xs):
            result = cls.cons(x, result)
        return result

    def is_simple_list(self):
        return self.to_list() is not None

    @memoize
    def to_list(self):
        d = self
        result = []
        while d.head != self.empty_list.head:
            if d.head != self.cons.head:
                return None
            result.append(d['head'])
            d = d['tail']
        return result


    #Dictionaries------------------------
            
    @classmethod
    @as_head("a dictionary that maps [key] to [value] and maps other keys according to [other]")
    def dict_cons(cls, key, value, other):
        return cls(cls.dict_cons.head, key=key, value=value, other=other)

    @classmethod
    @as_head("a dictionary that doesn't map anything to anything")
    def empty_dict(cls):
        return cls(cls.empty_dict.head)

    @classmethod
    def from_dict(cls, m):
        result = cls.empty_dict()
        if type(m) != dict:
            raise TypeError("Cannot convert non-dict to dict Term")
        for k, v in m.iteritems():
            result = cls.dict_cons(k, v, result)
        result = result
        return result

    def is_simple_dict(self):
        return self.to_dict() is not None
    
    #FIXME this will overflow the stack for 1000+ element dictionaries stored linearly
    #TODO in the long run we should have an efficient canonical representation, and use
    #a dictionary subclass that lazily unpacks terms here
    def to_dict(self):
        d = self
        result = {}
        if d.head == self.empty_dict.head:
            return {}
        elif d.head == self.dict_cons.head:
            other = d['other'].to_dict()
            if other is None:
                return None
            else:
                return dict(other, **{d['key']:d['value']})

    #Pair-------------------------------

    @classmethod
    @as_head("a pair with first element [a] and second element [b]")
    def pair(cls, a, b):
        return cls(cls.pair.head, a=a, b=b)

    @classmethod
    @weak_memoize
    def from_pair(cls, pair):
        if type(pair) != tuple:
            return TypeError("Can't convert non-tuple to pair Term")
        if len(pair) != 2:
            return ValueError("Can't convert non-pair tuple to pair Term")
        return cls.pair(**pair)

    @memoize
    def to_pair(self):
        if self.head != self.pair.head:
            return None
        return (self['a'], self['b'])

    def is_simple_pair(self):
        return self.to_pair() is not None

    #Lists and dicts of strings--------

    @classmethod
    def from_dict_of_str(cls, m):
        return cls.from_dict({cls.from_str(k):v for k, v in m.iteritems()})

    def to_dict_of_str(self):
        return {k.to_str():v for k, v in self.to_dict().iteritems()}

    @classmethod
    def from_list_of_str(cls, xs):
        return cls.from_list([cls.from_str(x) for x in xs])

    def to_list_of_str(self):
        return [x.to_str() for x in self.to_list()]

    #Constants------------------------------

    @classmethod
    @as_head("the property that everything satisfies")
    def trivial(cls):
        return cls(cls.trivial.head)

    @classmethod
    @as_head("nothing")
    def none(cls):
        return cls(cls.none.head)

term_arg = functools.partial(prepare_arg, Term)

def simple(head, *arg_names):
    @as_head(head)
    def make(*args, **kwargs):
        assert(len(args) + len(kwargs) == len(arg_names))
        T_args = dict(zip(arg_names, args))
        assert(all(k in arg_names[len(args):] for k in kwargs.iterkeys()))
        T_args.update(kwargs)
        return Term(make.head, **T_args)
    return make
