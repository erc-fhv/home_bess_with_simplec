import numpy as np

from model_archive.controller_infrastructure.local_data_acquisition import LocalDataAcquisition
from model_archive.central_surplus_controller.central_surplus_controller import CentralSurplusController
from model_archive.controller_infrastructure.decentral_flex_controller import DecentralFlexController


# --- LocalDataAcquisition ---

def test_lda_surplus():
    lda = LocalDataAcquisition('lda', delta_t=900)
    result = lda.step(0, P_gen_=[-1000], P_load_=[500])
    assert np.isclose(result['P_residual'], -500)

def test_lda_deficit():
    lda = LocalDataAcquisition('lda', delta_t=900)
    result = lda.step(0, P_gen_=[-500], P_load_=[1000])
    assert np.isclose(result['P_residual'], 500)

def test_lda_multiple_inputs():
    lda = LocalDataAcquisition('lda', delta_t=900)
    result = lda.step(0, P_gen_=[-1000, -500], P_load_=[800, 200])
    assert np.isclose(result['P_residual'], -500)

def test_lda_empty_inputs():
    lda = LocalDataAcquisition('lda', delta_t=900)
    result = lda.step(0)
    assert np.isclose(result['P_residual'], 0)
    assert result['E_flex'] == {}
    assert result['P_flex'] == {}


def test_lda_state_passthrough():
    lda = LocalDataAcquisition('lda', delta_t=900, has_gen=False, has_load=False, has_state=True)
    result = lda.step(0, E_flex_dict={'bes_1': 1000, 'bes_2': 2000})
    assert result['E_flex'] == {'bes_1': 1000, 'bes_2': 2000}


def test_lda_flex_passthrough():
    lda = LocalDataAcquisition('lda', delta_t=900, has_gen=False, has_load=False, has_flex=True)
    result = lda.step(0, P_flex_dict={'bes_1': 500, 'bes_2': -300})
    assert result['P_flex'] == {'bes_1': 500, 'bes_2': -300}


# --- CentralSurplusController ---

def test_central_surplus_charges():
    ctrl = CentralSurplusController('ctrl', flex_config={'bes': 5000})
    result = ctrl.step(0, P_residual_=[-1000])
    assert np.isclose(result['P_set_dict']['bes'], 1000)

def test_central_deficit_discharges():
    ctrl = CentralSurplusController('ctrl', flex_config={'bes': 5000})
    result = ctrl.step(0, P_residual_=[500])
    assert np.isclose(result['P_set_dict']['bes'], -500)

def test_central_balanced():
    ctrl = CentralSurplusController('ctrl', flex_config={'bes': 5000})
    result = ctrl.step(0, P_residual_=[0])
    assert np.isclose(result['P_set_dict']['bes'], 0)

def test_central_proportional_split():
    ctrl = CentralSurplusController('ctrl', flex_config={'bes_a': 3000, 'bes_b': 1000})
    result = ctrl.step(0, P_residual_=[-2000])
    assert np.isclose(result['P_set_dict']['bes_a'], 1500)
    assert np.isclose(result['P_set_dict']['bes_b'], 500)

def test_central_clipping():
    ctrl = CentralSurplusController('ctrl', flex_config={'bes_a': 1000, 'bes_b': 1000})
    result = ctrl.step(0, P_residual_=[-5000])
    assert np.isclose(result['P_set_dict']['bes_a'], 1000)
    assert np.isclose(result['P_set_dict']['bes_b'], 1000)

def test_central_deficit_clipping():
    ctrl = CentralSurplusController('ctrl', flex_config={'bes_a': 1000, 'bes_b': 1000})
    result = ctrl.step(0, P_residual_=[5000])
    assert np.isclose(result['P_set_dict']['bes_a'], -1000)
    assert np.isclose(result['P_set_dict']['bes_b'], -1000)


# --- DecentralFlexController ---

def test_decentral_passthrough():
    ctrl = DecentralFlexController('dfc', delta_t=900)
    assert np.isclose(ctrl.step(0, P_cmd=500)['P_set'], 500)
    assert np.isclose(ctrl.step(0, P_cmd=-300)['P_set'], -300)
    assert np.isclose(ctrl.step(0, P_cmd=0)['P_set'], 0)
