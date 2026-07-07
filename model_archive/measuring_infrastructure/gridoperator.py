import pandas as pd

class GridOperator():
    def __init__(self, name, delta_t=60*60*24):
        '''Grid operator. 
        The model mimics the daily retrieval of the data from the smart meters 
        and provides the data to the registerd parties/(i.e. energy communities) 
        behaviour is similar to the austrian EDA platform.

        Parameters
        ----------
        name : str, name of the model
        delta_t : int, timestep in s, default to 24 h = 86400 s, 
        
        Inputs
        ----------
        
        Outputs
        ----------
        df_P_day : Dataframe containg smart meter data of one day
        '''
        self.name = name
        self.delta_t = delta_t
        self.inputs = []
        self.outputs = ['df_P_day']
        self._smart_meter_models = []
        self.callbacks = []

    def register_smartmeter(self, smart_meter_model):
        self._smart_meter_models += [smart_meter_model]

    def register_callback_new_data(self, callback:callable):
        # register a callback, which can recieve updated ec data
        self.callbacks.append(callback)

    def step(self, time):
        # recieve data from smart meters
        pd.Series([]).rename()
        df_P_day = pd.concat(
            objs=[sm.retrieve_data() for sm in self._smart_meter_models], 
            axis=1
            )
        # call callbacks (controller(s))
        for cb in self.callbacks:
            cb(df_P_day)

        return {'df_P_day': df_P_day}