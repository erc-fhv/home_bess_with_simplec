# FlECs-Framework — Copilot Instructions

## Architecture

FlECs is a Python cosimulation framework for energy community scenarios (buildings, PV, heat pumps, batteries, controllers, metering/billing). **SimPlEC** (`simplec` package) is the orchestration engine — it resolves execution order, routes data between models, and handles time-stepping.

### Key directories

| Path | Purpose |
|---|---|
| `models/<component>/` | Self-contained model packages (logic + tests) |
| `scenarios/` | Scenario scripts that wire models via SimPlEC |
| `data/output/` | Parquet simulation results (`<scenario>/<sub>/<timestamp>.parquet`) |
| `data_explorer/` | Dash-based interactive dashboard for result inspection |
| `util/` | Shared utilities (caching, plotting styles) |
| `prep/`, `post/` | Pre-/post-processing notebooks |

## Model Interface (duck-typed, no base class)

Every model must expose these attributes and a `step()` method — SimPlEC discovers them via structural typing:

```python
class MyModel:
    name: str          # unique identifier
    delta_t: int       # timestep in seconds
    inputs: list[str]  # input port names
    outputs: list[str] # output port names

    def step(self, time: pd.Timestamp, **inputs) -> dict[str, Any]:
        ...  # return {output_name: value}
```

- **Multi-inputs**: names ending with `_` (e.g. `P_`, `c_`) receive aggregated lists from multiple connections.
- **Dict multi-inputs**: names ending with `_dict` (e.g. `P_el_dict`) receive dictionaries keyed by source model name.
- **Dict outputs for routing**: names ending with `_dict` can route per-recipient values keyed by target model name.
- **Event-based models**: return `'next_exec_time'` in the output dict to schedule next execution (e.g. heat pump).
- **Time-series models** (PV, household): preload a DataFrame at init; `step()` is just a table lookup.

## Scenario Wiring Pattern

```python
sim = Simulation()
model_ref = sim.add_model(ModelClass(...), watch_values=[...])
sim.connect(source, sink, ('src_output', 'sink_input'))
sim.connect(source, sink, 'shared_name')          # when names match
sim.connect(source, sink, ..., time_shifted=True, init_values={...})  # break algebraic loops
sim.connect_constant(42.0, model, 'input_name')
sim.simulate(pd.date_range(...), output_data_path='path.parquet')
```

## Naming & Unit Conventions

- **Physical variables**: LaTeX-style — `P_el`, `E_bes`, `Q_dot_hp`, `T_is`.
- **Units**: SI base units everywhere; temperatures in °C. If non-SI is needed, append unit: `P_el_in_kW`.
- **Sign convention**: Consumption from grid is **positive** (egoistic sign convention).
- **Classes**: CamelCase. Instances can reuse the lowercase name: `building = Building(...)`. Do not append `Model`.

## Testing

- **pytest** with fixtures. Tests live next to their models: `models/<component>/test_<component>.py`.
- Unit tests instantiate a model (mocking expensive deps like pickle/API), call `step()`, assert with `np.isclose()`.
- Integration tests build mini-scenarios with `Simulation()`, run `sim.simulate(times)`, assert on `sim.df`.
- Mock models follow the same duck-typed interface (see `SmartMeterMock` pattern in legal/financial tests).

## MPC Controller (Pyomo/HiGHS)

`MPController` in `models/mp_controller/` is composable: add MILP sub-models and forecasters at init. Sub-models implement `MILPModelProto` (Protocol) with `pyo_block_rule(block)`. Shared variables (e.g. `P_el`) are coupled via sum-to-zero constraints for energy balance. Forecasters use `@Forcasting.register(name)` decorator.

## Caching

`@cache_result()` from `util/cache_manager.py` caches expensive computations (PV API calls, load profile generation). Cache key = hash of args + source code. Invalidates automatically on code or argument changes.

## Dashboard (`data_explorer/dashboard.py`)

Dash + Plotly app with a JSON config store (`dcc.Store`). Configs (axis labels, traces per subplot) can be saved/loaded from `.configs/`. The dashboard reads parquet output and renders up to 3 subplots with dual y-axes.
