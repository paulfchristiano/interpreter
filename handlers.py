import computations
#FIXME circular import, this file was always kind of awkward anyway
import views
from term import Term as T
import representations
import askers

question_var = T("a variable referring to a representation of the question currently being answered")

def simple_handler():
    return computations.quote_representation(T("was not answered"))

def view_handler():
    return computations.make_literal_term(askers.answer_is(
                computations.askQ_literal(views.predict_output(
                    computations.askQ_literal(views.get_starting_view(
                        computations.getvar(computations.quote(question_var))
                    ))
                ))
            ))
