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
from sartale.browse import DISPLAY_WINDOW
from sartale.gcov import Layer
from sartale.products import (
    DISPLAY_LOOKS,
    FORECAST_FLAG,
    INTERFERENCE_FLAG,
    assert_same_grid,
    composite_choice,
    composite_indices,
    multilook_layer,
    render_frame,
    seasonal_composite,
    shared_stretch,
    write_cog,
    write_webp_3857,
)
from sartale.run_pipeline import main, verified_dates

NAME_FMT = ("NISAR_L2_PR_GCOV_{cycle:03d}_084_A_019_4005_DHDH_A_{ymd}T220325_{ymd}T220400_"
            "P05023_N_F_J_001")
DATES = ["2026-07-26", "2026-08-19", "2026-09-12", "2026-10-18"]


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


def test_composite_choice_skips_2_july_when_it_comes_first():
    dates = ["2026-07-02", "2026-07-26", "2026-08-19", "2026-09-12", "2026-10-18"]
    assert composite_choice(dates) == (1, 3, 4)


def test_composite_choice_is_unchanged_without_2_july():
    assert composite_choice(DATES) == composite_indices(len(DATES))


def test_composite_choice_skips_every_flagged_date():
    dates = ["2026-07-02", "2026-07-14", "2026-07-26", "2026-08-19", "2026-08-31", "2026-09-12",
             "2026-09-24", "2026-10-06", "2026-10-18"]
    e, m, l = composite_choice(dates, {"2026-07-02", "2026-07-14"})
    assert [dates[e], dates[m], dates[l]] == ["2026-07-26", "2026-09-12", "2026-10-18"]


def test_composite_choice_uses_a_flagged_date_only_if_nothing_else_is_left_and_never_2_july():
    dates = ["2026-07-02", "2026-07-14", "2026-07-26"]
    assert composite_choice(dates, set(dates)) == (1, 2, 2)


def test_composite_choice_with_nothing_else_than_2_july_fails():
    with pytest.raises(ValueError, match="2026-07-02"):
        composite_choice(["2026-07-02"])


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


def test_write_webp_3857_max_width_caps_a_windowed_frame_only(tmp_path):
    layer = multilook_layer(_layer(n=300), 3)
    gray = np.full((100, 100), 128, np.uint8)
    w = write_webp_3857(gray, layer, tmp_path / "a.webp", window=(71.0, 34.0, 72.0, 34.5))
    c = write_webp_3857(gray, layer, tmp_path / "b.webp", window=(71.0, 34.0, 72.0, 34.5), max_width=300)
    assert w == pytest.approx(c)  # same place on the map
    assert Image.open(tmp_path / "a.webp").size[0] > 300
    width, height = Image.open(tmp_path / "b.webp").size
    assert width == 300 and height == pytest.approx(300 * (w[3] - w[1]) / (w[2] - w[0]), abs=1)


def test_window_is_the_preview_window_and_holds_tarbela():
    assert config.WINDOW == DISPLAY_WINDOW
    west, south, east, north = config.WINDOW
    assert west < 71.56 and east > 72.7 and south < 34.0 and north > 34.1


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

def _make_stack(tmp_path, dates=DATES, skip=None, shift_last=False, extra_dates=(), accuracy="N"):
    """Files for `dates`; the search manifest also lists `extra_dates` that have no file (not built)."""
    gdir = tmp_path / "gcov"
    gdir.mkdir()
    granules = []
    for i, d in enumerate(sorted([*dates, *extra_dates])):
        ymd = d.replace("-", "")
        name = NAME_FMT.format(cycle=10 + i, ymd=ymd)
        acc = accuracy if d == dates[0] else "N"
        granules.append({"name": name, "start": f"{d}T22:03:25+00:00", "crid": "P05023",
                         "accuracy": acc, "coverage": "F", "cycle": 10 + i})
        if name == skip or d in extra_dates:
            continue
        dx = 100.0 if shift_last and d == dates[-1] else 0.0
        write_gcov(gdir / f"{name}.h5", seed=i, scale=10 ** (-i / 2), dx=dx,
                   granule_id=name, release_id="P05023")
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

    assert list(m) == ["stack", "crid", "maturity", "bounds", "dates", "acquisitions", "composite",
                       "composite_dates", "stretch_db", "gap", "pixel_m", "analysis_m"]
    assert m["acquisitions"] == DATES
    assert m["composite_dates"] == [DATES[0], DATES[2], DATES[3]]
    assert m["stack"] == config.STACK_ID and m["crid"] == config.CRID
    assert m["maturity"] == "Provisional"
    assert m["gap"] == {"start": config.GAP_START, "end": config.GAP_END}
    assert m["composite"] == "frames/composite_HH.webp"
    assert m["bounds"] == pytest.approx(list(config.WINDOW), abs=1e-4)
    assert m["analysis_m"] == 3 * STEP
    assert m["pixel_m"] == pytest.approx(3 * STEP * DISPLAY_LOOKS, rel=0.05)  # display only: 3 x 100 m x 2 here

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


