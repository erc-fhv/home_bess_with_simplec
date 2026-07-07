import pyomo.environ as pyo
from models.mp_controller import pyo_helpers as ph
from component_test_helper import make_EC_test_model, component_test_setup
from models.mp_controller.opt_models.energy_community import ResidualLoadModel

def test_ec_resid():
    model = make_EC_test_model(3)

    ec = ResidualLoadModel()

    model.ec = pyo.Block(rule=ec.pyo_block_rule)

    # Grid constraints:
    @model.Constraint(model.periods)
    def grid_constraint(m, p):
        return (model.ec.P_el[p] + m.P_resid_plus[p] - m.P_resid_minus[p] == 0)
    
    ph.set_indexed_block_attribute_by_name(model, 'ec', 'P_resid', [0, 1, -1])

    solver = pyo.SolverFactory('appsi_highs')
    res = solver.solve(model)

    P_resid_p = pyo.value(model.P_resid_plus[:])
    P_resid_m = pyo.value(model.P_resid_minus[:])

    assert P_resid_p == [0, 0, 1]
    assert P_resid_m == [0, 1, 0]