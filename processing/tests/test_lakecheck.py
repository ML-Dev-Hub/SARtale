import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import numpy as np
import pytest
from pyproj import Transformer

from sartale import lakecheck
from sartale.lakecheck import compare_masks, find_clear_scene, mndwi_water
from test_lakebuild import N, PX, make_lake, write_pass


def test_mndwi_water_threshold():
    green = np.array([[0.30, 0.10, 0.20]])
    swir = np.array([[0.10, 0.30, 0.20]])  # MNDWI +0.5, -0.5, 0.0
    assert mndwi_water(green, swir).tolist() == [[True, False, False]]  # strict >
    assert mndwi_water(green, swir, threshold=-0.1).tolist() == [[True, False, True]]


def test_mndwi_water_nan_and_zero_sum_are_not_water():
    out = mndwi_water(np.array([np.nan, 0.0]), np.array([0.1, 0.0]))
    assert out.tolist() == [False, False]


def test_compare_masks_identical_is_iou_1():
    m = np.zeros((10, 10), bool)
    m[2:6, 2:6] = True
    r = compare_masks(m, m.copy(), pixel_m=10.0)
    assert r["iou"] == 1.0 and r["area_error_pct"] == 0.0
    assert r["radar_km2"] == r["optical_km2"] == pytest.approx(16 * 100 / 1e6)


def test_compare_masks_half_overlap():
    a = np.zeros((4, 4), bool)
    b = np.zeros((4, 4), bool)
    a[0:2, :] = True  # 8 px
    b[1:3, :] = True  # 8 px, 4 shared
    r = compare_masks(a, b, pixel_m=1000.0)
    assert r["iou"] == pytest.approx(4 / 12)
    assert r["radar_km2"] == 8.0 and r["optical_km2"] == 8.0 and r["area_error_pct"] == 0.0


def test_area_error_sign():
    big = np.ones((4, 4), bool)
    small = np.zeros((4, 4), bool)
    small[:2, :2] = True
    assert compare_masks(big, small, 10.0)["area_error_pct"] == pytest.approx(300.0)
    assert compare_masks(small, big, 10.0)["area_error_pct"] == pytest.approx(-75.0)


def test_compare_masks_empty_optical_has_no_percentage():
    r = compare_masks(np.ones((2, 2), bool), np.zeros((2, 2), bool), 10.0)
    assert r["area_error_pct"] is None and r["iou"] == 0.0
    r0 = compare_masks(np.zeros((2, 2), bool), np.zeros((2, 2), bool), 10.0)
    assert r0["iou"] is None


def test_compare_masks_ignores_pixels_outside_valid():
    a = np.ones((2, 2), bool)
    b = np.ones((2, 2), bool)
    valid = np.array([[True, False], [False, False]])
    assert compare_masks(a, b, 1000.0, valid=valid)["radar_km2"] == 1.0


class FakeResp:
    def __init__(self, features):
        self._f = features

    def raise_for_status(self):
        pass

    def json(self):
        return {"features": self._f}


def feat(fid, dt, cloud):
    return {"id": fid, "properties": {"datetime": dt, "eo:cloud_cover": cloud}, "assets": {}}


def test_find_clear_scene_picks_nearest_clear(monkeypatch):
    sent = {}

    def post(url, json=None, timeout=None):
        sent.update(url=url, body=json)
        return FakeResp([feat("far", "2026-07-13T05:30:00Z", 1), feat("near", "2026-07-11T05:30:00Z", 5),
                         feat("cloudy", "2026-07-10T05:30:00Z", 60)])

    monkeypatch.setattr(lakecheck.requests, "post", post)
    s = find_clear_scene((74.8, 36.3, 74.9, 36.4), "2026-07-10", days=3, max_cloud=20)
    assert s["id"] == "near"
    assert sent["url"].startswith("https://earth-search.aws.element84.com/v1")
    assert sent["body"]["collections"] == ["sentinel-2-l2a"]
    assert sent["body"]["datetime"] == "2026-07-07T00:00:00Z/2026-07-13T23:59:59Z"


def test_find_clear_scene_none_when_all_cloudy(monkeypatch):
    monkeypatch.setattr(lakecheck.requests, "post", lambda *a, **k: FakeResp([feat("c", "2026-07-10T05:30:00Z", 90)]))
    assert find_clear_scene((74.8, 36.3, 74.9, 36.4), "2026-07-10") is None


def test_scl_cloud_share_counts_cloud_shadow_and_invalid():
    scl = np.array([[4, 4, 9, 3], [8, 10, 0, 11]])  # veg, veg, cloud, shadow / cloud, cirrus, nodata, snow
    assert lakecheck.scl_cloud_share(scl) == pytest.approx(5 / 8)
    assert lakecheck.scl_cloud_share(np.full((3, 3), 6)) == 0.0


def test_radar_water_mask_matches_build(tmp_path):
    from sartale.lakebuild import build_lakes, radar_water_mask
    cache = tmp_path / "cache"
    a = make_lake("alpha")
    for d in ["2026-06-18", "2026-06-30", "2026-07-12", "2026-07-24"]:
        write_pass(cache, a, d, "156A")
        write_pass(cache, a, d, "063D")
    doc = build_lakes([a], cache, tmp_path / "out", "t")
    row = next(p for p in doc["lakes"][0]["series"] if p["date"] == "2026-07-12" and p["track"] == "156A")
    mask, x, y, epsg = radar_water_mask(a, cache, "2026-07-12_156A")
    assert mask.shape == (len(y), len(x)) and epsg == 32643
    assert mask.sum() * PX ** 2 / 1e6 == pytest.approx(row["area_km2"], abs=1e-3)
    wide, *_ = radar_water_mask(a, cache, "2026-07-12_156A", zone_only=False)
    assert wide.sum() >= mask.sum()
    with pytest.raises(KeyError):
        radar_water_mask(a, cache, "2026-01-01_156A")


def test_build_lakes_merges_checks(tmp_path):
    from sartale.lakebuild import build_lakes
    from sartale.lakebuild import check_key
    rows = [{"lake": "alpha", "note": lakecheck.NO_SCENE, "key": check_key(make_lake("alpha"))}]
    doc = build_lakes([make_lake("alpha")], tmp_path / "c", tmp_path / "o", "t", rows)
    assert doc["checks"] == rows
    # a row made for another method, zone or point is not carried
    assert build_lakes([make_lake("alpha")], tmp_path / "c", tmp_path / "o", "t",
                       [{"lake": "alpha", "note": lakecheck.NO_SCENE}])["checks"] == []
    assert build_lakes([], tmp_path / "c", tmp_path / "o", "t")["checks"] == []


