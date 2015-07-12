class frozendict(dict):

    def __repr__(self):
        return "frozen({})".format(super(frozendict, self).__repr__())

    def __hash__(self):
        return self._hash

    #FIXME I compute the hash here so that I throw an error if there are unhashable types
    #it would be a bit faster to compute when needed
    #almost all frozendicts get hashed immediately though, so it's not a big deal
    def __init__(self, *args, **kwargs):
        super(frozendict, self).__init__(*args, **kwargs)
        self._hash = hash(frozenset(self.iteritems()))

    #Credit: Oren Tirosh, http://code.activestate.com/recipes/414283/
    @property
    def _blocked_attribute(obj):
        raise AttributeError, "A frozendict cannot be modified."

    __delitem__ = __setitem__ = clear = _blocked_attribute
    pop = popitem = setdefault = update = _blocked_attribute
