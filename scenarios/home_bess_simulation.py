"""Home BESS Simulation Scenario"""

import pathlib
import datetime

import pandas as pd

from simplec import Simulation

from models.legal_financial_and_metering.electric_utility_company import ElectricUtilityCompany
from models.battery_storage.battery_storage import BatteryStorage
from models.legal_financial_and_metering.smart_meter import SmartMeter
from model_archive.central_surplus_controller.central_surplus_controller import CentralSurplusController
# from models.mp_controller_homebattery.mpc_controller_pulp import MpController
from models.mp_controller_homebattery.mpc_controller import MpController
from models.mp_controller_homebattery.forecasting import GamResidualForecaster, PerfectResidualForecaster
from models.mp_controller_homebattery.grid_setpoint_adapter import GridSetpointConverter
from models.optimization_core.bess import BESSParams
from models.netload_reader.netload_reader import NetloadReader
from util.graph_export import export_simulation_graph


######################
# Config
######################
MPC_PERIOD = '15min' # Choose: '15min' (as in real system) or '24h'
USE_REAL_HORIZON = True # Choose: True (as in real system) or False (use fixed horizon)
USE_REAL_PREDICTION = True # Choose: True (GAM forecast) or False (perfect prediction)
CONTROL_PGRID = True # Choose: True (Control P_grid) or False (Control P_bat)
BATTERY_ETA_CHARGE = 0.867 # Choose: 0.867 (based on real measurement) or 0.936 (datasheet spec)
BATTERY_ETA_DISCHARGE = 0.906 # Choose: 0.906 (based on real measurement) or 0.936 (datasheet spec)
BATTERY_P_MAX = 3*9000 # Choose: 8000 W (controller limit) or 3*9000 W (inverter peak limit)
USE_BATTERY_LIFE = True    # Choose: True (as in real system) or False

SUB_SCEN_KEY = 'mp_control' # 'reference_control' # 'no_control' |
SIM_START = '2026-04-10 19:30'
SIM_END = '2026-04-17 19:30'
SIM_TZ = 'Europe/Vienna'
SOC_INIT_PERCENT = 77 # based on real measurement one moment before SIM_START

######################
# Simulation Setup
######################
times = pd.date_range(start=SIM_START, end=SIM_END, freq='15min', inclusive='left', tz=SIM_TZ)
sim = Simulation()

######################
# Electric Utility Company
######################
utility = sim.add_model(
    ElectricUtilityCompany(
        name='Electric Utility Company',
        use_epex_prices=True,
        download_start=SIM_START,
        download_end=str((pd.Timestamp(SIM_END) + pd.Timedelta(days=3)).date()),
        epex_offset_buy_eur_kwh=0.0144,
        epex_offset_sell_eur_kwh=0.006,
        grid_fee_eur_kwh=0.06,
        vat=0.20,
        timezone=SIM_TZ,
        ),
    watch_values=['bill', 'price_buy', 'price_sell'],
    )

######################
# Household with given net load profile (load minus PV. Without battery effects)
######################
household_prosumer = sim.add_model(
    NetloadReader(
        name='PV and Load (w/o Battery)',
        source='victron',
        delta_t=15*60,
        start=SIM_START,
        end=SIM_END,
        force_refetch=True,
    ),
    watch_values=['load', 'pv', 'net_load'],
    )

######################
# Household Battery Electric Storage
######################
household_bes = sim.add_model(
    BatteryStorage(
        name='Battery',
        E_0_percent=SOC_INIT_PERCENT,
        P_max_charge= BATTERY_P_MAX,
        P_max_discharge= BATTERY_P_MAX,
        eta_charge = BATTERY_ETA_CHARGE,
        eta_discharge = BATTERY_ETA_DISCHARGE,
        battery_life=USE_BATTERY_LIFE,
        ),
    watch_values=['P_set', 'P_bat', 'E', 'SOC_percent', 'SOC_min_percent'],
    )

######################
# Household Meter (total grid power → billing)
######################
household_meter = sim.add_model(
    SmartMeter('Smart Meter'),
    watch_values=['P_grid'],
    )

######################
# Connect all above models.
######################
sim.connect(household_prosumer, household_meter, ('net_load', 'P_'))
sim.connect(household_bes, household_meter, ('P_bat', 'P_'))
sim.connect(household_meter, utility, ('P_grid', 'P_el'))

######################
# Controller Connections
######################

match SUB_SCEN_KEY:

    case 'mp_control':

        if USE_REAL_PREDICTION:
            forecaster = GamResidualForecaster(
                use_real_horizon=USE_REAL_HORIZON,
            )
        else:
            forecaster = PerfectResidualForecaster(
                net_load_series_w=household_prosumer.df['net_load'],
                use_real_horizon=USE_REAL_HORIZON,
            )

        mpc = sim.add_model(
            MpController(
                name='Model Predictive Controller',
                delta_t=15*60,
                mpc_period=MPC_PERIOD,
                bes_params=BESSParams(
                    E_min_kWh=household_bes.E_min / 3_600_000,
                    E_max_kWh=household_bes.E_max / 3_600_000,
                    P_max_cha_kW=8, # Same as in real system.
                    P_max_dis_kW=8, # Same as in real system.
                    eta_cha=0.936,
                    eta_dis=0.936,
                    E_0_kWh=household_bes.E / 3_600_000,
                    E_final_percent = 50.0,
                ),
                utility_company=utility,
                forecaster=forecaster,
            ),
            watch_values=['P_grid_set', 'P_bat_set', 'P_residual_forecast', 'horizon_length'],
        )

        # Battery energy state → MPC (time-shifted to break algebraic loop)
        sim.connect(
            household_bes, mpc, ('E', 'bes_E'),
            time_shifted=True, init_values={'E': household_bes.E},
            )

        if CONTROL_PGRID:
            # Control the grid power directly via MPC
            adapter = sim.add_model(GridSetpointConverter(name='Grid Setpoint Adapter'))
            sim.connect(mpc, adapter, 'P_grid_set')
            sim.connect(household_prosumer, adapter, 'net_load')
            sim.connect(adapter, household_bes, 'P_set')
        else:
            # Control the battery power via MPC
            sim.connect(mpc, household_bes, ('P_bat_set', 'P_set'))

    case 'no_control':
        sim.connect_constant(0, household_bes, 'P_set')

    case 'reference_control':
        reference_controller = sim.add_model(
            CentralSurplusController(
                name='Reference Controller',
                delta_t=900,
                flex_config={
                    'household_bes': min(household_bes.P_max_charge, household_bes.P_max_discharge),
                }
            )
        )
        sim.connect(household_prosumer, reference_controller, ('net_load', 'P_residual_'))
        sim.connect(reference_controller, household_bes, ('P_set_dict', 'P_set'))


timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")

# Export simulation graph for visualization
export_simulation_graph(
    sim,
    f'data/graph/{pathlib.Path(__file__).stem}/'
    f'{SUB_SCEN_KEY}/{timestamp}.json'
    )

output_data_path = f'data/output/{pathlib.Path(__file__).stem}/{SUB_SCEN_KEY}/{timestamp}.parquet'
sim.simulate(
    times,
    output_data_path=output_data_path)
print(f"Simulation completed. Saved results to {output_data_path}.")
