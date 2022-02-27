# Environment and HAL initialization
import sys, os
HAL_BASE = "/usr/local/"
os.environ["HAL_BASE_PATH"] = HAL_BASE
sys.path.append(HAL_BASE+"lib/")
import hal_py
hal_py.plugin_manager.load_all_plugins()
from typing import List, Dict
from hal_plugins import graph_algorithm


ZERO = hal_py.BooleanFunction.Value.ZERO
ONE =  hal_py.BooleanFunction.Value.ONE


class ArgsPool():
    """
    Manages all possible input variables to a given list of boolean functions
    Handles:
        1. Incrementing arguments vector values
        2. Making sure that oposite outputs of FFs will have oposite boolean values
        3. When evaluating a function using ArgsPool, the relevent arguments for
           that function are selected and passed to it
        4. Printing of the arguments, FSM state and FSM inputs
    """

    def bool2str(bool_val: hal_py.BooleanFunction.Value) -> str:
        """
        Convert hal boolean value to '0' or '1' characters
        """

        if bool_val == ZERO:
            return "0"
        else:
            return "1"

    def __init__(self, netlist: hal_py.Netlist, functions_list: List[hal_py.BooleanFunction]) -> None:
        """
        Collecting all argument of the given function list and creates an ArgsPool instance

        Args:
            netlist (hal_py.Netlist): The netlist from which the functions are taken
            functions_list (List[hal_py.BooleanFunction]): List of functions from which to
                collect arguments
        """

        # List[str]: Strings of net ids of the arguments of all the functions (no repetitions)
        self.net_ids_str = []

        # Dict[str, hal_py.BooleanFunction.Value]: Arguments dict (ready for evaluate() function)
        self.args = {}
        
        # int: Numeric vaule representing the arguments vector
        # (for example, if the args are [0, 1, 1], self.args_bin = 3)
        self.args_bin = 0

        self.pin_names = []  # List[str]: Name of the pins from which each net starts
        self.gate_names = []  # List[str]: Name of gates from which each net starts
        
        # List[hal_py.Net]: Nets representing the state of the FSM (nets starting at
        # a 'Q' pin of a flip flop)
        self.state_nets = []

        # List[hal_py.Net]: Nets representing the input of the FSM (global input nets)
        self.input_nets = []

        for function in functions_list:
            new_names = function.get_variables()
            for name in new_names:
                if name not in self.net_ids_str:
                    self.net_ids_str.append(name)
                    self.args[name] = ZERO
                    
                    net = netlist.get_net_by_id(int(name))

                    # If a net is a global input net, consider it an input to the FSM
                    if net.is_global_input_net():
                        self.input_nets.append(net)
                        self.pin_names.append(netlist.get_net_by_id(int(name)).get_name())
                        self.gate_names.append('Global')
                    else:
                        source_endpoint = netlist.get_net_by_id(int(name)).get_sources()[0]
                        self.gate_names.append(source_endpoint.get_gate().get_name())
                        pin_name = source_endpoint.get_pin()
                        self.pin_names.append(pin_name)

                        # If a net starts at a 'Q' pin of a ff, consider it a state bit of the FSM
                        if pin_name == "Q":
                            self.state_nets.append(net)

        # int: Maximal number that can be represented with the arguments
        self.max_args_val = 2 ** len(self.net_ids_str) - 1

        self.is_finished_states = False  # bool: True if thera are no more possible states

        self.validate_args()

    def __str__(self) -> str:
        """
        String representation of the arguments vector

        Returns:
            str: A string describing for each argument:
                - Net ID
                - Gate name
                - Pin name
                - Boolean value (0 or 1)
        """

        state_nets_ids = [str(net.get_id()) for net in self.state_nets]
        input_nets_ids = [str(net.get_id()) for net in self.input_nets]
        net_str = "Net:\t"
        gate_str = "Gate:\t"
        pin_str = "Pin:\t"
        val_str = "Value:\t"
        input_str = "Input:\t"
        state_str = "State:\t"
        for ind, cur_net in enumerate(self.net_ids_str):
            # Net
            net_str += "{}\t".format(self.net_ids_str[ind])

            # Gate
            cur_gate_name = self.gate_names[ind]
            gate_str += "{}".format(cur_gate_name)
            if len(cur_gate_name) < 8:
                gate_str += "\t"

            # Pin
            cur_pin_name = self.pin_names[ind]
            pin_str += "{}".format(cur_pin_name)
            if len(cur_pin_name) < 8:
                pin_str += "\t"

            # Value
            if self.args[cur_net] == ZERO:
                value = 0
            else:
                value = 1
            val_str += "{}\t".format(value)

            # Input
            if cur_net in input_nets_ids:
                input_str += "\u2191\t".format(value)
            else:
                input_str += "\t".format(value)

            # State
            if cur_net in state_nets_ids:
                state_str += "\u2191\t".format(value)
            else:
                state_str += "\t".format(value)

        return net_str + "\n" + gate_str + "\n" + pin_str + "\n" + \
               val_str + "\n" + input_str + "\n" + state_str + "\n"

    def get_state_str(self) -> str:
        """
        Get a string which is the concatenation of the values of the
        arguments representing the state of the FSM

        Returns:
            str: The state of the FSM (for example 0010)
        """

        state_vector_str = ""
        for state_net in self.state_nets:
            net_id = str(state_net.get_id())
            state_vector_str += ArgsPool.bool2str(self.args[net_id])
        return state_vector_str

    def get_input_str(self) -> str:
        """
        Get a string which is the concatenation of the values of the
        arguments representing the input of the FSM

        Returns:
            str: The input of the FSM (for example 11001)
        """

        input_vector_str = ""
        for input_net in self.input_nets:
            net_id = str(input_net.get_id())
            net_name = input_net.get_name()
            input_vector_str += "{}".format(ArgsPool.bool2str(self.args[net_id]))
        return input_vector_str

    def evaluate(self, function:hal_py.BooleanFunction) -> str:
        """
        Evaluate given function with its arguments taken from self.args dictionary

        Args:
            function (hal_py.BooleanFunction): The function to evalueate

        Returns:
            str: A character of the evaluation result ('0' or '1')
        """

        names2eval = function.get_variables()
        args2eval = {}
        for net_name in names2eval:
            args2eval[net_name] = self.args[net_name]
        return ArgsPool.bool2str(function.evaluate(args2eval))

    def is_increment_possible(self) -> bool:
        """
        Check if maximal possible argument vector value is reached

        Returns:
            bool: True if self.max_args_val is not reached
        """

        return not self.is_finished_states

    def increment_args(self):
        """
        Increment argument vector by the smallest valid amount (keeping opposite
        pins of FFs with oposite values)
        """

        self.args_bin += 1
        if self.args_bin == self.max_args_val:
            self.is_finished_states = True
        self.update_state()
        self.validate_args()

    def update_state(self):
        """
        Parse the integer self.args_bin to the arguments values in the dictionary self.args
        """

        for bit, var in enumerate(self.net_ids_str):
            if (self.args_bin >> bit) & 1:
                self.args[var] = ONE
            else:
                self.args[var] = ZERO

    def validate_args(self):
        """
        Increment self.args_bin until all oposite outputs of FFs ('Q' and 'QN' pins)
        have oposite boolean values
        """

        while not self.is_state_valid():
            self.args_bin += 1
            self.update_state()
            if self.args_bin == self.max_args_val:
                self.is_finished_states = True
                return

    def is_state_valid(self) -> bool:
        """
        Check if opposite outputs of same FFs ('Q' and 'QN' pins) have opposite values

        Returns:
            bool: True if all FFs have valid output net boolean values
        """
        
        # Iterate over each function argument and save it to a dictionary
        # of gates-pins. Check if there are arguments which are opposite
        # pins of the same gate and if such pins found, verify that their
        # values are opposite
        existing_pins = {}
        for var_index, cur_net in enumerate(self.net_ids_str):
            cur_gate = self.gate_names[var_index]
            cur_val = self.args[cur_net]
            cur_pin_name = self.pin_names[var_index]
            if cur_gate in existing_pins:
                other_pin_name = existing_pins[cur_gate].name
                if ((cur_pin_name == 'Q' and other_pin_name == 'QN') or
                   (cur_pin_name == 'QN' and other_pin_name == 'Q')) and \
                   cur_val == existing_pins[cur_gate].value:
                   return False
            existing_pins[cur_gate] = Pin(cur_pin_name, cur_val)
        return True

class Pin():
    def __init__(self, name, value):
        self.name = name
        self.value = value
            