def test_check_uses_the_radar_zone_with_an_outline(tmp_path, monkeypatch):
    import json
    from dataclasses import replace
    from sartale.lakebuild import radar_water_masks

    base = make_lake("ringed")
    d = 0.003  # about 300 m
    ring = [[base.lon + sx * d, base.lat + sy * d] for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1))]
    poly = tmp_path / "outline.geojson"
    poly.write_text(json.dumps({"type": "Polygon", "coordinates": [ring]}), encoding="utf-8")
    lake = replace(base, outline=str(poly))
    cache = tmp_path / "cache"
    for day in ["2026-06-18", "2026-06-30", "2026-07-12"]:
        write_pass(cache, lake, day, "156A")
        write_pass(cache, lake, day, "063D")
    r = radar_water_masks(lake, cache, "2026-07-12_156A")
    circle = radar_water_masks(replace(lake, outline=None), cache, "2026-07-12_156A")["zone"]
    assert r["zone"].sum() < circle.sum()  # the outline zone really is not the circle

    monkeypatch.setattr(lakecheck, "search_scenes", lambda *a, **k: [
        {"id": "S2X", "properties": {"datetime": "2026-07-12T05:00:00Z", "eo:cloud_cover": 1.0},
         "assets": {"green": {}, "swir16": {}, "scl": {}}}])
    everywhere = np.ones(r["zone"].shape, bool)
    monkeypatch.setattr(lakecheck, "optical_on_grid", lambda scene, x, y, epsg: {
        "water": everywhere, "valid": everywhere, "window_cloud_share": 0.0, "invalid_share": 0.0})
    series = [{"date": "2026-07-12", "track": "156A", "excluded": None, "area_km2": 0.1, "observable_share": 1.0}]
    row = lakecheck.check_lake(lake, cache, series, log=lambda *_: None)
    assert row["optical_km2"] == pytest.approx(r["zone"].sum() * PX ** 2 / 1e6)
    assert row["radar_km2"] == pytest.approx(r["zone_mask"].sum() * PX ** 2 / 1e6)


def test_check_skips_passes_the_status_would_not_use(monkeypatch):
    """M6: same validity rule as the status, so an unobservable or area-less pass is never the check pass."""
    monkeypatch.setattr(lakecheck, "search_scenes", lambda *a, **k: pytest.fail("no valid pass: must not search"))
    lake = make_lake("x")
    series = [
        {"date": "2026-07-12", "track": "156A", "excluded": None, "area_km2": 0.1, "observable_share": 0.2},
        {"date": "2026-07-24", "track": "156A", "excluded": None, "area_km2": None, "observable_share": 0.9},
        {"date": "2026-08-05", "track": "156A", "excluded": "bright", "area_km2": None, "observable_share": 0.9},
    ]
    assert lakecheck.check_lake(lake, "unused", series, log=lambda *_: None) == {"lake": "x", "note": "no valid NISAR pass"}


def _band(offset):
    return {"green": {"href": "g.tif", "raster:bands": [{"scale": 0.0001, "offset": offset}]}}


def test_reflectance_keeps_the_band_offset_when_the_item_has_not_applied_it():
    f = {"id": "old", "properties": {"datetime": "2026-08-17T05:30:00Z", "eo:cloud_cover": 1},
         "assets": _band(-0.1)}
    scene = lakecheck._scene(f, lakecheck.Date(2026, 8, 17))
    r = lakecheck._reflectance(scene, "green", np.array([0, 1000, 2500]))
    assert np.isnan(r[0])  # DN 0 is no data
    assert r[1:] == pytest.approx([0.0, 0.15])


def test_reflectance_drops_the_offset_earth_search_has_already_applied():
    """Earth Search items flagged earthsearch:boa_offset_applied already had the -0.1 BOA offset removed from the
    DNs; applying the band's offset again shifts every reflectance by -0.1 and breaks MNDWI over turbid lakes."""
    f = {"id": "new", "properties": {"datetime": "2026-08-17T05:30:00Z", "eo:cloud_cover": 1,
                                     "earthsearch:boa_offset_applied": True},
         "assets": _band(-0.1)}
    scene = lakecheck._scene(f, lakecheck.Date(2026, 8, 17))
    assert scene["boa_offset_applied"] is True
    r = lakecheck._reflectance(scene, "green", np.array([0, 1, 1500]))
    assert np.isnan(r[0])
    assert r[1:] == pytest.approx([0.0001, 0.15])  # scale kept, offset 0


def test_reflectance_flag_false_keeps_the_offset():
    f = {"id": "x", "properties": {"datetime": "2026-08-17T05:30:00Z", "earthsearch:boa_offset_applied": False},
         "assets": _band(-0.1)}
    scene = lakecheck._scene(f, lakecheck.Date(2026, 8, 17))
    assert lakecheck._reflectance(scene, "green", np.array([2000]))[0] == pytest.approx(0.1)


def test_season_words_and_dates():
    assert lakecheck.season_text() == "15 Jun–30 Sep"
    assert lakecheck.in_season("2026-06-15") and lakecheck.in_season("2026-09-30")
    assert not lakecheck.in_season("2026-06-14") and not lakecheck.in_season("2026-10-01")
    assert lakecheck.in_season("2026-10-05", season=((6, 1), (10, 9)))


def test_check_with_no_open_water_season_pass_is_a_note(monkeypatch):
    monkeypatch.setattr(lakecheck, "search_scenes", lambda *a, **k: pytest.fail("no in-season pass: must not search"))
    series = [{"date": d, "track": "084A", "excluded": None, "area_km2": 0.1, "observable_share": 1.0}
              for d in ("2026-06-01", "2026-10-18", "2026-10-30")]
    row = lakecheck.check_lake(make_lake("x"), "unused", series, log=lambda *_: None)
    assert row == {"lake": "x", "note": "no open-water-season pair (15 Jun–30 Sep)", "season": "15 Jun–30 Sep"}


