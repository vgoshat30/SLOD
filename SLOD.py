# Environment and HAL initialization
import sys, os

HAL_BASE = "/usr/local/"
os.environ["HAL_BASE_PATH"] = HAL_BASE
sys.path.append(HAL_BASE+"lib/")
import hal_py

from typing import Dict, List, Tuple, Union

from sympy import symbols
from sympy.logic.boolalg import to_cnf, And, Or, Not, BooleanTrue, BooleanFalse
from sympy.parsing.sympy_parser import parse_expr
from sympy.logic import simplify_logic

from pysat.formula import IDPool, CNF
from pysat.solvers import Solver

import hal_py
import FSM


def sym_cnf2clauses(expr) -> tuple:
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
    if len(clause.args) == 0:
        literals = [vars_pool.id(str(clause))]
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


def sym_cnf2sat(sym_func: Union[Not, And], 
                vars_pool: IDPool = None) -> Tuple[List[List[int]], IDPool]:
    if vars_pool is None:
        vars_pool = IDPool()
    func_clauses = []
    cur_cnf_clauses = sym_cnf2clauses(sym_func)
    for clause in cur_cnf_clauses:
        func_clauses.append(parse_clause(clause, vars_pool))
    return func_clauses, vars_pool


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
        return sym_functions[0], pin2net_dict
    else:
        return sym_functions, pin2net_dict


def get_args_dict_sym(literals_vec: List[int], vars_pool: IDPool, 
                        pin2net_dict: Dict[str, FSM.PosNegNet],
                        is_get_keys: bool) -> Dict[str, bool]:
    inputs_dict = {}
    for literal in literals_vec:
        arg_value = True
        if literal < 0:
            literal = -literal
            arg_value = False
        pin_name = vars_pool.obj(literal)
        if pin_name in pin2net_dict.keys() and \
            (is_get_keys == pin2net_dict[pin_name].is_key_net):
            inputs_dict[pin_name] = arg_value
    return inputs_dict


def decrypt(netlist: hal_py.Netlist, functions: List[hal_py.BooleanFunction],
        correct_key: Dict[str, bool]):

    # Vectors of sympy boolean expressions, each describing a state
    # (number of elements are the number of flip flops)
    # Those are Y1 and Y2 of the algorithm
    y1_symbols = []
    y2_symbols = []

    outputs1_sym = []
    outputs2_sym = []

    unlocked_cirquit = []

    # C1_sym and C2_sym will be updated with a sympy boolean CNF expressions 
    # describing the realtions C1(X, K1, Y1) and C1(X, K2, Y2) respectively.
    # All relations are logically ANDed between them, preserving th CNF
    # representation
    C1_sym = BooleanTrue()
    C2_sym = BooleanTrue()

    # Sympy boolean CNF expression which will hold the CNF representation
    # of y1 ^ y2 (where y1 and y2 are the resiters output vectors)
    y1_diff_y2_sym = BooleanFalse()

    pin2net_dict = {}

    for FF_ind, function in enumerate(functions):
        # String names of the output vecors of all the flip flops for
        # both variable options (1 and 2)
        y1_name = 'y{}_1'.format(FF_ind)
        y2_name = 'y{}_2'.format(FF_ind)

        y1_symbols.append(symbols(y1_name))
        y2_symbols.append(symbols(y2_name))

        cur_output1_sym, cur_pin2net1 = func2sym(netlist, function, 1)
        cur_output2_sym, cur_pin2net2 = func2sym(netlist, function, 2)

        unlocked_cirquit.append(cur_output1_sym.subs(correct_key))

        # pin2net_dict will be used to identificate key nets
        pin2net_dict.update(cur_pin2net1)
        pin2net_dict.update(cur_pin2net2)

        outputs1_sym.append(cur_output1_sym)
        outputs2_sym.append(cur_output2_sym)

        # XNOR is equivalent to ==
        # y1_symbols[-1] is the symbol of the output of the current FF
        C1_sym &= to_cnf(~(outputs1_sym[-1] ^ y1_symbols[-1]))
        C2_sym &= to_cnf(~(outputs2_sym[-1] ^ y2_symbols[-1]))

        # At least one bit of the output vector (state vector)
        # sould be diffetent between assignment options 1 and 2
        # XOR is equivalent to !=
        y1_diff_y2_sym |= y1_symbols[-1] ^ y2_symbols[-1]

    y1_diff_y2_sym = to_cnf(y1_diff_y2_sym)

    # Line 3 of the Logic Decryption Algorithm in the paper 
    F1_sym = C1_sym & C2_sym
    
    # CNF clauses of the function F1_y1_y2_sym, ready for SAT solver
    F1, vars_pool = sym_cnf2sat(F1_sym)
    y1_diff_y2, vars_pool = sym_cnf2sat(y1_diff_y2_sym, vars_pool)

    Fi = CNF(from_clauses=F1)
    
    with Solver(name='g4', with_proof=True) as s:
        s.append_formula(F1)
        s.append_formula(y1_diff_y2)

        while s.solve():
            SOL = s.get_model()

            Xd = get_args_dict_sym(SOL, vars_pool, pin2net_dict, is_get_keys=False)

            Yd = {}
            for FF_ind, cur_unlocked_func in enumerate(unlocked_cirquit):
                unlocked_output = cur_unlocked_func.subs(Xd)
                Yd[y1_symbols[FF_ind]] = unlocked_output
                Yd[y2_symbols[FF_ind]] = unlocked_output

            C1_d_sym = C1_sym.subs(Xd)
            C1_d_sym = C1_d_sym.subs(Yd)

            C2_d_sym = C2_sym.subs(Xd)
            C2_d_sym = C2_d_sym.subs(Yd)

            C1_d, _ = sym_cnf2sat(C1_d_sym, vars_pool)
            C2_d, _ = sym_cnf2sat(C2_d_sym, vars_pool)

            Fi.extend(C1_d)
            Fi.extend(C2_d)

            s.append_formula(C1_d)
            s.append_formula(C2_d)

    with Solver(name='g4', bootstrap_with=Fi.clauses, with_proof=True) as s:
        SAT = s.solve()
        SOL = s.get_model()
        Kc = get_args_dict_sym(SOL, vars_pool, pin2net_dict, is_get_keys=True)


        print('\n\nFunction test:\n\n\tFunc.:\n\n{}\n\n\tSAT:\t{}\n\tModel:\t{}'
            .format(F1_sym & y1_diff_y2_sym, SAT, SOL))
        print('\nid2obj:\t{}'.format(vars_pool.id2obj))
        print(Xd)
    


if __name__ == "__main__":

    IS_FIRST_NETLIST = 0

    if IS_FIRST_NETLIST:
        netlist, functions = FSM.analyze_fsm("./project2_cipher_v1.v", 
            "./NangateOpenCellLibrary_functional.lib")
        
        decrypt(netlist, functions, {'START_1': True})
    else:
        netlist, functions = FSM.analyze_fsm("./project2_cipher_v2_obfuscated.v", 
            "./NangateOpenCellLibrary_functional.lib")

        decrypt(netlist, functions, {'INPUT0_1': True,
                                     'INPUT1_1': False,
                                     'INPUT2_1': False,
                                     'INPUT3_1': False,
                                     'INPUT4_1': False,
                                     'INPUT5_1': True,
                                     'START_1': True})

    
