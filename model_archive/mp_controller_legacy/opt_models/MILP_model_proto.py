import pyomo.environ as pyo
from typing import Protocol, runtime_checkable


@runtime_checkable
class MILPModelProto(Protocol):
    """Protocol for MILP sub-models used in the optimization problem.

    Each sub-model defines a Pyomo Block via ``pyo_block_rule`` and declares
    its interface through attribute lists.

    Attributes
    ----------
    name : str
        Unique identifier for this component
    state_inputs : list[str]
        Names of mutable Params set each step (initial conditions)
    forecast_inputs : list[str]
        Names of indexed mutable Params updated each step (forecasts)
    control_outputs : list[str]
        Names of Vars indexed by ``model.periods`` whose period-0 values
        are returned to SimPlEC
    shares : list[str]
        Names of Vars coupled via sum-to-zero constraints across components
        (egoistic sign convention: + consumption, - feed-in)
    """

    name: str
    state_inputs: list[str]
    forecast_inputs: list[str]
    control_outputs: list[str]
    shares: list[str]

    def pyo_block_rule(self, block: pyo.Block) -> None:
        ...