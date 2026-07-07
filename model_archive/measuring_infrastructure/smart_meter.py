import pandas as pd
from collections import deque
from statistics import mean

class SmartMeter():
    def __init__(self, name, delta_t = 60):
        '''
        Smart meter model 

        Parameters
        ----------
        name : str, name of the model
        delta_t : int, timestep in s, default 60s, 
        
        Inputs
        ----------
        P_ : Input of electrical power
        
        Outputs
        ----------
        P_grid : Grid Power in W
        '''

        self.name = name
        self.delta_t = delta_t  # s

        self.inputs = ['P_'] # P_ as list attribute (endswith '_')
        self.outputs = ['P_grid']

        self.reccords = []

    def step(self, time, P_):
        P_grid = sum(P_)
        self.reccords.append((time, P_grid))
        return {'P_grid': P_grid}

    def retrieve_data(self) -> pd.Series:
        '''retrieve the quarter hourly Energy as pd.Series
        data only contains new values since the last retrieval'''

        if not self.reccords:
            return pd.Series([], name=self.name)
        
        df = pd.DataFrame.from_records(
            self.reccords, 
            columns=['index', self.name], 
            index='index'
            )
        self.reccords = []
   
        if df.shape[0] < 15:
            return pd.Series([], name=self.name)
        
        ser = df.squeeze()
        # resampled_data = (ser*self.delta_t).resample('15min').sum()
        resampled_data : pd.Series = ser.resample('15min').mean()
        
        return resampled_data


class ElectricityMeter():
    def __init__(self, name, delta_t = 60):
        '''
        Electricity meter model, this model sums up all electric powers connected to it. It does not return data (it is not a smart meter).

        Parameters
        ----------
        name : str, name of the model
        delta_t : int, timestep in s, default 60s, 
        
        Inputs
        ----------
        P_ : Input of electrical power
        
        Outputs
        ----------
        P_grid : Grid Power in W
        '''
        self.name = name
        self.delta_t = delta_t  # s

        self.inputs = ['P_'] # P_ as list attribute (endswith '_')
        self.outputs = ['P_grid']

        self.reccords = []

    def step(self, time, P_):
        P_grid = sum(P_)
        return {'P_grid': P_grid}
    

class SimpleElectricityMeter():
    def __init__(self, name):
        '''
        A smart meter model which additionally computes the hourly mean power
        
        Parameters
        ----------
        name : Name of the model
        
        Inputs:
        -------
        P_ : Loads and generation powers, consumption > 0

        Outputs:
        --------
        P_grid : residual load at the grid connection
        P_grid_mean_h : hourly mean power of the grid power (running mean)
        '''    
        self.name = name
        self.delta_t = 60  # s

        self.inputs = ['P_'] # P_ as list attribute (endswith '_')
        self.outputs = ['P_grid', 'P_grid_mean_h']

        self.reccords = deque(maxlen=int(3600/self.delta_t))

    def step(self, time, P_):
        P_grid = sum(P_)
        self.reccords.append(P_grid)
        return {'P_grid': P_grid, 'P_grid_mean_h': mean(self.reccords)}
        
