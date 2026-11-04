import numpy as np
import pytest

from sartale.render import render_frame, shared_stretch


def test_stretch_is_shared_across_dates():
    lo, hi = shared_stretch(np.array([[[-30.0, -20.0]], [[-10.0, 0.0]]]))
    assert lo < -20 and hi > -10


def test_stretch_needs_finite_values():
    with pytest.raises(ValueError):
        shared_stretch(np.array([[np.nan]]))


def test_render_frame_reserves_zero_for_nodata():
    out = render_frame(np.array([[np.nan, -40.0, -15.0, 10.0]]), (-30.0, 0.0))
    assert out.dtype == np.uint8
    assert out[0, 0] == 0
    assert out[0, 1] == 1 and out[0, 3] == 255  # clipped at both ends
    assert 1 < out[0, 2] < 255
