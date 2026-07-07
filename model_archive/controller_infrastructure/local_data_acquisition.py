class LocalDataAcquisition():
    def __init__(self, name, delta_t=900, has_gen=True, has_load=True, has_flex=False, has_state=False) -> None:
        '''Local data acquisition model for a grid connection / metering point.

        Collects generation (PV) and load (household) data at a metering point
        and computes the uncontrolled residual power for the centralized controller.
        Collects individual flexibility powers and states keyed by component name.

        Parameter:
        ---------
        name : str, name of the model (typically the metering point identifier)
        delta_t : int, time step in seconds (default: 900 = 15 min)
        has_gen : bool, whether generation (PV) inputs are connected (default: True)
        has_load : bool, whether load inputs are connected (default: True)
        has_flex : bool, whether flexibility feedback inputs are connected (default: False)
        has_state : bool, whether shifted local state feedback inputs are connected (default: False)

        Inputs (depending on flags):
        -------
        P_gen_ : list[float], generation powers (feedin < 0) in W
        P_load_ : list[float], load powers (consumption > 0) in W
        P_flex_dict : dict[str, float], individual flexibility powers in W (time-shifted feedback),
                  keyed by component/battery name
        E_flex_dict : dict[str, float], individual local storage states in J (time-shifted feedback),
                   keyed by component/battery name

        Outputs:
        --------
        P_residual : float, uncontrolled residual power (gen + load, excludes flex) in W.
                     Negative means surplus (net export), positive means deficit (net import).
        P_flex : dict[str, float], individual flexibility powers keyed by component name
        E_flex : dict[str, float], individual storage states keyed by component name
        '''
        self.name = name
        self.delta_t = delta_t

        self.inputs = []
        if has_gen:
            self.inputs.append('P_gen_')
        if has_load:
            self.inputs.append('P_load_')
        if has_flex:
            self.inputs.append('P_flex_dict')
        if has_state:
            self.inputs.append('E_flex_dict')
        self.outputs = ['P_residual', 'P_flex', 'E_flex']

    def step(self, time, P_gen_=None, P_load_=None, P_flex_dict=None, E_flex_dict=None):
        # Handle None defaults (fixes mutable default argument issue)
        if P_gen_ is None:
            P_gen_ = []
        if P_load_ is None:
            P_load_ = []
        if P_flex_dict is None:
            P_flex_dict = {}
        if E_flex_dict is None:
            E_flex_dict = {}
        
        # Compute uncontrolled residual (gen + load only, excludes flex feedback)
        P_residual = sum(P_gen_) + sum(P_load_)
        
        # Pass through flexibility powers and states as dicts for central controller to access
        return {
            'P_residual': P_residual,
            'P_flex': P_flex_dict,
            'E_flex': E_flex_dict,
        }
