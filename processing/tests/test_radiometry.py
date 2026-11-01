import numpy as np
import pytest

from sartale.radiometry import log_ratio_db, mask_power, multilook_linear, to_db


def test_mask_power_removes_invalid():
    out = mask_power(np.array([1.0, 0.0, -1.0, np.nan, np.inf, 9.0]), fill=9.0)
    assert out[0] == 1.0 and np.isnan(out[1:]).all()


def test_multilook_averages_linear_power_not_db():
    out = multilook_linear(np.array([[1.0, 100.0], [1.0, 100.0]]), factor=2)
    assert out.shape == (1, 1)
    assert to_db(out)[0, 0] == pytest.approx(17.03, abs=0.01)  # dB averaging would give 10.0


def test_multilook_blanks_cell_below_min_valid():
    a = np.array([[1.0, np.nan], [np.nan, np.nan]])
    assert np.isnan(multilook_linear(a, factor=2, min_valid=0.5)[0, 0])


def test_multilook_trims_partial_edge_cells():
    assert multilook_linear(np.ones((5, 7)), factor=2).shape == (2, 3)


def test_log_ratio_is_10_db_for_tenfold_power():
    assert log_ratio_db(np.array([10.0]), np.array([1.0]))[0] == pytest.approx(10.0)
