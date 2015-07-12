import askers
import term
from term import Term as T
import properties

class Counter(askers.BaseAsker):

    def __init__(self, *args, **kwargs):
        super(Counter, self).__init__(*args, **kwargs)
        self.cost = 1

    def reply(self, *args, **kwargs):
        result = super(Counter, self).reply(*args, **kwargs)
        return result.add(queries(T.from_int(self.cost)))

    def process_response(self, response, *args, **kwargs):
        if response.head == queries.head:
            #TODO could easily do this inside the system
            self.cost += response['k'].to_int()
            return properties.trivial()
        else:
            return super(Counter, self).process_response(response, *args, **kwargs)

queries = term.simple("[k] queries were posed while answering", 'k')