def test_check_picks_the_clearest_in_season_pair_and_says_which_season(tmp_path, monkeypatch):
    lake = make_lake("lk")
    cache = tmp_path / "cache"
    days = ["2026-07-12", "2026-08-17", "2026-10-29"]
    for d in days:
        write_pass(cache, lake, d, "156A")
        write_pass(cache, lake, d, "063D")
    scenes = {"S2-jul": ("2026-07-12", 5.0), "S2-aug": ("2026-08-18", 1.0), "S2-oct": ("2026-10-29", 0.0)}
    monkeypatch.setattr(lakecheck, "search_scenes", lambda *a, **k: [
        {"id": sid, "properties": {"datetime": f"{d}T05:00:00Z", "eo:cloud_cover": 1.0},
         "assets": {"green": {}, "swir16": {}, "scl": {}}} for sid, (d, _) in scenes.items()])
    seen = []

    def optical(scene, x, y, epsg):
        seen.append(scene["id"])
        ones = np.ones((len(y), len(x)), bool)
        return {"water": ones, "valid": ones, "window_cloud_share": scenes[scene["id"]][1] / 100, "invalid_share": 0.0}

    monkeypatch.setattr(lakecheck, "optical_on_grid", optical)
    series = [{"date": d, "track": "156A", "excluded": None, "area_km2": 0.1, "observable_share": 1.0} for d in days]
    row = lakecheck.check_lake(lake, cache, series, log=lambda *_: None)
    assert "S2-oct" not in seen  # an October pair is never read: the lake may be frozen
    assert (row["s2_id"], row["nisar_date"], row["days_apart"]) == ("S2-aug", "2026-08-17", 1)  # clearest beats nearest
    assert row["season"] == "15 Jun–30 Sep" and row["s2_window_cloud_pct"] == 1.0


def test_a_clouded_lake_zone_is_not_reported_as_measured_zero_water(tmp_path, monkeypatch):
    """C05: cloud covers the whole lake zone but only a sliver of the window. The window share passes, the zone
    is unseen, so the pair is not used and the row says no clear scene instead of radar 0 / optical 0."""
    lake = make_lake("tiny")
    cache = tmp_path / "cache"
    for d in ["2026-07-12", "2026-07-24", "2026-08-05"]:
        write_pass(cache, lake, d, "156A")
        write_pass(cache, lake, d, "063D")
    monkeypatch.setattr(lakecheck, "search_scenes", lambda *a, **k: [
        {"id": "S2C", "properties": {"datetime": "2026-07-12T05:00:00Z", "eo:cloud_cover": 1.0},
         "assets": {"green": {}, "swir16": {}, "scl": {}}}])

    def optical(scene, x, y, epsg):
        from sartale.lakebuild import radar_water_masks
        zone = radar_water_masks(lake, cache, "2026-07-12_156A")["zone"]
        return {"water": np.zeros(zone.shape, bool), "valid": ~zone, "window_cloud_share": 0.01, "invalid_share": 0.01}

    monkeypatch.setattr(lakecheck, "optical_on_grid", optical)
    series = [{"date": "2026-07-12", "track": "156A", "excluded": None, "area_km2": 0.1, "observable_share": 1.0}]
    row = lakecheck.check_lake(lake, cache, series, log=lambda *_: None)
    assert "note" in row and "radar_km2" not in row and "optical_km2" not in row
    assert row["note"].startswith(lakecheck.NO_SCENE)


def test_zone_valid_share():
    zone = np.zeros((4, 4), bool)
    zone[:2] = True
    valid = np.ones((4, 4), bool)
    valid[0] = False
    assert lakecheck.zone_valid_share(valid, zone) == 0.5
    assert lakecheck.zone_valid_share(valid, np.zeros((4, 4), bool)) == 0.0


# --- snow and ice are not a clear view (I2) ------------------------------------------------------------------------

def synthetic_scene(tmp_path, lake, scl_at, sid="S2_SYN", date="2026-07-12", cloud=1.0):
    """A Sentinel-2 item whose B03, B11 and SCL are local GeoTIFFs over 10 km around `lake` (EPSG 32643): MNDWI is
    water everywhere (green 0.2, SWIR 0.05), and SCL is `scl_at(dx, dy)` of the offsets from the lake point in metres
    (on the 20 m SCL grid). Returns the STAC feature."""
    import rasterio
    from rasterio.transform import from_origin
    cx, cy = Transformer.from_crs(4326, 32643, always_xy=True).transform(lake.lon, lake.lat)
    half = 5000.0
    folder = tmp_path / sid
    folder.mkdir(parents=True, exist_ok=True)

    def write(name, px, values):
        n = int(2 * half / px)
        tf = from_origin(cx - half, cy + half, px, px)
        with rasterio.open(folder / f"{name}.tif", "w", driver="GTiff", width=n, height=n, count=1,
                           dtype=values.dtype, crs="EPSG:32643", transform=tf) as dst:
            dst.write(values, 1)
        return {"href": str(folder / f"{name}.tif"), "raster:bands": [{"scale": 0.0001, "offset": -0.1}]}

    n10, n20 = int(2 * half / 10), int(2 * half / 20)
    off20 = (np.arange(n20) + 0.5) * 20 - half
    dxx, dyy = np.meshgrid(off20, -off20)
    assets = {"green": write("green", 10.0, np.full((n10, n10), 2000, np.uint16)),
              "swir16": write("swir16", 20.0, np.full((n20, n20), 500, np.uint16)),
              "scl": write("scl", 20.0, scl_at(dxx, dyy).astype(np.uint8))}
    return {"id": sid, "properties": {"datetime": f"{date}T05:00:00Z", "eo:cloud_cover": cloud,
                                      "earthsearch:boa_offset_applied": True}, "assets": assets}


def test_snow_and_ice_are_neither_water_nor_a_clear_view(tmp_path):
    """I2: SCL 11 over the west half; water (SCL 6) over the east half. Snow must leave `valid`, so a snow-covered
    zone is not a clear zone with 0% water."""
    lake = _absent_lake()
    f = synthetic_scene(tmp_path, lake, lambda dx, dy: np.where(dx < 0, lakecheck.SCL_SNOW, 6))
    scene = lakecheck._scene(f, lakecheck.Date(2026, 7, 12))
    x, y, epsg = lakecheck.absence_grid(lake)
    opt = lakecheck.optical_on_grid(scene, x, y, epsg)
    cx = Transformer.from_crs(4326, epsg, always_xy=True).transform(lake.lon, lake.lat)[0]
    west, east = x < cx - 50, x > cx + 50
    assert not opt["valid"][:, west].any() and opt["snow"][:, west].all() and not opt["water"][:, west].any()
    assert opt["valid"][:, east].all() and opt["water"][:, east].all() and not opt["snow"][:, east].any()
    assert opt["window_cloud_share"] == 0.0  # snow is not cloud: the window share stays a cloud share
    w = lakecheck.zone_water(lake, opt, x, y, epsg)
    assert w["zone_valid_share"] == pytest.approx(0.5, abs=0.02) and w["snow_share"] == pytest.approx(0.5, abs=0.02)
    assert w["water_share"] == 1.0  # of the clear half
    assert not lakecheck.qualifies(w)


