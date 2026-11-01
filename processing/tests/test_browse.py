"""Tests for the browse-preview path. All inputs are small synthetic arrays, never the real files."""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import numpy as np
import pytest
from PIL import Image
from pyproj import Transformer

from sartale import config
from sartale.browse import (
    DISPLAY_WINDOW,
    FORECAST_FLAG,
    INTERFERENCE_FLAG,
    build_preview_manifest,
    geo_extent,
    load_browse,
    pixel_size_m,
    shared_extent,
    split_channels,
    write_preview_frames,
)
from sartale.run_pipeline import main

NAME_FMT = ("NISAR_L2_PR_GCOV_{cycle:03d}_084_A_019_4005_DHDH_A_{ymd}T002239_{ymd}T002313_"
            "P05023_{acc}_F_J_001")
EXTENT = (70.5, 33.0, 74.4, 36.2)  # wide enough to cover the display window
SHAPE = (64, 80)


def _rgb(hh=200, hv=100, shape=SHAPE, fill=None):
    rgb = np.zeros((*shape, 3), np.uint8)
    rgb[..., 0] = hh
    rgb[..., 1] = hv
    rgb[..., 2] = hh  # blue repeats red, as in the real files
    if fill is not None:
        rgb[fill] = 0
    return rgb


# --- split_channels -------------------------------------------------------------

def test_split_channels_returns_red_as_hh_and_green_as_hv():
    rgb = np.array([[[10, 20, 10], [30, 40, 30]]], np.uint8)
    hh, hv = split_channels(rgb)
    assert hh.dtype == np.uint8 and hv.dtype == np.uint8
    assert hh.tolist() == [[10, 30]] and hv.tolist() == [[20, 40]]


def test_split_channels_makes_black_fill_transparent_zero():
    rgb = np.array([[[0, 0, 0], [5, 6, 5]]], np.uint8)
    hh, hv = split_channels(rgb)
    assert hh[0, 0] == 0 and hv[0, 0] == 0
    assert hh[0, 1] == 5 and hv[0, 1] == 6


def test_split_channels_keeps_real_pixels_above_zero():
    """A real pixel with one zero channel must not be mistaken for fill."""
    rgb = np.array([[[0, 9, 0]]], np.uint8)
    hh, hv = split_channels(rgb)
    assert hh[0, 0] == 1 and hv[0, 0] == 9


def test_split_channels_rejects_red_not_equal_blue():
    rgb = np.array([[[10, 20, 11]]], np.uint8)
    with pytest.raises(ValueError, match="red and blue"):
        split_channels(rgb)


def test_split_channels_rejects_wrong_shape():
    with pytest.raises(ValueError, match="RGB"):
        split_channels(np.zeros((4, 4), np.uint8))


# --- geo_extent -----------------------------------------------------------------

def test_geo_extent_maps_valid_block_to_footprint():
    valid = np.zeros((80, 100), bool)
    valid[5:75, 10:90] = True  # rows 5..74, cols 10..89
    west, south, east, north = geo_extent(valid, (0.0, 0.0, 8.0, 7.0))
    # 80 valid columns span 8 degrees, so 0.1 degree per pixel; 10 columns lie west of the block
    assert west == pytest.approx(-1.0) and east == pytest.approx(9.0)
    assert north == pytest.approx(7.5) and south == pytest.approx(-0.5)


def test_geo_extent_rejects_empty_mask():
    with pytest.raises(ValueError, match="no valid"):
        geo_extent(np.zeros((4, 4), bool), (0.0, 0.0, 1.0, 1.0))


def test_shared_extent_averages_close_extents_and_rejects_far_ones():
    a = (70.5, 33.0, 74.4, 36.2)
    b = (70.502, 33.002, 74.402, 36.202)
    got = shared_extent([a, b])
    assert got == pytest.approx((70.501, 33.001, 74.401, 36.201))
    with pytest.raises(ValueError, match="differ"):
        shared_extent([a, (71.0, 33.0, 74.4, 36.2)])


def test_pixel_size_m_is_ground_metres_per_pixel():
    # one degree of latitude is about 111 km: 100 pixels over 1 degree north-south
    assert pixel_size_m((70.0, 34.0, 71.0, 35.0), (100, 100)) == pytest.approx(
        np.mean([111_320 * np.cos(np.radians(34.5)) * 0.01, 110_950 * 0.01]), rel=0.01)


