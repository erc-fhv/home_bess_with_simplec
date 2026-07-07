import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from pylpg import lpg_execution, lpgdata
import pandas as pd
import time
import shutil
from pathlib import Path

@pytest.fixture(scope="session", autouse=True)
def clean_dir(request: pytest.FixtureRequest):
    """
    Setup: delete the pylpg output directory if it exists (.venv/lib/python3.11/site-packages/pylpg/C1).
    Teardown: delete it again after the session.
    Runs automatically for the whole test session (autouse=True).
    """
    dirpath = Path(".venv/lib/python3.11/site-packages/pylpg/C1")
    if dirpath.exists():
        try:
            shutil.rmtree(dirpath)
            print(f"[setup] removed {dirpath}")
        except Exception as exc:
            pytest.skip(f"Could not remove {dirpath} in setup: {exc}")

    yield  # run tests

    # Teardown: try again
    shutil.rmtree(dirpath)


def test_initialization_and_caching(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """
    Test the initialization of the Household.
    """
    monkeypatch.setenv("TMP", str(tmp_path)) # imports after environment patch
    from model_archive.loadprofilegenerator.household import Household

    # create model
    start1 = time.perf_counter()
    model1 = Household(
        name='TestHousehold1'
    )
    start2 = time.perf_counter()
    # create model again (should load from cache)
    model2 = Household(
        name='TestHousehold2'
    )
    end = time.perf_counter()

    result = model2.step(
        time= pd.to_datetime('2021-07-01 00:00:00+02:00'),
    )
    assert 'P_el' in result

    assert model1.name == "TestHousehold1"
    assert model2.name == "TestHousehold2"
    assert (end - start2) * 10 < (start2 - start1), 'Loading from cache is not at least 10x faster than normal execution'
    assert 'P_el' in result
    assert 'dot_Q_gain_int' in result
    assert 'dot_Q_ww' in result

def test_step_method_with_different_initialisation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """
    Test the `step` method of Household with valid inputs.
    """
    monkeypatch.setenv("TMP", str(tmp_path)) # imports after environment patch
    from model_archive.loadprofilegenerator.household import Household
    from pylpg import lpgdata
    from pylpg.lpgpythonbindings import EnergyIntensityType

    # create model
    model = Household(
        name ='TestHousehold3',
        delta_t = 60*15,
        year = 2021,
        householdref = lpgdata.Households.CHR05_Family_3_children_both_with_work,
        housetype= lpgdata.HouseTypes.HT23_No_Infrastructure_at_all,
        startdate = '2021-01-01T00:00:00',
        enddate = '2021-12-31T00:00:00',
        geographic_location = lpgdata.GeographicLocations.Germany_Muenchen,
        simulate_transportation = False,
        chargingset = None,
        transportation_device_set = None,
        travel_route_set = None,
        random_seed = 1,
        energy_intensity = EnergyIntensityType.Random,
    )

    result = model.step(
        time= pd.to_datetime('2021-07-01 12:00:00+02:00'),
    )
    assert 'P_el' in result
    assert 'dot_Q_gain_int' in result
    assert 'dot_m_ww' in result
    assert np.isclose(result['P_el'], 69.1398, rtol=1e-3)
    assert np.isclose(result['dot_Q_gain_int'], 69.1398, rtol=1e-3)
    assert np.isclose(result['dot_Q_ww'], 0.0)