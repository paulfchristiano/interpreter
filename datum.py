from ipdb import set_trace as debug
from utilities import unformat
from copy import copy
from weakref import WeakValueDictionary

def unhold_first(f):
    def unheld_f(self, *args,**kwargs):
        if self.fn is not None:
            self.unhold()
        return f(self,*args,**kwargs)
    return unheld_f

class Datum(object):
    """
    Datum is the type of all objects manipulated within the tool.

    A datum has two primary fields:
    head: a string that explains what the datum is
    bindings: a dictionary that defines strings used in the head

    By convention, d.bindings['_modifiers'] is a list of properties satisfied by d.
    d.modifiers returns d.bindings['_modifiers'], 
    or an empty list if d.bindings['_modifiers'] is a missing value

    There are builtin routines for conversion to/from and manipulation 
    of strings, ints, lists, dicts, characters, pairs, bools...
    """


    def __init__(self, _head,_modifiers=None, _bindings=None,**kwargs):
        """
        Initialize a new Datum.

        _head is the head of the datum, which will be displayed whenever the datum is displayed
        _bindings maps a dictionary mapping each name to its interpretation at this datum
        _modifiers can be either a datum or a list, which is stored in bindings['_modifiers']
        If it is a list, it is first converted to a datum.

        _head can also be a callable, which creates a lazy datum.
        These data should only be stored as referents in other data.
        Whenever they are accessed, teh head is run and the datum is replaced with the result.

        """

        self.ids = []
        """
        A DatumID object that indexes a representation of self
        in the database from which it was loaded.

        Is None if self was not loaded from a database.
        """

        self.explained_bindings = {}
        """
        A cache for the values of self[s]

        When a value is looked up in bindings, it is annotated with its source.
        explained_bindings caches these annotated versions for unadorned string queries,
        so that they don't have to be recomputed

        In general, self.explained_bindings[s] = self.bindings[s].explain(looking up s)
        """

        if callable(_head):
            self.fn = _head
            """
            A function that should be called in order to populate the fields of self.

            Will be called the first time that the head or bindings of this datum are accessed.
            """

        elif type(_head) == str:
            self.fn = None
            self._head = _head


            if type(_modifiers) == list:
                _modifiers = Datum.from_list(_modifiers)
            if _modifiers is not None:
                kwargs['_modifiers'] = _modifiers

            if _bindings is None:
                self._bindings = {}
            else:
                self._bindings = dict(_bindings)
            self._bindings.update(**kwargs)

            for v in self._bindings.values():
                assert v.__class__.__name__ == 'Datum'

        else:
            debug()

    #Basic methods--------------------------------

    @property
    @unhold_first
    def head(self):
        return self._head

    @property
    @unhold_first
    def bindings(self):
        return self._bindings

    @property
    def modifiers(self):
        if '_modifiers' not in self.bindings:
            return empty_list
        result = self['_modifiers']
        if result.is_list():
            return result
        else:
            #XXX this can happen e.g. because _modifiers was a lambda expression that couldn't be reloaded
            #from a previous session.
            #There obviously needs to be a better way to fix this.
            return empty_list

    @unhold_first
    def __getitem__(self,key):

        #key may be a string or a datum representing a string
        #key_s is the string
        #key_d is the datum representing that string
        def get_value(key_s,key_d):
            return self.bindings[key_s].explain(lookup_H,key=key_d,datum=self)

        if type(key) is str:
            if key not in self.explained_bindings:
                key_s = key
                key_d = Datum.from_str(key)
                self.explained_bindings[key] = get_value(key_s,key_d)
            return self.explained_bindings[key]

        else:
            key_s = key.to_str()
            key_d = key
            return get_val(key_s,key_d)

    def __contains__(self,key):
        return key in self.bindings

    def __iter__(self):
        return self.bindings.__iter__()

    def __repr__(self):
        
        return str(self)

        #I stopped using the version below because accidentally
        # printing repr(...) was too destructive, and very rarely needed.
        if self.fn is not None:
            return "D({})".format(self.fn)
        else:
            return "D({},_bindings={})".format(self._head,self._bindings)

    def __str__(self):
        return "D{}({})".format(
            "[saved]" if self.ids else "",
            "--lambda--" if self.fn is not None else self._head
        )

    #Lazy evaluation------------------------------

    #XXX this could be modified to prevent stack overflows by using greenlets
    #but if there is an overflow it means something has probably gone wrong,
    #so for now I'm leaving it as is
    def unhold(self):
        if self.is_held():
            #If self.fn() evaluates to an explicit datum, this process terminates immediately.
            #If self.fn() evaluates to a lazy datum, then that datum will also be evaluated
            #and this process continues until an explicit datum is produced.
            #All of the lazy datums encountered in this way are then collapsed with self.become(other)
            equivalent_versions = []
            newest = self
            while newest.is_held():
                equivalent_versions.append(newest)
                newest = newest.fn()
            for version in equivalent_versions:
                version.become(newest)

    def hold(self,fn):
        self.fn = fn
        del self._bindings
        del self._head
        del self.explained_bindings


    def is_held(self):
        return self.fn is not None

    #XXX it's awkward that we merely copy dict, rather than actually becoming a copy
    def become(self,other):
        self.__dict__ = other.__dict__

    #Updating-------------------------------------

    def update(self,_modifiers=None,_bindings=None,append_modifiers=False,**kwargs):
        """
        Return a copy of self with the indicated updates applied.

        _modifiers: Either a single modifier or a list of modifiers.
        If a single modifier, then it is appended to the list of modifiers.
        If a list of modifiers, then it either replaces or is appended to the list of modifiers,
        based on the boolean append_modifiers.

        _bindings: A dictionary containing bindings to update or add to self.

        Additional arguments s=x indicate the update self.bindings[s]=x
        """

        #This dictionary will be the bindings of the new datum
        new_bindings = dict(self.bindings)

        #This dictionary includes all of the updates
        #some updates may have involved additional data, which is preserved here
        #This information is only used for explaining the update, not for computing the result
        update_bindings = {}

        for k, v in kwargs.items() + (_bindings.items() if _bindings is not None else []):
            new_bindings[k if type(k) == str else k.to_str()] = v
            update_bindings[Datum.from_str(k) if type(k) == str else k] = v

        if _modifiers is not None and type(_modifiers) is not list and not _modifiers.is_list():
            _modifiers = [_modifiers]
            append_modifiers = True
        if type(_modifiers) is list:
            _modifiers = Datum.from_list(_modifiers)
        if append_modifiers:
            new_bindings['_modifiers'] = self.modifiers.list_concat(_modifiers)
        elif _modifiers is not None:
            new_bindings['_modifiers'] = _modifiers

        result = Datum(self.head,_bindings=new_bindings)

        #test to see if any of the updated fields are exposed
        invalidate_hash = any(self.is_exposed(item) for item in new_bindings.items())
        #if not, carry over the old value of _hash
        if not invalidate_hash and self.is_hashed():
            result._hash = self._hash

        return result.explain(update_H,datum=self,
                bindings=Datum.from_dict(update_bindings)
            )

    @unhold_first
    def explain(self,arg,*args,**kwargs):
        """
        Return a copy of self with its source changed to arg.

        If arg is a datum, it is used as the source.
        If arg is a string, then Datum(arg,*args,**kwargs) is used as the source.

        The source is the explanation provided for where a datum came from.
        It takes the form of an action that produced the datum.
        It is stored in _modifiers.
        All previous sources are stored as well.

        For example, if f(x) = 3+x, then the source of f(7) might be 'applying f to 7.'
        The previous source might be 'adding 3 to 7.'
        """

        #by making this a function we can avoid creating the datum unless it is needed
        def action():
            return Datum(arg,*args,**kwargs) if type(arg) == str else arg

        def add_explanation(l):
            if l == empty_list:
                old_source = Datum("no information is available about how it was produced")
                return Datum.from_list([Datum(source_H,action=action(),old_source=old_source)])
            m = l['head']
            if m.head == source_H:
                return l.update(head=Datum(source_H,action=action(),old_source=m))
            else:
                return l.update(tail=add_explanation(l['tail']))

        #I would prefer to use an update here (which would preserve the hash automatically)
        #but alas that would lead to an infinite loop...
        result = Datum(self.head, Datum(lambda:add_explanation(self.modifiers)), self.bindings)
        if self.is_hashed():
            result._hash = self._hash

        return result

    #Manipulating modifiers-------------

    def modifier_map(self, f):
        """Return a copy of self in which all modifiers m have been replaced by f(m) if f(m) != None"""
        def g(m):
            n = f(m)
            return m if n is None else n
        return self.update(_modifiers=self.modifiers.list_map(g))

    def modifier_filter(self,f):
        """Return a copy of self in which all modifiers not satisfying f have been removed."""
        return self.update(_modifiers=self.modifiers.list_filter(f))

    def modifier_find(self,arg):
        f = arg
        if type(arg) is str:
            def f(x): return x.head == arg
        for m in self.modifiers.to_list():
            if f(m):
                return m
        return None

    #Hashing and equality-------------------------

    def __eq__(self,other):
        """
        Test if self and other have the same head and if all exposed bindings are equal.

        This is tested quickly using the invariant that hash(a) == hash(b) implies a==b.
        """
        return (self.head == other.head and hash(self) == hash(other))

    def __ne__(self,other):
        return not (self == other)

    def exposed_bindings(self):
        """
        Return the list of all exposed bindings. (see is_exposed)
        """

        for item in self.bindings.iteritems():
            if self.is_exposed(item):
                yield item

    def only_exposed(self):
        """
        Return a copy of self with all non-exposed information stripped out.
        
        This can be used as a cache key without preventing non-exposed properties from being
        garbage collected. This is often relevant because _modifier tends to be very big.
        """
        result = self.__class__(self.head,_bindings=dict(self.exposed_bindings()))
        if self.is_hashed():
            result._hash = self._hash
        return result


    def is_exposed(self, binding):
        """
        Return whether a (k,v) pair is an exposed binding

        An exposed binding is one that affects equality comparisons.
        This method provides the only definition of exposed bindings.
        """

        return binding[0][0] != '_'


    def __hash__(self):
        if not self.is_hashed():
            self.set_hash_recursive()
        return self._hash

    def is_hashed(self):
        """
        Test to see if self has already been hashed
        """
        return hasattr(self, "_hash")

    def set_hash(self):
        """
        Compute the hash of self, assuming all children have been hashed before.
        
        Stores the result as _hash so it can be looked up quickly.
        Sets Datum.hashes[_hash]=self, so that possible hash collisions can be detected.

        If there is a hash collision, _hash is incremented until there is no collision.
        """

        if self.is_hashed() and self._hash in self.hashes:
            return

        candidate_hash = hash((self.head, tuple(sorted(list(self.exposed_bindings())))))

        #we look for hash in Datum.hashes to see if there is a hash collision
        #if so we adjust the hash to maitain the invariant that if hash(a) == hash(b),
        #then a == b
        while candidate_hash in self.hashes:
            other = self.hashes[candidate_hash]
            are_equal = True
            if self.head != other.head:
                are_equal = False
            self_num_exposed = 0
            other_num_exposed = 0
            for k, v in self.exposed_bindings():
                self_num_exposed += 1
                if v != other.bindings.get(k,None):
                    are_equal = False
            for k, v in other.exposed_bindings():
                other_num_exposed += 1
            if self_num_exposed != other_num_exposed:
                are_equal = False
            if are_equal:
                break
            else:
            #in this case self and eq are not equal, so we increment the hash
                candidate_hash = candidate_hash + 1

        self._hash = candidate_hash
        self.hashes[self._hash] = self

    def set_hash_recursive(self):
        """
        Computes the hash of self, and all of its children.

        Uses a stack rather than recursion, in order to order to prevent a stack overflow
        when called on highly recursive objects.
        """
        if not hasattr(self,'hashes'):
            self.__class__.hashes = WeakValueDictionary()
        to_hash = [self]
        while to_hash:
            d = to_hash[-1]
            unhashed_children = False
            for k, v in d.exposed_bindings():
                if not v.is_hashed():
                    to_hash.append(v)
                    unhashed_children = True
            if not unhashed_children:
                d.set_hash()
                to_hash.pop()

    #Conversions and operations on special types---------------------

    #Strings and chars-----------------

    str_to_d = {}
    d_to_str = {}

    @classmethod
    def from_str(cls, s):
        if s not in cls.str_to_d:
            if type(s) != str:
                raise TypeError("Cannot convert non-string to a string Datum")
            result = cls(string_H,list=cls.from_list([cls.from_char(c) for c in s])).explain(
                    "translating a python string into a datum"
                )
            cls.str_to_d[s] = result
            cls.d_to_str[result] = s
        return cls.str_to_d[s]

    @classmethod
    def make_str(cls,l):
        return cls(string_H,list=l)

    def to_str(self):
        if self not in self.d_to_str:
            if self.head != string_H:
                raise ValueError("Cannot convert non-string Datum to string")
            self.d_to_str[self.only_exposed()] = ''.join([c.to_char() for c in self['list'].to_list()])
        return self.d_to_str[self]

    def str_concat(self,other):
        return Datum(string_H,list=self['list'].list_concat(other['list'])).explain(
                "concatenating [a] to [b]",
                a = self,
                b = other
            )

    char_to_d = {}
    d_to_char = {}

    @classmethod
    def from_char(cls, c):
        if c not in cls.char_to_d:
            if type(c) != str:
                raise TypeError("Cannot convert non-string to a character Datum")
            if len(c) != 1:
                raise ValueError("Cannot convert non-character to a character Datum")
            result = cls(char_H,x=cls.from_int(ord(c))).explain(
                    "translating a python character into a datum"
                )
            cls.char_to_d[c] = result
            cls.d_to_char[result] = c
        return cls.char_to_d[c]

    def to_char(self):
        if self not in self.d_to_char:
            if self.head != char_H:
                raise ValueError("Cannot convert non-char Datum to char")
            self.d_to_char[self.only_exposed()] = chr(self['x'].to_int())
        return self.d_to_char[self]

    #Booleans---------------------------

    bool_to_d = {}

    @classmethod
    def from_bool(cls,b):
        if b not in cls.bool_to_d:
            result = yes if b else no
            result = result.explain(
                    "translating a python boolean into a datum"
                )
            cls.bool_to_d[b] = result
        return cls.bool_to_d[b]

    def to_bool(self):
        if self == yes:
            return True
        elif self == no:
            return False
        else:
            raise ValueError("Cannot convert non-bool Datum to bool")

    __bool__ = to_bool
    __nonzero__ = __bool__

    #Integers---------------------------

    int_to_d = {}
    d_to_int = {}

    @classmethod
    def from_int(cls, k):
        if k not in cls.int_to_d:
            if type(k) != int:
                raise TypeError("Cannot convert non-integer to an integer Datum")
            result = None
            if k == 0:
                result = zero
            elif k < 0:
                result = cls(negative_H,x= cls.from_int(-k))
            elif k % 2 == 0:
                result = cls(even_H,x=cls.from_int(k/2))
            elif k % 2 == 1:
                result = cls(odd_H,x=cls.from_int(k/2))
            result = result.explain("translating a python integer into a datum")
            cls.int_to_d[k] = result
            cls.d_to_int[result] = k
        return cls.int_to_d[k]

    def to_int(self):
        if self not in self.d_to_int:
            result  = None 
            if self == zero:
                result = 0
            elif self.head == negative_H:
                result = -1* self['x'].to_int()
            elif self.head == even_H:
                result = 2*self['x'].to_int()
            elif self.head == odd_H:
                result = 2*self['x'].to_int() + 1
            else:
                raise ValueError("Cannot convert non-integer Datum to integer")
            self.d_to_int[self.only_exposed()] = result
        return self.d_to_int[self]

    #Lists------------------------------

    @classmethod
    def from_list(cls,xs):
        if type(xs) != list:
            raise TypeError("Cannot convert non-list to a list Datum")
        result = empty_list
        for x in reversed(xs):
            result = cls(list_H,head=x,tail=result)
        result = result.explain("translating a python list into a datum")
        return result

    @classmethod
    def make_list(cls,head,tail):
        return cls(list_H,head=head,tail=tail)

    def is_list(self):
        return (self.head == list_H and 'head' in self and 'tail' in self) or (self == empty_list)

    def to_list(self):
        d = self
        result = []
        while d != empty_list:
            if d.head != list_H:
                raise ValueError("Cannot convert non-list Datum to a list")
            result.append(d['head'])
            d = d['tail']
        return result

    def list_head(self):
        if not self.is_list():
            raise ValueError("Can't get head of a non-list")
        elif self == empty_list:
            raise ValueError("Can't get head of an empty list")
        return self['head']

    def list_tail(self):
        if not self.is_list():
            raise ValueError("Can't get tail of a non-list")
        elif self == empty_list:
            raise ValueError("Can't get tail of an empty list")
        return self['tail']


    def list_concat(self,other):
        result = None
        if self == empty_list:
            result = other
        elif self.is_list():
            result = self.update(tail=self['tail'].list_concat(other))
        else:
            raise ValueError("Can't concat to a non-list")
        return result.explain(
                "concatenating [a] to [b]",
                a = self,
                b = other
            )

    def list_map(self,f):
        if not self.is_list():
            raise ValueError("Can't map over a non-list")
        if self == empty_list:
            return self
        else:
            return self.update(head=f(self['head']),
                    tail=self['tail'].list_map(f))

    def list_filter(self,f):
        if not self.is_list():
            raise ValueError("Can't map over a non-list")
        if self == empty_list:
            return self
        else:
            tail = self['tail'].list_filter(f)
            if f(self['head']):
                return self.update(tail=tail)
            else:
                return tail


    #Dictionaries------------------------
            
    @classmethod
    def from_dict(cls,m):
        result = empty_dict
        if type(m) != dict:
            raise TypeError("Cannot convert non-dict to dict Datum")
        for k, v in m.iteritems():
            result = Datum(dict_H,key=k,value=v,other=result)
        result = result.explain("translating a python list into a datum")
        return result

    @classmethod
    def make_dict(cls,k,v,m):
        return cls(dict_H,key=k,value=v,other=m)

    def is_dict(self):
        return (self.head == dict_H) or (self == empty_dict)

    def to_dict(self):
        d = self
        result = {}
        while d != empty_dict:
            if d.head != dict_H:
                raise ValueError("Cannot convert non-dict Datum to a dict")
            result[d['key']] = d['value']
            d = d['other']
        return result

    def dict_key(self):
        if not self.is_dict():
            raise ValueError("Can't get key of a non-dict")
        elif self == empty_dict:
            raise ValueError("Can't get key of an empty dict")
        return self['key']

    def dict_value(self):
        if not self.is_dict():
            raise ValueError("Can't get value of a non-dict")
        elif self == empty_dict:
            raise ValueError("Can't get value of an empty dict")
        return self['value']

    def dict_other(self):
        if not self.is_dict():
            raise ValueError("Can't get other of a non-dict")
        elif self == empty_dict:
            raise ValueError("Can't get other of an empty dict")
        return self['other']

    def dict_update(self,other):
        if not self.is_dict() or not other.is_dict():
            raise ValueError("Can't do a dictionary update on a non-dict Datum")
        if other == empty_dict:
            return self
        else:
            return Datum.make_dict(other.dict_key(),other.dict_value(),self.dict_update(other.dict_other()))

    #Pair-------------------------------

    @classmethod
    def make_pair(cls,a,b):
        return cls(pair_H,a=a,b=b)

    @classmethod
    def from_pair(cls,pair):
        if type(pair) != tuple:
            return TypeError("Can't convert non-tuple to pair Datum")
        if len(pair) != 2:
            return ValueError("Can't convert non-pair tuple to pair Datum")
        return cls(pair_H,a=pair[0],b=pair_1)

    def to_pair(self):
        if self.head != pair_H:
            raise ValueError("Can't convert non-pair Datum to pair")
        return (self['a'],self['b'])

    #Lists and dicts of strings--------

    @classmethod
    def from_dict_of_str(cls,m):
        return cls.from_dict({cls.from_str(k):v for k,v in m.iteritems()})

    def to_dict_of_str(self):
        return {k.to_str():v for k,v in self.to_dict().iteritems()}

    @classmethod
    def from_list_of_str(cls,xs):
        return cls.from_list([cls.from_str(x) for x in xs])

    def to_list_of_str(self):
        return [x.to_str() for x in self.to_list()]


#Literal heads-----------

string_H = "a [list] of characters which should be interpreted as a string"
list_H = "a list with first element [head] and following elements [tail]"
dict_H = "a dictionary that maps [key] to [value] and maps other keys according to [other]"
pair_H = "a pair with first element [a] and second element [b]"
char_H = "the character with ASCII code [x]"

even_H = "two times [x]"
odd_H = "two times [x] plus one"
negative_H = "the additive inverse of [x]"
empty_H = "an empty list"

#Literals---------------

empty_list = Datum(empty_H)
empty_dict = Datum("a dictionary that doesn't map anything to anything")

yes = Datum("yes")
no = Datum("no")
zero = Datum("the number zero")
none = Datum("nothing")

#Heads for tracing------------

source_H = "was produced by performing [action] and previously satisfied [old_source]"

lookup_H = "looking up the referent of [key] in [datum]"
update_H = "updating [datum] with new bindings [bindings]"
