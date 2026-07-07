from models.battery_storage.battery_storage import BatteryStorage
import numpy as np

def test_initialization():
    batterystorage = BatteryStorage(name='battery_storage_model1')
    assert batterystorage.name                == 'battery_storage_model1'
    assert batterystorage.delta_t             ==         3600 # s
    assert batterystorage.E                   ==  2500 * 3600 # J
    assert batterystorage.E_max               == 50000 * 3600 # J
    assert batterystorage.E_min               ==            0 # J
    assert batterystorage.eta_charge          ==         0.95 #
    assert batterystorage.eta_discharge       ==         0.95 #
    assert batterystorage.C_rate              ==            1 # 1/h
    assert batterystorage.P_max_charge        ==        50000 # W
    assert batterystorage.P_max_discharge     ==        50000 # W
    assert batterystorage.self_discharge_rate ==        2.e-8 # 1/s

def test_c_rate_sets_default_power_limits():
    batterystorage = BatteryStorage(
                 name                = 'battery_storage_1',
                 E_max               =      5 * 3600, # J
                 E_min               =      1 * 3600, # J
                 C_rate              =           0.5
    )
    assert np.isclose(batterystorage.P_max_charge, 2.0)
    assert np.isclose(batterystorage.P_max_discharge, 2.0)

def test_explicit_power_limit_overrides_c_rate():
    batterystorage = BatteryStorage(
                 name                = 'battery_storage_1',
                 E_max               =      5 * 3600, # J
                 E_min               =             0, # J
                 C_rate              =             1,
                 P_max_charge        =             3, # W
                 P_max_discharge     =             4  # W
    )
    assert np.isclose(batterystorage.P_max_charge, 3.0)
    assert np.isclose(batterystorage.P_max_discharge, 4.0)

def test_step_normal_charge():
    batterystorage = BatteryStorage(
                 name                = 'battery_storage_1',
                 delta_t             =          3600, # s
                 E_0                 =      2 * 3600, # J
                 E_max               =      5 * 3600, # J
                 E_min               =             0, # J
                 eta_charge          =             1, #
                 eta_discharge       =             1, #
                 P_max_charge        =             2, # W
                 P_max_discharge     =             2, # W
                 self_discharge_rate =             0 # 1/s
    )
    output = batterystorage.step(1, 2.)
    assert np.isclose(output['P_grid'], 2.)
    assert np.isclose(output['E'],      4.*3600)

def test_step_normal_discharge():
    batterystorage = BatteryStorage(
                 name                = 'battery_storage_1',
                 delta_t             =          3600, # s
                 E_0                 =      3 * 3600, # J
                 E_max               =      5 * 3600, # J
                 E_min               =             0, # J
                 eta_charge          =             1, #
                 eta_discharge       =             1, #
                 P_max_charge        =             2, # W
                 P_max_discharge     =             2, # W
                 self_discharge_rate =             0 # 1/s
    )
    output = batterystorage.step(1, -2.)
    assert np.isclose(output['P_grid'], -2.)
    assert np.isclose(output['E'],      1.*3600)

def test_step_over_charge():
    batterystorage = BatteryStorage(
                 name                = 'battery_storage_1',
                 delta_t             =          3600, # s
                 E_0                 =      4 * 3600, # J
                 E_max               =      5 * 3600, # J
                 E_min               =             0, # J
                 eta_charge          =             1, #
                 eta_discharge       =             1, #
                 P_max_charge        =             2, # W
                 P_max_discharge     =             2, # W
                 self_discharge_rate =             0 # 1/s
    )
    output = batterystorage.step(1, 2.)
    assert np.isclose(output['P_grid'], 1.)
    assert np.isclose(output['E'],      5.*3600)

def test_step_over_discharge():
    batterystorage = BatteryStorage(
                 name                = 'battery_storage_1',
                 delta_t             =          3600, # s
                 E_0                 =      1 * 3600, # J
                 E_max               =      5 * 3600, # J
                 E_min               =             0, # J
                 eta_charge          =             1, #
                 eta_discharge       =             1, #
                 P_max_charge        =             2, # W
                 P_max_discharge     =             2, # W
                 self_discharge_rate =             0 # 1/s
    )
    output = batterystorage.step(1, -2.)
    assert np.isclose(output['P_grid'], -1.)
    assert np.isclose(output['E'],      0.*3600)

