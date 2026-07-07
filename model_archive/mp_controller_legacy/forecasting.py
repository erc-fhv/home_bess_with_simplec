import pandas as pd
import numpy as np
from typing import Protocol, Any, runtime_checkable


#################
# Protocol for the forecasting classes
#################
@runtime_checkable
class ForecastingProto(Protocol):
    """Protocol for forecasting classes used by MPController.

    Implementations handle their own out-of-band data (weather series,
    callbacks, irregular data) via custom methods or constructor arguments.
    Only set_data() and get_forecast() are called by the controller.
    """
    inputs: list[str]  # SimPlEC-routed input names

    def set_forecast_length(self, n: int) -> None:
        ...

    def set_data(self, time, **inputs: Any):
        ...

    def get_forecast(self, time) -> list:
        ...


class GenericPersistenceForecasting:
    """Ring-buffer persistence forecaster for a single variable.

    Stores the last N+delay values and returns the oldest N as forecast.
    """
    def __init__(self, inpt: str, init_val=np.nan, delay=1):
        self.inputs = [inpt]
        self.inpt = inpt
        self.init_val = init_val
        self.delay = delay

    def get_forecast(self, time) -> list:
        return self.ser.loc[:self.periods - 1].values.tolist()

    def set_data(self, time, **values) -> None:
        value = self._aggregate_value(values[self.inpt])
        self.ser = self.ser.shift(-1)
        self.ser.loc[self.last_index] = value

    def _aggregate_value(self, value):
        if isinstance(value, list):
            return float(sum(value))
        if isinstance(value, dict):
            return float(sum(value.values()))
        return value

    def set_forecast_length(self, n: int) -> None:
        self.periods = n
        self.ser = pd.Series(
            data=np.full(self.delay + self.periods, self.init_val),
            index=range(self.delay + self.periods),
        )
        self.last_index = self.delay + self.periods - 1