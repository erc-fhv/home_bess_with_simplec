import pandas as pd

class DistributionSystemOperatorECAware():
    '''
    Simple Distribution System Operator model

    It calculates grid fees and splits the demand
    into energy community and non energy community demand/supply.

    Parameters
    ----------
    name : str, name of the model
    grid_fee_ec_consumption : float, in €/kWh
    grid_fee_ec_feedin : float, in €/kWh
    grid_fee_consumption : float, in €/kWh
    grid_fee_feedin : float, in €/kWh

    Inputs
    ------
    P_el_ec_dict : float (multiinput), Electric power for consumers / producers in the EC
    (P_el_dict : float (multiinput), Electric power for consumers / producers not in the EC)

    Sign convention:
     - P > 0  -> consumption
     - P < 0  -> generation

    Outputs
    --------
    grid_fee_dict : participant_grid_fee,
    P_ec : dict of EC power for the EC operator
    P_residual : dict of residual power for the utility company
    '''
    delta_t = 15 * 60 # s
    inputs = ['P_el_ec_dict'] # , 'P_el_dict']
    outputs = ['grid_fee_dict', 'P_ec', 'P_residual']

    def __init__(self, name, grid_fee_ec_consumption: float, grid_fee_ec_feedin: float,
                 grid_fee_consumption: float, grid_fee_feedin: float, suffix: str = '_bill'
                 ) -> None:
        self.name = name
        self.grid_fee_ec_consumption = grid_fee_ec_consumption
        self.grid_fee_ec_feedin = grid_fee_ec_feedin
        self.grid_fee_consumption = grid_fee_consumption
        self.grid_fee_feedin = grid_fee_feedin
        self.suffix = suffix

    def step(self, time, P_el_ec_dict):  # , P_el_dict):
        ###################
        # Calculate Energy traded in EC
        ###################
        # Initialize output dicts
        eg_power = {k: 0.0 for k in P_el_ec_dict}
        residual = {}

        # Separate consumers and generators
        consumers = {k: v for k, v in P_el_ec_dict.items() if v > 0}
        generators = {k: -v for k, v in P_el_ec_dict.items() if v < 0}  # make positive

        total_consumption = sum(consumers.values())
        total_generation = sum(generators.values())

        if total_consumption == 0 or total_generation == 0: # No EG trading possible
            residual = P_el_ec_dict.copy()
        else:
            # Amount of power that can be traded inside the EG
            traded_power = min(total_consumption, total_generation)

            # 1) Allocate EG power to consumers proportionally
            for meter, cons in consumers.items():
                share = cons / total_consumption
                eg_power[meter] = share * traded_power

            # 2) Allocate EG power to generators proportionally (negative sign!)
            for meter, gen in generators.items():
                share = gen / total_generation
                eg_power[meter] = -share * traded_power

            # 3) Compute residual (import/export with grid)
            for meter, p in P_el_ec_dict.items():
                residual[meter] = p - eg_power[meter]

        ###################
        # Calculate grid fees for each participant
        ###################
        participant_grid_fee = {}
        # # Calculate grid fees for each participant not in EC
        # for model, P in P_el_dict.items():
        #     if P > 0: # Consumption
        #         participant_grid_fee[model] = self.grid_fee_consumption * P * self.delta_t
        #     else: # feedin
        #         participant_grid_fee[model] = self.grid_fee_feedin * P * self.delta_t
        # Calculate grid fees for each participant in EC
        for meter in P_el_ec_dict.keys():
            P_eg = eg_power[meter]
            P_resid = residual[meter]
            if P_eg > 0 or P_resid > 0: # Consumption
                participant_grid_fee[meter + self.suffix] = \
                    (self.grid_fee_ec_consumption * P_eg
                    + self.grid_fee_consumption * P_resid) \
                    * self.delta_t / 1000 / 3600 # €/kWh * W * s *(1 k / 1000) * (1 h / 3600 s)
            else: # feedin
                participant_grid_fee[meter + self.suffix] = \
                    - (self.grid_fee_ec_feedin * P_eg
                    + self.grid_fee_feedin * P_resid) \
                    * self.delta_t / 1000 / 3600 # €/kWh * W * s *(1 k / 1000) * (1 h / 3600 s)

        return {
            'grid_fee_dict': participant_grid_fee,
            'P_ec': eg_power,  # power dict for the EC operator
            'P_residual': residual # power dict for the utility company
            }