def test_step_charging_effiency():
    batterystorage = BatteryStorage(
                 name                = 'battery_storage_1',
                 delta_t             =          3600, # s
                 E_0                 =      1 * 3600, # J
                 E_max               =      5 * 3600, # J
                 E_min               =             0, # J
                 eta_charge          =           0.8, #
                 eta_discharge       =             1, #
                 P_max_charge        =             2, # W
                 P_max_discharge     =             2, # W
                 self_discharge_rate =             0 # 1/s
    )
    output = batterystorage.step(1, 2.)
    assert np.isclose(output['P_grid'], 2)
    assert np.isclose(output['E'], (1+2*0.8)*3600)

def test_step_discharging_effiency():
    batterystorage = BatteryStorage(
                 name                = 'battery_storage_1',
                 delta_t             =          3600, # s
                 E_0                 =      3 * 3600, # J
                 E_max               =      5 * 3600, # J
                 E_min               =             0, # J
                 eta_charge          =             1, #
                 eta_discharge       =           0.8, #
                 P_max_charge        =             2, # W
                 P_max_discharge     =             2, # W
                 self_discharge_rate =             0 # 1/s
    )
    output = batterystorage.step(1, -2.)
    assert np.isclose(output['P_grid'], -2)
    assert np.isclose(output['E'], (3-2/0.8)*3600)


def test_battery_life_real_scenario():
    """Real-world scenario April 10-17:
    - Apr 10-14: normal days, battery always charges to 100% → min stays at 10%
    - Apr 15: hits lower limit at ~22:00, never reaches 85% → min rises to 15%
    - Apr 16: charges to 100% in afternoon → min returns to 10%
    - Apr 17: normal day again, min stays at 10%
    """
    from datetime import datetime, timedelta

    bat = BatteryStorage(
        name='bl_test',
        delta_t=3600,             # 1h steps
        E_max=100 * 3600,         # 100 Wh → 1W·1h = 1% SOC
        E_0_percent=50,
        E_min_percent=10,
        eta_charge=1.0,
        eta_discharge=1.0,
        P_max_charge=100,
        P_max_discharge=100,
        self_discharge_rate=0,
        battery_life=True,
    )

    # --- Apr 10-14: normal days, battery charges to 100% each day ---
    for d in range(10, 15):
        day = datetime(2026, 4, d)
        bat.E = bat.E_max * 0.50
        bat.step(day, 0)                            # register new day
        bat.step(day + timedelta(hours=12), 1_000_000)     # charge to 100%
        bat.step(day + timedelta(hours=23), 0)       # idle rest of day
        assert bat._bl_min_percent == 10, f"Apr {d}: min should stay 10%"

    # --- Apr 15: discharge to lower limit at ~22:00, never reach 85% ---
    day_15 = datetime(2026, 4, 15)
    bat.E = bat.E_max * 0.50
    bat.step(day_15, 0)                              # register new day
    assert bat._bl_min_percent == 10                 # still 10% at start of day

    bat.E = bat.E_max * 0.14                         # SOC just above 10%
    bat.step(day_15 + timedelta(hours=21), 0)        # idle, no hit yet
    assert bat._bl_min_percent == 10                 # not yet increased

    bat.step(day_15 + timedelta(hours=23), -1_000_000)      # discharge → hits 10% limit
    assert bat._bl_min_percent == 15, "After hitting min on Apr 15 22:00, expected 15%"

    # --- Apr 16: dynamic min is 15%, charge to 100% in afternoon → min returns to 10% ---
    day_16 = datetime(2026, 4, 16)
    bat.E = bat.E_max * 0.20
    bat.step(day_16, 0)                              # register new day
    assert np.isclose(bat.E_min, bat.E_max * 0.15), "Dynamic E_min should be 15%"

    out = bat.step(day_16 + timedelta(hours=14), 1_000_000)  # charge to 100%
    assert out['SOC_percent'] >= 95
    assert bat._bl_min_percent == 10, "After reaching 95% on Apr 16, expected 10%"

    # --- Apr 17: normal day, min stays at 10% ---
    day_17 = datetime(2026, 4, 17)
    bat.E = bat.E_max * 0.50
    bat.step(day_17, 0)
    assert np.isclose(bat.E_min, bat.E_max * 0.10), "E_min should be back to 10%"
    assert bat._bl_min_percent == 10
