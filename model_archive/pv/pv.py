import pandas as pd
from pathlib import Path
from pvlib.iotools import get_pvgis_hourly
from util.cache_manager import cache_result
from model_archive.pv.geosphere_interface import get_nearest_station_values
import warnings


class PvgisPV():
    def __init__(self, name,
            latitude: float  = 47.440878,
            longitude: float = 9.996436,
            start: str = '2009-01-01 00:00',
            end: str   = '2010-01-01 23:59',
            surface_tilt: float = 0.,
            surface_azimuth: float = 180.,
            peakpower: float= 5.,
            tz: str = 'UTC',
            only_power = True,
            upsample_w_geosphere: bool = False,
            geo_max_dist: float = 10.,
            resample_15_min = False,
            **kwargs,
            ):
        '''
        PV model based on PVGis with hourly resolution and a method for upsampling to 10 min.

        Parameter:
        ---------

        latitude : In decimal degrees, between -90 and 90, north is positive (ISO 19115)
        longitude : In decimal degrees, between -180 and 180, east is positive (ISO 19115)
        start : start time, like '2009-01-01 00:00' in UTC
        end : end time, like '2010-01-01 23:59' in UTC
        surface_tilt : Tilt angle from horizontal plane
        surface_azimuth : Orientation (azimuth angle) of the (fixed) plane. Clockwise from north
         (north=0, east=90, south=180, west=270)
        peakpower : float, Nominal power of PV System in kW
        upsample_w_geosphere : bool, Experimental feature; uses closest geosphere austria data to
        upsample PV data to 10 minutes, might fail for locations! See Notes. Default is False.
        tz : str, timezone spezifier in accordance with pandas. The time zone,
         the index is converted to. Default is 'UTC'. Note that `start` and `end` are specified in
         UTC and need to consider time zone conversion.
        only_power : bool, model only has one output, "P", otherwise weather data from PvGis
         will be included
        geo_max_dist : float, maximum distance to next gesophere station for upsampling in km,
         raise error if exceeded. Default is 10 km.
        resample_15_min : Resample the 10 min upsampled PV data to 15 min resolution.
         Only takes effect when  upsample_w_geosphere = True. Default: True
        **kwargs are passed to .get_pvgis_hourly, see nots for additional info.

        Inputs:
        ------
        None

        Outputs:
        -------
        P : float, electrical PV system power (ac-side) in W (feedin < 0)

        Notes:
        ------
        - documentation for the PVgis web tool can be useful: https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/getting-started-pvgis/pvgis-user-manual_en
        - upsample_w_geosphere is an experimental feature which only works for austrian locations.
        The sub hour behaviour of the PV power output is created using radiation data from the
        closest weather station from geosphere.
         The data is scaled to have the same hourly yield, therefore, the sub hour behaviour might
         not be to scale, compared to a real system.
        - Common **kwargs for PVGis are (see PVGis docs for complete list):
            usehorizon : Include effects of horizon
            pvcalculation : Return estimate of hourly PV production
            peakpower : Nominal power of PV system in kW
            pvtechchoice : ({'crystSi', 'CIS', 'CdTe', 'Unknown'}, default: 'crystSi')
            mountingplace : ({'free', 'building'}, default: free) – Type of mounting for PV system.
            Options of ‘free’ for free-standing and ‘building’ for building-integrated.
            loss : (float, default: 0) – Sum of PV system losses in percent. Required if
            pvcalculation=True
            optimal_surface_tilt : (bool, default: False) – Calculate the optimum tilt angle.
            Ignored for two-axis tracking
            optimalangles : (bool, default: False) – Calculate the optimum tilt and azimuth angles.
            Ignored for two-axis tracking.
        '''
        self.name = name
        params = dict(
            latitude             = latitude,
            longitude            = longitude,
            start                = start,
            end                  = end,
            surface_tilt         = surface_tilt,
            surface_azimuth      = surface_azimuth,
            peakpower            = peakpower,
            tz                   = tz,
            only_power           = only_power,
            **kwargs
            )

        if upsample_w_geosphere:
            self.df = self.get_df_pvgis_upsample_geosphere(geo_max_dist=geo_max_dist, **params)
            self.delta_t = 600 # s = 10 min
            if resample_15_min:
                self.df = self.df.resample('5min', origin='start').interpolate(deg=1) # upsample 5
                self.df = self.df.resample('15min', origin='start').mean() # downsample 15 min
                self.delta_t = 900 # s = 15 min
        else:
            self.df = self.get_preprocess_pvgis_hourly_df(**params)
            self.delta_t = 3600 # s

        self.inputs = []
        self.outputs = list(self.df.columns)

    @staticmethod
    @cache_result()
    def get_preprocess_pvgis_hourly_df(only_power, tz: str='UTC', **pvgis_params) -> pd.DataFrame:
        """
        Interface to PvGis, only returs the pd.DataFrame with basic preprocessing.
        Results are cached with cache_manager

        Parameters:
        ----------
        tz : str, timezone spezifier in accordance with pandas. The time zone, the index is
        converted to. Default is 'UTC'.
        pvgis_params : dict, parameters passed to PVGis `get_pvgis_hourly`

        Notes:
        ------
        - Only complete years can be loaded, therefore, the imported dataframe is cliped exactly to
        the selected date range after download.
        - The Power values of PVGis are positive, to conform with modelling convention,
        they need to be converted to negative values
        - To simplify interaction with other models, the index is rounded to full hours.
        The introduced error should be acceptable for most analysis.
            - The timestamps provided by PVGis are regularly hourly, however, depending on the
            dataset, the timesteps do not fall onto zero minutes for example they fall on HH:10.
            See the description in the official PVGis documentation for the reason for the time
            offset here:
            https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/getting-started-pvgis/pvgis-user-manual_en#ref-9-hourly-solar-radiation-and-pv-data
            - Considering, that PVGis provides instance measurements (depended on the Database) and
            not hourly means, justifies this decision.
        - Timezone can be converted to specified timezone
        """
        df = get_pvgis_hourly(pvcalculation=True, **pvgis_params)[0]
        df = df.loc[pvgis_params['start']:pvgis_params['end'],:]
        df['P'] = -df['P']
        df.index = df.index.round('h')
        df.index = df.index.tz_convert(tz)
        if only_power:
            df = df[['P']]
        return df

    def get_df_pvgis_upsample_geosphere(
            self, latitude, longitude, start, end, geo_max_dist, **kwargs
            ):
        pvgis_data = self.get_preprocess_pvgis_hourly_df(
            latitude  = latitude,
            longitude = longitude,
            start = start,
            end   = end,
            **kwargs
            )
        global_irradiance_geosphere = get_nearest_station_values(
            lat = latitude,
            lon = longitude,
            start_dt=start,
            end_dt=end,
            max_dist=geo_max_dist,
            parameters=['CGLO']).iloc[:,0]

        nans_count = global_irradiance_geosphere.isna().sum()
        # missing = "".join([("x" if i else " ") for i in global_irradiance_geosphere.isna().resample("7d").apply(any)])
        if nans_count > 0:
            pct_nans = nans_count / len(global_irradiance_geosphere) * 100
            warnings.warn(
                f'Global irradiation contains {nans_count} Nans ({pct_nans:.2f}%).'+
                f'Fallback to hourly values where missing.', #  Visualization: [{missing}]',
                UserWarning
                )
