# Environment and HAL initialization
from operator import is_
import sys, os
from xmlrpc.client import boolean

from click import password_option
HAL_BASE = "/usr/local/"
os.environ["HAL_BASE_PATH"] = HAL_BASE
sys.path.append(HAL_BASE+"lib/")
import hal_py
hal_py.plugin_manager.load_all_plugins()
from hal_plugins import graph_algorithm
from ArgsPool import ArgsPool
from typing import Dict, List, Union, Tuple
import re


ZERO = hal_py.BooleanFunction.Value.ZERO
ONE =  hal_py.BooleanFunction.Value.ONE
HAL_NOT_CHAR = '!'
SYMPY_NOT_CHAR = '~'


class PosNegNet():
    def __init__(self, net: Union[hal_py.Net, str], is_negative: boolean) -> None:
        if is_negative:
            self.pos = None
            self.neg = str(net)
        else:
            self.pos = str(net)
            self.neg = None

    def add_net(self, net: hal_py.Net, is_negative: boolean):
        if is_negative:
            self.neg = str(net)
        else:
            self.pos = str(net)

    def __str__(self) -> str:
        return "PosNet - {}, NegNet - {}".format(self.pos, self.neg)


def clear_all(netlist: hal_py.Netlist):
    """Deleting all existing modules and groupings

    Args:
        netlist (hal_py.Netlist): The netlist to clear
    """

    for m in netlist.get_modules(): netlist.delete_module(m)
    for g in netlist.get_groupings(): netlist.delete_grouping(g)
    

def create_grouping(netlist: hal_py.Netlist, gates: List[hal_py.Gate], name: str):
    """
    Create a grouping in a given netlist from the given ga

    Args:
        netlist (hal_py.Netlist): The netlist in which to create the grouping
        gates (List[hal_py.Gate]): The gates to include in the grouping
        name (str): The name of the grouping
    """

    grp = netlist.create_grouping(name)
    for gate in gates: grp.assign_gate(gate)


def highlight_ffs(netlist: hal_py.Netlist):
    """
    Create a grouping of all the FFs in the netlist, which highlights
    them in the hal GUI

    Args:
        netlist (hal_py.Netlist): The netlist in which to highlight the FFs
    """

    all_ffs = get_ffs(netlist)
    create_grouping(netlist, all_ffs, "FFs")


def get_ffs(netlist_or_module: Union[hal_py.Netlist, hal_py.Module]) -> List[hal_py.Gate]:
    """
    Get list of the flip flops (gates containing 'FF' in the name) in a netlist or a module

    Args:
        netlist_or_module (Union[hal_py.Netlist, hal_py.Module]): Netlist or module

    Returns:
        List[hal_py.Gate]: All the flip flops
    """

    return netlist_or_module.get_gates(lambda g : "FF" in g.get_type().get_name())
 
   
def get_not_ffs(netlist_or_module: Union[hal_py.Netlist, hal_py.Module]) -> List[hal_py.Gate]:
    """
    Oposite of the function get_ffs

    Args:
        netlist_or_module (Union[hal_py.Netlist, hal_py.Module]): Netlist or module

    Returns:
        List[hal_py.Gate]: All the gates that ARE NOT flip flops
    """

    return netlist_or_module.get_gates(lambda g : "FF" not in g.get_type().get_name())


def get_ffs_num(gates: List[hal_py.Gate]) -> int:
    """
    Count number of FFs in a given list of gates

    Args:
        gates (List[hal_py.Gate]): Gate to count FFs in

    Returns:
        int: Number of FFs
    """

    ff_num = 0
    for g in gates:
        if 'FF' in g.get_type().get_name():
            ff_num += 1
    return ff_num


def get_fsm_candidates(netlist: hal_py.Netlist) -> List[List[hal_py.Gate]]:
    """
    Find all subgraphs made of strongly connected components that are bigger
    that one node

    Args:
        netlist (hal_py.Netlist): The netlist in which to search for the FSM

    Returns:
        List[List[hal_py.Gate]]: List of strongly connected components
    """

    graph_algorithms = hal_py.plugin_manager.get_plugin_instance("graph_algorithm")

    # Getting all strongly connected components
    scc = graph_algorithms.get_strongly_connected_components(netlist)
    
    # Ignore single nodes
    candidates = []
    for c in scc:
        if len(c) > 1:
            candidates.append(c)

    return candidates


