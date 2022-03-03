# Environment and HAL initialization
import sys, os
HAL_BASE = "/usr/local/"
os.environ["HAL_BASE_PATH"] = HAL_BASE
sys.path.append(HAL_BASE+"lib/")
import hal_py

from typing import List, Tuple, Union
from sympy.logic.boolalg import to_cnf, And, Or, Not
from pysat.formula import CNF, IDPool
from sympy.parsing.sympy_parser import parse_expr
from sympy.logic import simplify_logic
import hal_py
import FSM


def sympy2cnf(expr) -> tuple:
    if not isinstance(expr, And):
        return expr,
    return expr.args


def sympy2dnf(expr) -> tuple:
    if not isinstance(expr, Or):
        return expr,
    return expr.args


def parse_clause(clause: Union[Not, Or], vars_pool: IDPool) -> List[int]:
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
    return literals


def str2sym_cnf(function_str: str) -> Union[Not, And]:
    sympy_expr = parse_expr(function_str)
    sympy_expr_cnf = simplify_logic(to_cnf(sympy_expr))
    return sympy_expr_cnf


def sym2sat(sym_functions: Union[List[Union[Not, And]], Union[Not, And]]) -> Tuple[List[List[int]], IDPool]:
    vars_pool = IDPool(start_from=1)
    all_func_clauses_list = []
    if type(sym_functions) is not list:
        sym_functions_for_iter = [sym_functions]
    else:
        sym_functions_for_iter = sym_functions
    for sym_func in sym_functions_for_iter:
        cur_func_clauses = []
        cur_cnf_clauses = sympy2cnf(sym_func)
        for clause in cur_cnf_clauses:
            cur_func_clauses.append(parse_clause(clause, vars_pool))
        all_func_clauses_list.append(cur_func_clauses)
    if type(sym_functions) is list:
        return all_func_clauses_list, vars_pool
    else:
        return all_func_clauses_list[0], vars_pool


def func2sym_cnf(netlist: hal_py.Netlist, functions: List[hal_py.BooleanFunction],
                 group_num: int) -> List[Union[Not, And]]:
    sym_functions = []
    for func in functions:
        func_str, pin2net_dict = FSM.get_function_str(netlist, func, group_num)
        sym_cnf = str2sym_cnf(func_str)
        sym_functions.append(sym_cnf)
    return sym_functions


def decrypt(netlist: hal_py.Netlist, functions: List[hal_py.BooleanFunction]):
    sym_cnf_functions = func2sym_cnf(netlist, functions, 2)

    # TODO: Create sympy variables for the output vector y.
    # One output for each of the three functions and two variations
    # (the Y1 and Y2 in the paper alorithm). Should be:
    # y1_1, y2_1, y3_1
    # y1_2, y2_2, y3_2
    # Use sympy xor to add the constraint y1 ~= y2 <=> y1 ^ y2

    cnf_clauses, vars_pool = sym2sat(sym_cnf_functions)
    print(cnf_clauses)


if __name__ == "__main__":

    netlist, functions = FSM.analyze_fsm("./project2_cipher_v1.v", 
        "./NangateOpenCellLibrary_functional.lib")
    
    # netlist, functions = FSM.analyze_fsm("./project2_cipher_v2_obfuscated.v", 
    #     "./NangateOpenCellLibrary_functional.lib")

    decrypt(netlist, functions)
