import json
import importlib
from pathlib import Path

import pandas as pd

from util.cache_manager import cache_result


def _default_credentials_path() -> Path:
    return Path(__file__).resolve().parents[3] / '.json'


def _load_entsoe_token(credentials_path: str | Path | None = None) -> str:
    path = Path(credentials_path) if credentials_path is not None else _default_credentials_path()
    if not path.exists():
        raise FileNotFoundError(
            f'Could not find credentials file at {path}. '
            'Expected JSON key "Entsoe-Token".'
        )

    with open(path, 'r', encoding='utf-8') as f:
        credentials = json.load(f)

    token = credentials.get('ENTSOE_API_KEY')
    if not token:
        raise KeyError(f'Missing "Entsoe-Token" in credentials file: {path}')
    return str(token)


@cache_result()
def _download_entsoe_day_ahead_prices(
        entsoe_zone: str,
        download_start_iso: str,
        download_end_iso: str,
        credentials_path: str | None = None,
        ) -> pd.Series:
    try:
        entsoe_module = importlib.import_module('entsoe')
        EntsoePandasClient = entsoe_module.EntsoePandasClient
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            'ENTSO-E integration requires the optional package "entsoe-py". '
            'Install it to use `use_entsoe_day_ahead=True`.'
        ) from exc

    token = _load_entsoe_token(credentials_path)
    client = EntsoePandasClient(api_key=token)

    download_start = pd.Timestamp(download_start_iso)
    download_end = pd.Timestamp(download_end_iso)
    prices_eur_per_mwh = client.query_day_ahead_prices(
        country_code=entsoe_zone,
        start=download_start,
        end=download_end,
    )

    if isinstance(prices_eur_per_mwh, pd.DataFrame):
        if prices_eur_per_mwh.shape[1] != 1:
            raise ValueError('Expected a single ENTSO-E day-ahead price series.')
        prices_eur_per_mwh = prices_eur_per_mwh.iloc[:, 0]

    if prices_eur_per_mwh.empty:
        raise ValueError('ENTSO-E returned an empty day-ahead price series.')

    prices_eur_per_kwh = prices_eur_per_mwh.astype(float).sort_index() / 1000.0
    return prices_eur_per_kwh

class ElectricUtilityCompany():
    '''
    Simple ElectricUtilityCompany

    It calculates real time prices for arbitrary consumers
    based on residual loads and provide day ahead prices.

    Parameter
    -----------
    price_consumption : pd.Series datetime indexed prices time series in €/kWh
    price_feedin : pd.Series datetime indexed prices time series in €/kWh

    Input
    ------
    P_el : dict[str:float], Electrical power per consumer / producer

    Output
    --------
    cost_dict : dict, multiioutput cost per participant in €/delta_t
    consumption_price : float, current consumption price in €/kWh
    feedin_price : float, current feed-in price in €/kWh
    day_ahead_prices : pd.Series, datetime indexed consumption prices in €/delta_t

    Sign convention:
     - P > 0  -> consumption
     - P < 0  -> generation
    '''
    delta_t = 15 * 60 # s
    inputs = ['P_el']
    outputs = ['cost_dict', 'consumption_price', 'feedin_price', 'day_ahead_prices']

    def __init__(
            self,
            name,
            price_consumption: pd.Series | None = None,
            price_feedin: pd.Series | None = None,
            suffix: str = '_bill',
            use_entsoe_day_ahead: bool = False,
            entsoe_zone: str = 'AT',
            download_start=None,
            download_end=None,
            offset_consumption_eur_per_kwh: float = 0.0,
            offset_feedin_eur_per_kwh: float = 0.0,
            entsoe_credentials_path: str | Path | None = None,
            ) -> None:
        self.name = name
        self.suffix = suffix

        if use_entsoe_day_ahead:
            if download_start is None or download_end is None:
                raise ValueError(
                    'With `use_entsoe_day_ahead=True`, `download_start` and '
                    '`download_end` must be provided explicitly.'
                )

            start = pd.Timestamp(download_start)
            end = pd.Timestamp(download_end)
            if start >= end:
                raise ValueError('`download_start` must be earlier than `download_end`.')

            base_prices = _download_entsoe_day_ahead_prices(
                entsoe_zone=entsoe_zone,
                download_start_iso=start.isoformat(),
                download_end_iso=end.isoformat(),
                credentials_path=str(entsoe_credentials_path) if entsoe_credentials_path is not None else None,
            )

            base_prices = base_prices.sort_index()
            base_prices = base_prices.resample(f'{self.delta_t}s').ffill()
            self.price_consumption = base_prices + offset_consumption_eur_per_kwh
            self.price_feedin = base_prices + offset_feedin_eur_per_kwh
        else:
            if price_consumption is None or price_feedin is None:
                raise ValueError(
                    '`price_consumption` and `price_feedin` must be provided '
                    'when `use_entsoe_day_ahead=False`.'
                )
            self.price_consumption = price_consumption.sort_index()
            self.price_feedin = price_feedin.sort_index()

    def step(self, time, P_el):
        outputs = {}
        outputs['consumption_price'] = self.price_consumption[time]
        outputs['feedin_price'] = self.price_feedin[time]
        cost = {}
        for model, P in P_el.items():
            if P > 0: # Consumption
                cost[model + self.suffix] = \
                    self.price_consumption[time] * P * self.delta_t / 1000 / 3600 # €/kWh * W * s *(1 k / 1000) * (1 h / 3600 s)
            else: # feedin
                cost[model + self.suffix] = \
                    self.price_feedin[time] * P * self.delta_t / 1000 / 3600 # €/kWh * W * s *(1 k / 1000) * (1 h / 3600 s)
        outputs['cost_dict'] = cost

        if time == (time.normalize() + pd.Timedelta(hours=12)):
            start = (time.normalize() + pd.Timedelta(days=1))
            end   = start + pd.Timedelta(days=1)
            outputs['day_ahead_prices'] = self.price_consumption.loc[start:end]

        return outputs