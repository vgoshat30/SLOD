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
    vars_pool = IDPool(start_from=1)
    cnf_object = CNF()

    sympy_expr = parse_expr(function_str)
    sympy_expr_cnf = simplify_logic(to_cnf(sympy_expr))
    all_clauses = sympy2cnf(sympy_expr_cnf)
    for clause in all_clauses:
        literals = []
        # If the clause is atom (only one variable, for example, ~Q618)
        if len(clause.args) == 1:
            literals = [-vars_pool.id(str(clause.args[0]))]
        else:
            for variable in clause.args:
                if isinstance(variable, Not):
                    variable = ~variable
                    cur_literal = -vars_pool.id(str(variable))
                else:
                    cur_literal = vars_pool.id(str(variable))
                literals.append(cur_literal)
        cnf_object.append(literals)
    return cnf_object.clauses, vars_pool


def sat2pin(literals_vector, vars_pool):
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
            pin_name = vars_pool.obj(-literal)
            pos_net = pins2net_dict[pin_name].pos
            neg_net = pins2net_dict[pin_name].neg
            if pos_net is not None:
                args_dict[pos_net] = FSM.ZERO
            if neg_net is not None:
                args_dict[neg_net] = FSM.ONE
        else:
            pin_name = vars_pool.obj(literal)
            pos_net = pins2net_dict[pin_name].pos
            neg_net = pins2net_dict[pin_name].neg
            if pos_net is not None:
                args_dict[pos_net] = FSM.ONE
            if neg_net is not None:
                args_dict[neg_net] = FSM.ZERO
    return args_dict


if __name__ == "__main__":
    netlist, functions = FSM.analyze_fsm("./project2_cipher_v1.v", 
        "./NangateOpenCellLibrary_functional.lib")
    
    netlist, functions = FSM.analyze_fsm("./project2_cipher_v2_obfuscated.v", 
        "./NangateOpenCellLibrary_functional.lib")

    for cur_func_ind, cur_func in enumerate(functions):
        solution = None
        solution_str = None
        solution_hal_args = None
        sulution_eval = None

        s = Solver(name='g4', with_proof=True)

        # Conversion to function string with pin names (and not net IDs)
        # as arguments is required so SymPy can parse them as expression
        # variables and not as constants (net IDs are integers)
        cur_func_str, pin2net_dict = FSM.get_function_str(netlist, cur_func)

        cnf_clauses, pin2sat_pool = get_cnf_clauses(cur_func_str)
        s.append_formula(cnf_clauses)
        is_sat = s.solve()
        if is_sat:
            solution = s.get_model()
            solution_str = sat2pin(solution, pin2sat_pool)
            solution_hal_args = literals2args(solution, pin2sat_pool, pin2net_dict)
            sulution_eval = cur_func.evaluate(solution_hal_args)
        
        print("\n\nFunction {}:\n\n\tNets repr.:\t{}\n\tPins repr.:\t{}\n\t"
        "SatVars-Pin:\t{}\n\tClauses:\t{}\n\tIs Satisfiable:\t{}\n\tSolution:\t{}\n\t\t\t{}\n\t"
        "Evaluation:\t{}"
            .format(cur_func_ind, cur_func, cur_func_str, pin2sat_pool.id2obj,
                    cnf_clauses, is_sat, solution, solution_hal_args, sulution_eval))
        print()
        s.delete()