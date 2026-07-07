# Heat Pump Models

Event-based heat pump models for SimPlEC scenarios, including a simplified COP approach and a thermodynamic refrigerant-cycle approach with optional electrical power control.

## Overview

This module currently provides four variants:

- `HeatPumpEventBased`: simple COP model with fixed nominal electrical power.
- `HeatPumpWControlEventBased`: simple COP model with electrical power clipping (`P_el_min` ... `P_el_max`) around a nominal thermal target.
- `HeatPumpCoolingcircleEventBased`: refrigerant-cycle model (CoolProp) with fixed nominal electrical power.
- `HeatPumpCoolingcircleWControl`: refrigerant-cycle model (CoolProp) with electrical power clipping (`P_el_min` ... `P_el_max`) around a nominal thermal target.

All classes follow the SimPlEC duck-typed interface (`name`, `delta_t`, `inputs`, `outputs`, `step`).

## File Overview

```text
heat_pump/
├── heat_pump.py          # Heat pump model variants
└── test_heat_pump.py     # Unit tests (currently cooling-circle variants)
```

## Interface (Inputs, Outputs, Scheduling)

### Shared inputs

All four classes use:

- `state` (binary): `1` = ON, `0` = OFF
- `T_source` (°C): source-side temperature
- `T_sink` (°C): sink-side temperature

### Outputs by class

- `HeatPumpEventBased.outputs = ['cop', 'P_el', 'dot_Q_hp']`
- `HeatPumpWControlEventBased.outputs = ['P_el', 'dot_Q_hp']`
- `HeatPumpCoolingcircleEventBased.outputs = ['P_el', 'dot_Q_hp']`
- `HeatPumpCoolingcircleWControl.outputs = ['P_el', 'dot_Q_hp']`

Additionally, `step(...)` returns `next_exec_time` in all variants.

### Event scheduling behavior

Scheduling is currently hardcoded and **not** derived from `delta_t`:

- If `state == 1`: `next_exec_time = time + 60 s`
- If `state == 0`: `next_exec_time = time + 1 day`

## Model Variants

### 1) `HeatPumpEventBased`

Constructor:

```python
HeatPumpEventBased(name, delta_t=60, eta=0.5, P_el_nom=2000)
```

Behavior:

- ON: `P_el = P_el_nom`
- COP from simple temperature lift relation:

  $$
  \mathrm{cop} = \eta \cdot \frac{T_\mathrm{sink}+273.15}{(T_\mathrm{sink}+273.15)-(T_\mathrm{source}+273.15)}
  $$

- Thermal output: `dot_Q_hp = P_el * cop`

### 2) `HeatPumpWControlEventBased`

Constructor:

```python
HeatPumpWControlEventBased(
    name,
    delta_t=60,
    eta=0.5,
    dot_Q_hp_nom=10000,
    P_el_max=2000,
    P_el_min=1000,
)
```

Behavior:

- ON:
  - compute `cop` with the same simple formula
  - compute nominal setpoint: `P_el_setpoint = dot_Q_hp_nom / cop`
  - clamp: `P_el = clip(P_el_setpoint, P_el_min, P_el_max)`
  - `dot_Q_hp = P_el * cop`
- OFF: `P_el = 0`, `dot_Q_hp = 0`

### 3) `HeatPumpCoolingcircleEventBased`

Constructor:

```python
HeatPumpCoolingcircleEventBased(
    name,
    delta_t=60,
    eta=0.8433,
    P_el_nom=3500,
    fluid='R290',
)
```

Behavior (ON):

- Uses a vapor-compression cycle approximation with CoolProp (`PropsSI`) and refrigerant `fluid`.
- Pinch offsets are fixed to:
  - `T1 = T_source - 3` °C (evaporator-side state)
  - `T3 = T_sink + 3` °C (condenser-side state)
- Compressor isentropic correction via `eta`:

  $$
  h_2 = h_1 + \frac{h_{2s}-h_1}{\eta}
  $$

- Electrical power is fixed: `P_el = P_el_nom`
- Mass flow from compressor work:

  $$
  \dot m = \frac{P_\mathrm{el}}{h_2-h_1}
  $$

- Thermal output:

  $$
  \dot Q_\mathrm{hp} = \dot m\,(h_2-h_3)
  $$

- OFF: `P_el = 0`, `dot_Q_hp = 0`

### 4) `HeatPumpCoolingcircleWControl`

Constructor:

```python
HeatPumpCoolingcircleWControl(
    name,
    delta_t=60,
    eta=0.8433,
    dot_Q_hp_nom=15000,
    P_el_max=5700,
    P_el_min=1000,
    fluid='R290',
)
```

Behavior (ON):

- Uses the same refrigerant-cycle state calculations as variant 3.
- Computes nominal compressor mass flow from thermal target:

  $$
  \dot m_\mathrm{nom} = \frac{\dot Q_{\mathrm{hp,nom}}}{h_2-h_3}
  $$

- Computes electrical setpoint:

  $$
  P_{\mathrm{el,set}} = \dot m_\mathrm{nom}(h_2-h_1)
  $$

- Clamps power: `P_el = clip(P_el_set, P_el_min, P_el_max)`
- Recomputes actual mass flow and thermal output from clamped `P_el`
- OFF: `P_el = 0`, `dot_Q_hp = 0`

## Units and Conventions

- `P_el`, `dot_Q_hp` in W
- Temperatures (`T_source`, `T_sink`) in °C
- `eta` dimensionless
- `state` is binary (`0`/`1`)
- SimPlEC sign convention is preserved (`P_el > 0` represents electrical consumption)

## Minimal SimPlEC Wiring Example

```python
import pandas as pd
from simplec import Simulation
from models.heat_pump.heat_pump import HeatPumpCoolingcircleWControl

sim = Simulation()

hp = sim.add_model(
    HeatPumpCoolingcircleWControl(name='hp', delta_t=60),
    watch_values=['P_el', 'dot_Q_hp']
)

# Example upstream model refs: controller, weather, building
sim.connect(controller, hp, ('state_hp', 'state'))
sim.connect(weather, hp, ('T_amb', 'T_source'))
sim.connect(building, hp, ('T_sink_hp', 'T_sink'))

times = pd.date_range('2024-01-01', periods=24*60, freq='min')
sim.simulate(times, output_data_path='data/output/hp_example.parquet')
```

## Testing

Current tests are in `test_heat_pump.py` and cover the cooling-circle variants:

- `HeatPumpCoolingcircleEventBased`
- `HeatPumpCoolingcircleWControl`

The tests verify initialization and representative `step(...)` behavior for ON/OFF operation.

## Notes and Limitations

- In the simple COP variants, very small sink-source temperature lift may produce numerically extreme COP values due to the denominator in the COP relation.
- In all variants, scheduling when ON/OFF is currently fixed to `60 s` / `1 day`, independent of the configured `delta_t`.
- Cooling-circle variants depend on CoolProp fluid-property availability for the selected `fluid` (default `R290`).
