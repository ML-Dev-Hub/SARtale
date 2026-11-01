import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import h5py
import numpy as np
import pytest
from pyproj import Transformer

from sartale import gcov
from sartale.gcov import read_layer

EPSG = 32642
N = 100
STEP = 100.0  # metres
CENTER_LONLAT = (71.75, 34.15)
FULL_BBOX = (71.4, 33.9, 72.1, 34.4)
BBOX_INSIDE_FIXTURE = (71.74, 34.14, 71.76, 34.16)
BBOX_OUTSIDE = (10.0, 10.0, 10.1, 10.1)


def _write(path, descending_y):
    cx, cy = Transformer.from_crs(4326, EPSG, always_xy=True).transform(*CENTER_LONLAT)
    x = cx + (np.arange(N) - N / 2) * STEP
    y = cy + (np.arange(N) - N / 2) * STEP
    if descending_y:
        y = y[::-1]
    rng = np.random.default_rng(0)
    with h5py.File(path, "w") as f:
        g = f.create_group(gcov.GRID_GROUP)
        for term in ("HHHH", "HVHV"):
            d = rng.uniform(0.01, 1.0, (N, N)).astype("f4")
            d[0, 0] = 0.0  # invalid sample
            g.create_dataset(term, data=d)
        g.create_dataset(gcov.LOOKS, data=np.full((N, N), 5.0, "f4"))
        g.create_dataset(gcov.MASK, data=np.ones((N, N), "u1"))
        g.create_dataset(gcov.X_COORDS, data=x)
        g.create_dataset(gcov.Y_COORDS, data=y)
        p = g.create_dataset(gcov.PROJECTION, data=np.uint32(EPSG))
        p.attrs[gcov.EPSG_ATTR] = EPSG
    return path


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
