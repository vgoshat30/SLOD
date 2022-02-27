import hal_py
from hal_py import GateLibraryManager
hal_py.plugin_manager.load_all_plugins()

# Read the netlist - simple FSM implemented using LUT cells (Look-up Tables)
netlist = hal_py.NetlistFactory.load_netlist("/home/hwsec/hal/examples/fsm.v", "/usr/local/share/hal/gate_libraries/example_library.hgl")

# Print information about all the gates of type "LUT"
for gate in netlist.get_gates():
    if "LUT" in gate.type.name:
        print("{} (id {}, type {})".format(gate.name, gate.id, gate.type.name))
        print("  {}-to-{} LUT".format(len(gate.type.input_pins), len(gate.type.output_pins)))
        boolean_functions = gate.boolean_functions
        for name in boolean_functions:
            print("  {}: {}".format(name, boolean_functions[name]))
        print("")

# Find all FFsngp
ffs = netlist.get_gates(lambda g : "FF" in g.get_type().get_name())

###################################################################
# backtrace from net to global input
# return all gates inbetween
def dfs_from_net(net):
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

def get_state_str(state_dict):
    return_str = ""
    for id in state_dict:
        if id == hal_py.BooleanFunction.Value.ZERO:
            return_str += "0"
        else:
            return_str += "1"
    return return_str

###################################################################

# Get the transitive fan-in trees for each FF and evaluate their functions for the input of 0
for ff in ffs:
    datapin = ff.get_type().get_pins_of_type(hal_py.PinType.data)
    fanin_net = ff.get_fan_in_net(datapin.pop())
    gts = dfs_from_net(fanin_net)
    for ff1 in ffs:
        gts.remove(ff1)
    fanin_func = hal_py.NetlistUtils.get_subgraph_function(fanin_net,gts)
    instate = {}
    for var in fanin_func.get_variables():
        instate[var] = hal_py.BooleanFunction.Value.ZERO
    fanin_func.evaluate(instate)
    res = get_state_str([fanin_func.evaluate(instate)])
    print("{} input when 0 is applied to all the transitive fanin tree inputs is {}".format(ff.name, res))
