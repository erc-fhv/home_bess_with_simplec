import numpy as np
from scipy.linalg import expm

class TES():
    def __init__(
            self, name:str, delta_t=60, V=300, 
            h=1555, U=None, UA=2.5, N=10, k_1=8.2, k_2=1e6, c_p=4200, rho=1000, T_init=20
            ) -> None:
        '''
        Generic hot water Thermal Energy Storage (TES) with multiple layers.
        Can be inherited from.
        
        Parameter
        ----------
        name : str, name of the model
        delta_t : int, timestep in s, default 60s
        V : float, Volume in l
        h : float, Tank height in mm
        UA : float, optional Overal heat transfere coefficient of the tank in W/K
        U : float, optional Thermal transmittance of the tank in W/(K m^2) 
            only one of UA or U can be provided
        N : int, Number of layers
        k_1 : float, Thermal conductivity between layers for T_top >= T_bottom in W/(m K)
        k_2 : float, Thermal conductivity between layers for T_top < T_bottom in W/(m K)
        c_p : float, Specific heat capacity of the fluid in J/(kg K)
        rho : float, density of the fluid in kg/m^3
        T_init : float, Initialization Temperature for all layers in °C

        Input
        -----
        time : pd.datetime
        dot_m_i : list[float], mass flows in per layer (index 0 starts at the top) in kg/s
        T_i : list[float], Temperatures of dot_m_i in °C
        dot_m_o : list[float], mass flows out per layer (index 0 starts at the top) kg/s
        T_inf : float, environment temperature in °C
        dot_Q_in : list[float], heat input  dot_Q for each layer in W

        Output
        ------
        T_0, T_1, ..., T_N-1 : Temperatures of the layers from top (T_0) to bottom (T_N-1)
        '''

        # Convert parameters
        # Params in SI Units
        V   = V*1e-3 # Volume in l -> m^3
        h   = h*1e-3 # Tank height in mm -> m

        A_base = V / h # crossectional/base area of the tank in m^2
        d = np.sqrt(A_base / np.pi) * 2 # diameter of the tank in m
        A_lat = d*np.pi*h # lateral area of the tank
        A_tot = A_base + A_lat # Total surface area in m^2

        if U == None:
            if UA == None:
                raise ValueError('At least one of U or UA need to be supplied')
            U = UA / A_tot # Thermal transmittance of the tank in W/K/m^2
        
        UA_n = [U*A_base] + [U*A_lat/N] * N + [U*A_base]
        C_n  = [V * rho * c_p / N] * N

        # Set final parameters as attributes
        self.name = name
        self.delta_t   = delta_t

        self.UA_n:list[float] = UA_n # Heat transfere coefficient UA per layer in in W / K
        self.C_n:list[float]  = C_n  # Heat Capacity per layer J / kg
        self.N:int            = N # Number of layers
        self.A_l:float        = A_base # crossectional/base area of the tank in m^2
        self.h_l:float        = h / N # Height of the layers in m (each layer is equal) # TODO: could be made parametric
        self.k_1:float        = k_1 # Thermal conductivity between layers for T_n-1 >= T_n
        self.k_2:float        = k_2 # Thermal conductivity between layers for T_n-1 < T_n
        self.c_p:float        = c_p # Specific heat capacity of the fluid in J/(kg K)

        self.T_0:float = 273.15 # 0 °C in K

        # State
        self.x         = np.array([T_init + self.T_0]*N)
 
        # inputs outputs 
        self.inputs  = ['dot_m_i', 'T_i', 'dot_m_o', 'T_inf']
        self.outputs = [f'T_{i}' for i in range(self.N)]

    def step(self, time, dot_m_i, T_i, dot_m_o, T_inf, dot_Q_in):
        '''
        Step TES model.
        See class description for parameters.
        '''
        # Parameters
        delta_t = self.delta_t
        UA:list[float] = self.UA_n  # Thermal conductivity UA per layer in in W / K
        C:list[float]  = self.C_n   # Heat Capacity per layer J / kg
        N:int          = self.N   # Number of layers
        A_l:float      = self.A_l # Crosssectional area of the zylindric tank in m^2
        x_l:float      = self.h_l # Height of the layers in m (each layer is equal)
        k_1:float      = self.k_1 # Thermal conductivity between layers for T_n-1 >= T_n
        k_2            = self.k_2 # Thermal conductivity between layers for T_n-1 < T_n
        c_p            = self.c_p # Specific heat capacity of the fluid in J/(kg K)
        T_0            = self.T_0 # 0 °C in K
        
        # State
        x = self.x # Temperatures in K
        
        #################
        # Mass balance
        #################
        # check mass balance
        assert sum(dot_m_i) - sum(dot_m_o) == 0, 'mass balance not zero'

        dot_m     = np.zeros((N, N)) # dot_m[ein, aus]

        # Zeroth Layer
        dot_m_net = dot_m_i[0] - dot_m_o[0]
        if dot_m_net > 0:
            dot_m[0, 1] = dot_m_net
            dot_m[1, 0] = 0
        else:
            dot_m[0, 1] = 0
            dot_m[1, 0] = -dot_m_net

        # Mid Layers
        for n in range(1, N-1):
            dot_m_net = dot_m_i[n] - dot_m_o[n] + dot_m[n-1, n] - dot_m[n, n-1]
            if dot_m_net > 0:
                dot_m[n, n+1] = dot_m_net
                dot_m[n+1, n] = 0
            else:
                dot_m[n, n+1] = 0
                dot_m[n+1, n] = -dot_m_net

        #################
        # Effective thermal conductivity
        #################
        k = np.zeros(N)
        for n in range(1, N):
            if x[n-1] >= x[n]:
                k[n] = k_1
            else:
                k[n] = k_2

        #################
        # A Matrix
        #################
        A  = np.zeros((N, N))
        # Zeroth Layer (Top)
        A[0, 0]     = (-UA[0] - dot_m_o[0]*c_p - dot_m[0, 1]*c_p)/C[0] - k[1]*A_l/(x_l*C[0])
        A[0, 1]     = (dot_m[1, 0]*c_p )/C[0]+ k[1]*A_l/(x_l*C[0])

        # N-2  Mid Layers
        for n in range(1, N-1):
            A[n, n-1] = (dot_m[n-1, n]*c_p)/C[n] + k[n]*A_l/(x_l*C[n])
            A[n, n]   = (-UA[n] - dot_m_o[n]*c_p - dot_m[n, n+1]*c_p - dot_m[n, n-1]*c_p)/C[n] - k[n]*A_l/(x_l*C[n]) - k[n+1]*A_l/(x_l*C[n])
            A[n, n+1] = (dot_m[n+1, n]*c_p)/C[n] + k[n+1]*A_l/(x_l*C[n])

        # N-th Layer (Bottom)
        A[N-1, N-2] = (dot_m[N-2, N-1]*c_p)/C[N-1] + k[N-1]*A_l/(x_l*C[N-1])
        A[N-1, N-1] = (-UA[N-1] - dot_m_o[N-1]*c_p - dot_m[N-1, N-2]*c_p)/C[N-1] - k[N-1]*A_l/(x_l*C[N-1])

        #################
        # B-Matrix
        #################
        B  = np.zeros((N, 1+2*N))
        # u = [T_inf, T_1, ..., T_N, dot_Q_1, ..., dot_Q_N]
        for n in range(N):
            B[n, 0] = UA[n]/C[n]
            B[n, 1+n] = c_p/C[n]
            B[n, 1+N+n] = 1/C[n]

        #################
        # u-Vector (TODO: could be integrated into B-Matrix)
        #################
        u  = np.zeros(1+2*N)
        u[0] = T_inf + T_0
        for n in range(N):
            u[n+1] = dot_m_i[n]*(T_i[n] + T_0)
            u[1+N+n] = dot_Q_in[n]

        #################
        # discretize
        #################
        exponent = np.vstack((np.hstack((A, B)), np.zeros((B.shape[1], A.shape[1]+B.shape[1]))))*delta_t

        res = expm(exponent)

        Ad = res[:A.shape[0], :A.shape[1]]
        Bd = res[:B.shape[0], A.shape[1]:]

        ################
        # Solve
        ################
        x=Ad@x+Bd@u

        self.x = x

        return {f'T_{i}': T-T_0 for i, T in enumerate(x)}