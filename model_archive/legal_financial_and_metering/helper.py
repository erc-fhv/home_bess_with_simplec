from model_archive.legal_financial_and_metering.participant import Participant

from simplec import Simulation
from models.legal_financial_and_metering.smart_meter import SmartMeter
from model_archive.legal_financial_and_metering.distribution_system_operator \
    import DistributionSystemOperatorECAware
from model_archive.legal_financial_and_metering.energy_community import EnergyCommunity
from model_archive.legal_financial_and_metering.electric_utility_company import ElectricUtilityCompany

def add_participant_model_and_connect(
        sim: Simulation,
        smart_meter: SmartMeter,
        dso: DistributionSystemOperatorECAware,
        ec_operator: EnergyCommunity,
        utility_company: ElectricUtilityCompany
    ):
    participant = sim.add_model(
        Participant(smart_meter.name+'_bill', delta_t=15*60), # suffix '_bill' is mandatory!
        watch_values=['c_tot']
    )
    sim.connect(smart_meter, dso, ('P_grid', 'P_el_ec_dict'))
    sim.connect(ec_operator, participant, ('cost_dict', 'c_'))
    sim.connect(utility_company, participant, ('cost_dict', 'c_'))
    sim.connect(dso, participant, ('grid_fee_dict', 'c_'))

    return participant