def test_c05_a_snow_covered_lake_zone_is_not_a_measured_zero(tmp_path, monkeypatch):
    """I2 for the cross-check: the zone is under snow, the window is cloud-free. The pair must be a note, not radar
    0 / optical 0 km2."""
    lake = make_lake("frozen")
    cache = tmp_path / "cache"
    for d in ["2026-07-12", "2026-07-24", "2026-08-05"]:
        write_pass(cache, lake, d, "156A")
        write_pass(cache, lake, d, "063D")
    f = synthetic_scene(tmp_path, lake, lambda dx, dy: np.where(dx ** 2 + dy ** 2 < 1300 ** 2, lakecheck.SCL_SNOW, 5))
    monkeypatch.setattr(lakecheck, "search_scenes", lambda *a, **k: [f])
    series = [{"date": "2026-07-12", "track": "156A", "excluded": None, "area_km2": 0.1, "observable_share": 1.0}]
    row = lakecheck.check_lake(lake, cache, series, log=lambda *_: None)
    assert "note" in row and "radar_km2" not in row and "optical_km2" not in row
    assert row["note"].startswith(lakecheck.NO_SCENE)


# --- absence check (I1, I2) ----------------------------------------------------------------------------------------

def _absent_lake():
    from dataclasses import replace
    return replace(make_lake("basin"), lake_state="no_lake", lake_state_source="dry")


def _scenes(*rows):
    return [{"id": sid, "properties": {"datetime": f"{d}T05:00:00Z", "eo:cloud_cover": c},
             "assets": {"green": {}, "swir16": {}, "scl": {}}} for sid, d, c in rows]


def _optical(by_id):
    """A fake optical_on_grid: by scene id, (clear, snow, water) as shares of the lake zone's pixels (water counted
    from the clear ones). Snow and cloud are not valid, as optical_on_grid makes them; outside the zone all is clear."""
    from sartale.lakewater import lake_zone

    def optical(scene, x, y, epsg):
        clear, snow, water = by_id[scene["id"]]
        shape = (len(y), len(x))
        zone = lake_zone(shape, x, y, epsg, _absent_lake())
        rank = np.full(shape, -1.0)
        rank[zone] = np.arange(zone.sum()) / zone.sum()  # 0..1 over the zone pixels, row by row
        valid = ~zone | (rank < clear)
        snowy = zone & (rank >= clear) & (rank < clear + snow)
        wet = zone & (rank < water)
        return {"water": wet & valid, "valid": valid, "snow": snowy, "window_cloud_share": 0.0,
                "invalid_share": float(1 - valid.mean())}
    return optical


def _prior(lake, **extra):
    from sartale.lakebuild import absence_zone
    return {"date": "2026-09-06", "s2_id": "S2_SEP", "water_share": 0.01, "water_km2": 0.03, "zone_valid_share": 1.0,
            "snow_share": 0.0, "forming": False, "pending_scene": None, "confirmed": None, "threshold": 0.04,
            "checked": "2026-09-08", "searched": "2026-09-08", "no_view_since": False,
            "rule": lakecheck.ABSENCE_RULE, "source": lakecheck.ABSENCE_SOURCE, "zone": absence_zone(lake), **extra}


def test_absence_check_runs_in_winter_and_uses_a_clear_snow_free_scene(monkeypatch):
    """I1: the check is not limited to 15 Jun-30 Sep. A clear, snow-free January scene is used."""
    spans = []

    def search(bbox, a, b):
        spans.append((a, b))
        return _scenes(("S2_JAN", "2027-01-15", 5.0), ("S2_SEP", "2026-09-06", 1.0))

    monkeypatch.setattr(lakecheck, "search_scenes", search)
    monkeypatch.setattr(lakecheck, "optical_on_grid", _optical({"S2_JAN": (1.0, 0.0, 0.0)}))
    lake = _absent_lake()
    row = lakecheck.absence_check(lake, "2027-01-20", _prior(lake), log=lambda *_: None)
    assert spans == [("2026-09-06", "2027-01-20")]  # everything since the last evidence, whatever the month
    assert (row["date"], row["s2_id"], row["checked"], row["searched"]) == ("2027-01-15", "S2_JAN", "2027-01-20", "2027-01-20")
    assert row["snow_share"] == 0.0 and row["zone_valid_share"] == 1.0 and row["no_view_since"] is False
    assert row["zone"] == _prior(lake)["zone"] and "season" not in row


def test_absence_check_spring_lake_is_seen(monkeypatch):
    """I1 scenario: Shisper's basin refills in March-May. Two clear April scenes a week apart with water on 7-9% of the
    zone turn the site into Lake may be forming instead of keeping September's dry evidence."""
    from sartale.lakebuild import is_forming
    monkeypatch.setattr(lakecheck, "search_scenes", lambda *a: _scenes(("S2_APR5", "2027-04-05", 10.0),
                                                                        ("S2_MAR29", "2027-03-29", 10.0)))
    monkeypatch.setattr(lakecheck, "optical_on_grid", _optical({"S2_APR5": (1.0, 0.0, 0.09),
                                                                "S2_MAR29": (1.0, 0.0, 0.07)}))
    lake = _absent_lake()
    row = lakecheck.absence_check(lake, "2027-04-08", _prior(lake), log=lambda *_: None)
    assert row["s2_id"] == "S2_APR5" and row["water_share"] == pytest.approx(0.09, abs=0.01)
    assert is_forming(row) and row["pending_scene"] is None
    assert [r["s2_id"] for r in row["confirmed"]] == ["S2_MAR29", "S2_APR5"]


# --- persistence (round 2, ruling a) --------------------------------------------------------------------------------

def _row(date, share, sid=None):
    return {"date": date, "s2_id": sid or f"S2_{date}", "water_share": share}


