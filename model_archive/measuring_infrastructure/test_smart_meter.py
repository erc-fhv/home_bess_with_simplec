import pytest
import numpy as np
import pandas as pd
from unittest.mock import MagicMock, patch
from models.measuring_infrastructure.smart_meter import SmartMeter


def test_smartmeter_initialization():
    smartmeter = SmartMeter('name')
    assert smartmeter.name == 'name'
    assert smartmeter.inputs == ['P_']
    assert smartmeter.outputs == ['P_grid']
    assert smartmeter.delta_t == 60

def test_smartmeter_step():
    smartmeter = SmartMeter('name')
    inputs = {'P_': [2., 3.]}
    assert smartmeter.step(1, **inputs)['P_grid'] == 5.

def test_smart_meter_retrieve_data_empty():
    smartmeter = SmartMeter('name')
    assert smartmeter.retrieve_data().empty, 'should return empty series'

def test_smart_meter_retrieve_data():
    smartmeter = SmartMeter('name')
    P_values = np.random.random((30, 2))*2000 # random P values

    for i, (p1, p2) in enumerate(P_values): # Step model 30 times 
        inputs = {'P_': [p1, p2]}
        timestamp = pd.to_datetime(i, origin='2022-01-01 00:00', unit='m') # timestamp required, minute steps!
        smartmeter.step(timestamp, **inputs)

    # calculate manually resampled results
    df = smartmeter.retrieve_data()
    expected_value1 = (P_values).sum(axis=1)[:15].mean()
    expected_value2 = (P_values).sum(axis=1)[15:30].mean()
    assert np.isclose(df['2022-01-01 00:00:00'], expected_value1, atol=1e-3), 'aggregation seems to fail'
    assert np.isclose(df['2022-01-01 00:15:00'], expected_value2, atol=1e-3), 'aggregation seems to fail'

    assert not smartmeter.reccords, 'after retrieve data, reccords list should be empty'

    # repeat test after emptying dataframe
    P_values = np.random.random((30, 2))*2000 # new random P values
    for i, (p1, p2) in enumerate(P_values): # Step model 30 times again with new values
        inputs = {'P_': [p1, p2]}
        timestamp = pd.to_datetime(i+30, origin='2022-01-01 00:00', unit='m') # timestamp required, minute steps!
        smartmeter.step(timestamp, **inputs)

    # calculate manually resampled results
    df = smartmeter.retrieve_data()
    expected_value1 = (P_values).sum(axis=1)[:15].mean()
    expected_value2 = (P_values).sum(axis=1)[15:30].mean()
    assert np.isclose(df.loc['2022-01-01 00:30:00'], expected_value1, atol=1e-3), 'aggregation seems to fail'
    assert np.isclose(df.loc['2022-01-01 00:45:00'], expected_value2, atol=1e-3), 'aggregation seems to fail'
    
