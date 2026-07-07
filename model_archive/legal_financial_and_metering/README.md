# Legal, Financial and Metering Models

This module contains billing-related models for energy community simulations.
The models are designed for SimPlEC duck typing (`name`, `delta_t`, `inputs`, `outputs`, `step`).

## Overview

- **SmartMeter** (`smart_meter.py`): aggregates multiple power inputs to one grid exchange signal (`P_grid`).
- **DistributionSystemOperatorECAware** (`distribution_system_operator.py`):
  - splits participant power into internally traded EC power (`P_ec`) and residual grid exchange (`P_residual`)
  - computes participant-specific grid fees (`grid_fee_dict`)
- **EnergyCommunity** (`energy_community.py`): calculates EC market costs/revenues (`cost_dict`) and EC operator profit (`profit_ec`) from `P_ec`.
- **ElectricUtilityCompany** (`electric_utility_company.py`): calculates external supplier costs/revenues (`cost_dict`) from `P_residual`.
  - Provides `consumption_price` and `feedin_price` outputs with current prices in €/kWh.
  - Supports static price series.
  - Optionally supports ENTSO-E day-ahead prices (cached), with configurable zone/span and absolute offsets for consumption/feed-in prices.
- **Participant** (`participant.py`): sums all connected cost components (`c_`) into total bill (`c_tot`).
- **Helper** (`helper.py`): convenience wiring via `add_participant_model_and_connect(...)`.

## Interaction and Data Flow

Typical setup for EC participants:

1. `SmartMeter` reports participant power to DSO as `P_el_ec_dict`.
2. `DistributionSystemOperatorECAware` computes:
   - `P_ec` (intra-EC traded power)
   - `P_residual` (power settled with utility)
   - `grid_fee_dict` (participant-specific grid fee components)
3. `EnergyCommunity` prices `P_ec` and outputs `cost_dict`.
4. `ElectricUtilityCompany` prices `P_residual` and outputs `cost_dict`.
5. `Participant` receives all cost streams through multi-input `c_` and returns `c_tot`.

## Ports and Naming Convention

- Multi-input conventions are used where names end with `_` (e.g. `c_`).
- Participant bill IDs are matched via suffixing (`_bill` by default).
  - Example: smart meter `consumer_1` maps to participant `consumer_1_bill`.

## Units and Sign Convention

- **Power**: `P_*` in **W**.
- **Prices**: in **€/kWh**.
- **Costs**: per simulation step, using
  \[
  c = p_{€/kWh} \cdot P_{W} \cdot \Delta t_{s} / (1000 \cdot 3600)
  \]
- Sign convention:
  - `P > 0`: consumption/import
  - `P < 0`: generation/export

## Utility Company: Optional ENTSO-E Day-Ahead Integration

`ElectricUtilityCompany` can run in two modes:

1. **Static mode** (default): pass `price_consumption` and `price_feedin` as `pd.Series`.
2. **ENTSO-E mode**: set `use_entsoe_day_ahead=True` and provide:
   - `entsoe_zone` (e.g. `AT`)
   - `download_start`, `download_end` (explicit datetime span)
   - optional `offset_consumption_eur_per_kwh`, `offset_feedin_eur_per_kwh`
   - optional `entsoe_credentials_path`

Token handling:

- Expected key in credentials JSON: `Entsoe-Token`
- Default path: one level above repository root (`../credentials.json`)

Caching:

- Download helper is decorated with `util.cache_manager.cache_result()`.
- Repeated calls with identical arguments reuse cached results.

## Minimal Wiring Pattern

```python
# connect dso and ec_operator and dso and utility company once
sim.connect(dso, ec_operator, ('P_ec', 'P_el'))
sim.connect(dso, utility_company, ('P_residual', 'P_el'))

# connections for each participant:
participant = sim.add_model(Participant(smart_meter.name + '_bill', delta_t=15*60))
sim.connect(smart_meter, dso, ('P_grid', 'P_el_ec_dict'))
sim.connect(ec_operator, participant, ('cost_dict', 'c_'))
sim.connect(utility_company, participant, ('cost_dict', 'c_'))
sim.connect(dso, participant, ('grid_fee_dict', 'c_'))
```

For a complete executable example, see `test_scenario_legal_and_financial.py`.
