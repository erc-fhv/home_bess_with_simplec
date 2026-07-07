from models.mp_controller.opt_models.battery_storage import BatteryStorageModel
import pyomo.environ as pyo
from models.mp_controller import pyo_helpers as ph

from component_test_helper import make_EC_test_model, component_test_setup
        
def test_bes_function_simple_1():
    model = make_EC_test_model(3)

    bes = BatteryStorageModel(
                    name='bes_1', 
                    E_min=0., 
                    E_max=3, 
                    P_max_cha=1., 
                    P_max_dis=1., 
                    eta_cha=1., 
                    eta_dis=1.)

    model.bes = pyo.Block(rule=bes.pyo_block_rule)

    # Grid constraints:
    @model.Constraint(model.periods)
    def grid_constraint(m, p):
        return (model.bes.P_el[p] + m.P_resid_plus[p] - m.P_resid_minus[p] == 0) # 
    
    ph.set_block_attribute_by_name(model, 'bes', 'E_BES_0', 1.)

    solver = pyo.SolverFactory('appsi_highs')
    res = solver.solve(model)

    P_bes = ph.get_all_indexed_block_attributes_by_name(model, 'bes', 'P_el')
    E_bes = ph.get_all_indexed_block_attributes_by_name(model, 'bes', 'E')

    assert P_bes == [0, 0, 0]
    assert E_bes == [1, 1, 1, 1]


def test_bes_function_simple_2():
    bes = BatteryStorageModel(
                    name='bes', 
                    E_min=0., 
                    E_max=3, 
                    P_max_cha=1., 
                    P_max_dis=1., 
                    eta_cha=1., 
                    eta_dis=1.)
    
    model = component_test_setup(
        comp=bes,
        P_resid=[0, 1, -1],
        n_periods=3,
        delta_t=1
        )
    
    # set comp initial values
    # ph.set_indexed_block_attribute_by_name(model, 'ec', 'P_resid_ec', P_resid)
    ph.set_block_attribute_by_name(model, 'comp', 'E_BES_0', 1)

    # solve model
    solver = pyo.SolverFactory('appsi_highs')
    res = solver.solve(model)

    # get results
    P_comp = ph.get_all_indexed_block_attributes_by_name(model, 'comp', 'P_el')
    E_comp = ph.get_all_indexed_block_attributes_by_name(model, 'comp', 'E')
    P_resid_p = pyo.value(model.P_resid_plus[:])
    P_resid_m = pyo.value(model.P_resid_minus[:])


    assert P_comp == [0, -1, 1]
    assert E_comp == [1, 1, 0, 1]
    assert P_resid_p == [0, 0, 0]
    assert P_resid_m == [0, 0, 0]


def test_bes_function_efficiencies():
    bes = BatteryStorageModel(
                    name='bes', 
                    E_min=0., 
                    E_max=4, 
                    P_max_cha=1., 
                    P_max_dis=1., 
                    eta_cha=.5, 
                    eta_dis=.6)
    
    model = component_test_setup(
        comp=bes,
        P_resid=[0, 1, -1],
        n_periods=3,
        delta_t=1
        )
    
    # set comp initial values
    # ph.set_indexed_block_attribute_by_name(model, 'ec', 'P_resid_ec', P_resid)
    ph.set_block_attribute_by_name(model, 'comp', 'E_BES_0', 2)

    # solve model
    solver = pyo.SolverFactory('appsi_highs')
    res = solver.solve(model)

    # get results
    P_comp = ph.get_all_indexed_block_attributes_by_name(model, 'comp', 'P_el')
    E_comp = ph.get_all_indexed_block_attributes_by_name(model, 'comp', 'E')
    P_resid_p = pyo.value(model.P_resid_plus[:])
    P_resid_m = pyo.value(model.P_resid_minus[:])


    assert P_comp == [0, -1, 1]
    assert E_comp == [2,  2,  2-1/0.6, 2-1/0.6+1*0.5]
    assert P_resid_p == [0, 0, 0]
    assert P_resid_m == [0, 0, 0]

def test_bes_function_limits():
    bes = BatteryStorageModel(
                    name='bes', 
                    E_min=0., 
                    E_max=4, 
                    P_max_cha=1., 
                    P_max_dis=1., 
                    eta_cha=1., 
                    eta_dis=1.)
    
    model = component_test_setup(
        comp=bes,
        P_resid=[0, -1, 2, 1, 1, 1],
        n_periods=6,
        delta_t=1
        )
    
    # set comp initial values
    # ph.set_indexed_block_attribute_by_name(model, 'ec', 'P_resid_ec', P_resid)
    ph.set_block_attribute_by_name(model, 'comp', 'E_BES_0', 2)

    # solve model
    solver = pyo.SolverFactory('appsi_highs')
    res = solver.solve(model)

    # get results
    P_comp = ph.get_all_indexed_block_attributes_by_name(model, 'comp', 'P_el')
    E_comp = ph.get_all_indexed_block_attributes_by_name(model, 'comp', 'E')
    P_resid_p = pyo.value(model.P_resid_plus[:])
    P_resid_m = pyo.value(model.P_resid_minus[:])


    assert P_comp ==   [0, 1, -1, -1, -1, 0]
    assert E_comp == [2, 2, 3,   2,  1,  0, 0]
    assert P_resid_p == [0, 0, 0, 0, 0, 0]
    assert P_resid_m == [0, 0, 1, 0, 0, 1]