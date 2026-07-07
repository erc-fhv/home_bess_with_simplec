class DecentralFlexController():
    def __init__(self, name, delta_t=900) -> None:
        '''Decentralized flexibility controller that relays setpoints from the
        centralized controller to a local flexibility model.

        Acts as a pass-through. Serves as an extension point for future local
        safety logic (SOC limits, ramp rates, etc.).

        Parameter:
        ---------
        name : str, name of the model
        delta_t : int, time step in seconds (default: 900 = 15 min)

        Inputs:
        -------
        P_cmd : float, commanded power setpoint from CentralSurplusController in W

        Outputs:
        --------
        P_set : float, setpoint power forwarded to the flexibility model in W
        '''
        self.name = name
        self.delta_t = delta_t

        self.inputs = ['P_cmd']
        self.outputs = ['P_set']

    def step(self, time, P_cmd):
        return {'P_set': P_cmd}
