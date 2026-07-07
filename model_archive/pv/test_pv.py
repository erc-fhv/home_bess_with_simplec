import pytest
import pandas as pd
from unittest.mock import patch
import pytest
import importlib
from tests.test_utils import assert_valid_index
import time
import numpy as np

@pytest.fixture
def mock_pvgis_data():
    # Create a mock DataFrame similar to what get_pvgis_hourly returns
    idx = pd.date_range('2021-01-01 00:00', periods=3, freq='h', tz='UTC')
    df = pd.DataFrame({'P': [1000, 2000, 3000]}, index=idx)
    metadata = {'info': 'mock'}
    time.sleep(1)
    return df, metadata

@patch('models.pv.pv.get_pvgis_hourly')
def test_pvgis_pv_init_and_df_mocked(mock_get_pvgis_hourly, mock_pvgis_data, monkeypatch, tmp_path):
    monkeypatch.setenv("TMP", str(tmp_path))
    from model_archive.pv.pv import PvgisPV
    mock_get_pvgis_hourly.return_value = mock_pvgis_data
    pv = PvgisPV(
        'test_pv',
        latitude=47.0,
        longitude=9.0,
        start='2021-01-01 00:00',
        end='2021-12-31 23:59',
        )
    # Check DataFrame shape and columns
    assert isinstance(pv.df, pd.DataFrame)
    assert 'P' in pv.df.columns
    assert (pv.df['P'] <= 0).all(), 'PV not compliant with sign convention'
    # Check outputs
    assert pv.outputs == ['P']
    assert_valid_index(pv.df.index, freq='1h', tz='UTC') # TODO: do this for actual downloaded df

def test_pvgis_pv_init_df_download_and_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("TMP", str(tmp_path))
    from model_archive.pv.pv import PvgisPV

    start1 = time.perf_counter()
    pv1 = PvgisPV(
        'test_pv',
        latitude=47.0,
        longitude=9.0,
        start='2021-01-01 00:00',
        end='2021-12-31 23:59',
        )
    start2 = time.perf_counter()
    pv2 = PvgisPV(
        'test_pv_cache',
        latitude=47.0,
        longitude=9.0,
        start='2021-01-01 00:00',
        end='2021-12-31 23:59',
        )
    end = time.perf_counter()

    assert isinstance(pv1.df, pd.DataFrame)
    assert isinstance(pv2.df, pd.DataFrame)
    assert 'P' in pv1.df.columns
    assert (pv1.df['P'] <= 0).all(), 'PV not compliant with sign convention'
    assert pv1.outputs == ['P']
    assert_valid_index(pv1.df.index, freq='1h', tz='UTC')
    assert (end - start2) * 3 < (start2 - start1), \
        'Loading from cache is not at least 3x faster than normal download'

@patch('models.pv.pv.get_pvgis_hourly')
def test_step_method(mock_get_pvgis_hourly, mock_pvgis_data, monkeypatch, tmp_path):
    monkeypatch.setenv("TMP", str(tmp_path))
    from model_archive.pv.pv import PvgisPV
    mock_get_pvgis_hourly.return_value = mock_pvgis_data
    pv = PvgisPV(
        'test_pv',
        latitude=47.0,
        longitude=9.0,
        start='2021-01-01 00:00',
        end='2021-12-31 23:59',
        )
    time = pv.df.index[0]
    result = pv.step(time)
    assert isinstance(result, dict)
    assert 'P' in result
    assert result['P'] == pv.df.iloc[0]['P']

def test_upsampling_geosphere(monkeypatch, tmp_path):
    monkeypatch.setenv("TMP", str(tmp_path))
    from model_archive.pv.pv import PvgisPV
    pv_raw = PvgisPV(
        'test_pv',
        latitude=47.4325,
        longitude=9.72556,
        start='2021-01-01 00:00',
        end='2021-12-31 23:59',
        )
    pv_ups = PvgisPV(
        'test_pv',
        latitude=47.4325,
        longitude=9.72556,
        start='2021-01-01 00:00',
        end='2021-12-31 23:59',
        upsample_w_geosphere=True
        )
    assert isinstance(pv_ups.df, pd.DataFrame)
    assert 'P' in pv_ups.df.columns
    assert (pv_ups.df['P'] <= 0).all(), 'PV not compliant with sign convention'
    assert pv_ups.outputs == ['P']
    assert_valid_index(pv_ups.df.index, freq='1h', tz='UTC')

    yearly_energy_raw = pv_raw.df.sum() * 1e-3
    yearly_energy_ups = pv_ups.df.sum() * 60*10/3600e3
    assert np.isclose(yearly_energy_raw, yearly_energy_ups), \
        'Yearly energy not the same for upsampled model'

    pv_ups_hourly_mean = pv_ups.df.resample('h', origin='start').mean()
    diff = (pv_ups_hourly_mean["P"] - pv_raw.df["P"]).dropna()
    diff_not_zero = diff[~diff.apply(lambda x: np.isclose(0, x))]
    assert not any(diff_not_zero), \
        f'Hourly energy not the same for upsampled model on following instances: {diff_not_zero}'

def test_upsampling_raises_max_distance(monkeypatch, tmp_path):
    monkeypatch.setenv("TMP", str(tmp_path))
    from model_archive.pv.pv import PvgisPV
    with pytest.raises(ValueError):
        pv_ups = PvgisPV(
            'test_pv',
            latitude=47.0,
            longitude=9.0,
            start='2021-01-01 00:00',
            end='2021-12-31 23:59',
            upsample_w_geosphere=True
            )