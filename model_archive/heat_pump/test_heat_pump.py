import pytest
import numpy as np
import pandas as pd
from model_archive.heat_pump.heat_pump import HeatPumpCoolingcircleEventBased, HeatPumpCoolingcircleWControl

@pytest.fixture
def mocked_HP_model():
    """
    Provides a mocked instance of HPModel for testing.
    """
    model = HeatPumpCoolingcircleEventBased(
        name="TestHP",
        delta_t=60,
        eta=0.8433,
        P_el_nom=3500,
        fluid='R290'
                )
    yield model

def test_initialization(mocked_HP_model):
    """
    Test the initialization of the HPModel.
    """
    model = mocked_HP_model
    assert model.name == "TestHP"
    assert model.P_el_nom ==  3500 # Default nominal power
    assert isinstance(model.inputs, list)
    assert isinstance(model.outputs, list)

def test_step_method_with_demand(mocked_HP_model):
    """
    Test the `step` method of HPModel with valid inputs.
    """
    model = mocked_HP_model
    result = model.step(
        time=pd.to_datetime('2021-01-01 00:00:00'),
        state=1,
        T_source=-5,
        T_sink=20
    )
    assert "dot_Q_hp" in result
    assert np.isclose(result["dot_Q_hp"], 40870.54416905677)

def test_step_method_without_demand(mocked_HP_model):
    """
    Test the `step` method of HPModel with valid inputs.
    """
    model = mocked_HP_model
    result = model.step(
        time=pd.to_datetime('2021-01-01 00:00:00'),
        state=0,
        T_source=-5,
        T_sink=20
    )
    assert "dot_Q_hp" in result
    assert np.isclose(result["dot_Q_hp"], 0)

@pytest.fixture
def mocked_HP_WControl_model():
    """
    Provides a mocked instance of HPModel with control for testing.
    """
    model = HeatPumpCoolingcircleWControl(
        name="TestHPWControl",
        delta_t=60,
        eta=0.8433,
        dot_Q_hp_nom=15000,
        P_el_max=5700,
        P_el_min=1000,
        fluid='R290'
                )
    yield model

def test_initialization(mocked_HP_WControl_model):
    """
    Test the initialization of the HPModel.
    """
    model = mocked_HP_WControl_model
    assert model.name == "TestHPWControl"
    assert model.dot_Q_hp_nom ==  15000 # Default nominal heat output
    assert isinstance(model.inputs, list)
    assert isinstance(model.outputs, list)

def test_step_method_with_demand(mocked_HP_WControl_model):
    """
    Test the `step` method of HPModel with valid inputs.
    """
    model = mocked_HP_WControl_model
    result = model.step(
        time=pd.to_datetime('2021-01-01 00:00:00'),
        state=1,
        T_source=-5,
        T_sink=20
    )
    assert "P_el" in result
    assert np.isclose(result["P_el"], 2091.971167458356)

def test_step_method_without_demand(mocked_HP_WControl_model):
    """
    Test the `step` method of HPModel with valid inputs.
    """
    model = mocked_HP_WControl_model
    result = model.step(
        time=pd.to_datetime('2021-01-01 00:00:00'),
        state=0,
        T_source=-5,
        T_sink=20
    )
    assert "P_el" in result
    assert np.isclose(result["P_el"], 0)