def select_fsm(candidates: List[List[hal_py.Gate]]) -> List[hal_py.Gate]:
    """
    Find the strongly connected sub-graph with the smalles amount of nodes.
    This is assumed to be the control path state machine

    Args:
        candidates (List[List[hal_py.Gate]]): All the candidate to the smallest SCC sub-graph

    Returns:
        List[hal_py.Gate]: The control path FSM
    """

    selected_index = 0
    min_ffs_num = get_ffs_num(candidates[selected_index])
    for ind, c in enumerate(candidates):
        cur_ffs_num = get_ffs_num(c)
        if cur_ffs_num < min_ffs_num:
            min_ffs_num = cur_ffs_num
            selected_index = ind 
    return candidates[selected_index]
    
    
def dfs_from_net(net: hal_py.Net) -> List[hal_py.Gate]:
    """
    Backtrace from a FFs input net to global input. Return all gates inbetween.
    This function is given in the hal_sample_script.py in the assignment

    Args:
        net (hal_py.Net): The net connected to the FF input

    Returns:
        List[hal_py.Gate]: All the gates between a global input or a FFs output
            to the given net
    """

    gate_list = []
    stack = [net]
    while(stack):
        n = stack.pop()
        for endpoint in n.get_sources():
            gate = endpoint.get_gate()
            if gate not in gate_list:
                gate_list.append(gate)
                for net in gate.get_fan_in_nets():
                    if not net.is_global_input_net():
                        stack.append(net)
    return gate_list


def get_ff_input_func(netlist: hal_py.Netlist, flipflop: hal_py.Gate) -> hal_py.BooleanFunction:
    """
    Get boolean function of the input to a given FF

    Args:
        netlist (hal_py.Netlist): The netlist in which the flip flops are
        flipflop (hal_py.Gate): The FF which input function to calculate

    Returns:
        hal_py.BooleanFunction: The input function
    """ 

    fanin_net = flipflop.get_fan_in_net('D')
    gates = dfs_from_net(fanin_net)
    all_ffs = get_ffs(netlist)
    for ff in all_ffs:
            if ff in gates: gates.remove(ff)
    func = hal_py.NetlistUtils.get_subgraph_function(fanin_net, gates)
    return func


def get_function_str(netlist: hal_py.Netlist, function: hal_py.BooleanFunction) \
    -> Tuple[str, Dict[str, str]]:
    """Get a string describing a given boolean function with gate names and pin names
    instead of net IDs. Also get a dictionary that translates from the pin names to net IDs.
    For example, pin Q of gate _771_ will be 'Q_771'.
    Global input nets are treated as nets of gate _Global_ with the net name as the pin name.
    For example, global input INPUT(0) will be 'INPUT0'

    Args:
        netlist (hal_py.Netlist): The netlist in which the function is defined
        function (hal_py.BooleanFunction): The funciton to print

    Returns:
        Tuple[str, Dict[str, str]]: 
            str: Print-ready string of the function with arguments as pin names (Q_619, INPUT2, ...)
            Dict[str, str]: Dictionary with argument names (pin names) as keys and net IDs as values
    """

    net_indexes_str = str(function)
    pin_names_str = net_indexes_str
    pin2net_dict = {}
    net_names = function.get_variables()
    for net_str in net_names:
        net = netlist.get_net_by_id(int(net_str))
        sign_char = ''
        is_negative = False
        if net.is_global_input_net():
            pin_name = netlist.get_net_by_id(int(net_str)).get_name()
            pin_name = pin_name.replace('(', '')
            pin_name = pin_name.replace(')', '')
            gate_name = ''
        else:
            source_endpoint = netlist.get_net_by_id(int(net_str)).get_sources()[0]
            gate_name = source_endpoint.get_gate().get_name()
            pin_name = source_endpoint.get_pin()
            if pin_name == 'QN':
                is_negative = True
                pin_name = pin_name[:-1]
                sign_char = HAL_NOT_CHAR
            pin_name += '_'
        gate_name = gate_name.replace('_', '')
        pin_display_name = pin_name+gate_name
        if pin_display_name in pin2net_dict:
            pin2net_dict[pin_display_name].add_net(net_str, is_negative)
        else:
            pin2net_dict[pin_display_name] = PosNegNet(net_str, is_negative)
        # Avoid replacing two (for example) first digits of a three digit number
        pin_names_str = re.sub(net_str+'\\b', sign_char+pin_display_name, pin_names_str)
    pin_names_str = pin_names_str.replace(HAL_NOT_CHAR, SYMPY_NOT_CHAR)
    return pin_names_str, pin2net_dict


