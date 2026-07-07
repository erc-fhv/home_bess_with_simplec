import pyomo.environ as pyo
from models.mp_controller import pyo_helpers as ph

def make_EC_test_model(n_periods=3, delta_t=60*15):
    model      = pyo.ConcreteModel()

    model.timepoints = pyo.RangeSet(0, n_periods) # Range of timepoints
    model.periods    = pyo.RangeSet(0, n_periods-1) # Range of periods
    model.delta_t    = pyo.Param(initialize=delta_t) # s

    model.P_resid_plus  = pyo.Var(model.periods, domain=pyo.NonNegativeReals) # Residual Grid load W 
    model.P_resid_minus = pyo.Var(model.periods, domain=pyo.NonNegativeReals) # Residual Grid load W

    @model.Objective(sense=pyo.minimize)
    def objective_rule(m):
        return pyo.quicksum(m.P_resid_plus[p]+m.P_resid_minus[p] for p in m.periods)    
    return model


def component_test_setup(comp, P_resid:list, n_periods=3, delta_t=60*15):
    model = make_EC_test_model(n_periods, delta_t)

    model.comp = pyo.Block(rule=comp.pyo_block_rule)

    # Grid constraints:
    @model.Constraint(model.periods)
    def grid_constraint(m, p):
        return (P_resid[p] + model.comp.P_el[p] + m.P_resid_plus[p] - m.P_resid_minus[p] == 0)
    return model 
