import pandas as pd
import pyomo.environ as pyo
from pyomo.opt import SolverFactory

from models.optimization_core.bess import BESSParams, bess_rule
from models.mp_controller_homebattery.forecasting import ResidualForecaster


class MpController:
    """
    Rolling MPC controller with dynamic horizon for home battery.

    The net-load forecast and horizon are fully delegated to a *forecaster*
    object passed at construction time.  Use :class:`GamResidualForecaster` for the
    default GAM-based forecast or :class:`PerfectResidualForecaster` for an upper-bound, both from
    ``models.mp_controller_homebattery.forecasting``.
    """

    def __init__(
        self,
        name: str,
        delta_t: int,
        bes_params: BESSParams,
        utility_company,
        forecaster: ResidualForecaster,
        mpc_period: str = '15min',
        ):

        self.name = name
        self.delta_t = delta_t
        self._bes_params = bes_params
        self._utility = utility_company
        self._forecaster = forecaster
        self._mpc_period = pd.Timedelta(mpc_period)

        self.inputs = [
            'bes_E',               # float, J — current battery energy
        ]
        self.outputs = [
            'P_grid_set',          # float, W — desired grid power (positive=buy)
            'P_bat_set',           # float, W — desired battery power (positive=charge)
            'P_residual_forecast', # float, W
            'horizon_length',      # int, number of periods in the current optimization horizon
        ]

        self._solver = SolverFactory('highs')
        self._models: dict[int, pyo.ConcreteModel] = {}

        self._last_opt_time: pd.Timestamp | None = None
        self._plan_P_grid_set: dict[pd.Timestamp, float] = {}
        self._plan_P_bat_set: dict[pd.Timestamp, float] = {}
        self._plan_P_residual: dict[pd.Timestamp, float] = {}
        self._cached_horizon_length: int = 0

    def _get_model(self, n: int) -> pyo.ConcreteModel:
        """Return a Pyomo model for *n* periods, building & caching on first use."""
        if n not in self._models:
            m = pyo.ConcreteModel()
            m.timepoints = pyo.RangeSet(0, n)
            m.periods    = pyo.RangeSet(0, n - 1)
            m.delta_t    = pyo.Param(initialize=self.delta_t)

            m.bes = pyo.Block(rule=bess_rule(self._bes_params))

            m.P_resid = pyo.Param(m.periods, mutable=True, initialize=0.0, domain=pyo.Reals)
            m.c_buy   = pyo.Param(m.periods, mutable=True, initialize=0.0, domain=pyo.Reals)
            m.c_sell  = pyo.Param(m.periods, mutable=True, initialize=0.0, domain=pyo.Reals)

            m.P_buy  = pyo.Var(m.periods, domain=pyo.NonNegativeReals)
            m.P_sell = pyo.Var(m.periods, domain=pyo.NonNegativeReals)

            @m.Constraint(m.periods)
            def power_balance(m, p):
                # P_bat > 0 = charge (consumption), P_bat < 0 = discharge (generation)
                # Sources: P_buy + discharge = Sinks: P_resid + P_sell + charge
                # → P_buy - P_bat - P_resid - P_sell = 0
                return m.P_buy[p] - m.bes.P_bat[p] - m.P_resid[p] - m.P_sell[p] == 0.0

            @m.Objective(sense=pyo.minimize)
            def cost(m):
                return sum(
                    (m.c_buy[p] * m.P_buy[p] - m.c_sell[p] * m.P_sell[p])
                    * (m.delta_t / 3600.0)
                    for p in m.periods
                )

            self._models[n] = m
        return self._models[n]

    def step(self, time, bes_E) -> dict:

        needs_reopt = (
            self._last_opt_time is None
            or (time - self._last_opt_time) >= self._mpc_period
        )

        if needs_reopt:
            # Forecast → net-load in kW for the optimisation horizon
            forecast_kw = self._forecaster.forecast(time)

            # Prices for the same horizon [time, horizon_end]
            horizon_end = forecast_kw.index[-1]
            prices_buy = self._utility.get_price_buy_horizon(time, horizon_end)
            prices_sell = self._utility.get_price_sell_horizon(time, horizon_end)

            n = len(forecast_kw)
            assert len(prices_buy) == n, (
                f"prices_buy has {len(prices_buy)} values, expected {n} "
                f"for [{time}, {horizon_end}). Download more EPEX prices?"
            )
            assert len(prices_sell) == n

            assert (prices_buy > prices_sell).all(), (
                f"price_buy must exceed price_sell (arbitrage-free), "
                f"violations at: {prices_buy[prices_buy <= prices_sell].index.tolist()}"
                f"Please add a grid-power mutex constraint to the optimization model."
            )

            forecast_kw_vals = forecast_kw.values

            m = self._get_model(n)
            m.bes.E_0.set_value(bes_E / 3_600_000)
            for t in range(n):
                m.P_resid[t].set_value(float(forecast_kw_vals[t]))
                m.c_buy[t].set_value(float(prices_buy.iloc[t]))
                m.c_sell[t].set_value(float(prices_sell.iloc[t]))

            self._solver.solve(m)

            # Store full plan for all timesteps in the horizon
            for t_idx, ts in enumerate(forecast_kw.index):
                self._plan_P_grid_set[ts] = (
                    (pyo.value(m.P_buy[t_idx]) - pyo.value(m.P_sell[t_idx])) * 1000.0
                )
                self._plan_P_bat_set[ts] = pyo.value(m.bes.P_bat[t_idx]) * 1000.0
                self._plan_P_residual[ts] = float(forecast_kw_vals[t_idx]) * 1000.0
            self._cached_horizon_length = n
            self._last_opt_time = time

        return {
            'P_grid_set':          self._plan_P_grid_set[time],
            'P_bat_set':           self._plan_P_bat_set[time],
            'P_residual_forecast': self._plan_P_residual[time],
            'horizon_length':      self._cached_horizon_length,
        }
