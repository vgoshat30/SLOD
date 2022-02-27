from curses.ascii import FS
from sympy import to_dnf
from sympy.logic.boolalg import to_cnf, And, Or, Not
from sympy.logic import simplify_logic
from sympy.parsing.sympy_parser import parse_expr
from pysat.formula import CNF, IDPool
from pysat.solvers import Solver
from ArgsPool import ZERO

import FSM


def sympy2cnf(expr) -> tuple:
    if not isinstance(expr, And):
        return expr,
    return expr.args


def sympy2dnf(expr) -> tuple:
    if not isinstance(expr, Or):
        return expr,
    return expr.args


def get_cnf_clauses(function_str):
    vpool = IDPool(start_from=1)
    cnf_object = CNF()

    sympy_expr = parse_expr(function_str)
    sympy_expr_cnf = simplify_logic(to_cnf(sympy_expr))
    all_clauses = sympy2cnf(sympy_expr_cnf)
    for clause in all_clauses:
        literals = []
        for variable in clause.args:
            if isinstance(variable, Not):
                variable = ~variable
                cur_literal = -vpool.id(str(variable))
            else:
                cur_literal = vpool.id(str(variable))
            literals.append(cur_literal)
        cnf_object.append(literals)
    return cnf_object.clauses, vpool


def literals2pins(literals_vector, vars_pool):
    str_vector = []
    for literal in literals_vector:
        sign_str = ''
        if literal < 0:
            literal = -literal
            sign_str = '~'
        str_vector.append(sign_str + vars_pool.obj(literal))
    return str_vector

def literals2args(literals_vector, vars_pool, pins2net_dict):
    args_dict = {}
    for literal in literals_vector:
        if literal < 0:
            literal = -literal
            args_dict[pins2net_dict[vars_pool.obj(literal)]] = FSM.ZERO
        else:
            args_dict[pins2net_dict[vars_pool.obj(literal)]] = FSM.ONE
    return args_dict


if __name__ == "__main__":
    # TODO: Return functions as functions and not as strings and use the
    # FSM.get_function_str function here.
    # Use the functions to evalueate the state vector
    function_strings, pins2net_dicts = FSM.analyze_fsm("./project2_cipher_v1.v",
                                        "./NangateOpenCellLibrary_functional.lib")
    
    # function_strings = FSM.analyze_fsm("./project2_cipher_v2_obfuscated.v",
    #                                     "./NangateOpenCellLibrary_functional.lib")

    # TODO: Use dictionary of arguments nets and names from ArgsPool
    # object in FSM.analyze_fsm to convers a possible solution of the
    # SAT solver to function arguments assignment to allow evaluation
    # and checking whether the SAT solver is right.
    # Conisider extending ArgsPool class

    for func_ind, cur_func in enumerate(function_strings):
        s = Solver(name='g4', with_proof=True)
        clauses, vpool = get_cnf_clauses(cur_func)
        s.append_formula(clauses)
        is_sat = s.solve()
        solution = s.get_model()
        solution_str = literals2pins(solution, vpool)
        print("\nFunction {}:\n\t{}\n\tClauses:\t{}\n\tIs Satisfiable:\t{}\n\tSolution:\t{}"
            .format(func_ind, cur_func, clauses, is_sat, solution_str))
        print(literals2args(solution, vpool, pins2net_dicts[func_ind]))
        s.delete()