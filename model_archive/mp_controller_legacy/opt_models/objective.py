import pyomo.environ as pyo
from typing import Literal


class Objective:
    """Objective function MILP sub-model.

    Participates in the shared P_el sum-to-zero constraint and defines
    the optimization objective.

    Parameters
    ----------
    name : str
        Unique identifier (default 'EC')
    objective : str
        One of 'self-consumption', 'self-consumption-slack', 'peak-power-slack'
    """

    def __init__(self, name='EC',
                 objective: Literal['self-consumption',
                                    'self-consumption-slack',
                                    'peak-power-slack'] = 'self-consumption'):
        self.name = name

        self.state_inputs = []
        self.forecast_inputs = []
        self.control_outputs = ['P_el']
        self.shares = ['P_el']

        match objective:
            case 'self-consumption':
                self.pyo_block_rule = self._self_consumption_block_rule
            case 'self-consumption-slack':
                self.pyo_block_rule = self._self_consumption_block_rule_w_slack
                self.shares = ['P_el', 'slack']
            case 'peak-power-slack':
                self.pyo_block_rule = self._peak_power_block_rule_w_slack
                self.shares = ['P_el', 'slack']
            case _:
                raise ValueError(f"'{objective}' not a valid objective")

    def _self_consumption_block_rule(self, block):
        model = block.model()
        block.P_el          = pyo.Var(model.periods, domain=pyo.Reals) # Electrical Power in W (feed in = positive, consumption = negative)
        block.P_resid_plus  = pyo.Var(model.periods, domain=pyo.NonNegativeReals) # Residual Grid load W 
        block.P_resid_minus = pyo.Var(model.periods, domain=pyo.NonNegativeReals) # Residual Grid load W

        @block.Constraint(model.periods)
        def grid_constraint(b, p):
            return b.P_resid_plus[p] - b.P_resid_minus[p] == b.P_el[p]
        
        @block.Objective(sense=pyo.minimize)
        def objective_rule(b):
            return pyo.quicksum(b.P_resid_plus[p]+b.P_resid_minus[p] for p in model.periods)
        
    def _self_consumption_block_rule_w_slack(self, block):
        model = block.model()
        # Shared Variables
        block.P_el          = pyo.Var(model.periods, domain=pyo.Reals) # Electrical Power in W (feed in = positive, consumption = negative)
        block.slack         = pyo.Var(model.periods, domain=pyo.Reals) # Slack Variable in W
        
        # Helper Variables
        block.P_resid_plus  = pyo.Var(model.periods, domain=pyo.NonNegativeReals) # Residual Grid load W 
        block.P_resid_minus = pyo.Var(model.periods, domain=pyo.NonNegativeReals) # Residual Grid load W

        @block.Constraint(model.periods)
        def grid_constraint(b, p):
            return b.P_resid_plus[p] - b.P_resid_minus[p] == b.P_el[p]
        
        @block.Objective(sense=pyo.minimize)
        def objective_rule(b):
            return pyo.quicksum(b.P_resid_plus[p]+b.P_resid_minus[p] - block.slack[p] for p in model.periods) # slack negative due to summation of shared variables
        
    def _peak_power_block_rule_w_slack(self, block):
        model = block.model()
        # Shared Variables
        block.P_el          = pyo.Var(model.periods, domain=pyo.Reals) # Electrical Power in W (feed in = positive, consumption = negative)
        block.slack         = pyo.Var(model.periods, domain=pyo.Reals) # Slack Variable in W
        
        # Helper Variables
        block.P_max_resid_plus  = pyo.Var(domain=pyo.NonNegativeReals) # Peak Residual Grid load W
        block.P_max_resid_minus = pyo.Var(domain=pyo.NonNegativeReals) # Peak Residual Grid load W

        @block.Constraint(model.periods)
        def max_constraint_1(b, p):
            return b.P_el[p] <= b.P_max_resid_plus
        
        @block.Constraint(model.periods)
        def max_constraint_2(b, p):
            return b.P_el[p] >= -b.P_max_resid_minus
        
        @block.Objective(sense=pyo.minimize)
        def objective_rule(b):
            return b.P_max_resid_plus + b.P_max_resid_minus - pyo.quicksum(block.slack[p] for p in model.periods) # slack negative due to summation of shared variables