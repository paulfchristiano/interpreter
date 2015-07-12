import pymongo
import term
from term import Term
import representations
from representations import Representation
from bson.objectid import ObjectId
from memoization import memoize, memoize_constructor
from ipdb import set_trace as debug
from frozendict import frozendict
from stackless import stackless

#TODO this file does several different things, that could be reused seperately
#I should make it so the database can be used without the terms
#I should make it so that the terms can be used without the representations

class Termsbase(object):

    def __init__(self,db="tooldb",collection="terms"):
        if db is None:
            db = "tooldb"
        if collection is None:
            collection = "terms"
        self.db = db
        self.collection = collection
        self.client = pymongo.MongoClient()[self.db][self.collection] 

    #Basic operations-----------------------------

    def __repr__(self):
        return "Termsbase(db={},collection={})".format(self.db,self.collection)

    def __eq__(self,other):
        return self.db == other.db and self.collection == other.collection

    def __ne__(self,other):
        return not (self == other)


    #Convert between mongodb and python-----------

    def translate(self,json,to_python):
        """
        Convert all ids between TermId <---> ObjectId, and all strings from str <--->unicode.

        to_python=True [default]: ObjectId-->TermId, unicode-->str (for use in python)
        to_python=False: TermId-->ObjectId (for use in mongodb)
        """
        def t(x): return self.translate(x, to_python=to_python)

        if type(json) is dict:
            return {t(k):t(v) for k, v in json.iteritems()}

        elif type(json) is list:
            return tuple(t(x) for x in json)

        elif type(json) is tuple:
            return tuple(t(x) for x in json)

        elif type(json) is ObjectId and to_python:
            return TermId(json,self)

        elif hasattr(json,'objectid') and not to_python:
            if json.db != self:
                raise ValueError("Unwrapping an id for the wrong database")
            return json.objectid

        elif type(json) is unicode and to_python:
            return str(json)

        else:
            return json

    def to_python(self,json):
        return self.translate(json,to_python=True)

    def to_mongo(self,json):
        return self.translate(json,to_python=False)

    #Reading and writing-------------------------

    def write(self,json):
        json = self.to_mongo(json)
        id = json.get('_id',ObjectId())
        self.client.replace_one({'_id':id},json,upsert=True)
        return self.to_python(id)

    def stash_pointer(self, source):
        self.set_pointer(source, ())

    #FIXME this implementation of pointers is a holdover from an old version
    #I don't feel like this is at all the right way to handle things
    def set_pointer(self,source,target):
        self.write({'_id':source, 'pointer':target})

    def read(self,id):
        result = self.client.find_one({'_id':self.to_mongo(id)})
        if result is None:
            raise KeyError(id)
        return self.to_python(result)

def load_pointer(db, name):
    pointer = db.read(name)
    if len(pointer.get('pointer', ())) == 0:
        raise KeyError("did not find a pointer", name)
    return load(pointer['pointer'])

def save_as(db, pointer, term):
    handle = save(db, term)
    db.set_pointer(pointer, handle)


class TermId(object):
    def __init__(self, id, db):
        self.objectid = id
        self.db = db

    def __hash__(self):
        return hash(self.objectid)

    def __eq__(self,other):
        return self.objectid == other.objectid and self.db == other.db

    def __ne__(self,other):
        return not (self == other)

#TODO I think that I should split this into two files
#since the stuff below is likely to change and grow, and the stuff above
#is relatively likely to be reused in a different context.
#At the same time I should probably fix the stupid pointer behavior.

def load_first(f):

    def wrapped(self, *args, **kwargs):
        if not self.loaded: 
            self.load()
        return f(self, *args, **kwargs)

    return wrapped

def from_db():
    return term.MetaTerm(from_db.head)
from_db.head = "loading from the database"

class FromDB(object):

    def __init__(self, id):
        self.db_id = id
        self.db = id.db
        self.loaded = False

    @load_first
    def __hash__(self):
        return super(FromDB, self).__hash__()

    def load(self):
        if self.loaded:
            return
        else:
            record = self.db.read(self.db_id)
            self.construct_from_record(record)
            self.loaded = True

    def construct_from_record(self, record):
        self._hash = record['hash']

    @staticmethod
    def to_record(object, db):
        record = {}
        record['hash'] = hash(object)
        return record

