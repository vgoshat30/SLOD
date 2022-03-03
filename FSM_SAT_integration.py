from pysat.solvers import Solver
import FSM
import SLOD


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
    # netlist, functions = FSM.analyze_fsm("./project2_cipher_v1.v", 
    #     "./NangateOpenCellLibrary_functional.lib")
    
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

        sym_cnf = SLOD.str2sym_cnf(cur_func_str)
        cnf_clauses, pin2sat_pool = SLOD.sym2sat(sym_cnf)
        
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