def test_step_one_scene_above_is_only_pending():
    st = lakecheck.step(lakecheck.start_state(), _row("2026-10-16", 0.145), 0.04)
    assert st["forming"] is False and st["pending_scene"] == _row("2026-10-16", 0.145)


def test_step_a_second_scene_above_five_days_later_confirms():
    st = lakecheck.step(lakecheck.start_state(), _row("2026-10-16", 0.145), 0.04)
    near = lakecheck.step(st, _row("2026-10-19", 0.2), 0.04)  # 3 days: too close to confirm, still pending
    assert near == st
    st = lakecheck.step(near, _row("2026-10-21", 0.06), 0.04)
    assert st["forming"] is True and st["pending_scene"] is None
    assert st["confirmed"] == [_row("2026-10-16", 0.145), _row("2026-10-21", 0.06)]


def test_step_a_scene_below_clears_the_pending_one():
    st = lakecheck.step(lakecheck.start_state(), _row("2026-10-16", 0.145), 0.04)
    st = lakecheck.step(st, _row("2026-10-18", 0.006), 0.04)  # even 2 days later: the newest two do not agree
    assert st == lakecheck.start_state()


def test_step_a_forming_site_returns_only_after_two_scenes_below():
    forming = {"forming": True, "pending_scene": None, "confirmed": [_row("2026-04-01", 0.07), _row("2026-04-08", 0.09)]}
    one = lakecheck.step(forming, _row("2026-04-20", 0.01), 0.04)
    assert one["forming"] is True and one["pending_scene"] == _row("2026-04-20", 0.01)
    wet_again = lakecheck.step(one, _row("2026-04-25", 0.08), 0.04)
    assert wet_again["forming"] is True and wet_again["pending_scene"] is None
    two = lakecheck.step(lakecheck.step(one, _row("2026-04-22", 0.0), 0.04), _row("2026-04-26", 0.0), 0.04)
    assert two["forming"] is False and two["confirmed"] == [_row("2026-04-20", 0.01), _row("2026-04-26", 0.0)]


def test_absence_check_keeps_no_lake_on_a_single_wet_scene_and_records_it(monkeypatch):
    """The Shisper 16 Oct 2026 case: one scene above the threshold. The site stays No lake now, the scene is pending,
    and the next run's qualifying scene clears it."""
    from sartale.lakebuild import is_forming
    monkeypatch.setattr(lakecheck, "search_scenes", lambda *a: _scenes(("S2_WET", "2026-10-16", 25.0)))
    monkeypatch.setattr(lakecheck, "optical_on_grid", _optical({"S2_WET": (0.85, 0.0, 0.14)}))
    lake = _absent_lake()
    row = lakecheck.absence_check(lake, "2026-10-18", _prior(lake), log=lambda *_: None)
    assert row["forming"] is False and not is_forming(row)
    assert row["pending_scene"]["s2_id"] == "S2_WET" and row["pending_scene"]["water_share"] > 0.04
    monkeypatch.setattr(lakecheck, "search_scenes", lambda *a: _scenes(("S2_DRY", "2026-10-21", 10.0)))
    monkeypatch.setattr(lakecheck, "optical_on_grid", _optical({"S2_DRY": (1.0, 0.0, 0.006)}))
    after = lakecheck.absence_check(lake, "2026-10-25", row, log=lambda *_: None)
    assert after["forming"] is False and after["pending_scene"] is None and after["s2_id"] == "S2_DRY"


def test_absence_check_confirms_on_the_next_run(monkeypatch):
    lake = _absent_lake()
    pending = _prior(lake, date="2026-10-16", s2_id="S2_WET", water_share=0.14,
                     pending_scene={"date": "2026-10-16", "s2_id": "S2_WET", "water_share": 0.14})
    monkeypatch.setattr(lakecheck, "search_scenes", lambda *a: _scenes(("S2_WET2", "2026-10-23", 10.0)))
    monkeypatch.setattr(lakecheck, "optical_on_grid", _optical({"S2_WET2": (1.0, 0.0, 0.10)}))
    row = lakecheck.absence_check(lake, "2026-10-25", pending, log=lambda *_: None)
    assert row["forming"] is True and [r["s2_id"] for r in row["confirmed"]] == ["S2_WET", "S2_WET2"]


def test_a_first_check_reads_back_to_a_second_scene_five_days_older(monkeypatch):
    """Without evidence, the newest qualifying scene alone cannot give the state: the search goes on to a qualifying
    scene at least 5 days older, and stops there."""
    seen = []
    scenes = _scenes(("S2_N1", "2026-11-10", 5.0), ("S2_N2", "2026-11-08", 5.0), ("S2_N3", "2026-11-03", 5.0),
                     ("S2_N4", "2026-10-28", 5.0))

    def optical(scene, x, y, epsg):
        seen.append(scene["id"])
        return _optical({"S2_N1": (1.0, 0.0, 0.2), "S2_N2": (1.0, 0.0, 0.2), "S2_N3": (1.0, 0.0, 0.2),
                         "S2_N4": (1.0, 0.0, 0.2)})(scene, x, y, epsg)

    monkeypatch.setattr(lakecheck, "search_scenes", lambda *a: scenes)
    monkeypatch.setattr(lakecheck, "optical_on_grid", optical)
    lake = _absent_lake()
    row = lakecheck.absence_check(lake, "2026-11-12", None, log=lambda *_: None)
    assert seen == ["S2_N1", "S2_N2", "S2_N3"]
    assert row["s2_id"] == "S2_N1" and row["forming"] is True
    assert [r["s2_id"] for r in row["confirmed"]] == ["S2_N3", "S2_N2"]  # 3 and 8 Nov confirm; 10 Nov agrees
    assert row["threshold"] == 0.04 and row["rule"] == lakecheck.ABSENCE_RULE


# --- cloud-edge buffer (round 2, ruling b) --------------------------------------------------------------------------

