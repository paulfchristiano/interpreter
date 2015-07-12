#FIXME it would be nice to eliminate the dependence on a third party package
from decorator import decorator
from frozendict import frozendict
import weakref

def memoized(function_to_be_memoized, *args,**kwargs):
    f = function_to_be_memoized
    cache = f.cache
    args = tuple(args)
    kwargs = frozendict(**kwargs)

    cache = f.cache
    key_args = args

    if len(args) > 0 and hasattr(args[0], '__dict__'):
        caller = args[0]
        try:
            if f.cache_name in caller.__dict__:
                caller_cache = getattr(caller, f.cache_name)
            else:
                caller_cache = f.cache_maker()
                setattr(caller, f.cache_name, caller_cache)
            cache = caller_cache
            key_args = args[1:]
        except AttributeError:
            pass

    key = (key_args, kwargs)
    if key in cache:
        return cache[key]
    else:
        result = f(*args,**kwargs)
        cache[key] = result
        return result

def memoize_weakness_type(t):

    def memoize(f):
        f.cache_maker = t
        f.cache = f.cache_maker()
        f.cache_name = "_{}:{}_cache".format(f.func_name, f.__module__)
        memoized_f = decorator(memoized, f)
        #these attributes just make it easier to inspect memoized functions
        memoized_f.cache = f.cache
        memoized_f.cache_name = f.cache_name
        return memoized_f

    return memoize


def memoize_constructor_weakness_type(t):

    class Memoizer(type):

        @memoize_weakness_type(t)
        def __call__(cls, *args,**kwargs):
            return super(Memoizer,cls).__call__(*args, **kwargs)

    def memoize_constructor(C):

        class Memoized(C):
            __metaclass__ = Memoizer
        Memoized.__name__ = "{}({})".format("Memoized", C.__name__)

        return Memoized

    return memoize_constructor

memoize = memoize_weakness_type(dict)
memoize_constructor = memoize_constructor_weakness_type(dict)

weak_memoize = memoize_weakness_type(weakref.WeakValueDictionary)
weak_memoize_constructor = memoize_constructor_weakness_type(weakref.WeakValueDictionary)
