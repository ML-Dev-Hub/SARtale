import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import numpy as np
import pytest
from pyproj import Transformer

from gcov_fixture import CENTER_LONLAT, EPSG, STEP, write_gcov
from sartale.gcov import read_layer

FULL_BBOX = (71.4, 33.9, 72.1, 34.4)
BBOX_INSIDE_FIXTURE = (71.74, 34.14, 71.76, 34.16)
BBOX_OUTSIDE = (10.0, 10.0, 10.1, 10.1)


def _write(path, descending_y):
    return write_gcov(path, descending_y=descending_y)


@pytest.fixture(params=[False, True], ids=["y-asc", "y-desc"])
def gcov_file(tmp_path, request):
    return _write(tmp_path / "g.h5", request.param)


def test_read_layer_clips_to_bbox(gcov_file):
    full = read_layer(gcov_file, "HHHH", FULL_BBOX)
    layer = read_layer(gcov_file, "HHHH", BBOX_INSIDE_FIXTURE)
    assert layer.power.shape == (layer.y.size, layer.x.size)
    assert 0 < layer.power.size < full.power.size
    assert layer.looks.shape == layer.power.shape and layer.mask.shape == layer.power.shape
    cx, cy = Transformer.from_crs(4326, EPSG, always_xy=True).transform(*CENTER_LONLAT)
    assert abs(layer.x.mean() - cx) < 3 * STEP and abs(layer.y.mean() - cy) < 3 * STEP


def test_read_layer_masks_invalid_values(gcov_file):
    assert np.isnan(read_layer(gcov_file, "HHHH", FULL_BBOX).power[0, 0])


def test_read_layer_keeps_epsg(gcov_file):
    assert read_layer(gcov_file, "HVHV", FULL_BBOX).epsg == 32642


def test_read_layer_rejects_missing_term(gcov_file):
    with pytest.raises(KeyError, match="VVVV"):
        read_layer(gcov_file, "VVVV", FULL_BBOX)


def test_read_layer_rejects_bbox_outside_grid(gcov_file):
    with pytest.raises(ValueError, match="outside"):
        read_layer(gcov_file, "HHHH", BBOX_OUTSIDE)
