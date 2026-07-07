import os
from pathlib import Path
import pickle
import pandas as pd
from typing import Protocol


DEFAULT_HORIZON = 34 * 4    # 34 hours * 4 (15-min intervals) = 136 steps

class ResidualForecaster(Protocol):
    def forecast(self, time: pd.Timestamp) -> pd.Series:
        """Return net-load forecast in kW indexed by horizon timestamps."""
        ...


class GamResidualForecaster(ResidualForecaster):
    """Forecast residual net load in kW from weather horizons using the GAM model."""

    def __init__(
        self,
        weather_parquet: str | Path | None = None,
        model_filename: str | Path | None = None,
        use_real_horizon: bool = True,
        fixed_horizon_steps: int = DEFAULT_HORIZON,
    ):

        self.weather_cols = ['temperature_2m', 'wind_speed_10m', 'global_tilted_irradiance']
        self._use_real_horizon = use_real_horizon
        self._fixed_horizon_steps = fixed_horizon_steps
        self._model = None
        self.lagged_power = 7*24*4    # 7 Tage * 24 Stunden * 4 (15-Minuten-Intervalle)
        self.use_lagged_power = False

        if model_filename is None:
            model_filename = (
                Path(__file__).parent.parent.parent / 'data' / 'mp_controller_homebattery'
                / 'gam_model.pkl'
            )
        self.model_filename = Path(model_filename)

        if weather_parquet is None:
            weather_parquet = (
                Path(__file__).parent.parent.parent / 'data' / 'mp_controller_homebattery'
                / 'mpc_results_20260410_193659.parquet'
            )

        self._weather = pd.read_parquet(
            weather_parquet,
            columns=self.weather_cols + ['mpc_time', 'timestamp'],
        )
        self._weather['mpc_time'] = self._weather['mpc_time'].dt.floor('15min')
        self._weather['timestamp'] = self._weather['timestamp'].dt.floor('15min')

        weather_by_ts = self._weather.sort_values('timestamp').drop_duplicates('timestamp', keep='first')
        self._weather_by_timestamp = weather_by_ts.set_index('timestamp')[self.weather_cols].sort_index()

    def _load_model(self):
        if self._model is None:
            if not os.path.exists(self.model_filename):
                raise FileNotFoundError(
                    f'Model file {self.model_filename} not found. Please train the model first.'
                )
            with open(self.model_filename, 'rb') as file:
                self._model = pickle.load(file)
        return self._model

    def _create_feature_df(
        self,
        weather_data: pd.DataFrame,
        net_load_profile: pd.Series | None = None,
    ) -> tuple[pd.DataFrame, pd.Series | None]:
        features_df = pd.DataFrame({
            'hour_of_day': weather_data.index.hour,
            'day_of_week': weather_data.index.dayofweek,
            'temperature_2m': weather_data['temperature_2m'],
            'wind_speed_10m': weather_data['wind_speed_10m'],
            'global_tilted_irradiance': weather_data['global_tilted_irradiance'],
        })

        if self.use_lagged_power:
            if net_load_profile is None:
                raise ValueError('net_load_profile is required when use_lagged_power=True.')
            features_df['lag_7_days'] = net_load_profile.shift(self.lagged_power)

        return features_df, net_load_profile

    def _predict(self, weather_data: pd.DataFrame) -> pd.Series:
        model = self._load_model()
        features_df, _ = self._create_feature_df(weather_data)
        x = features_df.values
        prediction = model.gam.predict(x)
        return pd.Series(prediction, index=features_df.index)

    def forecast(self, time: pd.Timestamp) -> pd.Series:

        if self._use_real_horizon:
            act_weather_forecast = self._weather[self._weather['mpc_time'] == time]
            if act_weather_forecast.empty:
                raise ValueError(f'No weather forecast horizon available for mpc_time={time}.')

            act_weather_forecast = act_weather_forecast.set_index('timestamp').sort_index()
            act_weather_forecast = act_weather_forecast[self.weather_cols]

        else:
            # Fixed horizon starting at time
            horizon_idx = pd.date_range(start=time, periods=self._fixed_horizon_steps, freq='15min')
            act_weather_forecast = self._weather_by_timestamp.reindex(horizon_idx)
            if act_weather_forecast.isna().any().any():
                missing = act_weather_forecast[act_weather_forecast.isna().any(axis=1)].index[:5].tolist()
                raise ValueError(
                    'Fixed 24h horizon requested but weather values are missing for timestamps. '
                    f'Examples: {missing}'
                )

        return self._predict(act_weather_forecast)

    def train_model(self):
        from pygam import s, te, f
        import matplotlib.pyplot as plt
        import interfaces.get_weather_data as get_weather_data
        from loadforecasting_models import Gam

        data_file = Path(__file__).resolve().parent.parent / 'simulation' / 'data' / \
            'example_household_without_battery.csv'
        df_load = pd.read_csv(data_file, index_col=0)
        df_load.index = pd.to_datetime(df_load.index, utc=True)
        df_load.index = df_load.index.tz_convert('Europe/Vienna')
        net_load_profile = df_load['net_load_kw']
        net_load_profile = net_load_profile['2025-01-01':'2025-12-31']

        weather_data = get_weather_data.WeatherDataRetriever().retrieve_weather_data(
            time_range=net_load_profile.index,
            weather_actuality='actual',
        )

        features_df, net_load_profile = self._create_feature_df(weather_data, net_load_profile)
        if net_load_profile is None:
            raise RuntimeError('Training requires net_load_profile values.')

        features_names = features_df.columns.tolist()
        all_gam_terms = (
            f(features_names.index('day_of_week')) +
            te(
                s(features_names.index('hour_of_day'), n_splines=5),
                s(features_names.index('temperature_2m'), n_splines=5),
            ) +
            te(
                s(features_names.index('hour_of_day'), n_splines=10, lam=0.3),
                s(features_names.index('global_tilted_irradiance'), n_splines=10, lam=0.15),
            ) +
            te(
                s(features_names.index('temperature_2m'), n_splines=10, lam=0.3),
                s(features_names.index('wind_speed_10m'), n_splines=10, lam=0.15),
            )
        )
        if self.use_lagged_power:
            all_gam_terms += s(features_names.index('lag_7_days'))
            net_load_profile = net_load_profile[self.lagged_power:]
            features_df = features_df[self.lagged_power:]

        my_model = Gam(all_gam_terms)
        x = features_df.values
        y = net_load_profile.values
        my_model.train_model(x, y)
        predictions = my_model.predict(x)

        nmae = self.calculate_nmae(net_load_profile.values, predictions)
        print(f'nMae: {nmae:.2f}%')

        plt.figure(figsize=(12, 6))
        plt.plot(net_load_profile.index, net_load_profile.values, label='Actual Load', color='blue')
        plt.plot(net_load_profile.index, predictions, label='Predicted Load', color='orange')
        plt.xlabel('Date')
        plt.ylabel('Net Load (kW)')
        plt.title('Actual vs Predicted Net Load Profile')
        plt.legend()
        plt.grid()
        plt.show()

        if os.path.exists(self.model_filename):
            print(f'File {self.model_filename} already exists.')
        else:
            with open(self.model_filename, 'wb') as file:
                pickle.dump(my_model, file)

    def calculate_nmae(self, y_true, y_pred) -> float:
        import torch
        loss_fn = torch.nn.L1Loss()
        reference = y_true.max() - y_true.min()
        mae = loss_fn(torch.tensor(y_pred, dtype=torch.float32), torch.tensor(y_true, dtype=torch.float32))
        n_mae = 100.0 * mae / reference
        return n_mae.item()


