class ResidualLoadController():
    def __init__(self, name, delta_t=60) -> None:
        '''Simple Residual Load Controller that controlls a given flexibility by the excess power of the last time step.

        Parameter:
        ---------
        name : str, name of the model
        delta_t : timedelta of the controller

        Inputs:
        -------
        P_tot : float, current total grid power (feedin < 0) in W
        P_flex_ : list[float], Power of flexibilities, (feedin < 0) in W

        Outputs:
        --------
        P_set : float, setpoint power for the controlled unit in W
        '''
        # Parameter
        self.delta_t = delta_t

        self.inputs  = ['P_tot', 'P_flex_']
        self.outputs = ['P_set']

        self.name = name

    def step(self, time, P_tot, P_flex_):
        P_set = -P_tot + sum(P_flex_)
        return {'P_set': P_set}