#             # TODO: Test if nearest station contains nans take next one.
#             # TODO: implement options to pass a specific station_id in case the nearest stations fails
            global_irradiance_geosphere = global_irradiance_geosphere.astype(float).fillna(0.)

        global_irradiance_geosphere = -global_irradiance_geosphere
        global_irradiance_geosphere.index = global_irradiance_geosphere.index.tz_convert(
            kwargs['tz']
            )
        self.global_irradiance_geosphere = global_irradiance_geosphere

        ser = self.upsample_pvgis_w_geosphere(pvgis_data["P"], global_irradiance_geosphere)

        ser.name = 'P'
        # ser = ser.dropna()
        df = pd.DataFrame(ser)
        return df

    # @staticmethod
    # def upsample_pvgis_w_geosphere(P: pd.Series, g: pd.Series):
    #     r"""Use global irradiance from geosphere to upsample hourly timeseries
    #     of PvGis to 10 min resolution
    #     Upsampling with geosphere data is conducted as such:

    #     Parameter:
    #     -P : pd.Series, hourly Power with datetime index from PVGis
    #     -g : pd.Series, 10 minute global irradiance with datetime index from geosphere for same
    #         time as P

    #     Notes:
    #     ------
    #     The hourly PV generation is denoted as $P$ and 10 minute resolution irradiance data from
    #     Gesophere is denoted as $g_t: \forall \;t\in T$ with $T = \{1, 2, ..., 6\}$.

    #     Now for every hour, $P$ is upsampled to $P_t \in T$  as such:

    #     1. $g_t$ is scaled to match $P$ in mean as such:
    #         $$
    #         \tilde g_t =
    #         \begin{cases}
    #         g_t  \dfrac{P}{\bar g}, &\bar g>0, \\
    #         0,&\bar g=0,
    #         \end{cases} \qquad \forall t \in T.
    #         $$
    #         Where $\tilde g_t$ is the scaled irradiation and $\bar g$ the mean radiation for that hour.

    #     2. The scaled irradiation is added to $P$ and its mean is substracted.
    #         $$
    #         P_t = P + \tilde g_t - \bar g \qquad \forall t\in T.
    #         $$
    #     This guarantees energy preservation per hour since $\frac{1}{|T|}\sum_{t\in T} P_t = P$.
    #     """
    #     P.name = 'P'
    #     g.name = 'g'
    #     # merge relies on both series having a common 10 minute resolution
    #     merged = pd.merge(
    #         g, P, left_index=True, right_index=True, how='outer'
    #         )

    #     # ffill P_pvgis and remove first instances with dropna()
    #     # as PvGis starts at uneven times e.g. (required for resample start)
    #     merged = merged.ffill().dropna()

    #     def aggregation_func(df):
    #         assert len(df["P"].unique()) == 1, "Something is off with P data indexing: df={df}"

    #         P = df["P"].iloc[0]
    #         if df['g'].sum() != 0.:
    #             # scale noise to same hourly sum as Power
    #             df['g_scaled'] = df['g'] * P / df['g'].mean()
    #         else:
    #              df['g_scaled'] = 0
    #         col = P + df["g_scaled"] - df["g_scaled"].mean()
    #         return col

    #     # Time offset from PVGis can vary dependig on location, see PVGis Docs
    #     # start resampling at firts value (works after dropna)
    #     P = merged.resample('h', origin='start').apply(aggregation_func)
    #     return P.clip(None, 0) # no positive powers (can occure due to numerical issues)

    # @staticmethod
    # def upsample_pvgis_w_geosphere(P: pd.Series, g: pd.Series):
    #     r"""Use global irradiance from geosphere to upsample hourly timeseries
    #     of PvGis to 10 min resolution
    #     Upsampling with geosphere data is conducted as such:

    #     Parameter:
    #     -P : pd.Series, hourly Power with datetime index from PVGis
    #     -g : pd.Series, 10 minute global irradiance with datetime index from geosphere for same
    #         time as P

    #     Notes:
    #     ------
    #     The hourly PV generation is denoted as $P$ and 10 minute resolution irradiance data from
    #     Gesophere is denoted as $g_t: \forall \;t\in T$ with $T = \{1, 2, ..., 6\}$.

    #     Now for every hour, $P$ is upsampled to $P_t \in T$  as such:


    #     """
    #     P.name = 'P'
    #     g.name = 'g'
    #     # merge relies on both series having a common 10 minute resolution
    #     merged = pd.merge(
    #         g, P, left_index=True, right_index=True, how='outer'
    #         )

    #     # ffill P_pvgis and remove first instances with dropna()
    #     # as PvGis starts at uneven times e.g. (required for resample start)
    #     merged = merged.ffill().dropna()

    #     scale = merged['P'].sum() / merged['g'].sum()

    #     def aggregation_func(df):
    #         assert len(df["P"].unique()) == 1, "Something is off with P data indexing: df={df}"

    #         P = df["P"].iloc[0]
    #         if df['g'].sum() != 0.:
    #             # scale noise to same hourly sum as Power
    #             # df['g_scaled'] = df['g'] * P / df['g'].mean()
    #             df['g_scaled'] = df['g'] * scale
    #         else:
    #              df['g_scaled'] = 0
    #         col = P + df["g_scaled"] - df["g_scaled"].mean()
    #         return col

    #     # Time offset from PVGis can vary dependig on location, see PVGis Docs
    #     # start resampling at firts value (works after dropna)
    #     P = merged.resample('h', origin='start').apply(aggregation_func)
    #     return P # .clip(None, 0) # no positive powers (can occure due to numerical issues)

    # @staticmethod
    # def upsample_pvgis_w_geosphere(P: pd.Series, g: pd.Series):
    #     r"""Use global irradiance from geosphere to upsample hourly timeseries
    #     of PvGis to 10 min resolution
    #     Upsampling with geosphere data is conducted as such:

    #     Parameter:
    #     -P : pd.Series, hourly Power with datetime index from PVGis
    #     -g : pd.Series, 10 minute global irradiance with datetime index from geosphere for same
    #         time as P

    #     Notes:
    #     ------
    #     The hourly PV generation is denoted as $P$ and 10 minute resolution irradiance data from
    #     Gesophere is denoted as $g_t: \forall \;t\in T$ with $T = \{1, 2, ..., 6\}$.

    #     Now for every hour, $P$ is upsampled to $P_t \in T$  as such:


    #     """
    #     P.name = 'P'
    #     g.name = 'g'
    #     # merge relies on both series having a common 10 minute resolution
    #     merged = pd.merge(
    #         g, P, left_index=True, right_index=True, how='outer'
    #         )

    #     # ffill P_pvgis and remove first instances with dropna()
    #     # as PvGis starts at uneven times e.g. (required for resample start)
    #     merged = merged.ffill().dropna()

    #     hourofday = merged.groupby(merged.index.hour).sum()
    #     scale = hourofday['P'] / hourofday['g']

    #     def aggregation_func(df):
    #         # assert len(df["P"].unique()) == 1, "Something is off with P data indexing: df={df}"

    #         P = df["P"].iloc[0]
    #         hour = df.index[0].hour
    #         if df['g'].sum() != 0.:
    #             # scale noise to same hourly sum as Power
    #             # df['g_scaled'] = df['g'] * P / df['g'].mean()
    #             df['g_scaled'] = df['g'] * scale.loc[hour]
    #         else:
    #              df['g_scaled'] = 0
    #         col = P + df["g_scaled"] - df["g_scaled"].mean()
    #         return col

    #     # Time offset from PVGis can vary dependig on location, see PVGis Docs
    #     # start resampling at firts value (works after dropna)
    #     P = merged.resample('h', origin='start').apply(aggregation_func)
    #     return P # .clip(None, 0) # no positive powers (can occure due to numerical issues)

    @staticmethod
    def upsample_pvgis_w_geosphere(P: pd.Series, g: pd.Series):
        r"""Use global irradiance from geosphere to upsample hourly timeseries
        of PvGis to 10 min resolution
        Upsampling with geosphere data is conducted as such:

        Parameter:
        -P : pd.Series, hourly Power with datetime index from PVGis
        -g : pd.Series, 10 minute global irradiance with datetime index from geosphere for same
            time as P

        Notes:
        ------
        The hourly PV generation is denoted as $P$ and 10 minute resolution irradiance data from
        Gesophere is denoted as $g_t: \forall \;t\in T$ with $T = \{1, 2, ..., 6\}$.

        Now for every hour, $P$ is upsampled to $P_t \in T$  as such:

        1. $g_t$ is scaled to match $P$ in mean as such:
            $$
            \tilde g_t =
            \begin{cases}
            g_t  \dfrac{P}{\bar g}, &\bar g>0, \\
            0,&\bar g=0,
            \end{cases} \qquad \forall t \in T.
            $$
            Where $\tilde g_t$ is the scaled irradiation and $\bar g$ the mean radiation for that hour.

        2. The scaled irradiation is added to $P$ and its mean is substracted.
            $$
            P_t = P + \tilde g_t - \bar g \qquad \forall t\in T.
            $$
        This guarantees energy preservation per hour since $\frac{1}{|T|}\sum_{t\in T} P_t = P$.
        """
        P = -P # negate negative series for easier logic
        g = -g
        P_max = P.max()
        P.name = 'P'
        g.name = 'g'
        # merge relies on both series having a common 10 minute resolution
        merged = pd.merge(
            g, P, left_index=True, right_index=True, how='outer'
            )

        # ffill P_pvgis and remove first instances with dropna()
        # as PvGis starts at uneven times e.g. (required for resample start)
        merged = merged.ffill().dropna()

        def aggregation_func(df):
            assert len(df["P"].unique()) == 1, "Something is off with P data indexing: df={df}"
            P = df["P"].iloc[0]
            g_max = df['g'].max()
            g_mean = df['g'].mean()

            if df['g'].sum() != 0.:
                # scale g to same hourly sum as Power
                scale = P / g_mean
                df['g_scaled'] = df['g'] * scale
            else:
                 df['g_scaled'] = 0
            col = P + df["g_scaled"] - df["g_scaled"].mean()

            if col.max() > P_max: # make sure, the maximum is not exceeded
                scale = (P_max - P) / (g_max - g_mean)
                df['g_scaled'] = df['g'] * scale
                col = P + df["g_scaled"] - df["g_scaled"].mean()
            return col

        # Time offset from PVGis can vary dependig on location, see PVGis Docs
        # start resampling at firts value (works after dropna for merged df)
        P = merged.resample('h', origin='start').apply(aggregation_func)
        return -P.clip(0, P_max) # out of bounds can occure due to numerical innaccuracies

    def step(self, time):
        return self.df.loc[time].to_dict()


if __name__ == "__main__":
    pv = PvgisPV('test')
    time = pv.df.index[0]
    result = pv.step(time)