# --- write_preview_frames -------------------------------------------------------

def _frames(dates, hh=None):
    hh = hh or {}
    return {d: split_channels(_rgb(hh=hh.get(d, 150 + 10 * i), hv=90 + 10 * i)) for i, d in enumerate(dates)}


DATES = ["2026-07-02", "2026-07-26", "2026-09-12", "2026-10-18"]
COMPOSITE = ("2026-07-26", "2026-09-12", "2026-10-18")


def test_frames_share_identical_bounds_and_the_display_window(tmp_path):
    info = write_preview_frames(_frames(DATES), EXTENT, tmp_path)
    west, south, east, north = info["bounds"]
    assert (west, south, east, north) == pytest.approx(DISPLAY_WINDOW, abs=1e-4)
    sizes = {Image.open(tmp_path / rel).size
             for d in info["frames"].values() for rel in d.values()}
    sizes.add(Image.open(tmp_path / info["composite"]).size)
    assert len(sizes) == 1
    assert set(info["frames"]) == set(DATES)


def test_frames_are_webp_with_alpha_and_transparent_fill(tmp_path):
    frames = {}
    for d in DATES:
        rgb = _rgb()
        rgb[:, :40] = 0  # western half is fill
        frames[d] = split_channels(rgb)
    info = write_preview_frames(frames, EXTENT, tmp_path)
    img = Image.open(tmp_path / info["frames"]["2026-07-26"]["HH"])
    assert img.format == "WEBP"
    rgba = np.asarray(img.convert("RGBA"))
    assert rgba[..., 3].min() == 0 and rgba[..., 3].max() == 255
    h, w = rgba.shape[:2]
    # EXTENT spans 70.5..74.4; the window is 70.9..72.8, so the fill edge (72.45) is inside it
    assert rgba[h // 2, 5, 3] == 0          # far west of the window: fill
    assert rgba[h // 2, w - 5, 3] == 255    # far east: real pixels


def test_hh_and_hv_frames_carry_their_own_channel(tmp_path):
    frames = {d: split_channels(_rgb(hh=220, hv=40)) for d in DATES}
    info = write_preview_frames(frames, EXTENT, tmp_path)
    hh = np.asarray(Image.open(tmp_path / info["frames"]["2026-07-26"]["HH"]).convert("RGBA"))
    hv = np.asarray(Image.open(tmp_path / info["frames"]["2026-07-26"]["HV"]).convert("RGBA"))
    h, w = hh.shape[:2]
    assert abs(int(hh[h // 2, w // 2, 0]) - 220) < 12
    assert abs(int(hv[h // 2, w // 2, 0]) - 40) < 12


def test_composite_uses_hh_of_26_jul_12_sep_and_18_oct_as_red_green_blue(tmp_path):
    hh = {"2026-07-02": 250, "2026-07-26": 200, "2026-09-12": 120, "2026-10-18": 50}
    info = write_preview_frames(_frames(DATES, hh), EXTENT, tmp_path)
    comp = np.asarray(Image.open(tmp_path / info["composite"]).convert("RGBA"))
    h, w = comp.shape[:2]
    r, g, b, a = (int(v) for v in comp[h // 2, w // 2])
    assert a == 255
    assert abs(r - 200) < 14 and abs(g - 120) < 14 and abs(b - 50) < 14
    assert info["composite_dates"] == list(COMPOSITE)


def test_composite_never_uses_2_july(tmp_path):
    a = write_preview_frames(_frames(DATES, {"2026-07-02": 250}), EXTENT, tmp_path / "a")
    b = write_preview_frames(_frames(DATES, {"2026-07-02": 10}), EXTENT, tmp_path / "b")
    assert (tmp_path / "a" / a["composite"]).read_bytes() == (tmp_path / "b" / b["composite"]).read_bytes()


def test_composite_is_transparent_where_any_of_the_three_dates_has_fill(tmp_path):
    frames = _frames(DATES)
    rgb = _rgb(hh=120)
    rgb[:, 40:] = 0  # eastern part of 12 Sep is fill (lon 72.45 and east, inside the window)
    frames["2026-09-12"] = split_channels(rgb)
    info = write_preview_frames(frames, EXTENT, tmp_path)
    comp = np.asarray(Image.open(tmp_path / info["composite"]).convert("RGBA"))
    h, w = comp.shape[:2]
    assert comp[h // 2, w - 5, 3] == 0 and comp[h // 2, 5, 3] == 255


def test_missing_composite_date_is_an_error(tmp_path):
    frames = _frames(["2026-07-02", "2026-07-26"])
    with pytest.raises(ValueError, match="composite"):
        write_preview_frames(frames, EXTENT, tmp_path)


def test_window_must_lie_inside_the_image_extent(tmp_path):
    with pytest.raises(ValueError, match="window"):
        write_preview_frames(_frames(DATES), (71.5, 33.0, 74.4, 36.2), tmp_path)


def test_bounds_are_web_mercator_aligned(tmp_path):
    """The returned lon/lat bounds are those of the written pixels, not a rounded request."""
    info = write_preview_frames(_frames(DATES), EXTENT, tmp_path)
    tr = Transformer.from_crs(4326, 3857, always_xy=True)
    x0, y0 = tr.transform(info["bounds"][0], info["bounds"][1])
    x1, y1 = tr.transform(info["bounds"][2], info["bounds"][3])
    w, h = Image.open(tmp_path / info["composite"]).size
    assert (x1 - x0) / w == pytest.approx((y1 - y0) / h, rel=0.02)  # square pixels


# --- build_preview_manifest -----------------------------------------------------

def _granules(dates, forecast=("2026-07-14",)):
    out = {}
    for i, d in enumerate(dates):
        ymd = d.replace("-", "")
        out[d] = NAME_FMT.format(cycle=24 + i, ymd=ymd, acc="F" if d in forecast else "N")
    return out


ALL_DATES = ["2026-07-02", "2026-07-14", "2026-07-26", "2026-08-19", "2026-08-31",
             "2026-09-12", "2026-09-24", "2026-10-06", "2026-10-18"]


def _info(dates):
    return {
        "bounds": [70.9, 33.6, 72.8, 34.8],
        "frames": {d: {"HH": f"frames/{d}_HH.webp", "HV": f"frames/{d}_HV.webp"} for d in dates},
        "composite": "frames/composite_HH.webp",
        "composite_dates": list(COMPOSITE),
    }


def test_manifest_is_a_provisional_preview_with_no_stretch(tmp_path):
    m = build_preview_manifest(_info(ALL_DATES), _granules(ALL_DATES), 174, tmp_path)
    assert m["maturity"] == "Provisional preview"
    assert m["stretch_db"] is None
    assert m["gap"] == {"start": config.GAP_START, "end": config.GAP_END}
    assert m["bounds"] == [70.9, 33.6, 72.8, 34.8]
    assert [e["date"] for e in m["dates"]] == ALL_DATES
    assert m["pixel_m"] == 174
    assert m["crid"] == "P05023" and m["stack"] == config.STACK_ID
    assert json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8")) == m


def test_preview_manifest_lists_every_date_as_an_acquisition(tmp_path):
    m = build_preview_manifest(_info(ALL_DATES), _granules(ALL_DATES), 174, tmp_path)
    assert m["acquisitions"] == ALL_DATES


def test_manifest_carries_the_real_granule_ids(tmp_path):
    granules = _granules(ALL_DATES)
    m = build_preview_manifest(_info(ALL_DATES), granules, 174, tmp_path)
    for e in m["dates"]:
        assert e["granule"] == granules[e["date"]]
        assert e["granule"].startswith("NISAR_L2_PR_GCOV_")


def test_manifest_flags_only_2_july_and_the_forecast_orbit_date(tmp_path):
    m = build_preview_manifest(_info(ALL_DATES), _granules(ALL_DATES), 174, tmp_path)
    flags = {e["date"]: e.get("flag") for e in m["dates"]}
    assert flags["2026-07-02"] == INTERFERENCE_FLAG == (
        "Possible radio interference over the western area (unconfirmed). "
        "Do not read this as surface change.")
    assert flags["2026-07-14"] == FORECAST_FLAG == "Forecast-orbit product; positions may be less precise."
    assert [d for d, f in flags.items() if f] == ["2026-07-02", "2026-07-14"]
    # the key is absent, not null, for unflagged dates
    assert all("flag" not in e for e in m["dates"] if e["date"] not in flags or not flags[e["date"]])


def test_manifest_has_no_db_values_anywhere(tmp_path):
    m = build_preview_manifest(_info(ALL_DATES), _granules(ALL_DATES), 174, tmp_path)
    text = json.dumps(m).lower()
    assert "db" not in text.replace("stretch_db", "")


def test_manifest_rejects_mismatched_granule_date(tmp_path):
    granules = _granules(ALL_DATES)
    granules["2026-07-26"] = granules["2026-08-19"]
    with pytest.raises(ValueError, match="2026-07-26"):
        build_preview_manifest(_info(ALL_DATES), granules, 174, tmp_path)


def test_manifest_rejects_missing_granule(tmp_path):
    granules = _granules(ALL_DATES)
    del granules["2026-08-31"]
    with pytest.raises(ValueError, match="2026-08-31"):
        build_preview_manifest(_info(ALL_DATES), granules, 174, tmp_path)


# --- load_browse and the CLI ----------------------------------------------------

def _write_browse(tmp_path, dates, tamper=False):
    browse = tmp_path / "browse"
    browse.mkdir()
    granules = _granules(dates)
    entries, footprints = [], {}
    for i, d in enumerate(dates):
        rgb = _rgb(hh=150 + 10 * i, hv=80 + 10 * i, shape=(60, 80))
        rgb[:5] = 0
        rgb[-5:] = 0
        rgb[:, :6] = 0
        rgb[:, -6:] = 0
        name = f"{d.replace('-', '')}_LATLON.png"
        Image.fromarray(rgb, "RGB").save(browse / name)
        data = (browse / name).read_bytes()
        entries.append({"file": name, "granule": granules[d],
                        "sha256": "0" * 64 if tamper else hashlib.sha256(data).hexdigest(),
                        "bytes": len(data), "url": f"https://example.invalid/{name}"})
        # valid block rows 5..54, cols 6..73: footprint chosen so the full image is EXTENT-sized
        dx = (EXTENT[2] - EXTENT[0]) / 80
        dy = (EXTENT[3] - EXTENT[1]) / 60
        w, e = EXTENT[0] + 6 * dx, EXTENT[0] + 74 * dx
        n, s = EXTENT[3] - 5 * dy, EXTENT[3] - 55 * dy
        footprints[granules[d]] = [[e, s], [e, n], [w, n], [w, s]]
    (browse / "browse_manifest.json").write_text(json.dumps(entries), encoding="utf-8")
    fp = tmp_path / "footprints.json"
    fp.write_text(json.dumps({"source": "test", "footprints": footprints}), encoding="utf-8")
    return browse, fp, granules


def test_load_browse_reads_every_date_and_checks_sha256(tmp_path):
    browse, _, granules = _write_browse(tmp_path, DATES)
    loaded = load_browse(browse)
    assert sorted(loaded) == DATES
    assert loaded["2026-07-26"]["granule"] == granules["2026-07-26"]
    assert loaded["2026-07-26"]["rgb"].shape == (60, 80, 3)


def test_load_browse_rejects_a_file_that_does_not_match_its_hash(tmp_path):
    browse, _, _ = _write_browse(tmp_path, DATES, tamper=True)
    with pytest.raises(ValueError, match="sha256"):
        load_browse(browse)


def test_preview_command_writes_frames_and_manifest(tmp_path):
    browse, fp, granules = _write_browse(tmp_path, DATES)
    out = tmp_path / "out"
    main(["preview", "--browse-dir", str(browse), "--footprints", str(fp), "--out-dir", str(out)])
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert m["maturity"] == "Provisional preview" and m["stretch_db"] is None
    assert [e["date"] for e in m["dates"]] == DATES
    assert m["dates"][0]["flag"] == INTERFERENCE_FLAG
    assert m["bounds"] == pytest.approx(list(DISPLAY_WINDOW), abs=1e-4)
    for e in m["dates"]:
        assert e["granule"] == granules[e["date"]]
        for rel in e["frames"].values():
            assert (out / rel).is_file()
    assert (out / m["composite"]).is_file()
    # pixel size: about 3.9 degrees over 80 pixels at 34 N is 4.0 km, so well above the real 174 m
    assert m["pixel_m"] > 1000
