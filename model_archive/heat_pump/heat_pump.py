import numpy as np
import pandas as pd
import CoolProp.CoolProp as CP

class HeatPumpEventBased():
    def __init__(self, name, delta_t=60, eta=0.5, P_el_nom=2000) -> None:
        ''''
        Event based heat pump model with COP calculation using Tsink, Tsource and eta

        Parameter
        ---------
        name : str, name of the model
        delta_t : int, timestep in s, default 60s
        eta : float, efficiency (no unit)
        P_el_nom : float, nominal electrical power in W

        Inputs
        ---------
        state : binary, variable controlling the heat pump (no unit)
        T_source : float, source/outside temperature in °C
        T_sink : float, sink temperature in °C

        Outputs
        ---------
        cop : calculated coefficient of performance (COP)
        P_el : electrical power in W
        dot_Q_hp : calculated heating power in W
        '''
        # Parameter
        self.delta_t = delta_t

        self.eta      = eta
        self.P_el_nom = P_el_nom # nominal Power

        # internal Parameter
        self._cop_fun = lambda Tsource, Tsink, eta: (Tsink+273.15)/((Tsink+273.15) - (Tsource+273.15)) * eta
        
        # inputs outputs 
        self.inputs  = ['state', 'T_source', 'T_sink']
        self.outputs = ['cop', 'P_el', 'dot_Q_hp']
        self.name = name

    def step(self, time, state, T_source, T_sink):
        if state == 1:
            P_el = self.P_el_nom
            next_exec_time = pd.Timedelta(60, 'sec') + time
        else:
            P_el = 0
            next_exec_time = pd.Timedelta(1, 'day') + time
        cop = self._cop_fun(T_source, T_sink, self.eta)
        dot_Q_hp = P_el * cop

        
        return {'next_exec_time': next_exec_time, 'cop':cop, 'P_el':P_el, 'dot_Q_hp':dot_Q_hp}
    

class HeatPumpWControlEventBased():
    def __init__(self, name, delta_t=60, eta=0.5, dot_Q_hp_nom=10000, P_el_max=2000, P_el_min=1000) -> None:
        ''''
        Event based heat pump model with control

        Parameter
        ---------
        name : str, name of the model
        delta_t : int, timestep in s, default 60s
        eta : float, efficiency (no unit)
        dot_Q_hp_nom : float, nominal heating power in W
        P_el_max : float, maximum electrical power in W
        P_el_min : float, minimum electrical power in W

        Inputs
        ---------
        state : binary, variable controlling the heat pump (no unit)
        T_source : float, source/outside temperature in °C
        T_sink : float, sink temperature in °C
        
        Outputs
        ---------
        P_el : calculated electrical power in W
        dot_Q_hp : heating power in W
        '''
        # Parameter
        self.delta_t = delta_t

        self.eta      = eta  # "Gütegrad"
        self.dot_Q_hp_nom = dot_Q_hp_nom # nominal Power
        self.P_el_max = P_el_max
        self.P_el_min = P_el_min

        # internal Parameter
        self._cop_fun = lambda Tsource, Tsink, eta: (Tsink+273.15)/((Tsink+273.15) - (Tsource+273.15)) * eta
        
        # inputs outputs 
        self.inputs  = ['state', 'T_source', 'T_sink']
        self.outputs = ['P_el', 'dot_Q_hp']
        self.name = name

    def step(self, time, state, T_source, T_sink):
        if state == 1:
            dot_Q_hp_nom = self.dot_Q_hp_nom
            cop = self._cop_fun(T_source, T_sink, self.eta) # calc COP
            P_el_setpoint = dot_Q_hp_nom / cop # Calculate nominal P_el at current COP
            P_el = max(self.P_el_min, min(P_el_setpoint, self.P_el_max)) # Clip electrical power
            dot_Q_hp = P_el * cop
            
            next_exec_time = pd.Timedelta(60, 'sec') + time
        else:
            dot_Q_hp = 0
            P_el = 0
            next_exec_time = pd.Timedelta(1, 'day') + time

        return {'next_exec_time': next_exec_time, 'P_el':P_el, 'dot_Q_hp':dot_Q_hp}
        

