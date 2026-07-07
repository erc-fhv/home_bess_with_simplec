import pyomo.environ as pyo


class DHWHeaterTemperatureModel:
    """Domestic hot water heater with thermal buffer storage (temperature-based).

    Uses temperature as the state variable. Energy balance tracks T_tes
    based on electrical input and heat demand.

    Parameters
    ----------
    name : str
        Unique identifier
    P_nom : float
        Nominal electric power of heating element in W
    C_tes : float
        Total thermal capacitance of TES in J/K
    T_tes_min : float
        Minimum storage temperature in °C
    T_tes_max : float
        Maximum storage temperature in °C
    eta : float
        Coefficient of performance (fixed, no unit)
    """

    def __init__(self, name, P_nom=2_000, C_tes=4200 * 200,
                 T_tes_min=10, T_tes_max=80, eta=1):
        self.name = name
        self.P_nom = P_nom
        self.C_tes = C_tes
        self.T_tes_min = T_tes_min
        self.T_tes_max = T_tes_max
        self.cop = eta

        self.state_inputs = ['T_tes_0']
        self.states = ['T_tes']
        self.forecast_inputs = ['dot_Q_demand']
        self.control_outputs = ['on']
        self.shares = ['P_el']

    def pyo_block_rule(self, block):
        model = block.model()

        block.T_tes_0 = pyo.Param(
            mutable=True, domain=pyo.NonNegativeReals,
            validate=lambda _, E: self.T_tes_min <= E <= self.T_tes_max,
        )
        block.dot_Q_demand = pyo.Param(model.periods, mutable=True, domain=pyo.Reals)

        block.T_tes = pyo.Var(
            model.timepoints, domain=pyo.NonNegativeReals,
            bounds=(self.T_tes_min, self.T_tes_max),
        )
        block.on = pyo.Var(model.periods, domain=pyo.Boolean)
        block.P_el = pyo.Var(model.periods, domain=pyo.NonNegativeReals)

        @block.Constraint(model.periods)
        def energy_balance(block, p):
            return block.T_tes[p + 1] == block.T_tes[p] + (
                block.P_el[p] * self.cop - block.dot_Q_demand[p]
            ) * model.delta_t / self.C_tes

        block.initial_condition = pyo.Constraint(
            rule=lambda b: b.T_tes[0] == b.T_tes_0,
        )
        block.nominal_power = pyo.Constraint(
            model.periods,
            rule=lambda b, p: b.P_el[p] == self.P_nom * b.on[p],
        )


class DHWHeaterEnergyModel:
    """Domestic hot water heater with thermal buffer storage (energy-based).

    Uses energy as the state variable. Energy balance tracks E_tes
    based on electrical input and heat demand.

    Parameters
    ----------
    name : str
        Unique identifier
    eta : float
        Coefficient of performance (fixed, no unit)
    P_nom : float
        Nominal electric power of heating element in W
    E_tes_min : float
        Minimum storage energy in J
    E_tes_max : float
        Maximum storage energy in J
    """

    def __init__(self, name, eta=1, P_nom=7_000,
                 E_tes_min=200 * 4200 * 10, E_tes_max=200 * 4200 * 40):
        self.name = name
        self.cop = eta
        self.P_nom = P_nom
        self.E_tes_min = E_tes_min
        self.E_tes_max = E_tes_max

        self.state_inputs = ['E_tes_0']
        self.states = ['E_tes']
        self.forecast_inputs = ['dot_Q_demand']
        self.control_outputs = ['on']
        self.shares = ['P_el']

    def pyo_block_rule(self, block):
        model = block.model()

        block.E_tes_0 = pyo.Param(
            mutable=True, domain=pyo.NonNegativeReals,
            validate=lambda _, E: self.E_tes_min <= E <= self.E_tes_max,
        )
        block.dot_Q_demand = pyo.Param(model.periods, mutable=True, domain=pyo.Reals)

        block.E_tes = pyo.Var(
            model.timepoints, domain=pyo.NonNegativeReals,
            bounds=(self.E_tes_min, self.E_tes_max),
        )
        block.on = pyo.Var(model.periods, domain=pyo.Boolean)
        block.P_el = pyo.Var(model.periods, domain=pyo.NonNegativeReals)

        @block.Constraint(model.periods)
        def energy_balance(block, p):
            return block.E_tes[p + 1] == block.E_tes[p] + (
                block.P_el[p] * self.cop - block.dot_Q_demand[p]
            ) * model.delta_t

        block.initial_condition = pyo.Constraint(
            rule=lambda b: b.E_tes[0] == b.E_tes_0,
        )
        block.nominal_power = pyo.Constraint(
            model.periods,
            rule=lambda b, p: b.P_el[p] == self.P_nom * b.on[p],
        )


