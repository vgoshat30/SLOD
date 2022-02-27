from sympy import to_dnf
from sympy.logic.boolalg import to_cnf, And, Or, Not
from sympy.logic import simplify_logic
from sympy.parsing.sympy_parser import parse_expr
from pysat.formula import CNF, IDPool
from pysat.solvers import Solver


def get_cnf_clauses(expr) -> tuple:
    if not isinstance(expr, And):
        return expr,
    return expr.args


def get_dnf_clauses(expr) -> tuple:
    if not isinstance(expr, Or):
        return expr,
    return expr.args


vpool = IDPool(start_from=1)
cnf = CNF()

expr = parse_expr('~(~(~Q_620 & Q_619 & ~Q_618) & (~Q_618 | Q_619))')
cnf_expr = simplify_logic(to_cnf(expr))
print(cnf_expr)
all_clauses = get_cnf_clauses(cnf_expr)
for clause in all_clauses:
    literals = []
    for variable in clause.args:
        if isinstance(variable, Not):
            variable = ~variable
            cur_literal = -vpool.id(variable)
        else:
            cur_literal = vpool.id(variable)
        literals.append(cur_literal)
    cnf.append(literals)
    print(clause)
print(cnf.clauses)


s = Solver(name='g4', with_proof=True)
s.append_formula(cnf.clauses)
print(s.solve())
print(s.get_model())
s.delete()