class Grid():
    def __init__(self, name, delta_t = 60):

        '''
        Grid model with calculation of power at the substation

        Parameters
        ----------
        name : str, name of the model
        delta_t : int, timestep in s, default 60s, 
        
        Inputs
        ----------
        P_ : Multiple input powers in W
        
        Outputs
        ----------
        P_substation : Grid power at substation in W
        '''

        self.name = name
        self.delta_t = delta_t  # s

        self.inputs = [f'P_'] 
        self.outputs = ['P_substation']

    def step(self, time, P_):
        P_substation = sum(P_)
        return {'P_substation': P_substation}
    