def test_the_cloud_edge_buffer_removes_a_false_water_patch_next_to_cloud_shadow(tmp_path):
    """A cloud-shadow block (SCL 3) in the zone, bare soil (SCL 5) round it, and MNDWI water everywhere (as haze and
    shadow edges read). Without the buffer the soil next to the shadow counts as clear water; with it, nothing within
    100 m of the shadow is clear, and the rest of the zone is unchanged."""
    lake = _absent_lake()
    f = synthetic_scene(tmp_path, lake, lambda dx, dy: np.where((abs(dx) < 200) & (abs(dy) < 200), 3, 5))
    scene = lakecheck._scene(f, lakecheck.Date(2026, 7, 12))
    x, y, epsg = lakecheck.absence_grid(lake)
    raw = lakecheck.read_scene(scene, x, y, epsg)
    plain = lakecheck.grid_scene(scene, raw, x, y, epsg, buffer_m=0)
    buffered = lakecheck.grid_scene(scene, raw, x, y, epsg)
    cx, cy = Transformer.from_crs(4326, epsg, always_xy=True).transform(lake.lon, lake.lat)
    xx, yy = np.meshgrid(x - cx, y - cy)
    out = np.hypot(np.clip(abs(xx) - 200, 0, None), np.clip(abs(yy) - 200, 0, None))  # metres out of the shadow
    edge = (out > 25) & (out < 75)
    far = out > 140
    assert plain["water"][edge].all() and plain["valid"][edge].all()
    assert not buffered["water"][edge].any() and not buffered["valid"][edge].any()
    assert (buffered["valid"][far] == plain["valid"][far]).all() and buffered["water"][far].all()
    assert buffered["window_cloud_share"] == plain["window_cloud_share"]  # the window share is still SCL cloud only
    assert lakecheck.optical_on_grid(scene, x, y, epsg)["valid"].sum() == buffered["valid"].sum()


def test_near_cloud():
    scl = np.full((30, 30), 5)
    scl[15, 15] = 9
    near = lakecheck.near_cloud(scl, 10.0, 100.0)
    assert near[15, 25] and near[15, 5] and not near[15, 26] and not near[0, 0]
    assert lakecheck.near_cloud(scl, 10.0, 0).sum() == 1
    assert not lakecheck.near_cloud(np.full((5, 5), 11), 10.0, 100.0).any()  # snow is not cloud


# --- paging (round 2, ruling c) --------------------------------------------------------------------------------------

def test_search_follows_the_next_links_until_they_end(monkeypatch):
    calls = []
    page1 = {"features": [feat("a", "2026-11-10T05:00:00Z", 1), feat("b", "2026-11-08T05:00:00Z", 1)],
             "links": [{"rel": "next", "method": "POST", "href": "https://earth-search.aws.element84.com/v1/search",
                        "merge": False, "body": {"collections": ["sentinel-2-l2a"], "limit": 2, "next": "tok1"}}]}
    page2 = {"features": [feat("c", "2026-11-05T05:00:00Z", 1)],
             "links": [{"rel": "next", "method": "POST", "href": "https://earth-search.aws.element84.com/v1/search",
                        "merge": True, "body": {"next": "tok2"}}]}
    page3 = {"features": [], "links": [{"rel": "next", "method": "POST", "href": "x", "body": {"next": "tok3"}}]}
    pages = iter([page1, page2, page3])

    class Resp:
        def __init__(self, doc):
            self.doc = doc

        def raise_for_status(self):
            pass

        def json(self):
            return self.doc

    def post(url, json=None, timeout=None):
        calls.append(json)
        return Resp(next(pages))

    monkeypatch.setattr(lakecheck.requests, "post", post)
    items = lakecheck.search_scenes((74.5, 36.3, 74.6, 36.4), "2026-11-01", "2026-11-12", limit=2)
    assert [f["id"] for f in items] == ["a", "b", "c"]
    assert len(calls) == 3 and "next" not in calls[0]
    assert calls[1] == {"collections": ["sentinel-2-l2a"], "limit": 2, "next": "tok1"}  # merge false: the link's body
    assert calls[2]["next"] == "tok2" and calls[2]["limit"] == 2  # merge true: added to the last body


def test_search_refuses_endless_paging(monkeypatch):
    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"features": [feat("same", "2026-11-10T05:00:00Z", 1)],
                    "links": [{"rel": "next", "method": "POST", "href": "u", "body": {"next": "t"}}]}

    monkeypatch.setattr(lakecheck.requests, "post", lambda *a, **k: Resp())
    with pytest.raises(RuntimeError, match="more than 3 pages"):
        lakecheck.search_scenes((0, 0, 1, 1), "2026-11-01", "2026-11-12", max_pages=3)


def test_a_snow_covered_zone_does_not_count_as_clear(monkeypatch):
    """I2: a scene whose zone is snow-covered (clear of cloud) is not used: nothing qualifies, so the last evidence
    stands, dated by this search, and says that no clear, snow-free view has come since."""
    monkeypatch.setattr(lakecheck, "search_scenes", lambda *a: _scenes(
        ("S2_SNOW", "2026-11-08", 0.0), ("S2_THIN_SNOW", "2026-11-03", 0.0), ("S2_CLOUD", "2026-10-29", 30.0)))
    monkeypatch.setattr(lakecheck, "optical_on_grid", _optical({
        "S2_SNOW": (0.0, 1.0, 0.0),        # all snow: 0% clear
        "S2_THIN_SNOW": (0.9, 0.1, 0.0),   # 90% clear but 10% snow: not snow-free
        "S2_CLOUD": (0.5, 0.0, 0.0)}))     # half cloud
    lake = _absent_lake()
    prior = _prior(lake)
    row = lakecheck.absence_check(lake, "2026-11-12", prior, log=lambda *_: None)
    assert {k: row[k] for k in ("date", "s2_id", "water_share", "checked")} == \
        {"date": "2026-09-06", "s2_id": "S2_SEP", "water_share": 0.01, "checked": "2026-09-08"}
    assert row["searched"] == "2026-11-12" and row["no_view_since"] is True
    from sartale.lakestatus import absence_sentence
    assert absence_sentence(row) == ("Last checked 6 Sep 2026 with Sentinel-2 (S2_SEP): water on 1.0% of the lake "
                                     "zone; no clear, snow-free Sentinel-2 view of the zone since (searched to 12 "
                                     "Nov 2026).")