class PerfectResidualForecaster(ResidualForecaster):
    """Return perfect residual net-load forecast from the known net-load time series."""

    def __init__(
        self,
        net_load_series_w: pd.Series,
        weather_parquet: str | Path | None = None,
        use_real_horizon: bool = True,
        fixed_horizon_steps: int = DEFAULT_HORIZON,
    ):
        if not isinstance(net_load_series_w.index, pd.DatetimeIndex):
            raise TypeError('net_load_series_w must use a DatetimeIndex.')

        self._net_load_w = net_load_series_w.copy().sort_index()
        self._net_load_w.index = self._net_load_w.index.floor('15min')
        self._use_real_horizon = use_real_horizon
        self._fixed_horizon_steps = fixed_horizon_steps

        self._horizon = None
        if self._use_real_horizon:
            if weather_parquet is None:
                weather_parquet = (
                    Path(__file__).parent.parent.parent / 'data' / 'mp_controller_homebattery'
                    / 'mpc_results_20260410_193659.parquet'
                )

            self._horizon = pd.read_parquet(
                weather_parquet,
                columns=['mpc_time', 'timestamp'],
            )
            self._horizon['mpc_time'] = self._horizon['mpc_time'].dt.floor('15min')
            self._horizon['timestamp'] = self._horizon['timestamp'].dt.floor('15min')

    def forecast(self, time: pd.Timestamp) -> pd.Series:
        if self._use_real_horizon:
            if self._horizon is None:
                raise RuntimeError('Real horizon mode requires horizon data from weather parquet.')
            horizon_df = self._horizon[self._horizon['mpc_time'] == time]
            if horizon_df.empty:
                raise ValueError(f'No horizon definition available for mpc_time={time}.')
            horizon_idx = pd.DatetimeIndex(horizon_df['timestamp']).sort_values()
        else:
            horizon_idx = pd.date_range(start=time, periods=self._fixed_horizon_steps, freq='15min')

        net_load_kw = self._net_load_w.reindex(horizon_idx) / 1000.0

        if net_load_kw.isna().any():
            missing = net_load_kw[net_load_kw.isna()].index[:5].tolist()
            raise ValueError(
                'Perfect prediction requested but net-load values are missing for horizon timestamps. '
                f'Examples: {missing}'
            )

        return net_load_kw


if __name__ == '__main__':
    GamResidualForecaster().train_model()
