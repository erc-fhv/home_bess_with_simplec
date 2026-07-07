class SmartMeter():
    def __init__(self, name, delta_t = 60*15):
        '''
        Smart meter model, this model sums up all electric powers connected to it.

        Parameters
        ----------
        name : str, name of the model
        delta_t : int, timestep in s, default 900 s,

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
