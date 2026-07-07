import numpy as np
import pyomo.environ as pyo
import pytest

from models.optimization_core.bess import BESSParams, bess_block_rule


def _make_model(params: BESSParams, n_periods: int = 1, delta_t_s: int = 3600):
    """Minimal ConcreteModel with a single BESS block for testing."""
    m = pyo.ConcreteModel()
    m.timepoints = pyo.RangeSet(0, n_periods)
    m.periods    = pyo.RangeSet(0, n_periods - 1)
    m.delta_t    = pyo.Param(initialize=delta_t_s)
    m.bes        = pyo.Block(rule=bess_block_rule(params))
    return m


@pytest.fixture
def default_params():
    return BESSParams(
        E_min_kWh=0.0, E_max_kWh=10.0,
        P_max_cha_kW=5.0, P_max_dis_kW=5.0,
        eta_cha=1.0, eta_dis=1.0,
        E_0_kWh=0.0,
    )


def test_energy_balance_1h_charging(default_params):
    """P_cha=1 kW, delta_t=3600 s, eta_cha=1.0, E[0]=0 → E[1]=1 kWh."""
    m = _make_model(default_params, n_periods=1, delta_t_s=3600)

    m.bes.P_cha[0].fix(1.0)
    m.bes.P_dis[0].fix(0.0)
    m.bes.u_cha[0].fix(1)
    m.obj = pyo.Objective(expr=0)   # constant objective — just need feasibility

    solver = pyo.SolverFactory('highs')
    solver.solve(m)

    assert np.isclose(pyo.value(m.bes.E[1]), 1.0, atol=1e-6)


def test_energy_balance_15min_charging(default_params):
    """P_cha=4 kW, delta_t=900 s, eta_cha=1.0, E[0]=0 → E[1]=1 kWh."""
    m = _make_model(default_params, n_periods=1, delta_t_s=900)

    m.bes.P_cha[0].fix(4.0)
    m.bes.P_dis[0].fix(0.0)
    m.bes.u_cha[0].fix(1)
    m.obj = pyo.Objective(expr=0)

    solver = pyo.SolverFactory('highs')
    solver.solve(m)

    assert np.isclose(pyo.value(m.bes.E[1]), 1.0, atol=1e-6)


def test_E0_set_value_updates_initial_condition(default_params):
    """E_0.set_value() correctly updates the initial condition param."""
    m = _make_model(default_params)

    assert pyo.value(m.bes.E_0) == 0.0

    m.bes.E_0.set_value(3.5)
    assert pyo.value(m.bes.E_0) == 3.5

    # Solve and verify E[0] respects the updated initial condition
    m.bes.P_cha[0].fix(0.0)
    m.bes.P_dis[0].fix(0.0)
    m.bes.u_cha[0].fix(1)
    m.obj = pyo.Objective(expr=0)

    solver = pyo.SolverFactory('highs')
    solver.solve(m)

    assert np.isclose(pyo.value(m.bes.E[0]), 3.5, atol=1e-6)


def test_binary_prevents_simultaneous_discharge():
    """u_cha=1 forces P_dis=0 via dis_limit constraint."""
    params = BESSParams(
        E_max_kWh=10.0, P_max_cha_kW=5.0, P_max_dis_kW=5.0,
        eta_cha=1.0, eta_dis=1.0, E_0_kWh=5.0,
    )
    m = _make_model(params, n_periods=1, delta_t_s=3600)

    m.bes.u_cha[0].fix(1)
    # Maximise charging to drive the solver away from trivial zero solution
    m.obj = pyo.Objective(expr=-m.bes.P_cha[0])

    solver = pyo.SolverFactory('highs')
    solver.solve(m)

    assert pyo.value(m.bes.P_dis[0]) < 1e-6
