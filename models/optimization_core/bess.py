from dataclasses import dataclass

import pyomo.environ as pyo

from models.optimization_core.helpers import require_parent_sets


@dataclass(frozen=True)
class BESSParams:
    E_min_kWh: float = 0.0
    E_max_kWh: float = 1.0
    P_max_cha_kW: float = 1.0
    P_max_dis_kW: float = 1.0
    eta_cha: float = 1.0
    eta_dis: float = 1.0
    E_0_kWh: float = 0.0
    E_final_percent: float = 50.0


def bess_rule(params: BESSParams):
    """Return a Pyomo block rule closure for a BESS.

    Usage:
        model.community_bes = pyo.Block(rule=bess_rule(params))
    """
    def _rule(block: pyo.Block) -> pyo.Block:

        timepoints, periods, delta_t = require_parent_sets(block)

        # mutable E_0 Param (updated each MPC step)
        block.E_0 = pyo.Param(
            mutable=True, initialize=params.E_0_kWh,
            domain=pyo.NonNegativeReals,
        )

        # decision variables
        block.E = pyo.Var(
            timepoints, domain=pyo.NonNegativeReals,
            bounds=(params.E_min_kWh, params.E_max_kWh),
        )
        block.P_bat = pyo.Var(periods, domain=pyo.Reals)          # kW, consumption-positive
        block.P_cha = pyo.Var(periods, domain=pyo.NonNegativeReals,
                              bounds=(0, params.P_max_cha_kW))
        block.P_dis = pyo.Var(periods, domain=pyo.NonNegativeReals,
                              bounds=(0, params.P_max_dis_kW))
        block.y = pyo.Var(periods, domain=pyo.Binary)             # 1 = charging, 0 = discharging

        # constraints
        @block.Constraint(periods)
        def cha_exclusivity(b, t):
            return b.P_cha[t] <= params.P_max_cha_kW * b.y[t]

        @block.Constraint(periods)
        def dis_exclusivity(b, t):
            return b.P_dis[t] <= params.P_max_dis_kW * (1 - b.y[t])
        @block.Constraint(periods)
        def energy_balance(b, t):
            return (
                b.E[t + 1]
                == b.E[t]
                + (b.P_cha[t] * params.eta_cha - b.P_dis[t] / params.eta_dis)
                * (delta_t / 3600.0)
            )

        @block.Constraint(periods)
        def net_power(b, t):
            return b.P_bat[t] == b.P_cha[t] - b.P_dis[t]

        @block.Constraint()
        def initial_condition(b):
            return b.E[timepoints.first()] == b.E_0

        @block.Constraint()
        def final_condition(b):
            return b.E[timepoints.last()] == params.E_final_percent / 100.0 * params.E_max_kWh

        return block

    return _rule
