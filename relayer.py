import term
from term import Term as T
import askers
import properties
import dispatch
from dispatch import Dispatcher
from ipdb import set_trace as debug

class Relayer(askers.BaseAsker):

    def __init__(self, *args, **kwargs):
        super(Relayer, self).__init__(*args, **kwargs)
        self.to_relay = properties.trivial()

    def relay(self, m):
        self.to_relay = properties.both(m, self.to_relay)

    def reply(self, *args, **kwargs):
        reply = super(Relayer, self).reply(*args, **kwargs)
        return reply.add(self.to_relay)

    def pass_through(self, *heads):
        handler = dispatch.SimpleDispatcher("unnamed handler", ("property",))
        for head in heads:
            @handler(head, False)
            def relay(property):
                self.relay(property)
                return properties.trivial()
        return handler
