import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import numpy as np
import pytest
import rasterio
from PIL import Image
from pyproj import Transformer

from gcov_fixture import CENTER_LONLAT, EPSG, STEP, write_gcov
from sartale import config
from sartale.gcov import Layer
from sartale.products import (
    assert_same_grid,
    composite_indices,
    multilook_layer,
    render_frame,
    seasonal_composite,
    shared_stretch,
    write_cog,
    write_webp_3857,
)
from sartale.run_pipeline import main

NAME_FMT = ("NISAR_L2_PR_GCOV_{cycle:03d}_084_A_019_4005_DHDH_A_{ymd}T220325_{ymd}T220400_"
            "P05023_N_F_J_001")
DATES = ["2026-07-02", "2026-08-19", "2026-09-12", "2026-10-18"]


def _layer(n=12, descending_y=False):
    x = 500000.0 + np.arange(n) * 10.0
    y = 3800000.0 + np.arange(n) * 10.0
    if descending_y:
        y = y[::-1]
    rng = np.random.default_rng(1)
    return Layer(rng.uniform(0.01, 1.0, (n, n)), x, y, EPSG, None, None)


@pytest.fixture
def layer():
    return _layer()


def shifted(layer, dx):
    return replace(layer, x=layer.x + dx)


# --- spec tests ---------------------------------------------------------------

def test_assert_same_grid_rejects_shift(layer):
    with pytest.raises(ValueError, match="grid"):
        assert_same_grid([layer, shifted(layer, dx=10)])


def test_assert_same_grid_accepts_identical(layer):
    assert_same_grid([layer, replace(layer, power=layer.power * 2)])


def test_assert_same_grid_rejects_different_epsg(layer):
    with pytest.raises(ValueError, match="grid"):
        assert_same_grid([layer, replace(layer, epsg=32643)])


def test_stretch_is_shared_across_dates():
    lo, hi = shared_stretch(np.array([[[-30.0, -20.0]], [[-10.0, 0.0]]]))
    assert lo < -20 and hi > -10


def test_composite_of_identical_dates_is_grey():
    db = np.array([[-20.0, -10.0]])
    rgba = seasonal_composite(db, db, db, (-30.0, 0.0))
    assert (rgba[..., 0] == rgba[..., 1]).all() and (rgba[..., 1] == rgba[..., 2]).all()


def test_nan_pixels_are_transparent():
    rgba = seasonal_composite(*[np.array([[np.nan]])] * 3, (-30.0, 0.0))
    assert rgba[0, 0, 3] == 0


# --- more unit tests ----------------------------------------------------------

def test_composite_channels_are_early_mid_late():
    early, mid, late = (np.array([[v]]) for v in (-30.0, -15.0, 0.0))
    rgba = seasonal_composite(early, mid, late, (-30.0, 0.0))
    assert rgba.dtype == np.uint8 and rgba.shape == (1, 1, 4)
    assert rgba[0, 0, 0] < rgba[0, 0, 1] < rgba[0, 0, 2]
    assert rgba[0, 0, 3] == 255


def test_composite_transparent_if_any_date_missing():
    ok = np.array([[-10.0, -10.0]])
    bad = np.array([[np.nan, -10.0]])
    rgba = seasonal_composite(ok, bad, ok, (-30.0, 0.0))
    assert rgba[0, 0, 3] == 0 and rgba[0, 1, 3] == 255


def test_render_frame_reserves_zero_for_nodata():
    out = render_frame(np.array([[np.nan, -40.0, -15.0, 10.0]]), (-30.0, 0.0))
    assert out.dtype == np.uint8
    assert out[0, 0] == 0
    assert out[0, 1] == 1 and out[0, 3] == 255  # clipped at both ends
    assert 1 < out[0, 2] < 255


@pytest.mark.parametrize("n,expected", [(3, (0, 1, 2)), (4, (0, 2, 3)), (5, (0, 2, 4)), (6, (0, 3, 5))])
def test_composite_indices_middle_is_later_of_central_pair(n, expected):
    assert composite_indices(n) == expected


