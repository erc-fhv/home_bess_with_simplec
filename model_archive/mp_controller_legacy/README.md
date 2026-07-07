# MP Controller — Model Predictive Control via MILP

Receding-horizon Model Predictive Controller that solves a Mixed-Integer Linear Program (MILP) each time step using Pyomo and the HiGHS solver.

## Architecture

The module is split into two layers:

| Layer | Class | Responsibility |
|---|---|---|
| **Optimisation** | `OptimizationProblem` | Pure Pyomo: builds the model, wires shared-variable coupling, solves, reads results |
| **SimPlEC adapter** | `MPController` | Thin wrapper: routes SimPlEC inputs to forecasters/states, calls `solve()`, returns period-0 outputs |

Dependencies are injected — `MPController` receives an `OptimizationProblem` and a dict of forecasters at construction time.

```
┌─────────────────────────────────────────────────┐
│                  MPController                   │
│  (SimPlEC interface: inputs, outputs, step())   │
│                                                 │
│   forecasters ──► set_forecast()                │
│   state inputs ──► set_state()                  │
│                                                 │
│   ┌─────────────────────────────────────────┐   │
│   │         OptimizationProblem             │   │
│   │  ┌─────────┐ ┌───────────┐ ┌─────────┐ │   │
│   │  │Objective│ │ResidualLd.│ │ Battery │ │   │
│   │  └────┬────┘ └─────┬─────┘ └────┬────┘ │   │
│   │       └──── P_el ──┴──── P_el ──┘      │   │
│   │            (sum-to-zero coupling)       │   │
│   └─────────────────────────────────────────┘   │
│                                                 │
│   solve() ──► period-0 outputs                  │
└─────────────────────────────────────────────────┘
```

## File Overview

```
mp_controller/
├── mp_controller.py          # MPController — SimPlEC adapter
├── optimization_problem.py   # OptimizationProblem — Pyomo model builder/solver
├── forecasting.py            # ForecastingProto protocol + concrete forecasters
├── pyo_helpers.py            # Pyomo Block get/set helpers
├── opt_models/
│   ├── MILP_model_proto.py   # MILPModelProto — Protocol for sub-models
│   ├── battery_storage.py    # BatteryStorageModel
│   ├── dhwh.py               # DHWHeaterTemperatureModel, DHWHeaterEnergyModel
│   ├── energy_community.py   # ResidualLoadModel
│   ├── objective.py          # Objective (self-consumption / peak-power)
│   └── tests/                # Pyomo-level component tests
├── test_mp_controller.py     # Tests for OptimizationProblem + MPController
└── test_forecasting.py       # Tests for forecaster classes
```

## Sub-Model Protocol (`MILPModelProto`)

Every MILP sub-model must expose these attributes and a `pyo_block_rule` method:

```python
class MySubModel:
    name: str               # unique identifier
    state_inputs: list[str]     # mutable Params set each step (initial conditions)
    forecast_inputs: list[str]  # indexed mutable Params updated each step
    control_outputs: list[str]  # Vars whose period-0 values are returned to SimPlEC
    shares: list[str]           # Vars coupled via sum-to-zero across components

    def pyo_block_rule(self, block: pyo.Block) -> None:
        """Define Params, Vars, and Constraints on the block."""
        ...
```

**Shared variables** (listed in `shares`) are automatically coupled across all components via sum-to-zero constraints. This is how energy balance is enforced — e.g. all `P_el` contributions must sum to zero.

**Sign convention**: egoistic — consumption is positive, feed-in is negative.

## Available Sub-Models

| Class | Module | State | Forecast | Control Output | Shares |
|---|---|---|---|---|---|
| `BatteryStorageModel` | `battery_storage` | `E_BES_0` | — | `P_el` | `P_el` |
| `DHWHeaterTemperatureModel` | `dhwh` | `T_tes_0` | `dot_Q_demand` | `on` | `P_el` |
| `DHWHeaterEnergyModel` | `dhwh` | `E_tes_0` | `dot_Q_demand` | `on` | `P_el` |
| `ResidualLoadModel` | `energy_community` | — | `P_resid` | — | `P_el` |
| `Objective` | `objective` | — | — | `P_el` | `P_el` |

## Forecasting Protocol (`ForecastingProto`)

Forecasters are injected into `MPController` as a dict keyed by `'component.forecast_var'`:

```python
class ForecastingProto(Protocol):
    inputs: list[str]                        # SimPlEC-routed input names
    def set_forecast_length(self, n: int) -> None: ...
    def set_data(self, time, **inputs) -> None: ...
    def get_forecast(self, time) -> list: ...
```

Concrete implementations:

- **`GenericPersistenceForecasting`** — ring-buffer persistence forecaster for a single variable

## Usage Example

```python
from models.mp_controller.mp_controller import MPController
from models.mp_controller.optimization_problem import OptimizationProblem
from models.mp_controller.opt_models.battery_storage import BatteryStorageModel
from models.mp_controller.opt_models.energy_community import ResidualLoadModel
from models.mp_controller.opt_models.objective import Objective
from models.mp_controller.forecasting import GenericPersistenceForecasting

# 1. Build the optimization problem (pure Pyomo)
prob = OptimizationProblem(n_periods=96, delta_t=900)  # 24h at 15 min

prob.add_component(Objective('objective', objective='self-consumption'))
prob.add_component(ResidualLoadModel())
prob.add_component(BatteryStorageModel('BES', E_min=0, E_max=36_000_000,
                                       P_max_cha=5_000, P_max_dis=5_000))

# 2. Create forecasters
fc = GenericPersistenceForecasting(inpt='P_resid_meas', delay=1, init_val=0)

# 3. Wire into SimPlEC via MPController
ctr = MPController(
    name='mpc', delta_t=900,
    problem=prob,
    forecasters={'EC.P_resid': fc},
)

# 4. Use in a SimPlEC simulation
sim = Simulation()
mpc_ref = sim.add_model(ctr, watch_values=['BES.P_el'])
# ... connect state inputs, forecast inputs, control outputs ...
sim.simulate(times, output_data_path='output.parquet')
```

## Testing
Tests are structured in two tiers:

1. **Component tests** (`opt_models/tests/`) — instantiate a single sub-model in a standalone Pyomo model with a trivial objective, solve, and assert variable values.
2. **Integration tests** (`test_mp_controller.py`) — build an `OptimizationProblem` with multiple components, test `solve()` and `MPController.step()` end-to-end.
