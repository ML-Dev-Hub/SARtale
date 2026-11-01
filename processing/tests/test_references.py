from datetime import date

import numpy as np
import pytest

from sartale.references import nearest_date, water_agreement


def test_nearest_date_reports_day_gap():
    assert nearest_date(date(2026, 7, 2), [date(2026, 6, 28), date(2026, 7, 3)]) == (date(2026, 7, 3), 1)


def test_nearest_date_tie_picks_earlier():
    assert nearest_date(date(2026, 7, 2), [date(2026, 7, 4), date(2026, 6, 30)]) == (date(2026, 6, 30), 2)


def test_nearest_date_exact_match_is_zero_gap():
    assert nearest_date(date(2026, 7, 2), [date(2026, 7, 2)]) == (date(2026, 7, 2), 0)


def test_nearest_date_empty_raises():
    with pytest.raises(ValueError):
        nearest_date(date(2026, 7, 2), [])


def test_water_agreement_skips_invalid_classes():
    radar = np.array([True, True, False, True])
    dswx = np.array([1, 0, 0, 255])
    out = water_agreement(radar, dswx, water_values={1}, invalid_values={255})
    assert out == {"agreement": pytest.approx(2 / 3), "n_compared": 3}


def test_water_agreement_with_nothing_comparable_returns_none():
    out = water_agreement(np.array([True]), np.array([255]), {1}, {255})
    assert out == {"agreement": None, "n_compared": 0}


def test_water_agreement_skips_nan():
    radar = np.array([True, False, True])
    dswx = np.array([1.0, np.nan, 0.0])
    out = water_agreement(radar, dswx, {1}, {255})
    assert out == {"agreement": pytest.approx(0.5), "n_compared": 2}


def test_water_agreement_shape_mismatch_raises():
    with pytest.raises(ValueError):
        water_agreement(np.array([True, False]), np.array([1]), {1}, {255})
