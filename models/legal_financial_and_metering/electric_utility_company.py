import json
import importlib
from pathlib import Path

import pandas as pd

from util.cache_manager import cache_result


def _default_credentials_path() -> Path:
    return Path(__file__).resolve().parents[3] / '.json'


def _load_entsoe_token(credentials_path: str | Path | None = None) -> str:

    if credentials_path is not None:
        path = Path(credentials_path)
    else:
        path = _default_credentials_path()

    if not path.exists():
        raise FileNotFoundError(f'Could not find credentials file at {path}. ')

    with open(path, 'r', encoding='utf-8') as f:
        credentials = json.load(f)

    token = credentials.get('ENTSOE_API_KEY')
    if not token:
        raise KeyError(f'Missing "ENTSOE_API_KEY" in credentials file: {path}')
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
    assert download_start.tz is not None, "download_start must be timezone-aware"
    assert download_end.tz is not None, "download_end must be timezone-aware"
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
    Electricity supplier model for a single household.

    Calculates the electricity bill per timestep including energy price,
    grid fee, and VAT. Supports dynamic (EPEX spot-based) and fixed tariffs.

    Dynamic mode
    ------------
    price_sell = EPEX - epex_offset_sell_eur_kwh
    price_buy  = (EPEX + epex_offset_buy_eur_kwh + grid_fee_eur_kwh) * (1 + vat)

    Fixed mode
    ----------
    price_sell = fix_price_sell_eur_kwh  (constant)
    price_buy  = (fix_price_buy_eur_kwh + grid_fee_eur_kwh) * (1 + vat)  (constant)

    Parameters
    ----------
    name : str
        Unique model identifier.
    use_epex_prices : bool
        True  → dynamic EPEX spot prices (Series or ENTSO-E download).
        False → fixed tariff (scalars, no time-index required).
    epex_offset_buy_eur_kwh : float
        Markup on top of EPEX spot for consumption, in €/kWh.
    epex_offset_sell_eur_kwh : float
        Deduction from EPEX spot for feed-in, in €/kWh.
    grid_fee_eur_kwh : float
        Grid fee added to the consumption price, in €/kWh.
    vat : float
        Value-added tax as a fraction (e.g. 0.20 for 20 %).
        Applied to the full consumption price (energy + grid fee).
    fix_price_buy_eur_kwh : float | None
        Fixed energy purchase price before grid fee & VAT, in €/kWh.
        Required when use_dynamic_prices=False.
    fix_price_sell_eur_kwh : float | None
        Fixed feed-in tariff (already final, VAT not applied), in €/kWh.
        Required when use_epex_prices=False.
    epex_prices : pd.Series | None
        Datetime-indexed EPEX spot prices in €/kWh. Provide this OR the
        download_* parameters below, not both.
    entsoe_zone : str
        ENTSO-E bidding zone code, e.g. 'AT', 'DE_LU'.
    download_start : str | pd.Timestamp | None
        Start of the download window (inclusive). Required with use_entsoe_day_ahead.
    download_end : str | pd.Timestamp | None
        End of the download window (exclusive). Required with use_entsoe_day_ahead.
    entsoe_credentials_path : str | Path | None
        Path to the JSON credentials file containing 'ENTSOE_API_KEY'.
        Defaults to <repo-root>/.json.

    Inputs
    ------
    P_el : float
        Household electrical power in W.
        Sign convention: P_el > 0 → consumption, P_el < 0 → feed-in.

    Outputs
    -------
    bill : float
        Electricity cost for this timestep in €.
        Positive = payment, negative = feed-in revenue.
    price_buy : float
        Current all-in consumption price in €/kWh.
    price_sell : float
        Current feed-in tariff in €/kWh.
    '''

    delta_t = 15 * 60  # s
    inputs = ['P_el']
    outputs = ['bill', 'price_buy', 'price_sell']

    def __init__(
        self,
        name: str,
        use_epex_prices: bool = True,
        epex_offset_buy_eur_kwh: float = 0.0,
        epex_offset_sell_eur_kwh: float = 0.0,
        grid_fee_eur_kwh: float = 0.0,
        vat: float = 0.0,
        fix_price_buy_eur_kwh: float | None = None,
        fix_price_sell_eur_kwh: float | None = None,
        epex_prices: pd.Series | None = None,
        entsoe_zone: str = 'AT',
        download_start=None,
        download_end=None,
        entsoe_credentials_path: str | Path | None = None,
        timezone: str = 'Europe/Vienna',
    ) -> None:

        self.name = name
        self._use_epex_prices = use_epex_prices
        self._bill_cumulative: float = 0.0
        self._last_day: int | None = None

        if use_epex_prices:
            if epex_prices is not None:
                act_prices = epex_prices.sort_index().resample(f'{self.delta_t}s').ffill()
            else:
                if download_start is None or download_end is None:
                    raise ValueError(
                        'Without `epex_prices`, `download_start` and `download_end` '
                        'must be provided to fetch prices from ENTSO-E.'
                    )
                start = pd.Timestamp(download_start, tz=timezone)
                end = pd.Timestamp(download_end, tz=timezone)
                if start >= end:
                    raise ValueError('`download_start` must be earlier than `download_end`.')
                raw = _download_entsoe_day_ahead_prices(
                    entsoe_zone=entsoe_zone,
                    download_start_iso=start.isoformat(),
                    download_end_iso=end.isoformat(),
                    credentials_path=str(entsoe_credentials_path) \
                        if entsoe_credentials_path is not None else None,
                )
                if raw.index.tz is not None:
                    raw = raw.tz_convert(timezone)
                else:
                    raw = raw.tz_localize(timezone)
                act_prices = raw.sort_index().resample(f'{self.delta_t}s').ffill()
            self._price_sell_eur_kwh = act_prices - epex_offset_sell_eur_kwh
            self._price_buy_eur_kwh = (
                act_prices + epex_offset_buy_eur_kwh + grid_fee_eur_kwh
            ) * (1 + vat)
        else:
            if fix_price_buy_eur_kwh is None or fix_price_sell_eur_kwh is None:
                raise ValueError(
                    '`fix_price_buy_eur_kwh` and `fix_price_sell_eur_kwh` must be provided '
                    'when `use_epex_prices=False`.'
                )
            self._price_sell_eur_kwh = fix_price_sell_eur_kwh
            self._price_buy_eur_kwh = (fix_price_buy_eur_kwh + grid_fee_eur_kwh) * (1 + vat)

    @property
    def price_buy_eur_kwh(self) -> pd.Series | float:
        return self._price_buy_eur_kwh

    @property
    def price_sell_eur_kwh(self) -> pd.Series | float:
        return self._price_sell_eur_kwh

    def get_price_buy_horizon(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
        """Buy prices for the closed interval [start, end)."""
        idx = self._price_buy_eur_kwh.index
        return self._price_buy_eur_kwh[(idx >= start) & (idx <= end)]

    def get_price_sell_horizon(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
        """Sell prices for the closed interval [start, end)."""
        idx = self._price_sell_eur_kwh.index
        return self._price_sell_eur_kwh[(idx >= start) & (idx <= end)]

    def step(self, time, P_el):
        if self._use_epex_prices:
            price_buy = self._price_buy_eur_kwh[time]  # type: ignore[index]
            price_sell = self._price_sell_eur_kwh[time]  # type: ignore[index]
        else:
            price_buy = self._price_buy_eur_kwh
            price_sell = self._price_sell_eur_kwh

        if P_el >= 0:  # consumption
            bill_step = price_buy * P_el * self.delta_t / 1000 / 3600
        else:  # feed-in
            bill_step = price_sell * P_el * self.delta_t / 1000 / 3600

        if self._last_day != time.day:
            self._bill_cumulative = 0.0
            self._last_day = time.day
        self._bill_cumulative += bill_step

        return {
            'bill': self._bill_cumulative,
            'price_buy': price_buy,
            'price_sell': price_sell,
        }
