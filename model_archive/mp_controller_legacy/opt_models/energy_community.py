import pyomo.environ as pyo


class ResidualLoadModel:
    """Residual load passthrough MILP sub-model.

    Couples a forecast of residual load (P_resid) into the shared P_el
    sum-to-zero constraint.

    Parameters
    ----------
    name : str
        Unique identifier (default 'EC')
    """

    def __init__(self, name='EC'):
        self.name = name

        self.state_inputs = []
        self.forecast_inputs = ['P_resid']
        self.control_outputs = []
        self.shares = ['P_el']

    def pyo_block_rule(self, block):
        model = block.model()
        block.P_el       = pyo.Var(model.periods, domain=pyo.Reals) # Electrical Power in W (feed in = positive, consumption = negative)
        block.P_resid    = pyo.Param(model.periods, mutable=True, domain=pyo.Reals) # Residual load of EC (surplus_load > 0 > surplus_generation)

        @block.Constraint(model.periods)
        def grid_constraint(b, p):
            return b.P_el[p] == b.P_resid[p]
