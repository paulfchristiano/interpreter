from ipdb import set_trace as debug
import term
from term import Term as T
from collections import defaultdict
from memoization import memoize
import inspect
from frozendict import frozendict

class SimpleDispatcher(object):

    def __init__(self, name, args, undispatched=0):
        self.name = name
        self.handlers = defaultdict(lambda : defaultdict(list))
        self.undispatched_args = undispatched
        self.dispatched_args = len(args) - undispatched
        self.args = args

    #FIXME the several calling modes here are a bit ridiculous,
    #I think that in the future they are pretty likely to be changed to something
    #that is very susceptible to bugs
    def __call__(self, name=None, extract_args=None, *args):
        if args or type(extract_args) is str:
            name = (name, extract_args) + args
            extract_args = None

        if type(name) in [tuple, list]:
            names = name
        else:
            names = (name,)

        names = tuple(name.head if hasattr(name, 'head') else name for name in names)

        if extract_args is None:
            extractions = tuple(name is not None for name in names)
        elif type(extract_args) is bool:
            extractions = (extract_args,)
        else:
            extractions = extract_args

        assert len(names) == len(extractions)
        gap = self.dispatched_args - len(names)
        names = names + (None,)*gap
        extractions = extractions + (False,)*gap
        filters = tuple(name is not None for name in names)
        assert all(f or not e for f, e in zip(filters, extractions))
        unextracted_args = self.dispatched_args - sum(extractions)

        def add_handler(f):
            arg_names = inspect.getargspec(f).args[self.undispatched_args+unextracted_args:] #+1 for the asker
            self.handlers[filters][names].append((f, arg_names, extractions))

            if sum(extractions) == 1:
                extracted = [name for name, extract in zip(names, extractions) if extract]
                return term.simple(extracted[0], *arg_names)
            else:
                def throw(*args, **kwargs):
                    raise Exception("Dispatcher(f) only returns a function if there "
                        "is exactly one extracted argument.")
                return throw

        return add_handler

    def null_mask(self):
        return (False,)*self.dispatched_args

    def dispatched(self, args):
        return args[self.undispatched_args:]

    def undispatched(self, args):
        return args[:self.undispatched_args]

    def apply_handler(self, f, args, arg_names, extractions):
        pre_args = self.undispatched(args)
        args = self.dispatched(args)
        f_kwargs = {}
        f_args = tuple([arg for arg, extract in zip(args, extractions) if not extract])
        for arg, extract in zip(args, extractions):
            if extract:
                for name in arg_names:
                    if name in arg:
                        f_kwargs[name] = arg[name]
        return f(*(pre_args + f_args), **f_kwargs)

    def apply_all_handlers(self, mask, args):
        handlers = self.handlers[mask]
        key = tuple(arg.head if show else None for arg, show in zip(self.dispatched(args), mask))
        for f, arg_names, extractions in handlers[key]:
            result = self.apply_handler(f, args, arg_names, extractions)
            if result is not None:
                return result
        return None

    def dispatch(self, *args):
        #FIXME awkward circular imports
        #askers only needs the simple dispatcher...
        assert len(args) == len(self.args)
        masks = list(reversed(sorted(self.handlers.iterkeys())))
        for mask in masks:
            result = self.apply_all_handlers(mask, args)
            if result is not None:
                return result
        return None

#a simple dispatcher with a single undispaotched argument, an asker used to process the query
#also adds explanations, under the assumption that most inputs and outputs are terms
class Dispatcher(SimpleDispatcher):

    def __init__(self, name, args):
        super(Dispatcher, self).__init__(name, ("asker",)+args, undispatched=1)

    def dispatch(self, *args):
        from askers import BaseAsker
        assert(isinstance(args[0], BaseAsker))
        result = super(Dispatcher, self).dispatch(*args)
        if result is not None:
            return result
        import convert
        asker = args[0]
        term_args = args[1:]
        new_args = tuple(convert.reduce(asker, arg)  for arg in term_args)
        return super(Dispatcher, self).dispatch(asker, *new_args)

    def apply_handler(self, f, args, arg_names, extractions):
        result = super(Dispatcher, self).apply_handler(f, args, arg_names, extractions)
        if result is not None and isinstance(result, T):
            result = result.set(result.value.explain(
                term.MetaTerm("invoking [f] with args [args]", f=f, args=args)
            ))
        return result

