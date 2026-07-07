"""Net load reader model — outputs measured or fetched load/PV/net-load data."""

from pathlib import Path

import pandas as pd


class NetloadReader:
    """Time-series model that outputs net load (and optionally load/PV) data.

    Parameters
    ----------
    name : str
        Unique model identifier.
    delta_t : int
        Timestep in seconds. Default is 900 (15 min).
    source : str
        ``'victron'`` - fetch data via Victron VRM API;
        ``'file'`` - read from a CSV file at *file_path*.
    file_path : str or Path, optional
        Path to the CSV file when *source* is ``'file'``. The CSV must have a
        datetime index column and numeric data columns (e.g. ``net_load``) in
        Watts.
    victron_days : int, optional
        Number of days of history to fetch when *source* is ``'victron'``.
        Defaults to 14.
    timezone : str, optional
        Timezone for the data index. Defaults to ``'Europe/Vienna'``.

    Inputs
    ------
    (none)

    Outputs
    -------
    Columns of the loaded DataFrame, e.g.:
    load     : float, total household load in W
    pv       : float, PV generation in W  (positive = generating)
    net_load : float, load minus PV in W  (positive = consuming from grid)
    """

    def __init__(
        self,
        name: str,
        delta_t: int = 900,
        source: str = "file",
        file_path: "str | Path | None" = None,
        start: "str | None" = None,
        end: "str | None" = None,
        timezone: str = "Europe/Vienna",
        force_refetch: bool = False,
    ):
        self.name = name
        self.delta_t = delta_t
        self.inputs = []

        if source == "victron":
            if start is None or end is None:
                raise ValueError("start and end must be provided when source='victron'")
            from models.netload_reader.get_victron_data import fetch_victron_data

            # navigate to file from current file
            data_file = Path(__file__).resolve().parents[2] / "data" / "netload_reader" / \
                "victron_data.csv"
            if data_file.exists() and force_refetch is False:
                print(f"Loading Victron data from {data_file}.")
                self.df = pd.read_csv(data_file, index_col=0, parse_dates=True)
                if self.df.index.tz is None:
                    self.df.index = self.df.index.tz_localize(timezone)
                else:
                    self.df.index = self.df.index.tz_convert(timezone)
            else:
                self.df = fetch_victron_data(start=start, end=end, timezone=timezone,
                    add_end_buffer=pd.Timedelta(days=2), output_path=data_file)

        elif source == "file":
            if file_path is None:
                raise ValueError("file_path must be provided when source='file'")
            self.df = pd.read_csv(
                file_path,
                index_col=0,
                parse_dates=True,
            )
            if self.df.index.tz is None:
                self.df.index = self.df.index.tz_localize(timezone)
            else:
                self.df.index = self.df.index.tz_convert(timezone)

        else:
            raise ValueError(f"Unknown source '{source}'. Use 'victron' or 'file'.")

        self.outputs = list(self.df.columns)

    def step(self, time: pd.Timestamp) -> dict:
        return self.df.loc[time].to_dict()