def test_a_forming_site_is_not_turned_back_to_no_lake_now_by_a_snowy_scene(tmp_path, monkeypatch):
    """I2 scenario: the wet scene made the site Lake may be forming; a newer scene shows the zone frozen and snow-
    covered (0% water). It must not count, so the site stays Lake may be forming."""
    from sartale.lakebuild import FORMING_STATE, apply_absence, build_lakes
    from sartale.lakestatus import LAKE_FORMING
    lake = _absent_lake()
    wet = _prior(lake, date="2026-10-01", s2_id="S2_WET", water_share=0.08, water_km2=0.25, forming=True,
                 confirmed=[_row("2026-09-24", 0.07), _row("2026-10-01", 0.08, "S2_WET")])
    monkeypatch.setattr(lakecheck, "search_scenes", lambda *a: _scenes(("S2_FROZEN", "2026-10-20", 0.0)))
    monkeypatch.setattr(lakecheck, "optical_on_grid", _optical({"S2_FROZEN": (0.15, 0.85, 0.0)}))
    row = lakecheck.absence_check(lake, "2026-10-26", wet, log=lambda *_: None)
    assert row["s2_id"] == "S2_WET" and row["water_share"] == 0.08
    entry = apply_absence(build_lakes([lake], tmp_path / "c", tmp_path / "o", "t")["lakes"][0], row)
    assert entry["lake_state"] == FORMING_STATE and entry["status"]["status"] == LAKE_FORMING
    assert "no clear, snow-free Sentinel-2 view of the zone since" in entry["status"]["reason"]


def test_a_few_snow_pixels_do_not_void_a_clear_view(monkeypatch):
    monkeypatch.setattr(lakecheck, "search_scenes", lambda *a: _scenes(("S2_SPECK", "2026-08-30", 5.0)))
    monkeypatch.setattr(lakecheck, "optical_on_grid", _optical({"S2_SPECK": (0.995, 0.005, 0.0)}))
    lake = _absent_lake()
    row = lakecheck.absence_check(lake, "2026-09-01", _prior(lake, date="2026-08-01"), log=lambda *_: None)
    assert row["s2_id"] == "S2_SPECK" and 0 < row["snow_share"] <= lakecheck.ABSENCE_MAX_SNOW_SHARE


def test_absence_check_without_evidence_searches_back_over_a_winter(monkeypatch):
    spans = []

    def search(bbox, a, b):
        spans.append((a, b))
        return _scenes(("S2_NOV", "2026-11-08", 0.0), ("S2_SEP", "2026-09-29", 19.0), ("S2_AUG", "2026-08-30", 20.0))

    monkeypatch.setattr(lakecheck, "search_scenes", search)
    monkeypatch.setattr(lakecheck, "optical_on_grid", _optical({
        "S2_NOV": (0.0, 1.0, 0.0), "S2_SEP": (0.95, 0.0, 0.04), "S2_AUG": (1.0, 0.0, 0.01)}))
    lake = _absent_lake()
    row = lakecheck.absence_check(lake, "2026-11-12", None, log=lambda *_: None)
    assert spans == [("2025-10-08", "2026-11-12")]  # ABSENCE_FIRST_LOOKBACK_DAYS back
    assert row["s2_id"] == "S2_SEP" and row["checked"] == row["searched"] == "2026-11-12"
    assert row["no_view_since"] is True  # the newest clear, snow-free view is six weeks old: the site says so
    assert lakecheck.absence_check(lake, "2026-11-12", None, log=lambda *_: None, max_scenes=1) is None


def test_absence_check_tries_only_scenes_newer_than_the_evidence(monkeypatch):
    seen = []
    monkeypatch.setattr(lakecheck, "search_scenes", lambda *a: _scenes(("S2_SEP", "2026-09-06", 1.0)))

    def optical(scene, x, y, epsg):
        seen.append(scene["id"])
        return _optical({"S2_SEP": (1.0, 0.0, 0.0)})(scene, x, y, epsg)

    monkeypatch.setattr(lakecheck, "optical_on_grid", optical)
    lake = _absent_lake()
    row = lakecheck.absence_check(lake, "2026-09-10", _prior(lake), log=lambda *_: None)
    assert seen == [] and row["searched"] == "2026-09-10" and row["no_view_since"] is False


def test_no_view_since():
    assert not lakecheck.no_view_since("2026-09-06", "2026-09-13")
    assert lakecheck.no_view_since("2026-09-06", "2026-09-14")


# --- terrain shadow, seasonal forming share and an exclusion zone ---------------------------------------------------

def _zone_of(lake, x, y, epsg):
    from sartale.lakewater import lake_zone
    return lake_zone((len(y), len(x)), x, y, epsg, lake)


def _all_clear(shape, **extra):
    ones = np.ones(shape, bool)
    return {"water": ones.copy(), "valid": ones.copy(), "snow": np.zeros(shape, bool),
            "terrain_shadow": np.zeros(shape, bool), **extra}


def test_terrain_shadow_pixels_are_not_clear_in_the_absence_check():
    lake = _absent_lake()
    x, y, epsg = lakecheck.absence_grid(lake)
    zone = _zone_of(lake, x, y, epsg)
    opt_with_shadow = _all_clear(zone.shape)
    rank = np.cumsum(zone.ravel()).reshape(zone.shape)  # 1..n over the zone pixels
    opt_with_shadow["terrain_shadow"] = zone & (rank <= 0.3 * zone.sum())  # SCL 2 on 30% of the zone; MNDWI calls it water
    w = lakecheck.zone_water(lake, opt_with_shadow, x, y, epsg)
    assert w["zone_valid_share"] == pytest.approx(0.70, abs=0.001)
    shadow_only_water = {**opt_with_shadow, "water": opt_with_shadow["terrain_shadow"]}
    assert lakecheck.zone_water(lake, shadow_only_water, x, y, epsg)["water_share"] == 0.0


def test_the_cross_check_valid_mask_ignores_terrain_shadow(tmp_path):
    lake = _absent_lake()
    f = synthetic_scene(tmp_path, lake,
                        lambda dx, dy: np.where((abs(dx) < 200) & (abs(dy) < 200), lakecheck.SCL_TERRAIN_SHADOW, 5))
    scene = lakecheck._scene(f, lakecheck.Date(2026, 7, 12))
    x, y, epsg = lakecheck.absence_grid(lake)
    raw_with_scl2 = lakecheck.read_scene(scene, x, y, epsg)
    g = lakecheck.grid_scene(scene, raw_with_scl2, x, y, epsg)
    cx, cy = Transformer.from_crs(4326, epsg, always_xy=True).transform(lake.lon, lake.lat)
    xx, yy = np.meshgrid(x - cx, y - cy)
    shadow_block = (abs(xx) < 150) & (abs(yy) < 150)
    assert g["valid"][shadow_block].all() and g["terrain_shadow"][shadow_block].all()
    assert not g["terrain_shadow"][(abs(xx) > 260) | (abs(yy) > 260)].any()


