from models.mp_controller.forecasting import (
    GenericPersistenceForecasting,
)
import numpy as np
import pandas as pd

def test_persistence_store_data():
    fc = GenericPersistenceForecasting(inpt='v1')
    fc.set_forecast_length(n=3)

    fc.set_data(1, **{'v1': 1.})
    fc.set_data(1, **{'v1': 2.})

    assert np.array_equal(fc.ser.values, np.array([np.nan, np.nan, 1., 2.]), equal_nan=True)

def test_persistence_forecasting():
    fc = GenericPersistenceForecasting(inpt='v1')
    fc.set_forecast_length(n=3)

    fc.set_data(1, v1= 1.)
    fc.set_data(1, v1= 2.)
    fc.set_data(1, v1= 3.)
    fc.set_data(1, v1= 4.)

    assert fc.get_forecast(1) == [1., 2., 3.]

def test_persistence_forecasting_longer():
    fc = GenericPersistenceForecasting(inpt='v1')
    fc.set_forecast_length(n=3)

    fc.set_data(1, v1=1.)
    fc.set_data(1, v1=2.)
    fc.set_data(1, v1=3.)
    fc.set_data(1, v1=4.)
    fc.set_data(1, v1=5.)

    assert fc.get_forecast(1) == [2., 3., 4.]

def test_persistence_forecasting_delay():
    fc = GenericPersistenceForecasting(inpt='v1', delay=3)
    fc.set_forecast_length(n=3)

    fc.set_data(1, v1=1.)
    fc.set_data(1, v1=2.)
    fc.set_data(1, v1=3.)
    fc.set_data(1, v1=4.)
    fc.set_data(1, v1=5.)
    fc.set_data(1, v1=6.)
    fc.set_data(1, v1=7.)

    assert fc.get_forecast(1) == [2., 3., 4.]


def test_persistence_forecasting_multi_input_list_aggregation():
    fc = GenericPersistenceForecasting(inpt='P_residual_', delay=1, init_val=0)
    fc.set_forecast_length(n=3)

    fc.set_data(1, **{'P_residual_': [-1000., 500.]})
    fc.set_data(2, **{'P_residual_': [-900., 400.]})
    fc.set_data(3, **{'P_residual_': [-800., 300.]})
    fc.set_data(4, **{'P_residual_': [-700., 200.]})

    assert fc.get_forecast(4) == [-500., -500., -500.]


def test_persistence_forecasting_multi_input_dict_aggregation():
    fc = GenericPersistenceForecasting(inpt='P_residual_dict', delay=1, init_val=0)
    fc.set_forecast_length(n=2)

    fc.set_data(1, **{'P_residual_dict': {'a': -200., 'b': 50.}})
    fc.set_data(2, **{'P_residual_dict': {'a': -100., 'b': 25.}})
    fc.set_data(3, **{'P_residual_dict': {'a': -300., 'b': 75.}})

    assert fc.get_forecast(3) == [-150., -75.]
