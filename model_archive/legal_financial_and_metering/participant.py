class Participant():
    def __init__(self, name, delta_t):
        '''
        Participant model, this model sums up all cost components, connected to it.

        Parameters
        ----------
        name : str, name of the participant
        delta_t : int, timedelta in seconds

        Inputs
        ----------
        c_ : float, cost cmponents in €

        Outputs
        ----------
        c_tot : total cost per period
        '''
        self.name = name
        self.delta_t = delta_t  # s

        self.inputs = ['c_'] # list attribute (endswith '_')
        self.outputs = ['c_tot']

        self.reccords = []

        # TODO: implement thermal discomfort tracking into the model

    def step(self, time, c_):
        c_tot = sum(c_)
        return {'c_tot': c_tot}