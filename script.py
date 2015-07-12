from IPython.lib.deepreload import reload
excludes = [
 'ipdb',
 'os.path',
 'sys',
 'pytest',
 '__builtin__',
 '__main__',
 'pymongo',
 'bson',
 'bson.objectid',
 'IPython',
 'IPython.lib',
 'IPython.lib.deepreload'
]
deepreload = lambda x, reload=reload, excludes=excludes : reload(x , exclude=excludes)

import gc
gc.disable()

import ipdb
import ask
import fields
import root
import lists
import dictionaries
import ints
import convert
import representations
import properties
import updates
import outlines
import builtins
import computations
import term
import types
import state
import views
import functions
import strings
from term import Term as T

k = updates.update(updates.trivial(), T.from_int(0))
d = T('test [a]', a=k)
Q = T('a question about [this]', this=k)
asker = ask.Asker(Q)

a = T('a')
b = T('b')
c = T('c')

l1 = T.from_list([a, b, c])
l2 = T.from_list([a, a, a])

l12 = lists.zip(l1, l2)

d = dictionaries.from_items(l12)
