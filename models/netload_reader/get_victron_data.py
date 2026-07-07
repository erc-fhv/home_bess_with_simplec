"""Fetch data from the Victron VRM API."""

import json
from pathlib import Path

import pandas as pd
import requests

VRM_API_BASE = "https://vrmapi.victronenergy.com/v2"


def _get_credentials() -> dict:
    pw_file = Path(__file__).resolve().parents[3] / ".json"
    with open(pw_file, encoding="utf-8") as f:
        return json.load(f)


def _headers(token: str) -> dict:
    """Return auth headers. Token value already includes 'Token ' prefix."""
    return {"x-authorization": token}

def _get_stats(
    token: str,
    site_id: int,
    stat_type: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    interval: str = "15mins",
) -> dict:
    """Fetch stats from the VRM API."""
    resp = requests.get(
        f"{VRM_API_BASE}/installations/{site_id}/stats",
        headers=_headers(token),
        params={
            "type": stat_type,
            "interval": interval,
            "start": int(start.timestamp()),
            "end": int(end.timestamp()),
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def _records_to_series(records: dict, key: str, timezone: str) -> pd.Series:
    """Convert a single VRM records key to a timezone-aware pd.Series.

    Records format: {"attribute_code": [[timestamp_ms, value], ...]}
    Some keys may be booleans (flags) — only list entries are valid data.
    """
    if key not in records or not isinstance(records[key], list):
        raise ValueError(f"Key '{key}' not found or not a list in records")

    data = records[key]
    timestamps = pd.DatetimeIndex(
        [pd.Timestamp(row[0], unit="ms", tz="UTC") for row in data]
    )
    values = [row[1] for row in data]

    series = pd.Series(values, index=timestamps, dtype=float)
    series = series.tz_convert(timezone)
    series.index.name = "datetime"
    return series


def fetch_victron_data(
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    timezone: str = "Europe/Vienna",
    add_end_buffer: pd.Timedelta | None = None,
    output_path: Path | None = None,
) -> pd.DataFrame:
    """
    Fetch load and PV data from Victron VRM for a given time range.
    Without battery effects, net_load = load - pv.

    Returns a DataFrame with columns: load, pv, net_load (all in Watts).
    Index is a timezone-aware DatetimeIndex at 15-minute frequency.
    """
    creds = _get_credentials()
    token = creds["VICTRON_MQTT_API_KEY"]
    site_id = creds["VRM_SITE_ID"]

    start = pd.Timestamp(start, tz=timezone) if pd.Timestamp(start).tz is None \
        else pd.Timestamp(start).tz_convert(timezone)
    end = pd.Timestamp(end, tz=timezone) if pd.Timestamp(end).tz is None \
        else pd.Timestamp(end).tz_convert(timezone)

    start = start.floor('15min')

    end = end - pd.Timedelta(minutes=15) # Exclusive ende, since VRM API is inclusive

    if add_end_buffer is not None:
        end += add_end_buffer

    print(f"Fetching VRM data from {start} to {end} ...")

    # Fetch consumption and solar yield at 15-minute intervals
    consumption_resp = _get_stats(
        token, site_id, "consumption", start, end
    )
    solar_resp = _get_stats(
        token, site_id, "solar_yield", start, end
    )
    grid_resp = _get_stats(
        token, site_id, "grid", start, end
    )

    # consumption records (all in kWh per interval):
    #   Pc = from PV, Bc = from battery, Gc = from grid
    # Household load = Pc + Bc + Gc (total AC consumption, battery is just a source)
    c_records = consumption_resp["records"]
    load_parts = []
    for key in ["Pc", "Bc", "Gc"]:
        if key in c_records and isinstance(c_records[key], list):
            load_parts.append(_records_to_series(c_records, key, timezone))
    load = pd.concat(load_parts).groupby(level=0).sum() if load_parts else pd.Series(dtype=float)

    # solar_yield records (all in kWh per interval):
    #   Pc = PV → consumption, Pb = PV → battery, Pg = PV → grid
    # Total PV generation = Pc + Pb + Pg
    s_records = solar_resp["records"]
    pv_parts = []
    for key in ["Pc", "Pb", "Pg"]:
        if key in s_records and isinstance(s_records[key], list):
            pv_parts.append(_records_to_series(s_records, key, timezone))
    pv = pd.concat(pv_parts).groupby(level=0).sum() if pv_parts else pd.Series(dtype=float)

    # grid records (all in kWh per interval):
    #   Gc = grid → consumption, Gb = grid → battery
    #   Pg = PV → grid,          Bg = battery → grid
    # P_grid = (Gc + Gb) - (Pg + Bg)  [positive = import, negative = export]
    g_records = grid_resp["records"]
    grid_import_parts = []
    for key in ["Gc", "Gb"]:
        if key in g_records and isinstance(g_records[key], list):
            grid_import_parts.append(_records_to_series(g_records, key, timezone))
    grid_import = pd.concat(grid_import_parts).groupby(level=0).sum() \
        if grid_import_parts else pd.Series(dtype=float)

    grid_export_parts = []
    for key in ["Pg", "Bg"]:
        if key in g_records and isinstance(g_records[key], list):
            grid_export_parts.append(_records_to_series(g_records, key, timezone))
    grid_export = pd.concat(grid_export_parts).groupby(level=0).sum() \
        if grid_export_parts else pd.Series(dtype=float)

    # Battery charge energy: PV → battery (Pb) + grid → battery (Gb)
    bat_charge_parts = []
    for src, key in [(s_records, "Pb"), (g_records, "Gb")]:
        if key in src and isinstance(src[key], list):
            bat_charge_parts.append(_records_to_series(src, key, timezone))
    bat_charge = pd.concat(bat_charge_parts).groupby(level=0).sum()

    # Battery discharge energy: battery → consumption (Bc) + battery → grid (Bg)
    bat_discharge_parts = []
    for src, key in [(c_records, "Bc"), (g_records, "Bg")]:
        if key in src and isinstance(src[key], list):
            bat_discharge_parts.append(_records_to_series(src, key, timezone))
    bat_discharge = pd.concat(bat_discharge_parts).groupby(level=0).sum()

    # Convert from kWh per 15-min interval to average Watts
    interval_hours = 0.25
    load = load * 1000.0 / interval_hours
    pv = pv * 1000.0 / interval_hours
    grid_import = grid_import * 1000.0 / interval_hours
    grid_export = grid_export * 1000.0 / interval_hours
    bat_charge = bat_charge * 1000.0 / interval_hours
    bat_discharge = bat_discharge * 1000.0 / interval_hours

    # Combine into DataFrame, aligning on the common datetime index
    df = pd.DataFrame({
        "load": load, "pv": pv,
        "grid_import": grid_import, "grid_export": grid_export,
        "P_bat_charge": bat_charge, "P_bat_discharge": bat_discharge,
    })
    df.index.name = "datetime"
    df = df.fillna(0.0)

    # net_load = load - pv (positive = consuming from grid, negative = feeding)
    df["net_load"] = df["load"] - df["pv"]

    # P_grid = grid_import - grid_export: actual grid exchange including battery
    # positive = buying, negative = selling
    df["P_grid"] = df["grid_import"] - df["grid_export"]

    # P_bat = charge - discharge (positive = charging, negative = discharging)
    df["P_bat"] = df["P_bat_charge"] - df["P_bat_discharge"]

    # Sort and validate
    df = df.sort_index()
    assert df.index.tz is not None, "Index must be timezone-aware"

    # Fill gaps in the 15-min grid with zeros
    full_idx = pd.date_range(start=df.index.min(), end=df.index.max(),
                             freq='15min', tz=df.index.tz)
    df = df.reindex(full_idx).fillna(0.0)
    df.index.name = "datetime"

    # Save to CSV
    if output_path is not None:
        df.to_csv(output_path)
        print(f"Saved {len(df)} rows to {output_path}")

    return df


def fetch_victron_soc(
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    timezone: str = "Europe/Vienna",
) -> pd.Series:
    """Fetch battery SOC from Victron VRM for a given time range.

    Returns a Series of SOC values (%) with a timezone-aware DatetimeIndex
    at 15-minute intervals.
    """
    creds = _get_credentials()
    token = creds["VICTRON_MQTT_API_KEY"]
    site_id = creds["VRM_SITE_ID"]

    start = pd.Timestamp(start, tz=timezone) if pd.Timestamp(start).tz is None \
        else pd.Timestamp(start).tz_convert(timezone)
    end = pd.Timestamp(end, tz=timezone) if pd.Timestamp(end).tz is None \
        else pd.Timestamp(end).tz_convert(timezone)
    start = start.floor('15min')

    resp = requests.get(
        f"{VRM_API_BASE}/installations/{site_id}/stats",
        headers=_headers(token),
        params={
            "type": "custom",
            "attributeCodes[]": "SOC",
            "interval": "15mins",
            "start": int(start.timestamp()),
            "end": int(end.timestamp()),
        },
        timeout=60,
    )
    resp.raise_for_status()
    soc_data = resp.json()["records"]["SOC"]

    soc = pd.Series(
        [row[1] for row in soc_data],
        index=pd.DatetimeIndex(
            [pd.Timestamp(row[0], unit="ms", tz="UTC") for row in soc_data]
        ).tz_convert(timezone),
        dtype=float,
    )
    soc.index.name = "datetime"
    return soc


if __name__ == "__main__":
    df = fetch_victron_data(
        start=pd.Timestamp("2026-03-01 00:00", tz="Europe/Vienna"),
        end=pd.Timestamp("2026-04-30 23:45", tz="Europe/Vienna"),
    )

    print(df.tail(10))
    print(f"\nTotal rows: {len(df)}")
    print(f"Date range: {df.index[0]} to {df.index[-1]}")

    # store specific rows as csv:
    output_file = Path(__file__).parent / "victron_data.csv"
    df[['net_load']].to_csv(output_file)
    print(f"Saved data to {output_file}")
