import numpy as np
import pytest

from sartale.radiometry import mask_power, to_db


def test_mask_power_removes_invalid():
    out = mask_power(np.array([1.0, 0.0, -1.0, np.nan, np.inf, 9.0]), fill=9.0)
    assert out[0] == 1.0 and np.isnan(out[1:]).all()


def test_to_db_is_ten_log10_and_nan_for_non_positive():
    out = to_db(np.array([10.0, 1.0, 0.0, -1.0]))
    assert out[0] == pytest.approx(10.0) and out[1] == pytest.approx(0.0)
    assert np.isnan(out[2:]).all()
