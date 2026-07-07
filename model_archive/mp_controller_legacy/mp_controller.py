import pyomo.environ as pyo
from .forecasting import ForecastingProto
from .optimization_problem import OptimizationProblem


class MPController:
    """Thin SimPlEC adapter for Model Predictive Control using MILP.

    Receives an OptimizationProblem (pure Pyomo) and a dict of forecasters
    via dependency injection. Auto-derives SimPlEC inputs/outputs from the
    problem's components and the forecasters.

    Parameters
    ----------
    name : str
        Unique model name for SimPlEC
    delta_t : int
        Timestep in seconds
    problem : OptimizationProblem
        The optimization problem (already populated with components)
    forecasters : dict[str, ForecastingProto]
        Mapping of ``'component_name.forecast_var'`` to forecaster instances.
        Each forecaster must have an ``inputs`` attribute listing its
        SimPlEC-routed input names.
    sep : str
        Separator for nested variable names (default ``'.'``)
    return_forecast : bool
        Return forecast values as additional outputs
    return_future_control_output : bool
        Return full horizon of control outputs as additional outputs
    return_future_state : bool
        Return full horizon of states as additional outputs
    """

    def __init__(self, name: str, delta_t: int,
                 problem: OptimizationProblem,
                 forecasters: dict[str, ForecastingProto] | None = None,
                 sep: str = '.',
                 return_forecast: bool = False,
                 return_future_control_output: bool = False,
                 return_future_state: bool = False):
        self.name = name
        self.delta_t = delta_t
        self.problem = problem
        self.sep = sep
        self.return_forecast = return_forecast
        self.return_future_control_output = return_future_control_output
        self.return_future_state = return_future_state

        # Build forecaster registry: list of (prefix, forecast_var, forecaster)
        self._forecasters: list[tuple[str, str, ForecastingProto]] = []
        if forecasters:
            for key, forecaster in forecasters.items():
                comp_name, forecast_var = key.split('.', 1)
                # Validate component exists
                comp = self._find_component(comp_name)
                if comp is None:
                    raise ValueError(
                        f'Component "{comp_name}" not found in optimization problem. '
                        f'Available: {[c.name for c in problem.components]}'
                    )
                if forecast_var not in comp.forecast_inputs:
                    raise AttributeError(
                        f'Component "{comp_name}" has no forecast input "{forecast_var}". '
                        f'Available: {comp.forecast_inputs}'
                    )

                forecaster.set_forecast_length(problem.n_periods)
                if hasattr(forecaster, 'set_delta_t'):
                    forecaster.set_delta_t(delta_t)

                pre = comp_name + sep + 'forecast' + sep
                self._forecasters.append((pre, forecast_var, forecaster))

        # Auto-derive SimPlEC inputs and outputs
        self.inputs = []
        self.outputs = []

        for comp in problem.components:
            self.inputs += [comp.name + sep + si for si in comp.state_inputs]
            self.outputs += [comp.name + sep + o for o in comp.control_outputs]

            if return_future_control_output:
                self.outputs += [comp.name + sep + o + '_future' for o in comp.control_outputs]
            if return_future_state and hasattr(comp, 'states'):
                self.outputs += [comp.name + sep + s + '_future' for s in comp.states]

        for pre, forecast_var, forecaster in self._forecasters:
            self.inputs += [pre + inp for inp in forecaster.inputs]
            if return_forecast:
                self.outputs += [pre + forecast_var + '_future']

    def _find_component(self, name: str):
        for c in self.problem.components:
            if c.name == name:
                return c
        return None

    def step(self, time, **inputs) -> dict:
        """Execute one MPC step: update forecasts, solve, return outputs."""
        problem = self.problem
        sep = self.sep

        # 1. Update forecasters with input data
        for pre, _, forecaster in self._forecasters:
            forc_inputs = {inp: inputs[pre + inp] for inp in forecaster.inputs}
            forecaster.set_data(time, **forc_inputs)

        # 2. Create forecasts
        forecasts = {}
        for pre, forecast_var, forecaster in self._forecasters:
            forecasts[pre + forecast_var] = forecaster.get_forecast(time)

        # 3. Set component states from inputs
        for comp in problem.components:
            for state_name in comp.state_inputs:
                problem.set_state(comp.name, state_name,
                                  inputs[comp.name + sep + state_name])

        # 4. Set forecast data on components
        for comp in problem.components:
            pre = comp.name + sep + 'forecast' + sep
            for forecast_var in comp.forecast_inputs:
                problem.set_forecast(comp.name, forecast_var,
                                     forecasts[pre + forecast_var])

        # 5. Solve
        problem.solve()

        # 6. Extract outputs
        outputs = {}
        for comp in problem.components:
            for out_name in comp.control_outputs:
                outputs[comp.name + sep + out_name] = problem.get_output(
                    comp.name, out_name, period=0
                )

        if self.return_forecast:
            outputs.update({k + '_future': v for k, v in forecasts.items()})

        if self.return_future_control_output:
            for comp in problem.components:
                for out_name in comp.control_outputs:
                    outputs[comp.name + sep + out_name + '_future'] = \
                        problem.get_output_trajectory(comp.name, out_name, 'periods')

        if self.return_future_state:
            for comp in problem.components:
                if hasattr(comp, 'states'):
                    for state in comp.states:
                        outputs[comp.name + sep + state + '_future'] = \
                            problem.get_output_trajectory(comp.name, state, 'timepoints')

        return outputs