class HeatPumpCoolingcircleEventBased():
    def __init__(self, name, delta_t=60, eta=0.8433, P_el_nom=3500, fluid='R290') -> None:
        ''''
        Heat pump model with with cooling circle

        Parameter
        ---------
        name : str, name of the model
        delta_t : int, timestep in s, default 60s
        eta : float, isentropic efficiency (no unit)
        P_el_nom : float, nominal electrical power in W
        fluid : str, cooling fluid used in cooling circle

        Inputs
        ---------
        T_source : float, source/outside temperature in °C
        T_sink : float, room temperature in °C
        state : binary, variable controlling the heat pump (no unit)

        Outputs
        ---------
        P_el : float, calculated electrical power in W
        dot_Q_hp : float, calculated heating power in W
        '''
        
        # Parameter
        self.delta_t = delta_t # s

        self.eta      = eta # isentropic efficiency
        self.P_el_nom = P_el_nom # nominal power in W
        self.fluid    = fluid # fluid used in cooling circle

        # inputs outputs 
        self.inputs  = ['state', 'T_source', 'T_sink']
        self.outputs = ['P_el', 'dot_Q_hp']
        self.name = name

    def step(self, time, state, T_source, T_sink):
        if state == 1:

            P_el = self.P_el_nom
            x1=1 # fraction of vapor
            T1=T_source - 3 # °C
            x3=0 # fraction of vapor
            T3=T_sink + 3   # °C

            # State 1:
            h1=CP.PropsSI('H','T',T1+273.15,'Q',x1,self.fluid)
            p1=CP.PropsSI('P','T',T1+273.15,'Q',x1,self.fluid)
            s1=CP.PropsSI('S','T',T1+273.15,'Q',x1,self.fluid)

            # State 3:
            h3=CP.PropsSI('H','T',T3+273.15,'Q',x3,self.fluid)
            p3=CP.PropsSI('P','T',T3+273.15,'Q',x3,self.fluid)
            s3=CP.PropsSI('S','T',T3+273.15,'Q',x3,self.fluid)
            
            # State 2:
            p2=p3 # (2 -> 3: heat exchange with constant pressure)
            h2s=CP.PropsSI('H','P',p2,'S',s1,self.fluid)
            h2=h1+(h2s-h1)/self.eta
            T2=CP.PropsSI('T','P',p2,'H',h2,self.fluid)
            s2=CP.PropsSI('S','P',p2,'H',h2,self.fluid)

            # State 4:
            p4=p1 # (4 -> 1: heat exchange with constant pressure)
            h4=h3 # (3 -> 4: expansion with constant enthalpy)
            T4=CP.PropsSI('T','P',p4,'H',h4,self.fluid)
            s4=CP.PropsSI('S','P',p4,'H',h4,self.fluid)

            m1 = P_el / (h2-h1)

            dot_Q_hp = m1 * (h2-h3)

            cop = dot_Q_hp / P_el
            next_exec_time = pd.Timedelta(60, 'sec') + time

        else:
            P_el = 0
            cop = 0
            dot_Q_hp = P_el * cop
            next_exec_time = pd.Timedelta(1, 'day') + time
            
        return {'next_exec_time': next_exec_time, 'P_el':P_el, 'dot_Q_hp':dot_Q_hp}
    

class HeatPumpCoolingcircleWControl():
    def __init__(self, name, delta_t=60, eta=0.8433, dot_Q_hp_nom=15000, P_el_max=5700, P_el_min=1000, fluid='R290') -> None:
        ''''
        Heat pump model with with cooling circle and control
        Parameter
        ---------
        name : str, name of the model
        delta_t : int, timestep in s, default 60s
        eta : float, isentropic efficiency (no unit)
        dot_Q_hp_nom : float, nominal heating power in W
        P_el_max : float, maximum electrical power in W
        P_el_min : float, minimum electrical power in W
        fluid : str, cooling fluid used in cooling circle

        Inputs
        ---------
        T_source : float, source/outside temperature in °C
        T_sink : float, room temperature in °C
        state : binary, variable controlling the heat pump (no unit)

        Outputs
        ---------
        P_el : float, calculated electrical power in W
        dot_Q_hp : float, calculated heating power in W
        '''

        # Parameter
        self.delta_t      = delta_t # s

        self.eta          = eta # isentropic efficiency
        self.dot_Q_hp_nom = dot_Q_hp_nom # nominal hating power in W
        self.P_el_max     = P_el_max # maximum electrical power in W
        self.P_el_min     = P_el_min # minimum electrical power in W
        self.fluid        = fluid # cooling fluid

        # inputs outputs 
        self.inputs  = ['state', 'T_source', 'T_sink']
        self.outputs = ['P_el', 'dot_Q_hp']
        self.name = name

    def step(self, time, state, T_source, T_sink):
        if state == 1:

            dot_Q_hp_nom = self.dot_Q_hp_nom
            x1=1 # fraction of vapor
            T1=T_source -3 # °C
            x3=0 # fraction of vapor
            T3=T_sink +3   # °C

            # State 1:
            h1=CP.PropsSI('H','T',T1+273.15,'Q',x1,self.fluid)
            p1=CP.PropsSI('P','T',T1+273.15,'Q',x1,self.fluid)
            s1=CP.PropsSI('S','T',T1+273.15,'Q',x1,self.fluid)

            # State 3:
            h3=CP.PropsSI('H','T',T3+273.15,'Q',x3,self.fluid)
            p3=CP.PropsSI('P','T',T3+273.15,'Q',x3,self.fluid)
            s3=CP.PropsSI('S','T',T3+273.15,'Q',x3,self.fluid)
            
            # State 2:
            p2=p3 # (2 -> 3: heat exchange with constant pressure)
            h2s=CP.PropsSI('H','P',p2,'S',s1,self.fluid)
            h2=h1+(h2s-h1)/self.eta
            T2=CP.PropsSI('T','P',p2,'H',h2,self.fluid)
            s2=CP.PropsSI('S','P',p2,'H',h2,self.fluid)

            # State 4:
            p4=p1 # (4 -> 1: heat exchange with constant pressure)
            h4=h3 # (3 -> 4: expansion with constant enthalpy)
            T4=CP.PropsSI('T','P',p4,'H',h4,self.fluid)
            s4=CP.PropsSI('S','P',p4,'H',h4,self.fluid)

            m1_nom = dot_Q_hp_nom / (h2-h3)
            P_el_setpoint = m1_nom * (h2-h1)
            P_el = max(self.P_el_min, min(P_el_setpoint, self.P_el_max))
            m1 = P_el / (h2-h1)
            dot_Q_hp = m1 * (h2-h3)
            # cop = dot_Q_hp / P_el

            next_exec_time = pd.Timedelta(60, 'sec') + time

        else:
            dot_Q_hp = 0
            P_el = 0
            next_exec_time = pd.Timedelta(1, 'day') + time
            
        return {'next_exec_time': next_exec_time, 'P_el':P_el, 'dot_Q_hp':dot_Q_hp}
    