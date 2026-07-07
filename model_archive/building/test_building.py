import pytest
import numpy as np
import sklearn
import pickle
from unittest.mock import MagicMock, patch
from models.building.building import BuildingModel

@pytest.fixture
def mocked_building_model():
    """
    Provides a mocked instance of BuildingModel for testing.
    """
    # Mock the facade model's predict method
    mocked_fasade_model = MagicMock()
    mocked_fasade_model.predict.return_value = np.array([0.5])

    # Patch the pickle.load call to return the mocked facade model
    with patch("pickle.load", return_value=mocked_fasade_model):
        model = BuildingModel(name="TestBuilding")
        yield model

def test_fasade_model():
    with open('models/building/fasade_model.pkl', mode='rb') as f:
        model = pickle.load(f)
    output = model.predict([[200, 100, 50, 60, 70, 80]])
    assert isinstance(output, np.ndarray)
    assert output.shape == (1,)
    assert np.isclose(output[0], 1044.11618135) 

def test_initialization(mocked_building_model):
    """
    Test the initialization of the BuildingModel.
    """
    model = mocked_building_model
    assert model.name == "TestBuilding"
    assert model._x[0] == 20  # Default temperature
    assert isinstance(model.inputs, list)
    assert isinstance(model.outputs, list)

def test_step_method_with_valid_inputs(mocked_building_model):
    """
    Test the `step` method of BuildingModel with valid inputs.
    """
    model = mocked_building_model
    result = model.step(
        time=0,
        dot_Q_heat=500,
        dot_Q_cool=300,
        dot_Q_int=100,
        T_amb=25,
        I_dir=200,
        I_dif=100,
        I_s=50,
        I_w=60,
        I_n=70,
        I_e=80,
    )
    assert "T_building" in result
    assert isinstance(result["T_building"], float)

def test_facade_model_integration(mocked_building_model):
    """
    Verify that the facade model's predict method is called correctly.
    """
    model = mocked_building_model
    model.step(
        time=0,
        dot_Q_heat=500,
        dot_Q_cool=300,
        dot_Q_int=100,
        T_amb=25,
        I_dir=200,
        I_dif=100,
        I_s=50,
        I_w=60,
        I_n=70,
        I_e=80,
    )
    model.fasade_model.predict.assert_called_once_with([[200, 100, 50, 60, 70, 80]])

def test_matrix_computation(mocked_building_model):
    """
    Validate the matrix computations in the `step` method.
    """
    model = mocked_building_model

    # Set known model matrices for predictable results
    model._A = np.array([[1.0]])
    model._B = np.array([[1.0, 1.0]])
    model._F = np.array([[0.5, 0.5, 0.5]])
    model._x = np.array([20])

    result = model.step(
        time=0,
        dot_Q_heat=100,
        dot_Q_cool=50,
        dot_Q_int=20,
        T_amb=25,
        I_dir=200,
        I_dif=100,
        I_s=50,
        I_w=60,
        I_n=70,
        I_e=80,
    )
    expected_temperature = 20 + (100 + 50) + 0.5 * (20 + 25 + 0.5)
    assert np.isclose(result["T_building"], expected_temperature, atol=1e-2)
