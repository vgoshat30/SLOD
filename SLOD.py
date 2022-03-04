# Environment and HAL initialization
import sys, os

HAL_BASE = "/usr/local/"
os.environ["HAL_BASE_PATH"] = HAL_BASE
sys.path.append(HAL_BASE+"lib/")
import hal_py

from typing import List, Tuple, Union

from sympy import symbols
from sympy.logic.boolalg import to_cnf, And, Or, Not, BooleanTrue
from sympy.parsing.sympy_parser import parse_expr
from sympy.logic import simplify_logic

from pysat.formula import IDPool
from pysat.solvers import Solver

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


def sym_cnf2sat(sym_functions: Union[List[Union[Not, And]], Union[Not, And]], 
                vars_pool: IDPool = None) -> Tuple[List[List[int]], IDPool]:
    if vars_pool is None:
        vars_pool = IDPool()
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


def func2sym(netlist: hal_py.Netlist, functions: List[hal_py.BooleanFunction],
                 group_num: int) -> List[Union[Not, And]]:
    sym_functions = []
    if type(functions) is not list:
        function_for_iter = [functions]
    else:
        function_for_iter = functions
    for func in function_for_iter:
        func_str, pin2net_dict = FSM.get_function_str(netlist, func, group_num)
        sym_func = parse_expr(func_str)
        sym_functions.append(sym_func)
    if type(functions) is not list:
        return sym_functions[0]
    else:
        return sym_functions


def decrypt(netlist: hal_py.Netlist, functions: List[hal_py.BooleanFunction]):
    

    # TODO: Create sympy variables for the output vector y.
    # One output for each of the three functions and two variations
    # (the Y1 and Y2 in the paper alorithm). Should be:
    # y1_1, y2_1, y3_1
    # y1_2, y2_2, y3_2
    # Use sympy xor to add the constraint y1 ~= y2 <=> y1 ^ y2


    # cnf_clauses, vars_pool = sym_cnf2sat(sym_functions)


    y1_symbols = []
    y2_symbols = []

    C1_sym = BooleanTrue()
    C2_sym = BooleanTrue()
    y1_XOR_y2_sym = BooleanTrue()
    for register_num, function in enumerate(functions):
        out1_name = 'y{}_1'.format(register_num)
        out2_name = 'y{}_2'.format(register_num)

        y1_symbols.append(symbols(out1_name))
        y2_symbols.append(symbols(out2_name))

        function1_sym = func2sym(netlist, function, 1)
        function2_sym = func2sym(netlist, function, 2)

        # XNOR is equivalent to ==
        C1_sym &= to_cnf(~(function1_sym ^ y1_symbols[-1]))
        C2_sym &= to_cnf(~(function2_sym ^ y2_symbols[-1]))

        # XOR is equivalent to !=
        y1_XOR_y2_sym &= to_cnf(y1_symbols[-1] ^ y2_symbols[-1])
    
    F1_sym = C1_sym & C2_sym

    F1_y1_XOR_y2_sym = F1_sym & y1_XOR_y2_sym
    F1_y1_XOR_y2_sat, vars_pool = sym_cnf2sat(y1_XOR_y2_sym)
    
    s = Solver(name='g4', with_proof=True)
    
    s.append_formula(F1_y1_XOR_y2_sat)
    is_sat = s.solve()
    solution = s.get_model()
    print(is_sat)
    print(solution)
    print(1)


if __name__ == "__main__":

    # netlist, functions = FSM.analyze_fsm("./project2_cipher_v1.v", 
    #     "./NangateOpenCellLibrary_functional.lib")
    
    netlist, functions = FSM.analyze_fsm("./project2_cipher_v2_obfuscated.v", 
        "./NangateOpenCellLibrary_functional.lib")

    decrypt(netlist, functions)
