import pandas as pd
import numpy as np
from simplec import Simulation

from model_archive.controller_infrastructure.local_data_acquisition import LocalDataAcquisition
from model_archive.central_surplus_controller.central_surplus_controller import CentralSurplusController
from model_archive.controller_infrastructure.decentral_flex_controller import DecentralFlexController


class PVMock():
    delta_t = 900
    inputs = []
    outputs = ['P']

    def __init__(self, name, data: pd.Series) -> None:
        self.name = name
        self.data = data

    def step(self, time):
        return {'P': self.data[time]}


class LoadMock():
    delta_t = 900
    inputs = []
    outputs = ['P_el']

    def __init__(self, name, data: pd.Series) -> None:
        self.name = name
        self.data = data

    def step(self, time):
        return {'P_el': self.data[time]}


class BatteryMock():
    delta_t = 900
    inputs = ['P_set']
    outputs = ['P_grid']

    def __init__(self, name) -> None:
        self.name = name

    def step(self, time, P_set):
        return {'P_grid': P_set}


def test_scenario_reference_controller():
    '''Integration test: 2 metering points, 1 battery, 4 time steps.

    Meter A: PV (varying) + Load (1000 W constant)
    Meter B: Load only (500 W constant)
    Battery: single flex, P_max = 5000 W

    Step 0: PV=-2000 → surplus 500 → charge 500
    Step 1: PV=-1000 → deficit 500 → discharge -500
    Step 2: PV=-3000 → surplus 1500 → charge 1500
    Step 3: PV=0    → deficit 1500 → discharge -1500
    '''
    sim = Simulation()

    times = pd.date_range(start='2020-01-01 00:00+00:00', periods=4, freq='15min')

    # --- Mock data sources ---
    pv_data = pd.Series([-2000., -1000., -3000., 0.], index=times)
    load_a_data = pd.Series([1000., 1000., 1000., 1000.], index=times)
    load_b_data = pd.Series([500., 500., 500., 500.], index=times)

    pv = sim.add_model(PVMock('pv', pv_data))
    load_a = sim.add_model(LoadMock('load_a', load_a_data))
    load_b = sim.add_model(LoadMock('load_b', load_b_data))

    # --- Local data acquisition (one per metering point) ---
    lda_a = sim.add_model(
        LocalDataAcquisition('lda_a', delta_t=900, has_flex=True),
        watch_values=['P_residual']
    )
    lda_b = sim.add_model(
        LocalDataAcquisition('lda_b', delta_t=900, has_gen=False),
        watch_values=['P_residual']
    )

    sim.connect(pv, lda_a, ('P', 'P_gen_'))
    sim.connect(load_a, lda_a, ('P_el', 'P_load_'))
    sim.connect(load_b, lda_b, ('P_el', 'P_load_'))

    # --- Central controller ---
    central = sim.add_model(
        CentralSurplusController(
            'central', delta_t=900,
            flex_config={'decentral_bes': 5000}
        )
    )

    sim.connect(lda_a, central, ('P_residual', 'P_residual_'))
    sim.connect(lda_b, central, ('P_residual', 'P_residual_'))

    # --- Decentral flex controller ---
    decentral_bes = sim.add_model(
        DecentralFlexController('decentral_bes', delta_t=900),
        watch_values=['P_set']
    )

    sim.connect(central, decentral_bes, ('P_set_dict', 'P_cmd'))

    # --- Battery mock ---
    battery = sim.add_model(
        BatteryMock('battery'),
        watch_values=['P_grid']
    )

    sim.connect(
        decentral_bes, battery, ('P_set', 'P_set'),
        time_shifted=True, init_values={'P_set': 0}
    )

    # --- Battery feedback to LDA (time-shifted, for future P_meter use) ---
    sim.connect(
        battery, lda_a, ('P_grid', 'P_flex_dict'),
        time_shifted=True, init_values={'P_grid': 0}
    )

    # --- Simulate ---
    sim.simulate(times)

    # --- Assertions on LDA residuals ---
    residual_a = sim.df.loc[:, ('lda_a', 'outputs', 'P_residual')].values
    residual_b = sim.df.loc[:, ('lda_b', 'outputs', 'P_residual')].values

    np.testing.assert_allclose(residual_a, [-1000., 0., -2000., 1000.])
    np.testing.assert_allclose(residual_b, [500., 500., 500., 500.])

    # --- Assertions on controller setpoints ---
    P_set = sim.df.loc[:, ('decentral_bes', 'outputs', 'P_set')].values

    # surplus → charge (positive), deficit → discharge (negative)
    np.testing.assert_allclose(P_set, [500., -500., 1500., -1500.])

    # --- Assertions on battery (receives time-shifted P_set) ---
    P_grid = sim.df.loc[:, ('battery', 'outputs', 'P_grid')].values

    # time-shifted by one step, init=0
    np.testing.assert_allclose(P_grid, [0., 500., -500., 1500.])


def test_scenario_proportional_split_two_batteries():
    '''Integration test: 1 metering point, 2 batteries with different P_max.

    Meter A: PV=-4000 + Load=1000 → surplus=3000
    Battery A: P_max=3000 (75%)
    Battery B: P_max=1000 (25%)
    → P_set_a = 2250, P_set_b = 750
    '''
    sim = Simulation()

    times = pd.date_range(start='2020-01-01 00:00+00:00', periods=2, freq='15min')

    pv_data = pd.Series([-4000., -4000.], index=times)
    load_data = pd.Series([1000., 1000.], index=times)

    pv = sim.add_model(PVMock('pv', pv_data))
    load = sim.add_model(LoadMock('load', load_data))

    lda = sim.add_model(LocalDataAcquisition('lda', delta_t=900))  # no flex feedback

    sim.connect(pv, lda, ('P', 'P_gen_'))
    sim.connect(load, lda, ('P_el', 'P_load_'))

    central = sim.add_model(
        CentralSurplusController(
            'central', delta_t=900,
            flex_config={'dec_bes_a': 3000, 'dec_bes_b': 1000}
        )
    )

    sim.connect(lda, central, ('P_residual', 'P_residual_'))

    dec_a = sim.add_model(
        DecentralFlexController('dec_bes_a', delta_t=900),
        watch_values=['P_set']
    )
    dec_b = sim.add_model(
        DecentralFlexController('dec_bes_b', delta_t=900),
        watch_values=['P_set']
    )

    sim.connect(central, dec_a, ('P_set_dict', 'P_cmd'))
    sim.connect(central, dec_b, ('P_set_dict', 'P_cmd'))

    bat_a = sim.add_model(BatteryMock('bat_a'))
    bat_b = sim.add_model(BatteryMock('bat_b'))

    sim.connect(dec_a, bat_a, ('P_set', 'P_set'), time_shifted=True, init_values={'P_set': 0})
    sim.connect(dec_b, bat_b, ('P_set', 'P_set'), time_shifted=True, init_values={'P_set': 0})

    sim.simulate(times)

    P_set_a = sim.df.loc[:, ('dec_bes_a', 'outputs', 'P_set')].values
    P_set_b = sim.df.loc[:, ('dec_bes_b', 'outputs', 'P_set')].values

    # 3000W surplus split 75/25
    np.testing.assert_allclose(P_set_a, [2250., 2250.])
    np.testing.assert_allclose(P_set_b, [750., 750.])
