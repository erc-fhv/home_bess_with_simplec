class GridSetpointConverter:
    """Convert a grid-power setpoint into a battery-power setpoint.

    P_set = P_grid_set - net_load

    Positive P_set → charge battery (absorb surplus grid import or PV).
    Negative P_set → discharge battery (reduce grid import or increase export).
    """

    def __init__(self, name, delta_t=15*60):
        self.name = name
        self.delta_t = delta_t
        self.inputs = ['P_grid_set', 'net_load']
        self.outputs = ['P_set']

    def step(self, time, P_grid_set, net_load):
        return {'P_set': P_grid_set - net_load}
