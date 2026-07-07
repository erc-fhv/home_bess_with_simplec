import pandas as pd
import numpy as np
from simplec import Simulation

from model_archive.legal_financial_and_metering.distribution_system_operator import DistributionSystemOperatorECAware
from model_archive.legal_financial_and_metering.energy_community import EnergyCommunity
from model_archive.legal_financial_and_metering.electric_utility_company import ElectricUtilityCompany
from model_archive.legal_financial_and_metering.participant import Participant
from model_archive.legal_financial_and_metering.helper import add_participant_model_and_connect

class SmartMeterMock():
    delta_t = 60 *15  # s
    inputs = []
    outputs = ['P_grid']

    def __init__(self, name, data: pd.Series) -> None:
        self.name = name
        self.data = data

    def step(self, time):
        return {'P_grid': self.data[time]}


def test_scenario_legal_and_financial():
    sim = Simulation()

    times = pd.date_range(start='2020-01-01 00:00+00:00', periods=4, freq='15min')

    ##################
    # setup of infrastructure
    ##################
    dso = sim.add_model(
        DistributionSystemOperatorECAware(
            name='dso',
            grid_fee_consumption=0.15, # €
            grid_fee_feedin=0.08,  # €
            grid_fee_ec_consumption=0.05, # €
            grid_fee_ec_feedin=0.01,  # €
        ),
        # watch_heavy=['grid_fee_dict', 'P_ec', 'P_residual']
    )

    ec_operator = sim.add_model(
        EnergyCommunity(
            name = 'ec_operator',
            price_consumption=0.16,  # €
            price_feedin=0.14,  # €
        ),
        watch_values=['profit_ec'],
        # watch_heavy=['cost_dict']
    )
    sim.connect(dso, ec_operator, ('P_ec', 'P_el'))

    utility_company = sim.add_model(
        ElectricUtilityCompany(
            name='utility_company',
            price_consumption=pd.Series(np.full(4, 0.20), times),  # static prices
            price_feedin=pd.Series(np.full(4, 0.10), times),  # static prices
        ),
        watch_heavy=['cost_dict']
    )
    sim.connect(dso, utility_company, ('P_residual', 'P_el'))

    ##################
    # Participants
    ##################
    # Consumer with feedin
    powers = pd.Series([1000., -2000., -2000., -1000.], index=times)
    consumer_feedin = sim.add_model(
        SmartMeterMock('consumer_feedin', powers),
        watch_values=['P_grid']
    )
    consumer_feedin_participant = sim.add_model(
        Participant('consumer_feedin_bill', delta_t=15*60), # suffix '_bill' is mandatory!
        watch_values=['c_tot']
    )

    sim.connect(consumer_feedin, dso, ('P_grid', 'P_el_ec_dict'))
    sim.connect(ec_operator, consumer_feedin_participant, ('cost_dict', 'c_'))
    sim.connect(utility_company, consumer_feedin_participant, ('cost_dict', 'c_'))
    sim.connect(dso, consumer_feedin_participant, ('grid_fee_dict', 'c_'))

    # consumer (no feedin)
    powers = pd.Series([1000., 2000., 1000., 2000.], index=times)
    consumer = sim.add_model(
        SmartMeterMock('consumer', powers),
        watch_values=['P_grid']
    )
    consumer_participant = add_participant_model_and_connect(
        sim=sim,
        smart_meter=consumer, # type: ignore
        dso=dso,
        ec_operator=ec_operator,
        utility_company=utility_company
    )

    sim.simulate(times)

    cost_cons = sim.df.loc[:, ('consumer_bill', 'outputs', 'c_tot')].values
    cost_cons_w_fdin = sim.df.loc[:, ('consumer_feedin_bill', 'outputs', 'c_tot')].values


    assert np.isclose(cost_cons[0], (0.15 + 0.20) / 4), 'No EC electricity case is wrong'
    assert np.isclose(cost_cons[1], (0.05 + 0.16) / 4 * 2), 'Energy Community case is wrong'
    assert np.isclose(cost_cons[2], (0.05 + 0.16) / 4), 'Surpluss feedin case is wrong'
    assert np.isclose(cost_cons[3], (0.05 + 0.16 + 0.15 + 0.20) / 4), \
        'Surpluss consumption case is wrong'

    assert np.isclose(cost_cons_w_fdin[0], (0.15 + 0.20) / 4), 'No EC electricity case is wrong'
    assert np.isclose(cost_cons_w_fdin[1], (-0.14 + 0.01) / 4 * 2), 'Energy Community case is wrong'
    assert np.isclose(cost_cons_w_fdin[2], (-0.14 + 0.01 - 0.10 + 0.08) / 4), 'Surpluss feedin case is wrong'
    assert np.isclose(cost_cons_w_fdin[3], (-0.14 + 0.01) / 4), \
        'Surpluss consumption case is wrong'