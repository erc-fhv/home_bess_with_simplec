import numpy as np
from model_archive.TES.TES import TES

class DHWH(TES):
    def __init__(
            self, name, delta_t=60, V=300, h=1555, U=None, UA=2.5, N=10, k_1=8.2, k_2=1000000,
            c_p=4200, rho=1000, T_init=20, P_el_nom=2000., len_heat_elem=300.
            ) -> None:
        '''
        Param:
        ------
        P_el_nom : float, Nominal power of electrical heating element
        len_heat_elem : float, length of heating element in mm (from the bottom)
        '''
        self.P_el_nom = P_el_nom
        self.n_layrs_ht_elem =  int(np.ceil(len_heat_elem/(h/N)))
        super().__init__(
            name=name, delta_t=delta_t, V=V, h=h, U=U, UA=UA, N=N, k_1=k_1,
            k_2=k_2, c_p=c_p, rho=rho, T_init=T_init
            )

    def step(self, time, dot_m_o_DHW, T_i_DHW, T_inf, state):
        P_el = state * self.P_el_nom

        dot_m_i = [             0] + [0]*(self.N-2) + [   dot_m_o_DHW] # kg/s
        T_i     = [             0] + [0]*(self.N-2) + [       T_i_DHW] # K
        dot_m_o = [   dot_m_o_DHW] + [0]*(self.N-2) + [             0] # kg/s
        n = self.n_layrs_ht_elem
        dot_Q_in = [0]*(self.N-n) + [P_el/n]*n # W

        T = super().step(time, dot_m_i, T_i, dot_m_o, T_inf, dot_Q_in)

        return {'T_tw':T['T_6'], 'T_0':T['T_0'], 'P_el': P_el}