class BaseTermFromDB(FromDB):

    @property
    @load_first
    def head(self):
        return super(FromDB, self).head

    @property
    @load_first
    def bindings(self):
        return super(FromDB, self).bindings

    @property
    @load_first
    def id(self):
        return self._id

    def construct_from_record(self, record):
        super(BaseTermFromDB, self).construct_from_record(record)
        self._id = record['id']

    @staticmethod
    def to_record(term, db):
        record = super(BaseTermFromDB, BaseTermFromDB).to_record(term, db)
        record['id'] = term.id
        return record

class TermFromDB(BaseTermFromDB, Term):

    def construct_from_record(self, record):
        super(TermFromDB, self).construct_from_record(record)
        #self._source = load(record['source'])
        self._source = term.MetaTerm("loading from database")
        self._head = record['head']
        self._bindings = load(record['bindings'])

    @staticmethod
    def to_record(term, db):
        record = super(TermFromDB, TermFromDB).to_record(term, db)
        record['head'] = term.head
        record['bindings'] = save(db, term.bindings)
        #record['source'] = save(db, term.source)
        return record

class RepresentationFromDB(BaseTermFromDB, Representation):

    def construct_from_record(self, record):
        super(RepresentationFromDB, self).construct_from_record(record)
        self._head = representations.head
        self.represents = load(record['represents'])

    @staticmethod
    def to_record(term, db):
        record = super(RepresentationFromDB, RepresentationFromDB).to_record(term, db)
        record['represents'] = save(db, term.represents)
        return record

#FIXME this makes it clear how much duplicated effort there is between MetaTerms and Terms

class MetaTermFromDB(FromDB, term.MetaTerm):

    def construct_from_record(self, record):
        super(MetaTermFromDB, self).construct_from_record(record)
        self._head = record['head']
        self._bindings = load(record['bindings'])

    @staticmethod
    def to_record(meta, db):
        record = super(MetaTermFromDB, MetaTermFromDB).to_record(meta, db)
        record['head'] = meta.head
        record['bindings'] = save(db, meta.bindings)
        return record

    @property
    @load_first
    def head(self):
        return self._head

    @property
    @load_first
    def bindings(self):
        return self._bindings



def literal_from_id(id):
    return id
literal_from_id.to_record = lambda x, db : x

def frozendict_from_id(id):
    record = id.db.read(id)
    return frozendict((load(k), load(v)) for k, v in record['values'])
def frozendict_to_record(x, db):
    saved_dict = [(save(db, k), save(db, v)) for k, v in x.iteritems()]
    return {'values': saved_dict}
frozendict_from_id.to_record = frozendict_to_record

def tuple_from_id(id):
    record = id.db.read(id)
    return tuple(load(x) for x in record['values'])
def tuple_to_record(xs, db):
    saved_tuple = tuple(save(db, x) for x in xs)
    return {'values':saved_tuple}
tuple_from_id.to_record = tuple_to_record


representation_k = 'representation'
term_k = 'term'
literal_k = 'literal'
dict_k = 'dict'
tuple_k = 'tuple'
meta_k = 'metaterm'

constructors = {
        representation_k: RepresentationFromDB,
        term_k: TermFromDB,
        meta_k: MetaTermFromDB,
        literal_k: literal_from_id,
        dict_k: frozendict_from_id,
        tuple_k: tuple_from_id
}

kinds = [
    (Representation, representation_k),
    (Term, term_k),
    (term.MetaTerm, meta_k),
    (tuple, tuple_k),
    (dict, dict_k),
    (str, literal_k),
    (int, literal_k),
    (bool, literal_k)
]


@memoize
@stackless
def load(handle):
    kind, id = handle
    if kind == literal_k:
        return id
    else:
        constructor = constructors[kind]
        return constructor(id)

@memoize
@stackless
def save(db, x):
    kind = None
    for t, k in kinds:
        if isinstance(x, t):
            kind = k
            break
    if kind is None:
        raise ValueError("Can't save to DB")
    elif kind == literal_k:
        return (kind, x)
    else:
        constructor = constructors[kind]
        record = constructor.to_record(x, db)
        id = db.write(record)
        return (kind, id)
