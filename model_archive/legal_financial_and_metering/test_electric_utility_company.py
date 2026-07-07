import json

import numpy as np
import pandas as pd
import pytest

from model_archive.legal_financial_and_metering.electric_utility_company import ElectricUtilityCompany, _load_entsoe_token


def test_electric_utility_company_static_prices_backward_compatible():
    times = pd.date_range(start='2020-01-01 00:00+00:00', periods=4, freq='15min')
    model = ElectricUtilityCompany(
        name='utility',
        price_consumption=pd.Series(np.full(4, 0.2), index=times),
        price_feedin=pd.Series(np.full(4, 0.1), index=times),
    )

    outputs = model.step(times[0], {'consumer': 1000.0, 'producer': -1000.0})

    assert np.isclose(outputs['cost_dict']['consumer_bill'], 0.2 / 4)
    assert np.isclose(outputs['cost_dict']['producer_bill'], -0.1 / 4)
    assert np.isclose(outputs['consumption_price'], 0.2)
    assert np.isclose(outputs['feedin_price'], 0.1)


def test_load_entsoe_token_from_credentials_file(tmp_path):
    credentials_path = tmp_path / 'credentials.json'
    with open(credentials_path, 'w', encoding='utf-8') as f:
        json.dump({'Entsoe-Token': 'abc123'}, f)

    token = _load_entsoe_token(credentials_path)
    assert token == 'abc123'


def test_entsoe_mode_requires_explicit_span():
    with pytest.raises(ValueError, match='download_start'):
        ElectricUtilityCompany(
            name='utility',
            use_entsoe_day_ahead=True,
        )


def test_entsoe_mode_downloads_and_applies_offsets(monkeypatch):
    times = pd.date_range(start='2020-01-01 00:00+00:00', periods=8, freq='15min')
    hourly_prices = pd.Series(
        [0.10, 0.20, 0.30],
        index=pd.date_range(start='2020-01-01 00:00+00:00', periods=3, freq='1h')
    )

    def fake_download(**_kwargs):
        return hourly_prices

    monkeypatch.setattr(
        'models.legal_financial_and_metering.electric_utility_company._download_entsoe_day_ahead_prices',
        fake_download,
    )

    model = ElectricUtilityCompany(
        name='utility',
        use_entsoe_day_ahead=True,
        entsoe_zone='AT',
        download_start=pd.Timestamp('2020-01-01 00:00+00:00'),
        download_end=pd.Timestamp('2020-01-01 03:00+00:00'),
        offset_consumption_eur_per_kwh=0.02,
        offset_feedin_eur_per_kwh=-0.03,
    )

    outputs = model.step(times[1], {'consumer': 1000.0, 'producer': -1000.0})

    assert np.isclose(model.price_consumption.loc[times[1]], 0.12)
    assert np.isclose(model.price_feedin.loc[times[1]], 0.07)
    assert np.isclose(outputs['cost_dict']['consumer_bill'], 0.12 / 4)
    assert np.isclose(outputs['cost_dict']['producer_bill'], -0.07 / 4)
    assert np.isclose(outputs['consumption_price'], 0.12)
    assert np.isclose(outputs['feedin_price'], 0.07)


def test_day_ahead_prices_are_provided_correctly_at_noon():
    times = pd.date_range(start='2020-01-01 00:00+00:00', periods=3 * 24 * 4, freq='15min')
    price_consumption = pd.Series(np.linspace(0.10, 0.40, len(times)), index=times)
    price_feedin = pd.Series(np.full(len(times), 0.05), index=times)

    model = ElectricUtilityCompany(
        name='utility',
        price_consumption=price_consumption,
        price_feedin=price_feedin,
    )

    noon = pd.Timestamp('2020-01-01 12:00+00:00')
    outputs_noon = model.step(noon, {'consumer': 1000.0})

    expected_start = pd.Timestamp('2020-01-02 00:00+00:00')
    expected_end = expected_start + pd.Timedelta(days=1)
    expected_slice = price_consumption.loc[expected_start:expected_end]

    assert 'day_ahead_prices' in outputs_noon
    pd.testing.assert_series_equal(outputs_noon['day_ahead_prices'], expected_slice)

    not_noon = pd.Timestamp('2020-01-01 12:15+00:00')
    outputs_not_noon = model.step(not_noon, {'consumer': 1000.0})
    assert 'day_ahead_prices' not in outputs_not_noon
