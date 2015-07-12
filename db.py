import pymongo
from datum import Datum as D
from bson.objectid import ObjectId
import weakref

class Database(object):
    """
    Represents a connection to a mongodb instance.

    Stores the pymongo client, as well as a cache of all of the data
    that has been written or read to the database.
    Has methods for reading and writing data.

    The implementation is straightforward because data are immutable.
    """

    def __init__(self,db="tooldb",collection="data"):
        self.db = db
        self.collection = collection
        self.client = pymongo.MongoClient()[self.db][self.collection] 

        self.cache = weakref.WeakKeyDictionary()
        """
        cache stores each datum that has been loaded, so that repeat requests can be answered quickly

        Without the cache, the entire hierarchy corresponding to a datum would need to be reloaded.
        The cache uses weak references so that once an id isn't being used, the associated data can be freed.
        """

    #Basic operations-----------------------------

    def __repr__(self):
        return "Database(db={},collection={})".format(self.db,self.collection)

    def __eq__(self,other):
        return self.db == other.db and self.collection == other.collection

    def __ne__(self,other):
        return not (self == other)


    #Convert between mongodb and python-----------

    def translate(self,json,to_python=True):
        """
        Convert all ids between DatumId <---> ObjectId, and all strings from str <--->unicode.

        to_python=True [default]: ObjectId-->DatumId, unicode-->str (for use in python)
        to_python=False: DatumId-->ObjectId (for use in mongodb)
        """
        def t(x): return self.translate(x, to_python=to_python)

        if type(json) is dict:
            return {t(k):t(v) for k, v in json.iteritems()}

        elif type(json) is list:
            return [t(x) for x in json]

        elif type(json) is ObjectId and to_python:
            return DatumId(json,self)

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

    def read(self,id):

        result = self.client.find_one({'_id':self.to_mongo(id)})

        if result is None:
            raise KeyError(id)
        else:
            return self.to_python(result)

    #Saving and loading---------------------------

    def make_id(self,id=None):
        """
        Return an id suitable for reading or writing to this database.
        """
        return DatumId(objectid,self) if id is None else DatumId(id,self)

    def get_id(self,datum):
        for id in datum.ids:
            if id.db == self:
                return id 
        return None

    def is_saved(self,d):
        return d.is_held() or self.get_id(d) is not None

    def save(self,d):
        """
        Save d and all of its explicit descendants to the database and return the _id of d.

        Replaces d with a lambda expression that loads d from the database.
        """
        to_save = [d]
        last_id = None

        if d.is_held():
            return None

        while to_save:
            d = to_save[-1]
            unsaved = [v for v in d.bindings.values() if not self.is_saved(v)]
            if unsaved:
                to_save.extend(unsaved)
            else:
                to_save.pop()
                last_id = self.save_helper(d)

        return last_id

    def save_helper(self,datum):
        """Saves datum assuming that all of its children are already saved."""

        if datum.is_held():
            return
        saved_bindings = {k:self.get_id(v) for k, v in datum.bindings.iteritems()}
        json = {'head':datum.head, 'bindings':saved_bindings, 'ids':datum.ids}
        new_id = self.write(json)
        self.cache[new_id] = datum
        datum.ids.append(new_id)
        return new_id

    def load(self, id):
        """Load the datum with identifier id."""

        if id is None:
            return D("a replacement for a datum which could not be loaded")
        if id not in self.cache:
            json = self.read(id)
            if 'pointer' in json:
                return self.load(json['pointer'])
            else:
                result = D(json['head'],_bindings=self.to_load_all(json['bindings']))
                result.ids = json['ids']
                result.ids.append(id)
                self.cache[id] = result
        return self.cache[id]

    def to_load(self,id):
        return D(lambda : self.load(id))

    def to_load_all(self,bindings):
        return {k:self.to_load(v) for k,v in bindings.items()}

    def set_pointer(self,source,target):
        old_values = []
        try:
            old_data = self.read(source)
            old_values = old_data['old_values']
            old_values.append(old_data['pointer'])
        except KeyError:
            pass
        self.write({'_id':source, 'pointer':target, 'old_values':old_values})

    def save_as(self,datum,id):
        target = self.save(datum)
        self.set_pointer(id,target)

class DatumId(object):
    """
    A wrapper for pymongo _id's (which are either strings or ObjectID's).
    It allows these _id's to be weakly referenced,
    and tracks what database the id is valid in.
    """

    def __init__(self,id, db):
        self.objectid = id
        self.db = db

    def __hash__(self):
        return hash(self.objectid)

    def __eq__(self,other):
        return self.objectid == other.objectid and self.db == other.db

    def __ne__(self,other):
        return not (self == other)


