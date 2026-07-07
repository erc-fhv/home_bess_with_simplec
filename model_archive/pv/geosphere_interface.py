import requests
import numpy as np
import pandas as pd
from util.cache_manager import cache_result

@cache_result()
def get_geosphere_station_metadata() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    retrieve metadata for geosphere stations and parameter info via API. Results get cached with cache_manager.

    Return:
    -------
    (stations_meta_df, parameter_meta_df)
    """
    meta_url = 'https://dataset.api.hub.geosphere.at/v1/station/historical/klima-v2-10min/metadata'
    meta_response = requests.get(meta_url).json()
    stations_meta_df = pd.DataFrame.from_dict(meta_response['stations']).set_index('id')
    parameter_meta_df = pd.DataFrame.from_dict(meta_response['parameters']).set_index('name')
    return stations_meta_df, parameter_meta_df

@cache_result()
def get_geosphere_values_station(station_id:int, start_dt:str, end_dt:str, parameters:list[str]=['CGLO']) -> pd.DataFrame:
    """
    Get global radiation for a given station. Results get cached with cache_manager.

    Parameters:
    -----------
    station_id : int, meteostat station id
    start_dt : str, start date formatted as such '2021-01-01'
    end_dt : str, end date, formatted as such '2022-01-01'
    parameters : list[str], parameters to download from geosphere. Get available parameters with get_geosphere_station_metadata()

    Returns:
    --------
    pandas.DataFrame with the requested parameters for the given time range, downloaded from geosphere. 

    """
    url = f'https://dataset.api.hub.geosphere.at/v1/station/historical/klima-v2-10min?parameters={",".join(parameters)}&station_ids={station_id}&start={start_dt}&end={end_dt}'
    response = requests.get(url)
    response_dict = response.json()

    timestamp = response_dict['timestamps']
    columns = []
    data = []
    for key, values in response_dict['features'][0]['properties']['parameters'].items():
        columns.append(values['name']+' in '+values['unit'])
        data.append(values['data'])

    return pd.DataFrame(data=np.array(data).T, index=pd.to_datetime(timestamp), columns=columns)

def _haversine_km(lat1, lon1, lat2, lon2): # written by chat GPT-5 mini via github copilot # https://en.wikipedia.org/wiki/Haversine_formula
    """Vectorized haversine distance (km). lat/lon in degrees."""
    R = 6371.0
    lat1_r, lon1_r = np.radians(lat1), np.radians(lon1)
    lat2_r, lon2_r = np.radians(lat2), np.radians(lon2)
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = np.sin(dlat / 2.0)**2 + np.cos(lat1_r) * np.cos(lat2_r) * np.sin(dlon / 2.0)**2
    c = 2 * np.arcsin(np.sqrt(a))
    return R * c

@cache_result()
def nearest_stations(meteostat_stations_df, lat, lon, number_of_stations=1) -> pd.DataFrame:  # written by chat GPT-5 mini via github copilot
    """
    Return nearest station index, station row (pd.Series) and distance_km for given coordinates.

    Parameters:
    -----------
    stations_df: DataFrame with station rows and latitude/longitude columns.
    lat, lon: target coordinates (degrees).
    lat_col, lon_col: column names for lat/lon in stations_df.

    Returns:
    --------
    (index, row_series, distance_km)
    """
    stations_meta_df = meteostat_stations_df.copy()
    stations_meta_df['dists'] = _haversine_km(
        lat, lon,
        stations_meta_df['lat'], 
        stations_meta_df['lon'], 
        )
    stations_meta_df_sorted = stations_meta_df.sort_values('dists')
    return stations_meta_df_sorted.iloc[:number_of_stations]

@cache_result()
def get_nearest_station_values(
        lat, lon, start_dt, end_dt, max_dist=10, parameters=['CGLO']
        ) -> pd.DataFrame:
    """
    Retrieve 10-minute global horizontal irradiance (GHI) for the nearest Geosphere station.

    Parameters
    ----------
    lat : float,Latitude of the target location in decimal degrees. 
    lon : float, Longitude of the target location in decimal degrees.
    start_dt : str, Start date (inclusive) for the requested time range in 'YYYY-MM-DD' format.
    end_dt : str, End date (exclusive or as accepted by the API) for the requested time range in 'YYYY-MM-DD' format.
    max_dist : float, optional
        Maximum allowed distance in kilometers between the target coordinates and the chosen station.
        If the nearest station is farther than this threshold, a ValueError is raised. Default is 10.
    parameters : list[str], parameters to download from geosphere. 
        Get available parameters with get_geosphere_station_metadata()

    Returns
    -------
    pandas.DataFrame
        Time-indexed DataFrame containing the 10-minute GHI series (column name similar to
        'Globalstrahlung Mittelwert in W/m²') for the nearest Geosphere station.

    Raises
    ------
    ValueError
        If the nearest station distance exceeds `max_dist`.
    requests.exceptions.RequestException
        If the underlying HTTP requests to the Geosphere API fail (propagated from the helper functions).

    Notes
    -----
    - This function uses `get_geosphere_station_metadata()` to obtain station metadata and
    `get_geosphere_ghi_station()` to fetch the station's measurement series.
    - Distance is computed with the haversine formula.
    - The function returns the raw DataFrame from the API; callers may need to handle timezone
    conversion or resampling as required.

    Examples
    --------
    >>> df = get_nearest_station_values(47.4325, 9.72556, '2021-01-01', '2022-01-01', parameters=['CGLO'])
    >>> df.head()
    """
    station_meta_df, _ = get_geosphere_station_metadata()
    station_meta_df = station_meta_df.loc[(
        station_meta_df['has_global_radiation']
        & (pd.to_datetime(station_meta_df['valid_from']) <= pd.to_datetime(start_dt, utc=True))
        & (pd.to_datetime(station_meta_df['valid_to']) >= pd.to_datetime(end_dt, utc=True))
        )]
    # TODO raise if no valid df found
    nearest_station = nearest_stations(
        station_meta_df, lat, lon, 
        number_of_stations=1
        ).iloc[0]
    if nearest_station['dists'] > max_dist:
        raise ValueError(
            f'Distance to closest geosphere ({nearest_station["dists"]}\
            km) station exceeds the maximum of {max_dist} km. \
            Get available stations with\
            "PVGisPV.get_geosphere_station_metadata" \
            (ghi needs to be included) or go to \
            https://dataset.api.hub.geosphere.at/app/frontend/station/historical/klima-v2-10min'
            )
    return get_geosphere_values_station(int(nearest_station.name), start_dt, end_dt, parameters=parameters)
