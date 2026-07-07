import pyomo.environ as pyo
from models.mp_controller import pyo_helpers as ph
from component_test_helper import make_EC_test_model, component_test_setup
from models.mp_controller.opt_models.dhwh import DHWHeaterEnergyModel, DHWHeaterTemperatureModel


def test_dhw_function_simple():
    comp = DHWHeaterEnergyModel(
                    'dhwh', 
                   eta=1.,
                   P_nom=1.,
                   E_tes_min=0., 
                   E_tes_max=3)
    
    model = component_test_setup(
        comp=comp,
        P_resid=[0, -1, 1],
        n_periods=3,
        delta_t=1
        )
    
    # set comp initial values
    ph.set_indexed_block_attribute_by_name(model, 'comp', 'dot_Q_demand', [0, 0, 0])
    ph.set_block_attribute_by_name(model, 'comp', 'E_tes_0', 1)

    # solve model
    solver = pyo.SolverFactory('appsi_highs')
    res = solver.solve(model)

    # get results
    P_comp = ph.get_all_indexed_block_attributes_by_name(model, 'comp', 'P_el')
    E_comp = ph.get_all_indexed_block_attributes_by_name(model, 'comp', 'E_tes')
    P_resid_p = pyo.value(model.P_resid_plus[:])
    P_resid_m = pyo.value(model.P_resid_minus[:])

    assert P_comp == [0, 1, 0]
    assert E_comp == [1, 1, 2, 2]
    assert P_resid_p == [0, 0, 0]
    assert P_resid_m == [0, 0, 1]


def test_dhw_T_function_simple():
    comp = DHWHeaterTemperatureModel(
                   'dhwh', 
                   P_nom=1.,
                   C_tes=1,
                   T_tes_min=0., 
                   T_tes_max=3,
                   eta=1.)
    
    model = component_test_setup(
        comp=comp,
        P_resid=[0, -1, 1],
        n_periods=3,
        delta_t=1
        )
    
    # set comp initial values
    ph.set_indexed_block_attribute_by_name(model, 'comp', 'dot_Q_demand', [0, 0, 0])
    ph.set_block_attribute_by_name(model, 'comp', 'T_tes_0', 1)

    # solve model
    solver = pyo.SolverFactory('appsi_highs')
    res = solver.solve(model)

    # get results
    P_comp = ph.get_all_indexed_block_attributes_by_name(model, 'comp', 'P_el')
    E_comp = ph.get_all_indexed_block_attributes_by_name(model, 'comp', 'T_tes')
    P_resid_p = pyo.value(model.P_resid_plus[:])
    P_resid_m = pyo.value(model.P_resid_minus[:])

    assert P_comp == [0, 1, 0]
    assert E_comp == [1, 1, 2, 2]
    assert P_resid_p == [0, 0, 0]
    assert P_resid_m == [0, 0, 1]

