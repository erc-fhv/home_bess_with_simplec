class CentralSurplusController():
    def __init__(self, name, flex_config, delta_t=900) -> None:
        '''Centralized surplus power controller for an energy community.

        Collects residual power from all metering points and dispatches
        setpoints to flexibilities proportional to their maximum capacity.

        Parameter:
        ---------
        name : str, name of the model
        flex_config : dict, mapping of decentral flex controller names to their
                      maximum power capacity in W.
                      Example: {'decentral_bes_1': 5000, 'decentral_bes_2': 3000}
        delta_t : int, time step in seconds (default: 900 = 15 min)

        Inputs:
        -------
        P_residual_ : list[float], residual powers from all LocalDataAcquisition
                       instances in W. Negative = surplus, positive = deficit.

        Outputs:
        --------
        P_set_dict : dict[str, float], setpoint powers keyed by decentral flex
                     controller name. Positive = charge, negative = discharge.
                     Routed via SimPlEC _dict convention.
        '''
        self.name = name
        self.delta_t = delta_t
        self.flex_config = flex_config

        self.inputs = ['P_residual_']
        self.outputs = ['P_set_dict']

    def step(self, time, P_residual_):
        total_residual = sum(P_residual_)

        # Negative residual = surplus → charge (positive P_set)
        # Positive residual = deficit → discharge (negative P_set)
        P_set_total = -total_residual

        total_capacity = sum(self.flex_config.values())

        P_set_dict = {}
        for flex_name, P_max in self.flex_config.items():
            if total_capacity > 0:
                share = P_max / total_capacity
            else:
                share = 0
            P_set = P_set_total * share
            P_set = max(-P_max, min(P_max, P_set))
            P_set_dict[flex_name] = P_set

        return {'P_set_dict': P_set_dict}
