import numpy as np
import pandas as pd
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Forecasting(Protocol):
    """Protocol for all forecasting implementations."""

    inputs: list[str]

    def set_forecast_length(self, n: int) -> None: ...

    def set_data(self, time, **values) -> None: ...

    def get_forecast(self, time) -> list: ...


class GenericPersistenceForecasting:
    """Ring-buffer persistence forecaster for a single variable.

    Stores the last N+delay values and returns the oldest N as forecast.
    Sum-aggregates list and dict inputs automatically.
    """

    def __init__(self, inpt: str, init_val=np.nan, delay=1):
        self.inputs = [inpt]
        self.inpt = inpt
        self.init_val = init_val
        self.delay = delay

    def set_forecast_length(self, n: int) -> None:
        self.periods = n
        self.ser = pd.Series(
            data=np.full(self.delay + self.periods, self.init_val),
            index=range(self.delay + self.periods),
        )
        self.last_index = self.delay + self.periods - 1

    def set_data(self, time, **values) -> None:
        value = self._aggregate_value(values[self.inpt])
        self.ser = self.ser.shift(-1)
        self.ser.loc[self.last_index] = value

    def get_forecast(self, time) -> list:
        return self.ser.loc[: self.periods - 1].values.tolist()

    def _aggregate_value(self, value: Any) -> float:
        if isinstance(value, list):
            return float(sum(value))
        if isinstance(value, dict):
            return float(sum(value.values()))
        return float(value)