def test_the_exclusion_outline_leaves_the_zone():
    lake = _absent_lake()
    x, y, epsg = lakecheck.absence_grid(lake)
    zone = _zone_of(lake, x, y, epsg)
    xx, _ = np.meshgrid(x, y)
    river_mask = xx < np.median(x[zone.any(axis=0)])  # the west half of the zone
    opt_all_water = _all_clear(zone.shape)
    w = lakecheck.zone_water(lake, opt_all_water, x, y, epsg, exclude=river_mask)
    assert w["water_km2"] == pytest.approx((zone & ~river_mask).sum() * 1e-4)
    assert w["zone_valid_share"] == 1.0


def _khurdopin():
    from sartale.lakes import load_lakes
    return next(l for l in load_lakes(Path(__file__).resolve().parents[1] / "lakes_in.json") if l.id == "khurdopin")


def _khurdopin_with_melt_season():
    from dataclasses import replace
    from sartale.lakes import FormingSeason
    return replace(_khurdopin(), forming_seasons=(FormingSeason("03-15", "06-15", None, "t"),))


def absence_state_after(monkeypatch, rows, lake):
    """The evidence after absence_check(lake, "2026-06-30") over scenes with these (date, water share) rows."""
    shares = {f"S2_{d}": s for d, s in rows}
    monkeypatch.setattr(lakecheck, "search_scenes", lambda *a: _scenes(*[(f"S2_{d}", d, 5.0) for d, _ in rows]))
    monkeypatch.setattr(lakecheck, "optical_on_grid", lambda scene, x, y, epsg: {"id": scene["id"]})
    monkeypatch.setattr(lakecheck, "zone_water", lambda lk, opt, x, y, epsg, exclude=None: {
        "zone_valid_share": 1.0, "snow_share": 0.0, "water_share": shares[opt["id"]], "water_km2": 0.0})
    return lakecheck.absence_check(lake, "2026-06-30", log=lambda *_: None)


def test_a_scene_in_a_not_assessed_season_is_recorded_but_never_moves_the_state(monkeypatch):
    rows = [("2026-04-26", 0.997), ("2026-05-09", 0.186)]
    ev = absence_state_after(monkeypatch, rows, _khurdopin_with_melt_season())
    assert ev["forming"] is False and ev["pending_scene"] is None and ev["threshold"] is None
    assert ev["s2_id"] == "S2_2026-05-09" and ev["water_share"] == 0.186  # recorded: the newest clear view
    # the same scenes outside a season are two scenes above the share
    assert absence_state_after(monkeypatch, rows, _khurdopin())["forming"] is True


def test_scenes_after_a_not_assessed_season_count_again(monkeypatch):
    from sartale.lakebuild import forming_share
    lake = _khurdopin_with_melt_season()
    ev = absence_state_after(monkeypatch, [("2026-06-05", 0.9), ("2026-06-20", 0.5), ("2026-06-27", 0.6)], lake)
    assert ev["threshold"] == forming_share(lake) and ev["forming"] is True  # 20 and 27 Jun are after the season
    assert [r["date"] for r in ev["confirmed"]] == ["2026-06-20", "2026-06-27"]


def test_the_exclusion_outline_of_the_rule_lake_is_applied_to_the_zone(monkeypatch, tmp_path):
    from dataclasses import replace
    lake = _absent_lake()
    ring = [[lake.lon + sx * 0.002, lake.lat + sy * 0.002] for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1))]
    path = tmp_path / "river.geojson"
    path.write_text(json.dumps({"type": "Polygon", "coordinates": [ring]}), encoding="utf-8")
    trial = replace(lake, forming_exclude=str(path), forming_exclude_source="t")
    seen = []
    monkeypatch.setattr(lakecheck, "search_scenes", lambda *a: _scenes(("S2_A", "2026-07-01", 5.0)))
    monkeypatch.setattr(lakecheck, "optical_on_grid", lambda scene, x, y, epsg: {})
    monkeypatch.setattr(lakecheck, "zone_water", lambda lk, opt, x, y, epsg, exclude=None: seen.append(exclude) or {
        "zone_valid_share": 1.0, "snow_share": 0.0, "water_share": 0.0, "water_km2": 0.0})
    ev = lakecheck.absence_check(lake, "2026-07-02", log=lambda *_: None, rule_lake=trial)
    assert seen[0] is not None and seen[0].any() and ev["forming_rule"]["exclude"] is not None


def prev_with_rule(rule, lake):
    from sartale.lakebuild import absence_zone
    ev = {"date": "2026-08-17", "s2_id": "S2_DRY", "water_share": 0.0, "water_km2": 0.0, "zone_valid_share": 1.0,
          "snow_share": 0.0, "forming": False, "pending_scene": None, "confirmed": None, "threshold": 0.04,
          "forming_rule": rule, "checked": "2026-08-20", "searched": "2026-08-20", "no_view_since": False,
          "rule": lakecheck.ABSENCE_RULE, "source": "S2", "zone": absence_zone(lake)}
    return {"lakes": [{"id": lake.id, "absence_checked": ev}]}


def test_evidence_from_another_forming_rule_is_not_carried():
    from sartale.lakebuild import carried_absence, forming_rule
    lake = _khurdopin_with_melt_season()
    assert carried_absence(prev_with_rule({"share": 0.16, "seasons": [], "exclude": None}, lake), lake) is None
    assert carried_absence(prev_with_rule(forming_rule(lake), lake), lake) is not None


def test_forming_threshold_follows_the_season_and_wraps_the_year_end():
    from dataclasses import replace
    from sartale.lakebuild import forming_share, forming_threshold
    from sartale.lakes import FormingSeason
    lake = replace(_absent_lake(), forming_seasons=(FormingSeason("03-15", "06-15", None, "t"),
                                                    FormingSeason("12-01", "02-10", 0.3, "t")))
    base = forming_share(lake)
    assert [forming_threshold(lake, d) for d in ("2026-03-14", "2026-03-15", "2026-06-15", "2026-06-16")] \
        == [base, None, None, base]
    assert [forming_threshold(lake, d) for d in ("2026-11-30", "2026-12-01", "2027-01-20", "2027-02-10", "2027-02-11")] \
        == [base, 0.3, 0.3, 0.3, base]
