import numpy as np
import pickle


class BuildingModel():
    def __init__(self, name, delta_t = 60, T_building_0=20, count_of_dot_Q_int=1) -> None:
        
        '''
        Model of a building envelope for a simple building, represented as a RC model which is black box identified from a SynPro Dataset

        Parameters
        ----------
        name : str, name of the model
        delta_t : int, timestep in s, default 60s, 
        T_building_0 : float, building temperature at time t0 in °C
        count_of_dot_Q_int : integer, count of internal heat gains in W
        
        Inputs
        ----------
        dot_Q_heat : Heating power supplied to building in W
        dot_Q_cool : Cooling power supplied to building in W
        T_amb : Ambient temperature in °C
        I_dir : Specific direct radiation on a horizontal surface in W/m²
        I_dif : Specific diffuse radiation on a horizontal surface in W/m²
        I_s : Specific radiation on an vertical surface, which is oriented to south in W/m²
        I_w : Specific radiation on an vertical surface, which is oriented to west in W/m²
        I_n : Specific radiation on an vertical surface, which is oriented to north in W/m²
        I_e : Specific radiation on an vertical surface, which is oriented to east in W/m²
        
        Outputs
        ----------
        T_building : Building temperature in °C
        '''

        self.name = name

        # Parameters
        self.delta_t = delta_t  # s
        
        with open('models/building/fasade_model.pkl', mode='rb') as f:
            self.fasade_model = pickle.load(f)

        self._A = np.array([[0.99946908]])
        self._B = np.array([[1.27224559e-06, 1.29389956e-06]])
        self._F = np.array([[1.05513931e-06, 5.65074395e-04, 1.15661336e-06]])

        self._x = np.array([T_building_0])
        
        self.dot_Q_int_inputs = [f'dot_Q_int_{i}' for i in range(count_of_dot_Q_int)] # TODO: can be changed to new multiinput feature of simplec
        
        self.inputs = ['dot_Q_heat', 'dot_Q_cool', 'T_amb', 'I_dir', 'I_dif', 'I_s', 'I_w', 'I_n', 'I_e'] + self.dot_Q_int_inputs
        self.outputs = ['T_building']

    def step(self, time, dot_Q_heat, dot_Q_cool, T_amb, I_dir, I_dif, I_s, I_w, I_n, I_e, **dot_Q_int):
        dot_Q_int = sum(dot_Q_int.values())
        # dot_Q_int = [dot_Q_int[k] for k in self.dot_Q_int_inputs] # if more variable length inputs

        dot_Q_sol = self.fasade_model.predict([[I_dir, I_dif, I_s, I_w, I_n, I_e]])[0]

        u = np.array([dot_Q_heat, dot_Q_cool])
        d = np.array([dot_Q_int, T_amb, dot_Q_sol])

        self._x = self._A@self._x.T + self._B@u.T + self._F@d.T

        return {'T_building':self._x[0]}
    
