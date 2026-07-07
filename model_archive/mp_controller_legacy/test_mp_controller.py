from models.mp_controller.mp_controller import MPController
from models.mp_controller.optimization_problem import OptimizationProblem
from models.mp_controller.opt_models.battery_storage import BatteryStorageModel
from models.mp_controller.opt_models.energy_community import ResidualLoadModel
from models.mp_controller.opt_models.objective import Objective
from models.mp_controller.forecasting import GenericPersistenceForecasting
import pyomo.environ as pyo


# ---- OptimizationProblem tests (pure Pyomo, no SimPlEC) ----

def test_OptimizationProblem_init():
    prob = OptimizationProblem(n_periods=3, delta_t=60*15)

    assert isinstance(prob.model, pyo.ConcreteModel)
    assert isinstance(prob.model.periods, pyo.RangeSet)
    assert isinstance(prob.model.timepoints, pyo.RangeSet)
    assert isinstance(prob.model.delta_t, pyo.Param)


def test_OptimizationProblem_add_component():
    class ComponentMock():
        name = 'comp'
        state_inputs = ['a']
        forecast_inputs = []
        shares = ['P_el']
        control_outputs = []
        def pyo_block_rule(self, block):
            block.P_el = pyo.Var(block.model().periods)

    prob = OptimizationProblem(n_periods=3, delta_t=60*15)
    cm = ComponentMock()
    prob.add_component(cm)

    assert cm in prob.components
    assert hasattr(prob.model, 'comp')
    assert isinstance(prob.model.comp, pyo.Block)


def test_OptimizationProblem_solve():
    """Test solving a simple problem: BES + EC + Objective."""
    prob = OptimizationProblem(n_periods=3, delta_t=1)

    prob.add_component(Objective('objective', objective='self-consumption'))
    prob.add_component(ResidualLoadModel())
    prob.add_component(BatteryStorageModel('BES', E_min=0, E_max=5,
                                           P_max_cha=1, P_max_dis=1,
                                           eta_cha=1, eta_dis=1))

    prob.set_state('BES', 'E_BES_0', 2)
    prob.set_forecast('EC', 'P_resid', [1, 0, 0])
    prob.solve()

    assert prob.get_output('BES', 'P_el', period=0) == -1.


def test_OptimizationProblem_solver_error():
    """Test that infeasible problems raise SolverError."""
    import pytest
    from models.mp_controller.optimization_problem import SolverError

    prob = OptimizationProblem(n_periods=1, delta_t=1)
    prob.add_component(Objective('objective', objective='self-consumption'))

    class InfeasibleModel:
        name = 'bad'
        state_inputs = []
        forecast_inputs = []
        control_outputs = []
        shares = []
        def pyo_block_rule(self, block):
            model = block.model()
            block.x = pyo.Var(model.periods, bounds=(0, 5))
            @block.Constraint(model.periods)
            def impossible(b, p):
                return b.x[p] >= 10

    prob.add_component(InfeasibleModel())

    with pytest.raises(SolverError):
        prob.solve()


# ---- MPController tests (DI API) ----

def test_MPController_init():
    """Test MPController auto-derives inputs and outputs."""
    prob = OptimizationProblem(n_periods=3, delta_t=1)
    prob.add_component(Objective('objective', objective='self-consumption'))
    prob.add_component(ResidualLoadModel())
    prob.add_component(BatteryStorageModel('BES', E_min=0, E_max=5,
                                           P_max_cha=1, P_max_dis=1,
                                           eta_cha=1, eta_dis=1))

    class ForecastingMock:
        inputs = []
        def get_forecast(self, time): return [1, 0, 0]
        def set_data(self, time): pass
        def set_forecast_length(self, n): pass

    ctr = MPController(
        name='mpc', delta_t=1,
        problem=prob,
        forecasters={'EC.P_resid': ForecastingMock()},
    )

    assert 'BES.E_BES_0' in ctr.inputs
    assert 'BES.P_el' in ctr.outputs

    outputs = ctr.step(1, **{'BES.E_BES_0': 2})

    assert 'BES.P_el' in outputs
    assert outputs['BES.P_el'] == -1.


def test_MPController_with_real_forecaster():
    """Test MPController with GenericPersistenceForecasting."""
    prob = OptimizationProblem(n_periods=3, delta_t=1)
    prob.add_component(Objective('objective', objective='self-consumption'))
    prob.add_component(ResidualLoadModel())
    prob.add_component(BatteryStorageModel('BES', E_min=0, E_max=5,
                                           P_max_cha=1, P_max_dis=1,
                                           eta_cha=1, eta_dis=1))

    fc = GenericPersistenceForecasting(inpt='P_ec', delay=1, init_val=0)

    ctr = MPController(
        name='mpc', delta_t=1,
        problem=prob,
        forecasters={'EC.P_resid': fc},
    )

    inp = {'BES.E_BES_0': 2, 'EC.forecast.P_ec': 1}
    outputs = ctr.step(1, **inp)
    assert outputs['BES.P_el'] == 0.

    outputs = ctr.step(2, **inp)
    assert outputs['BES.P_el'] == 0.

    outputs = ctr.step(3, **inp)
    assert outputs['BES.P_el'] == 0.


def test_MPController_forecaster_integration():
    """Test MPController with a forecaster that receives input data."""
    prob = OptimizationProblem(n_periods=3, delta_t=1)
    prob.add_component(Objective('objective', objective='self-consumption'))
    prob.add_component(ResidualLoadModel())
    prob.add_component(BatteryStorageModel('BES', E_min=0, E_max=5,
                                           P_max_cha=1, P_max_dis=1,
                                           eta_cha=1, eta_dis=1))

    class ForecastingMock:
        def __init__(self):
            self.inputs = ['data']
            self.data = []
        def get_forecast(self, time) -> list:
            return self.data
        def set_data(self, time, data):
            assert len(data) == self.n_periods
            self.data = data
        def set_forecast_length(self, n):
            self.n_periods = n

    ctr = MPController(
        name='mpc', delta_t=1,
        problem=prob,
        forecasters={'EC.P_resid': ForecastingMock()},
    )

    outputs = ctr.step(1, **{'BES.E_BES_0': 2, 'EC.forecast.data': [1, 0, 0]})
    assert outputs['BES.P_el'] == -1.
