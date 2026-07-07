class HystController():
    def __init__(self, name, delta_t=60, T_set=21, hyst=4, state_0=0) -> None:
        '''Simple Hysteresis Controller that controlls a given value (e.g. temperature) around a mean value with a given hysteresis

        Parameter:
        ---------
        name : str, name of the model
        delta_t : timedelta of the controller
        T_set : float, setpoint temperature
        hyst : float, hysteresis band, centered around the mean of T_set
        state_0 : bool or 1/0, state at time=0

        Inputs:
        -------
        T_is : float, current temperatue (or other input value)

        Outputs:
        --------
        state : bool or 0/1, setpoint state for the controlled unit
        '''
        # Parameter
        self.delta_t = delta_t

        self.T_set = T_set 
        self.hyst = hyst

        self.state = state_0

        self.inputs  = ['T_is']
        self.outputs = ['state']

        self.name = name

    def step(self, time, T_is):
        if T_is > self.T_set + self.hyst/2: # upper limit; switch off
            self.state = 0
        elif T_is < self.T_set - self.hyst/2:  # lower limit, switch on
            self.state = 1
        else:
            pass # else leave state as is
        return {'state': self.state}