def test_build_composite_never_uses_2_july(tmp_path):
    dates = ["2026-07-02", "2026-07-26", "2026-08-19", "2026-09-12", "2026-10-18"]
    gdir, mpath, _ = _make_stack(tmp_path, dates=dates)
    out, _ = _build(tmp_path, gdir, mpath, dates=dates)
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert m["composite_dates"] == ["2026-07-26", "2026-09-12", "2026-10-18"]


def test_build_composite_skips_a_forecast_orbit_date_too(tmp_path):
    dates = ["2026-07-02", "2026-07-14", "2026-07-26", "2026-08-19", "2026-09-12"]
    gdir, mpath, granules = _make_stack(tmp_path, dates=dates)
    doc = json.loads(mpath.read_text(encoding="utf-8"))
    old = doc["granules"][1]["name"]
    new = old.replace("_P05023_N_", "_P05023_F_")
    doc["granules"][1].update(name=new, accuracy="F")
    mpath.write_text(json.dumps(doc), encoding="utf-8")
    write_gcov(gdir / f"{new}.h5", seed=1, granule_id=new, release_id="P05023")
    (gdir / f"{old}.h5").unlink()
    out, _ = _build(tmp_path, gdir, mpath, dates=dates)
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert m["composite_dates"] == ["2026-07-26", "2026-08-19", "2026-09-12"]


def test_build_warns_when_the_composite_has_to_use_a_flagged_date(tmp_path, capsys):
    dates = ["2026-07-14", "2026-07-26"]
    gdir, mpath, granules = _make_stack(tmp_path, dates=dates)
    doc = json.loads(mpath.read_text(encoding="utf-8"))
    for g in doc["granules"]:
        old = g["name"]
        g.update(name=old.replace("_P05023_N_", "_P05023_F_"), accuracy="F")
        write_gcov(gdir / f"{g['name']}.h5", seed=1, granule_id=g["name"], release_id="P05023")
        (gdir / f"{old}.h5").unlink()
    mpath.write_text(json.dumps(doc), encoding="utf-8")
    _build(tmp_path, gdir, mpath, dates=dates)
    assert "WARNING: the composite uses flagged dates" in capsys.readouterr().out


def test_build_flags_2_july_and_forecast_granules_like_the_preview(tmp_path):
    dates = ["2026-07-02", "2026-07-14", "2026-08-19", "2026-09-12"]
    gdir, mpath, granules = _make_stack(tmp_path, dates=dates)
    doc = json.loads(mpath.read_text(encoding="utf-8"))
    doc["granules"][1]["accuracy"] = "F"
    doc["granules"][1]["name"] = doc["granules"][1]["name"].replace("_P05023_N_", "_P05023_F_")
    mpath.write_text(json.dumps(doc), encoding="utf-8")
    old = granules[1]["name"]
    new = doc["granules"][1]["name"]
    write_gcov(gdir / f"{new}.h5", seed=1, granule_id=new, release_id="P05023")
    (gdir / f"{old}.h5").unlink()
    out, _ = _build(tmp_path, gdir, mpath, dates=dates)
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    flags = {e["date"]: e.get("flag") for e in m["dates"]}
    assert flags == {"2026-07-02": INTERFERENCE_FLAG, "2026-07-14": FORECAST_FLAG,
                     "2026-08-19": None, "2026-09-12": None}
    assert all("flag" not in e for e in m["dates"][2:])  # absent, not null


def test_build_stretch_is_not_set_by_2_july(tmp_path):
    dates = ["2026-07-02", "2026-07-26", "2026-08-19", "2026-09-12"]
    gdir, mpath, granules = _make_stack(tmp_path, dates=dates)
    name = granules[0]["name"]
    write_gcov(gdir / f"{name}.h5", seed=0, scale=1e6, granule_id=name, release_id="P05023")  # far brighter than the rest
    out, _ = _build(tmp_path, gdir, mpath, dates=dates)
    with_it = json.loads((out / "manifest.json").read_text(encoding="utf-8"))["stretch_db"]

    other = tmp_path / "other"
    other.mkdir()
    gdir2, mpath2, _ = _make_stack(other, dates=dates[1:])
    out2, _ = _build(other, gdir2, mpath2, dates=dates[1:])
    without = json.loads((out2 / "manifest.json").read_text(encoding="utf-8"))["stretch_db"]
    assert with_it["HH"][1] < 30  # 1e6 x would be about +60 dB
    assert with_it["HH"][1] == pytest.approx(without["HH"][1], abs=12)


