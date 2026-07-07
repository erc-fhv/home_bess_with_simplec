import pyomo.environ as pyo
from .opt_models.MILP_model_proto import MILPModelProto


class SolverError(Exception):
    """Raised when the optimization solver fails or returns infeasible."""
    pass


class OptimizationProblem:
    """Pure Pyomo optimization problem builder and solver.

    Owns the ConcreteModel, handles adding MILP sub-models as Blocks,
    wires shared-variable coupling (sum-to-zero constraints), and solves.

    No knowledge of SimPlEC, forecasters, or time-stepping — just Pyomo.

    Parameters
    ----------
    n_periods : int
        Length of optimization horizon
    delta_t : int
        Timestep in seconds
    pyo_solver_name : str
        Name of a Pyomo solver (passed to pyo.SolverFactory)
    pprint_model_file : str or None
        If set, pretty-print the model to this path on first solve
    """

    def __init__(self, n_periods: int, delta_t: int,
                 pyo_solver_name: str = 'appsi_highs',
                 pprint_model_file: str | None = None):
        self.n_periods = n_periods
        self.delta_t = delta_t
        self.pprint_model_file = pprint_model_file

        self.solver = pyo.SolverFactory(pyo_solver_name)

        self.model = pyo.ConcreteModel()
        self.model.timepoints = pyo.RangeSet(0, n_periods)
        self.model.periods = pyo.RangeSet(0, n_periods - 1)
        self.model.delta_t = pyo.Param(initialize=delta_t)

        self.components: list[MILPModelProto] = []
        self._shared_vars: set[str] = set()
        self._is_first_solve = True

    def add_component(self, component: MILPModelProto):
        """Add a MILP sub-model as a Pyomo Block and wire shared-variable coupling.

        Parameters
        ----------
        component : MILPModelProto
            Must implement the MILPModelProto protocol (name, state_inputs,
            forecast_inputs, control_outputs, shares, pyo_block_rule).
        """
        self.components.append(component)
        self.model.add_component(
            component.name,
            pyo.Block(rule=component.pyo_block_rule),
        )

        # Wire shared-variable sum-to-zero coupling
        for shared in component.shares:
            if shared not in self._shared_vars:
                self._shared_vars.add(shared)
                self.model.add_component(
                    f'sum_expr_{shared}',
                    pyo.Expression(self.model.periods, rule=0),
                )
                rule = lambda m, p, s=shared: m.find_component(f'sum_expr_{s}')[p] == 0
                self.model.add_component(
                    f'sum_constraint_{shared}',
                    pyo.Constraint(self.model.periods, rule=rule),
                )

            comp_block = self.model.find_component(component.name)
            shared_attr = comp_block.find_component(shared)
            for p in self.model.periods:
                self.model.find_component(f'sum_expr_{shared}')[p] += shared_attr[p]

    def set_state(self, component_name: str, var_name: str, value):
        """Set a mutable Param (state) on a component's Pyomo Block.

        Parameters
        ----------
        component_name : str
            Name of the component (as registered via add_component)
        var_name : str
            Name of the state_input Param on the Block
        value : scalar
            Value to set
        """
        block = self.model.find_component(component_name)
        setattr(block, var_name, value)

    def set_forecast(self, component_name: str, var_name: str, values: list):
        """Set indexed mutable Param (forecast) on a component's Pyomo Block.

        Parameters
        ----------
        component_name : str
            Name of the component
        var_name : str
            Name of the forcast_input indexed Param on the Block
        values : list
            Values indexed by period (length must match n_periods)
        """
        block = self.model.find_component(component_name)
        param = getattr(block, var_name)
        for p in self.model.periods:
            param[p] = values[p]

    def solve(self):
        """Solve the optimization problem.

        Raises
        ------
        SolverError
            If the solver does not return an optimal solution.
        """
        if self._is_first_solve and self.pprint_model_file:
            with open(self.pprint_model_file, 'w') as f:
                self.model.pprint(f)
        self._is_first_solve = False

        try:
            result = self.solver.solve(self.model)
        except RuntimeError as e:
            raise SolverError(str(e)) from e

        # Check solver status
        condition = result.solver.termination_condition
        if condition != pyo.TerminationCondition.optimal:
            raise SolverError(
                f'Solver terminated with condition: {condition}. '
                f'Status: {result.solver.status}'
            )

    def get_output(self, component_name: str, var_name: str, period: int = 0) -> float:
        """Read a single value from a component's output variable.

        Parameters
        ----------
        component_name : str
            Name of the component
        var_name : str
            Name of the controll_output Var on the Block
        period : int
            Period index to read (default 0 — current period for MPC)
        """
        block = self.model.find_component(component_name)
        return pyo.value(getattr(block, var_name)[period])

    def get_output_trajectory(self, component_name: str, var_name: str,
                              index_set: str = 'periods') -> list:
        """Read full trajectory of a variable across all periods or timepoints.

        Parameters
        ----------
        component_name : str
            Name of the component
        var_name : str
            Name of the Var on the Block
        index_set : str
            'periods' or 'timepoints' — which index set to iterate over
        """
        block = self.model.find_component(component_name)
        var = getattr(block, var_name)
        indices = self.model.periods if index_set == 'periods' else self.model.timepoints
        return [pyo.value(var[i]) for i in indices]