@pytest.mark.parametrize("descending_y", [False, True])
def test_multilook_layer_recomputes_block_centres(descending_y):
    layer = _layer(n=11, descending_y=descending_y)  # 11 -> trims to 9 -> 3 blocks
    ml = multilook_layer(layer, 3)
    assert ml.power.shape == (3, 3)
    # centre of the first three 10 m samples sits on the middle sample
    np.testing.assert_allclose(ml.x, layer.x[1:9:3])
    np.testing.assert_allclose(ml.y, layer.y[1:9:3])
    np.testing.assert_allclose(np.diff(ml.x), 30.0)
    assert ml.epsg == layer.epsg
    # block mean is linear power mean
    np.testing.assert_allclose(ml.power[0, 0], layer.power[:3, :3].mean())


@pytest.mark.parametrize("descending_y", [False, True])
def test_write_cog_georeferencing_roundtrip(tmp_path, descending_y):
    layer = multilook_layer(_layer(n=12, descending_y=descending_y), 3)
    arr = np.arange(16, dtype="f4").reshape(4, 4)
    arr[0, 0] = np.nan
    path = tmp_path / "a.tif"
    write_cog(arr, layer, path)
    with rasterio.open(path) as src:
        assert src.crs.to_epsg() == EPSG
        assert src.transform.a == pytest.approx(30.0) and src.transform.e == pytest.approx(-30.0)
        # centre of the pixel (0, 0) must equal the layer's first-row/col coordinates
        # in north-up order.
        cx, cy = src.xy(0, 0)
        assert cx == pytest.approx(layer.x[0])
        assert cy == pytest.approx(layer.y.max())
        data = src.read(1)
        expected = arr if descending_y else arr[::-1]  # file rows run north to south
        np.testing.assert_allclose(data, expected)  # NaN positions match too