def test_build_cogs_stay_at_analysis_resolution_and_frames_are_coarser(tmp_path):
    gdir, mpath, _ = _make_stack(tmp_path)
    out, cog = _build(tmp_path, gdir, mpath)
    with rasterio.open(cog / f"{DATES[0]}_HV.tif") as src:
        assert src.width == 33 and src.height == 33  # 100 fixture samples, multilooked by 3
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert m["pixel_m"] > m["analysis_m"]


def test_build_stops_on_a_mask_value_nobody_has_checked(tmp_path):
    gdir, mpath, granules = _make_stack(tmp_path)
    name = granules[0]["name"]
    mask = np.ones((100, 100), "u1")
    mask[:3] = 2
    write_gcov(gdir / f"{name}.h5", seed=0, mask=mask, granule_id=name, release_id="P05023")
    with pytest.raises(ValueError, match="mask value"):
        _build(tmp_path, gdir, mpath)


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


def test_build_lists_every_searched_date_as_an_acquisition_even_when_not_built(tmp_path):
    extra = ["2026-08-31", "2026-09-24", "2026-10-06"]
    gdir, mpath, _ = _make_stack(tmp_path, extra_dates=extra)
    out, _ = _build(tmp_path, gdir, mpath)
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert [d["date"] for d in m["dates"]] == DATES
    assert m["acquisitions"] == sorted([*DATES, *extra])


def test_build_deletes_a_stale_sites_json(tmp_path):
    gdir, mpath, _ = _make_stack(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    (out / "sites.json").write_text("[]", encoding="utf-8")
    _build(tmp_path, gdir, mpath)
    assert not (out / "sites.json").exists()


def test_build_deletes_frames_the_manifest_does_not_list(tmp_path):
    gdir, mpath, _ = _make_stack(tmp_path)
    frames = tmp_path / "out" / "frames"
    frames.mkdir(parents=True)
    for stale in ("2026-07-14_HH.webp", "2026-07-14_HV.webp"):
        (frames / stale).write_bytes(b"old")
    out, _ = _build(tmp_path, gdir, mpath)
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    listed = {Path(p).name for d in m["dates"] for p in d["frames"].values()} | {"composite_HH.webp"}
    assert {f.name for f in frames.iterdir()} == listed


def test_build_refuses_a_file_that_says_it_is_another_granule(tmp_path):
    gdir, mpath, granules = _make_stack(tmp_path)
    name = granules[1]["name"]
    write_gcov(gdir / f"{name}.h5", seed=1, granule_id=granules[2]["name"], release_id="P05023")
    with pytest.raises(ValueError, match="manifest expects"):
        _build(tmp_path, gdir, mpath)


def test_build_refuses_a_file_with_another_release_id(tmp_path):
    gdir, mpath, granules = _make_stack(tmp_path)
    name = granules[0]["name"]
    write_gcov(gdir / f"{name}.h5", seed=0, granule_id=name, release_id="P05024")
    with pytest.raises(ValueError, match="P05024"):
        _build(tmp_path, gdir, mpath)


def test_build_prints_a_mask_histogram_for_each_file(tmp_path, capsys):
    import numpy as np
    gdir, mpath, granules = _make_stack(tmp_path)
    name = granules[0]["name"]
    mask = np.ones((100, 100), "u1")
    mask[:3] = 255
    write_gcov(gdir / f"{name}.h5", seed=0, mask=mask, granule_id=name, release_id="P05023")
    _build(tmp_path, gdir, mpath)
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("mask ")]
    assert len(lines) == len(DATES)
    assert lines[0] == "mask 2026-07-26: 1: 9700, 255: 300"
    assert lines[1] == "mask 2026-08-19: 1: 10000"


def test_build_warns_about_a_forecast_orbit_granule_and_2_july_but_still_builds(tmp_path, capsys):
    dates = ["2026-07-02", "2026-08-19", "2026-09-12", "2026-10-18"]
    gdir, mpath, _ = _make_stack(tmp_path, dates=dates, accuracy="F")
    out, _ = _build(tmp_path, gdir, mpath, dates=dates)
    printed = capsys.readouterr().out
    assert "WARNING: 2026-07-02 is a forecast-orbit product" in printed
    assert "WARNING: 2026-07-02 shows likely radio interference" in printed
    assert printed.count("WARNING") == 2
    assert (out / "manifest.json").is_file()


