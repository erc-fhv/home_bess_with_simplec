from pylpg import lpg_execution, lpgdata
from pylpg.lpgpythonbindings import JsonReference, EnergyIntensityType
from util.cache_manager import cache_result
from types import SimpleNamespace
from pathlib import Path
import shutil
import pandas as pd

class Household():
    def __init__(self,               
                name,
                delta_t = 60*15,
                year: int = 2021,
                householdref: JsonReference = lpgdata.Households.CHR03_Family_1_child_both_at_work,
                housetype: str = lpgdata.HouseTypes.HT23_No_Infrastructure_at_all,
                startdate: str = '2021-01-01T00:00:00',
                enddate: str = '2021-12-31T00:00:00',
                geographic_location: JsonReference = lpgdata.GeographicLocations.Germany_Muenchen,
                simulate_transportation: bool = False,
                chargingset: JsonReference | None = None,
                transportation_device_set: JsonReference | None = None,
                travel_route_set: JsonReference | None = None,
                random_seed: int = 1,
                energy_intensity: EnergyIntensityType = EnergyIntensityType.Random,                
                ):
        '''
        Specifies a household/users from PyLoadProfileGenerator, see LPG webiste for reference: https://www.loadprofilegenerator.de/

        Parameter
        ----------
        name : str, name of the model
        delta_t : int, timestep in s,specified as 15 min = 900 s,
        year : int, sets the year for calculation
        householdref : string, predefined household from loadprofilegernerator, overvirvew of all households: https://www.loadprofilegenerator.de/results2/
        housetype : string, housetype defined from loadprofilegernerator,
        startdate : str, start date of calculation,
        enddate : str, end date of calculation,
        geographic_location : JsonReference, geographic location used in calculation,
        simulate_transportation : bool, specifies if a simulation of transportation is used in calculation,
        chargingset : JsonReference, specifies if a charging station of EVs is used in calculation,
        transportation_device_set : JsonReference, sets a transportation device for transportation simulation,
        travel_route_set : JsonReference, sets a travel route for transportation simulation,
        random_seed : int, for a random seed use -1,
        energy_intensity : EnergyIntensityType, sets the energy intensity of electrical devices
        
        Inputs
        ------
        
        Outputs
        -------
        P_el : float, Electricity usage in W 
        dot_Q_gain_int : float, internal heat gains in W
        dot_m_ww : float, warm water use at 35°C in kg/s
        dot_Q_ww : float, warm water use heatflow in W
        '''

        self.name = name
        self.delta_t = delta_t # s

        dhw_specs = SimpleNamespace( # specify inlet and outlet temperature for conversion of mass flow to dot_Q_ww
            T_inlet = 12, # °C 
            T_usage = 35, # °C
            c_p = 4200, # J/kg/K
        )

        self.df = self.generate_household_df(
            year = year,
            householdref  = householdref,
            housetype = housetype,
            startdate = startdate,
            enddate = enddate,
            geographic_location = geographic_location,
            simulate_transportation = simulate_transportation,
            chargingset = chargingset,
            transportation_device_set = transportation_device_set,
            travel_route_set = travel_route_set,
            random_seed = random_seed,
            energy_intensity = energy_intensity,
            resolution = '00:01:00',
            calc_options = None,
            delta_t = delta_t,
            dhw_specs=dhw_specs
        )

        self.inputs = []
        self.outputs = list(self.df.columns)

    @staticmethod
    @cache_result()
    def generate_household_df(
                year,
                householdref ,
                housetype,
                startdate,
                enddate,
                geographic_location,
                simulate_transportation,
                chargingset,
                transportation_device_set,
                travel_route_set,
                random_seed,
                energy_intensity,
                resolution,
                calc_options,
                delta_t,
                dhw_specs : SimpleNamespace
                ):
        
        # clear lpg 
        dirpath = Path(".venv/lib/python3.11/site-packages/pylpg/C1") # TODO: find a nicer solution instead of hard coding path here
        if dirpath.exists():
            try:
                shutil.rmtree(dirpath)
            except FileNotFoundError:
                pass

        df = lpg_execution.execute_lpg_single_household(
            year = year,
            householdref = householdref,
            housetype = housetype,
            startdate = startdate,
            enddate = enddate,
            geographic_location = geographic_location,
            simulate_transportation = simulate_transportation,
            chargingset = chargingset,
            transportation_device_set = transportation_device_set,
            travel_route_set = travel_route_set,
            random_seed = random_seed,
            energy_intensity = energy_intensity,
            resolution = resolution,
            calc_options = calc_options
            )
        
        # select and resample columns
        df = df.resample(str(delta_t)+'s').aggregate(
            func = {
                    'Electricity_HH1': 'sum', 
                    'Inner Device Heat Gains_HH1': 'sum', 
                    'Warm Water_HH1': 'sum'
                }
            )
        
        # rename columns for naming convention
        df = df.rename(
            columns={
                'Electricity_HH1': 'P_el', 
                'Inner Device Heat Gains_HH1' : 'dot_Q_gain_int', 
                'Warm Water_HH1' : 'dot_m_ww'
                }
            )
        
        # convert index to datetime
        df.index = pd.to_datetime(df.index, format="%d.%m.%Y %H:%M")
        df.index = df.index.tz_localize(tz='Etc/GMT-1').tz_convert('Europe/Berlin')

        # Convert to appropriate units
        df['P_el'] = df['P_el']/0.25*1000 # kWh/15min ~> W
        df['dot_Q_gain_int'] = df['dot_Q_gain_int'] / 0.25 * 1000 # kWh/15min ~> W
        df['dot_m_ww'] = df['dot_m_ww'] / 900 # l/15min ~> kg/s
        df['dot_Q_ww'] = df['dot_m_ww'] * dhw_specs.c_p * (dhw_specs.T_usage - dhw_specs.T_inlet)
        df.drop('dot_m_ww', axis=1)

        return df

    def step(self, time):
        return self.df.loc[time].to_dict()
    