def analyze_fsm(netlist_path: str, lib_path: str, print_functions: bool = False,
                print_args: bool = False, result_filename: str = None) \
                    -> Tuple[hal_py.Netlist, List[hal_py.BooleanFunction]]:
    """Main function of the module. Finds a control path FSM in a netlist and generates
    a .dot file describing the states transitions.
    - Each nod in the graph is described by the state vector and each edge is labeled by the
      input vector.
    - If Only one edge is going out of a node, the label can be ignored (the input doesn't matter)
    - to generate .pdf file out of the .dot file using the Graphviz library:
        dot -Tpdf fsm.dot -o fsm.pdf

    Args:
        netlist_path (str): Path to the netlist .v file
        lib_path (str): Path to the library file
        print_functions (bool): If True, the boolean functions are printed
        print_args (bool): If True, each state function's arguments iteration will be printed
        result_filename (str): The file name of the .dot output file (without extention)

    Returns:
        Tuple[hal_py.Netlist, List[hal_py.BooleanFunction]]:
            hal_py.Netlist: The analized netlist
            List[hal_py.BooleanFunction]: List of the logical functions for each state bit
    """
    
    netlist = hal_py.NetlistFactory.load_netlist(netlist_path, lib_path)

    clear_all(netlist)

    # Section1 - Determine finite state machine
    fsm_candid = get_fsm_candidates(netlist)
    fsm_gates = select_fsm(fsm_candid)
    
    # Section 2 - Create a module from the most likely sub-graph to be the FSM
    fsm_module = netlist.create_module("Control Path", netlist.get_top_module(), fsm_gates)
    
    # Section3 - Split the FSM to sequential and combinational logic
    seq_gates = get_ffs(fsm_module)
    netlist.create_module("Sequential", fsm_module, seq_gates)
    comb_gates = get_not_ffs(fsm_module)
    netlist.create_module("Combinational", fsm_module, comb_gates)
    
    # Section 4 - Find logical function for each of the state bits (FFs)
    state_functions = []
    for state_bit_ind, flipflop in enumerate(seq_gates):
        cur_func = get_ff_input_func(netlist, flipflop)
        state_functions.append(cur_func)
        print_str, _ = get_function_str(netlist, cur_func)
        if print_functions:
            print("\nBoolean function of bit {}:\n\n\t{}\n".format(state_bit_ind, print_str))

    # Sections 5, 6 - Find state transitions of the FSM
    if result_filename is not None:
        dot_file_name = result_filename + ".dot"
        with open(dot_file_name, "w+") as dot_file:
            dot_file.write("strict digraph G {\n")
            zero_state_str = len(seq_gates) * "0"
            dot_file.write("\t" + zero_state_str + "\n")
            argspool = ArgsPool(netlist, state_functions)
            while argspool.is_increment_possible():
                next_state = ""
                for function in state_functions:
                    next_state += argspool.evaluate(function)
                cur_state = argspool.get_state_str()
                cur_input = argspool.get_input_str()
                dot_file.write('\t{} -> {} [label="{}"]\n'.format(cur_state, next_state, cur_input))
                if print_args:
                    print("\n{}Next state: {}".format(argspool, next_state))
                argspool.increment_args()
            dot_file.write("}")

    return netlist, state_functions


if __name__ == "__main__":
    # Part 1 - Simple FSM
    analyze_fsm("./project2_cipher_v1.v", "./NangateOpenCellLibrary_functional.lib",
                print_functions=True, print_args=False, result_filename="fsm1")

    # Part 2 - Obfuscated FSM
    analyze_fsm("./project2_cipher_v2_obfuscated.v", "./NangateOpenCellLibrary_functional.lib",
                print_functions=True, print_args=False, result_filename="fsm2")