def test_build_prints_no_warning_for_the_default_dates(tmp_path, capsys):
    gdir, mpath, _ = _make_stack(tmp_path)
    _build(tmp_path, gdir, mpath)
    assert "WARNING" not in capsys.readouterr().out


# --- rebuild ------------------------------------------------------------------

def _with_sizes(gdir, mpath):
    doc = json.loads(mpath.read_text(encoding="utf-8"))
    for g in doc["granules"]:
        f = gdir / f"{g['name']}.h5"
        g["size"] = f.stat().st_size if f.exists() else 7_000_000_000
    mpath.write_text(json.dumps(doc), encoding="utf-8")


def _rebuild(tmp_path, gdir, mpath):
    out, cog = tmp_path / "out", tmp_path / "cog"
    sites_in = tmp_path / "sites_in.json"
    sites_in.write_text(json.dumps([{"id": "a", "name": "A", "lon": CENTER_LONLAT[0], "lat": CENTER_LONLAT[1],
                                     "role": "Stable urban control", "why": "bright on every date"}]), encoding="utf-8")
    main(["rebuild", "--gcov-dir", str(gdir), "--manifest-in", str(mpath), "--sites-in", str(sites_in),
          "--out-dir", str(out), "--cog-dir", str(cog)])
    return out


def test_verified_dates_takes_files_of_the_right_size_and_ignores_part_files(tmp_path, capsys):
    gdir, mpath, granules = _make_stack(tmp_path)
    _with_sizes(gdir, mpath)
    (gdir / f"{granules[1]['name']}.h5").rename(gdir / f"{granules[1]['name']}.h5.part")
    doc = json.loads(mpath.read_text(encoding="utf-8"))
    doc["granules"][2]["size"] += 1  # a wrong size is not verified
    assert verified_dates(doc["granules"], gdir) == [DATES[0], DATES[3]]
    printed = capsys.readouterr().out
    assert f"not used: {DATES[1]} (no complete file)" in printed
    assert f"not used: {DATES[2]} (size differs from CMR)" in printed


def test_rebuild_builds_every_verified_date_and_samples_the_sites(tmp_path, capsys):
    gdir, mpath, granules = _make_stack(tmp_path, extra_dates=["2026-08-31"])
    _with_sizes(gdir, mpath)
    (gdir / f"{granules[1]['name']}.h5.part").write_bytes(b"partial")
    out = _rebuild(tmp_path, gdir, mpath)
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert [d["date"] for d in m["dates"]] == DATES
    sites = json.loads((out / "sites.json").read_text(encoding="utf-8"))
    assert [p["date"] for p in sites[0]["series"]] == DATES
    assert "why" not in sites[0]
    printed = capsys.readouterr().out
    assert sum(ln.startswith("mask ") for ln in printed.splitlines()) == len(DATES)
    assert "a (Stable urban control) hh_db: spread" in printed
    assert "4 dates" in printed


def test_rebuild_reproduces_the_change_layer_when_there_are_enough_dates(tmp_path, capsys):
    dates = ["2026-07-26", "2026-08-19", "2026-08-31", "2026-09-12", "2026-09-24", "2026-10-06", "2026-10-18"]
    gdir, mpath, _ = _make_stack(tmp_path, dates=dates)
    _with_sizes(gdir, mpath)
    out = _rebuild(tmp_path, gdir, mpath)
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert len(m["change"]["baseline_dates"]) >= 5
    for path in m["change"]["frames"].values():
        assert (out / path).is_file()
    assert (tmp_path / "cog" / f"change_{dates[-1]}.tif").is_file()
    sites = json.loads((out / "sites.json").read_text(encoding="utf-8"))
    assert any(p["change_score"] is not None for p in sites[0]["series"])
    assert "change: threshold" in capsys.readouterr().out


def test_rebuild_with_too_few_dates_has_no_change_layer_and_null_site_scores(tmp_path, capsys):
    gdir, mpath, _ = _make_stack(tmp_path)
    _with_sizes(gdir, mpath)
    out = _rebuild(tmp_path, gdir, mpath)
    assert "change" not in json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    sites = json.loads((out / "sites.json").read_text(encoding="utf-8"))
    assert all(p["change_score"] is None for p in sites[0]["series"])
    assert "not enough dates" in capsys.readouterr().out


def test_rebuild_refuses_a_manifest_without_sizes(tmp_path):
    gdir, mpath, _ = _make_stack(tmp_path)
    with pytest.raises(ValueError, match="run `search` again"):
        _rebuild(tmp_path, gdir, mpath)
