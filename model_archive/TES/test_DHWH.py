import pytest
import numpy as np
from model_archive.TES.DHWH import DHWH
from unittest.mock import MagicMock, patch

@pytest.fixture
def mocked_TES_model():
    """
    Provides a mocked instance of DHWHModel for testing.
    """
    model = DHWH(
        name='TestDHWH',
        delta_t=60,
        V=100,
        h=795.7747,
        U=0.766,
        N=10,
        k_1=8.2,
        T_init=40,
        P_el_nom=2000,
        len_heat_elem=300
    )
    yield model

def test_initialization(mocked_TES_model):
    """
    Test the initialization of the DHWHModel.
    """
    model = mocked_TES_model
    assert model.name == "TestDHWH"
    assert model.x[6] ==  313.15 # Default thermal well temperature
    assert isinstance(model.inputs, list)
    assert isinstance(model.outputs, list)

def test_step_method_with_demand(mocked_TES_model):
    """
    Test the `step` method of DHWHModel with valid inputs.
    """
    model = mocked_TES_model
    result = model.step(
        time=0,
        dot_m_o_DHW=0.1,
        T_i_DHW=10,
        T_inf=10,
        state=0
    )
    assert "T_tw" in result
    assert np.isclose(result["T_tw"], 313.03895963-273.15)

def test_step_method_heating_without_demand(mocked_TES_model):
    """
    Test the `step` method of DHWHModel with valid inputs.
    """
    model = mocked_TES_model
    result = model.step(
        time=0,
        dot_m_o_DHW=0,
        T_i_DHW=10,
        T_inf=10,
        state=1
    )
    assert "T_tw" in result
    assert np.isclose(result["T_tw"], 313.85447819 - 273.15)

def test_step_method_without_demand_heating(mocked_TES_model):
    """
    Test the `step` method of DHWHModel with valid inputs.
    """
    model = mocked_TES_model
    result = model.step(
        time=0,
        dot_m_o_DHW=0,
        T_i_DHW=10,
        T_inf=10,
        state=0
    )
    assert "T_tw" in result
    assert np.isclose(result["T_tw"], 313.14671732 - 273.15)