def test_write_webp_3857_bounds_and_transparency(tmp_path):
    layer = multilook_layer(_layer(n=30), 3)
    gray = np.full((10, 10), 128, np.uint8)
    gray[0:3, 0:3] = 0  # nodata corner
    b1 = write_webp_3857(gray, layer, tmp_path / "f1.webp")
    b2 = write_webp_3857(np.full((10, 10), 200, np.uint8), layer, tmp_path / "f2.webp")
    assert b1 == b2
    left, bottom, right, top = b1
    assert right > left and top > bottom
    # bounds are Web Mercator metres around the layer
    tr = Transformer.from_crs(EPSG, 3857, always_xy=True)
    mx, my = tr.transform(layer.x.mean(), layer.y.mean())
    assert left < mx < right and bottom < my < top
    img = np.asarray(Image.open(tmp_path / "f1.webp").convert("RGBA"))
    assert img.shape[2] == 4
    assert img[..., 3].min() == 0 and img[..., 3].max() == 255
    # nodata corner (top-left in the layer) is transparent, centre is opaque
    h, w = img.shape[:2]
    assert img[h // 2, w // 2, 3] == 255


@pytest.mark.parametrize("descending_y", [False, True])
def test_write_webp_3857_is_north_up(tmp_path, descending_y):
    layer = multilook_layer(_layer(n=30, descending_y=descending_y), 3)
    north = layer.y.argmax()  # row index of the northernmost samples
    grid = np.full((10, 10), 50, np.uint8)
    grid[north] = 250
    write_webp_3857(grid, layer, tmp_path / "n.webp")
    img = np.asarray(Image.open(tmp_path / "n.webp").convert("RGBA"))
    opaque = img[..., 3] > 0
    rows = np.flatnonzero(opaque.any(axis=1))
    col = img.shape[1] // 2
    top = img[rows[0]:rows[0] + 6, col, 0]
    bottom = img[rows[-6]:rows[-1] + 1, col, 0]
    assert top.max() > 150 and bottom.max() < 150  # bright north row lands at the top


def test_write_webp_3857_accepts_rgba(tmp_path):
    layer = multilook_layer(_layer(n=30), 3)
    rgba = np.zeros((10, 10, 4), np.uint8)
    rgba[..., 0] = 255
    rgba[2:, :, 3] = 255
    write_webp_3857(rgba, layer, tmp_path / "c.webp")
    img = np.asarray(Image.open(tmp_path / "c.webp").convert("RGBA"))
    h, w = img.shape[:2]
    assert img[h // 2, w // 2, 3] == 255 and img[h // 2, w // 2, 0] > 200


# --- build end to end ---------------------------------------------------------

def _make_stack(tmp_path, dates=DATES, skip=None, shift_last=False):
    gdir = tmp_path / "gcov"
    gdir.mkdir()
    granules = []
    for i, d in enumerate(dates):
        ymd = d.replace("-", "")
        name = NAME_FMT.format(cycle=10 + i, ymd=ymd)
        granules.append({"name": name, "start": f"{d}T22:03:25+00:00", "crid": "P05023",
                         "accuracy": "N", "coverage": "F", "cycle": 10 + i})
        if name == skip:
            continue
        dx = 100.0 if shift_last and i == len(dates) - 1 else 0.0
        write_gcov(gdir / f"{name}.h5", seed=i, scale=10 ** (-i / 2), dx=dx)
    mpath = tmp_path / "search.json"
    mpath.write_text(json.dumps({"searched": "x", "granules": granules}), encoding="utf-8")
    return gdir, mpath, granules


def _build(tmp_path, gdir, mpath, dates=DATES):
    out, cog = tmp_path / "out", tmp_path / "cog"
    main(["build", "--gcov-dir", str(gdir), "--dates", ",".join(dates),
          "--manifest-in", str(mpath), "--out-dir", str(out), "--cog-dir", str(cog)])
    return out, cog


def test_build_writes_manifest_frames_and_cogs(tmp_path):
    gdir, mpath, granules = _make_stack(tmp_path)
    out, cog = _build(tmp_path, gdir, mpath)
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))

    assert list(m) == ["stack", "crid", "maturity", "bounds", "dates", "composite",
                       "stretch_db", "gap"]
    assert m["stack"] == config.STACK_ID and m["crid"] == config.CRID
    assert m["maturity"] == "Provisional"
    assert m["gap"] == {"start": config.GAP_START, "end": config.GAP_END}
    assert m["composite"] == "frames/composite_HH.webp"
    w, s, e, n = m["bounds"]
    assert w < CENTER_LONLAT[0] < e and s < CENTER_LONLAT[1] < n

    assert [d["date"] for d in m["dates"]] == DATES
    for d, g in zip(m["dates"], granules):
        assert d["granule"] == g["name"]
        assert d["frames"] == {"HH": f"frames/{d['date']}_HH.webp",
                               "HV": f"frames/{d['date']}_HV.webp"}
        for rel in d["frames"].values():
            assert (out / rel).is_file()
        for pol in ("HH", "HV"):
            assert (cog / f"{d['date']}_{pol}.tif").is_file()
    assert (out / m["composite"]).is_file()

    for pol in ("HH", "HV"):
        lo, hi = m["stretch_db"][pol]
        assert lo < hi
    sizes = {Image.open(out / d["frames"]["HH"]).size for d in m["dates"]}
    sizes.add(Image.open(out / m["composite"]).size)
    assert len(sizes) == 1  # every overlay shares one pixel grid, hence one bounds

    # the COG is multilooked to 30 m
    with rasterio.open(cog / f"{DATES[0]}_HH.tif") as src:
        assert src.transform.a == pytest.approx(3 * STEP)  # 100 m fixture, multilooked by 3


def test_build_fails_clearly_when_a_date_has_no_file(tmp_path):
    gdir, mpath, granules = _make_stack(tmp_path)
    missing = granules[1]["name"]
    (gdir / f"{missing}.h5").unlink()
    with pytest.raises(FileNotFoundError, match="2026-08-19"):
        _build(tmp_path, gdir, mpath)


def test_build_fails_when_date_not_in_search_manifest(tmp_path):
    gdir, mpath, _ = _make_stack(tmp_path)
    with pytest.raises(ValueError, match="2026-12-31"):
        _build(tmp_path, gdir, mpath, dates=[*DATES, "2026-12-31"])


def test_build_rejects_dates_on_different_grids(tmp_path):
    gdir, mpath, _ = _make_stack(tmp_path, shift_last=True)
    with pytest.raises(ValueError, match="grid"):
        _build(tmp_path, gdir, mpath)
