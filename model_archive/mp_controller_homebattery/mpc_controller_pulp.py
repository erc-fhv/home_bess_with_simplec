"""PuLP-based MPC controller — drop-in replacement for mpc_controller.py (Pyomo/HiGHS).

Uses the same MILP formulation as the real-system PuLP optimizer for A/B comparison.
"""

import numpy as np
import pandas as pd
import pulp

from models.optimization_core.bess import BESSParams
from models.mp_controller_homebattery.forecasting import ResidualForecaster

class MpController:
    """
    Rolling MPC controller with dynamic horizon for home battery (PuLP/CBC variant).

    The net-load forecast and horizon are fully delegated to a *forecaster*
    object passed at construction time.  Use :class:`GamResidualForecaster` for
    the default GAM-based forecast or :class:`PerfectResidualForecaster` for an
    oracle upper-bound, both from
    ``models.mp_controller_homebattery.forecasting``.
    """

    def __init__(
        self,
        name: str,
        delta_t: int,
        bes_params: BESSParams,
        utility_company,
        forecaster: ResidualForecaster,
        ):

        self.name = name
        self.delta_t = delta_t
        self._bes_params = bes_params
        self._utility = utility_company
        self._forecaster = forecaster

        self.inputs = [
            'bes_E',               # float, J — current battery energy
        ]
        self.outputs = [
            'P_grid_set',          # float, W — desired grid power (positive=buy)
            'P_residual_forecast', # float, W
            'horizon_length',      # int, number of periods in the current optimization horizon
        ]

    def step(self, time, bes_E) -> dict:

        # Forecast → net-load in kW for the optimisation horizon
        forecast_kw = self._forecaster.forecast(time)

        # Prices for the same horizon [time, horizon_end)
        horizon_end = forecast_kw.index[-1]
        prices_buy = self._utility.get_price_buy_horizon(time, horizon_end)
        prices_sell = self._utility.get_price_sell_horizon(time, horizon_end)

        n = len(forecast_kw)
        assert len(prices_buy) == n, (
            f"prices_buy has {len(prices_buy)} values, expected {n} "
            f"for [{time}, {horizon_end}). Download more EPEX prices?"
        )
        assert len(prices_sell) == n

        # --- PuLP MILP (identical to real-system optimizer) ---
        bp = self._bes_params
        capacity_kwh = bp.E_max_kWh
        soc_min_kwh = bp.E_min_kWh
        soc_max_kwh = bp.E_max_kWh
        max_charge_kw = bp.P_max_cha_kW
        max_discharge_kw = bp.P_max_dis_kW
        eta_charge = bp.eta_cha
        eta_discharge = bp.eta_dis
        delta_t_h = self.delta_t / 3600.0

        soc_init_kwh = float(np.clip(
            bes_E / 3_600_000,
            soc_min_kwh,
            soc_max_kwh,
        ))
        soc_final_kwh = float(np.clip(
            bp.E_final_percent / 100.0 * capacity_kwh,
            soc_min_kwh,
            soc_max_kwh,
        ))

        T = range(n + 1)   # n+1 SOC timepoints
        P = range(n)        # n periods

        model = pulp.LpProblem("MPC_BESS", pulp.LpMaximize)

        p_ch_kw  = pulp.LpVariable.dicts("p_ch",  P, 0, max_charge_kw)
        p_dis_kw = pulp.LpVariable.dicts("p_dis", P, 0, max_discharge_kw)
        soc_kwh  = pulp.LpVariable.dicts("soc",   T, soc_min_kwh, soc_max_kwh)
        p_sell_kw = pulp.LpVariable.dicts("p_sell", P, 0)
        p_buy_kw  = pulp.LpVariable.dicts("p_buy",  P, 0)
        y = pulp.LpVariable.dicts("y", P, 0, 1, cat="Binary")

        # Initial and final SOC
        model += soc_kwh[0] == soc_init_kwh
        model += soc_kwh[T[-1]] == soc_final_kwh

        # SOC dynamics
        for t in range(1, n + 1):
            model += soc_kwh[t] == soc_kwh[t - 1] + \
                delta_t_h * (eta_charge * p_ch_kw[t - 1] - p_dis_kw[t - 1] / eta_discharge)

        # Explicit SOC bounds
        for t in T:
            model += soc_kwh[t] <= soc_max_kwh
            model += soc_kwh[t] >= soc_min_kwh

        # Charge/discharge exclusivity
        for p in P:
            model += p_ch_kw[p]  <= max_charge_kw * y[p]
            model += p_dis_kw[p] <= max_discharge_kw * (1 - y[p])

        # Power balance (identical to real system)
        for p in P:
            model += (
                p_buy_kw[p] + p_dis_kw[p]
                ==
                forecast_kw.iloc[p] + p_sell_kw[p] + p_ch_kw[p]
            )

        # Objective: maximize profit
        model += pulp.lpSum(
            (prices_sell.iloc[p] * p_sell_kw[p]
             - prices_buy.iloc[p] * p_buy_kw[p]) * delta_t_h
            for p in P
        )

        # model.solve(pulp.PULP_CBC_CMD(msg=False))
        model.solve(pulp.apis.HiGHS(msg=False))
        if model.status != pulp.constants.LpStatusOptimal:
            raise ValueError(
                f"MILP nicht optimal gelöst (Status: {pulp.LpStatus[model.status]}). "
                f"SOC_init={soc_init_kwh:.3f} kWh, SOC_final={soc_final_kwh:.3f} kWh"
            )

        P_grid_set_kw = p_buy_kw[0].value() - p_sell_kw[0].value()

        return {
            'P_grid_set':          P_grid_set_kw * 1000.0,
            'P_residual_forecast': float(forecast_kw.iloc[0]) * 1000.0,
            'horizon_length':      n,
        }
