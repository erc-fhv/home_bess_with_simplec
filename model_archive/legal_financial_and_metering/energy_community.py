import pandas as pd

class EnergyCommunity():
    '''Simple EnergyCommunity to calculate prices for participants

    Parameters
    -----------
    price_consumption : pd.Series datetime indexed prices time series in €
    price_feedin : pd.Series datetime indexed prices time series in €
    suffix : str, suffix for the model name, that gets appended to the input models name

    Inputs
    ------
    P_el : dict[str:float], Electrical power per consumer / producer traded within the EC

    Outputs
    --------
    cost_dict : dict, multiioutput cost per participant in €
    profit_ec : float, profit of the ec in €

    Sign convention
     - P > 0  -> consumption
     - P < 0  -> generation
    '''
    delta_t = 15 * 60 # s
    inputs = ['P_el']
    outputs = ['cost_dict', 'profit_ec']

    def __init__(
            self, name, price_consumption: float, price_feedin: float, suffix: str = '_bill'
            ) -> None:
        self.name = name
        self.price_consumption = price_consumption
        self.price_feedin = price_feedin
        self.suffix = suffix

    def step(self, time, P_el):
        cost_dict = {}
        profit_ec = 0
        for model, P in P_el.items():
            if P > 0: # Consumption
                cost = \
                    self.price_consumption * P * self.delta_t / 1000 / 3600 # €/kWh * W * s *(1 k / 1000) * (1 h / 3600 s)
                cost_dict[model + self.suffix] = cost
                profit_ec += cost
            else: # feedin
                cost = \
                    self.price_feedin * P * self.delta_t / 1000 / 3600 # €/kWh * W * s *(1 k / 1000) * (1 h / 3600 s)
                cost_dict[model + self.suffix] = cost
                profit_ec += cost

        return {'cost_dict': cost_dict, 'profit_ec': profit_ec}