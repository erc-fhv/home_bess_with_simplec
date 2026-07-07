import pyomo.environ as pyo


class BatteryStorageModel:
    """Battery energy storage MILP sub-model with charge/discharge efficiencies.

    Requires the parent Pyomo model to have:
    - model.timepoints : RangeSet
    - model.periods : RangeSet
    - model.delta_t : Param (seconds)

    Parameters
    ----------
    name : str
        Unique identifier
    E_min : float
        Minimum energy in J
    E_max : float
        Maximum energy in J
    P_max_cha : float
        Maximum charging power in W
    P_max_dis : float
        Maximum discharging power in W
    eta_cha : float
        Charging efficiency [0, 1]
    eta_dis : float
        Discharging efficiency [0, 1]
    """

    def __init__(self, name, E_min=0., E_max=20_000. * 3600,
                 P_max_cha=20_000., P_max_dis=20_000.,
                 eta_cha=0.95, eta_dis=0.95):
        self.name = name
        self.E_min = E_min
        self.E_max = E_max
        self.P_max_cha = P_max_cha
        self.P_max_dis = P_max_dis
        self.eta_cha = eta_cha
        self.eta_dis = eta_dis

        self.state_inputs = ['E_BES_0']
        self.states = ['E']
        self.forecast_inputs = []
        self.control_outputs = ['P_el']
        self.shares = ['P_el']

    def pyo_block_rule(self, block):
        model = block.model()

        # Inputs
        block.E_BES_0   = pyo.Param(mutable=True, domain=pyo.NonNegativeReals, validate=lambda _, E: self.E_min <= E and E <= self.E_max) # J

        # Variables / Outputs
        block.E         = pyo.Var(model.timepoints, domain=pyo.NonNegativeReals, bounds=(self.E_min, self.E_max)) # J
        block.P_el      = pyo.Var(model.periods, domain=pyo.Reals) # Electrical Power in W (feed in = positive, consumption = negative)

        # helper Variables
        block.P_el_cha  = pyo.Var(model.periods, domain=pyo.NonNegativeReals) # Electrical charging Power in W (helper)
        block.P_el_dis  = pyo.Var(model.periods, domain=pyo.NonNegativeReals) # Electrical discharging Power in W (helper)
        block.bool      = pyo.Var(model.periods, domain=pyo.Boolean) # prevent same time charging and discharging

        @block.Constraint(model.periods)
        def energy_balance(block, p):
            return block.E[p+1] == block.E[p] + (block.P_el_cha[p] * self.eta_cha - block.P_el_dis[p] / self.eta_dis) * model.delta_t

        @block.Constraint(model.periods)
        def output_power(block, p):
            return block.P_el[p] == block.P_el_cha[p] - block.P_el_dis[p]

        @block.Constraint(model.periods)
        def power_limit_bool_cha(block, p):
            return block.P_el_cha[p] <= block.bool[p] * self.P_max_cha

        @block.Constraint(model.periods)
        def power_limit_bool_dis(block, p):
            return block.P_el_dis[p] <= (1 - block.bool[p]) * self.P_max_dis

        @block.Constraint()
        def initial_condition(block):
            return block.E[0] == block.E_BES_0