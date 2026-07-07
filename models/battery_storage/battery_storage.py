class BatteryStorage:
    def __init__(self,
                 name,
                 delta_t             =      15 * 60, # s
                 E_max               = 30720 * 3600, # J
                 E_0_percent         =           50, # %
                 E_min_percent       =           10, # %
                 eta_charge          =        0.936, #
                 eta_discharge       =        0.936, #
                 C_rate              =            1, # 1/h
                 P_max_charge        =         8000, # W
                 P_max_discharge     =         8000, # W
                 self_discharge_rate =            0, # 1/s
                 battery_life        =        False,
                 ) -> None:
        '''
        Storage model with charging, discharging efficiencies and selfdischarge

        Parameters
        ----------
        name : str, name of the model
        delta_t : int, timestep in s,
        E_max : float, Maximum capacity in J
        E_min_percent : float, Minimum capacity in % of E_max
        E_0_percent : float, Initial capacity in % of E_max
        eta_charge : float, charging efficiency (no unit)
        eta_discharge : float, discharging efficiency (no unit)
        C_rate : float, C-rate in 1/h used to derive default power limits
        P_max_charge : float | None, maximum charging Power in W
            If None, derived from C_rate and usable capacity.
        P_max_discharge : float | None, maximum discharging Power in W
            If None, derived from C_rate and usable capacity.
        self_discharge_rate : float selfdischarge rate in 1/s

        Inputs
        ----------
        P_set : Setpoint Power in W

        Outputs
        ----------
        P_bat : Actual Battery Power in W
        E : Energy content in storage in J
        SOC_percent : State of Charge in % of E_max
        SOC_min_percent : Minimum State of Charge in % of E_max (dynamic if battery_life is True)
        '''

        self.inputs  = ['P_set']
        self.outputs = ['P_bat', 'E', 'SOC_percent', 'SOC_min_percent']
        self.name    = name

        # Parameters
        self.delta_t             = delta_t
        self.E_max               = E_max
        self.E_min               = E_max * E_min_percent / 100.0
        self.eta_charge          = eta_charge
        self.eta_discharge       = eta_discharge
        self.C_rate              = C_rate
        usable_capacity_joule    = self.E_max - self.E_min
        default_power_limit      = self.C_rate * usable_capacity_joule / 3600
        self.P_max_charge        = default_power_limit if P_max_charge is None else P_max_charge
        self.P_max_discharge     = default_power_limit if P_max_discharge is None else P_max_discharge
        self.self_discharge_rate = self_discharge_rate

        # State
        self.E         = E_max * E_0_percent / 100.0  # J

        # Battery Life (Victron-style dynamic lower SOC limit)
        self.battery_life           = battery_life
        self._bl_min_percent        = E_min_percent
        self._bl_hard_min_percent   = E_min_percent
        self._bl_current_day        = None
        self._bl_hit_min_today      = False
        self._bl_reached_85_today   = False
        self._bl_reached_95_today   = False

    def _reset_battery_life(self, time):
        day = time.date()
        if day != self._bl_current_day:
            self._bl_current_day = day
            self._bl_prev_min_percent = self._bl_min_percent
            self._bl_hit_min_today = False
            self._bl_reached_85_today = False
            self._bl_reached_95_today = False
            self.E_min = self.E_max * self._bl_min_percent / 100.0

    def _update_battery_life(self, time, soc_percent):

        if self.E <= (self.E_min*1.2) and not self._bl_hit_min_today:
            self._bl_hit_min_today = True
            self._bl_min_percent += 5
        if soc_percent >= 85 and not self._bl_reached_85_today:
            self._bl_reached_85_today = True
            if self._bl_hit_min_today:
                self._bl_min_percent = self._bl_prev_min_percent
        if soc_percent >= 95 and not self._bl_reached_95_today:
            self._bl_reached_95_today = True
            self._bl_min_percent = max(self._bl_hard_min_percent,
                                       self._bl_min_percent - 5)

    def step(self, time, P_set):
        '''
        P_set : Setpoint Power: P_set>0... charging, P_set<0... discharging
        '''
        if self.battery_life:
            self._reset_battery_life(time)

        P_set_valid = min(self.P_max_charge, max(P_set, -self.P_max_discharge))

        # calculate potential new capacity
        if P_set_valid > 0:
            E_new = self.E + P_set_valid * self.delta_t * self.eta_charge
        else:
            E_new = self.E + P_set_valid * self.delta_t / self.eta_discharge

        # check limits and adjust
        if E_new < self.E_min:
            P_bat = (self.E_min - self.E) / self.delta_t * self.eta_discharge
            self.E = self.E_min
        elif E_new > self.E_max:
            P_bat = (self.E_max - self.E) / self.delta_t / self.eta_charge
            self.E = self.E_max
        else:
            P_bat = P_set_valid
            self.E = E_new

        soc_percent = self.E / self.E_max * 100.0

        # apply self discharge
        self.E = (self.E-self.E_min)*(1-self.self_discharge_rate*self.delta_t) + self.E_min

        if self.battery_life:
            self._update_battery_life(time, soc_percent)

        return {'P_bat': P_bat,
                'E': self.E,
                'SOC_percent': soc_percent,
                'SOC_min_percent': self.E_min / self.E_max * 100.0,
                }
