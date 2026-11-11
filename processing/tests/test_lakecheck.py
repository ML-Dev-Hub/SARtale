import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import numpy as np
import pytest

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
    rows = [{"lake": "alpha", "note": lakecheck.NO_SCENE}]
    doc = build_lakes([make_lake("alpha")], tmp_path / "c", tmp_path / "o", "t", rows)
    assert doc["checks"] == rows
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


# --- absence check -------------------------------------------------------------------------------------------------

def _absent_lake():
    from dataclasses import replace
    return replace(make_lake("basin"), lake_state="no_lake", lake_state_source="dry")


def _scenes(*rows):
    return [{"id": sid, "properties": {"datetime": f"{d}T05:00:00Z", "eo:cloud_cover": c},
             "assets": {"green": {}, "swir16": {}, "scl": {}}} for sid, d, c in rows]


def test_absence_check_outside_the_season_keeps_the_last_evidence(monkeypatch):
    monkeypatch.setattr(lakecheck, "search_scenes", lambda *a, **k: pytest.fail("outside the season: no search"))
    prior = {"date": "2026-08-17", "s2_id": "S2_OLD", "water_share": 0.0}
    assert lakecheck.absence_check(_absent_lake(), "2026-11-11", prior, log=lambda *_: None) is prior


def test_absence_check_without_evidence_bootstraps_from_the_last_season(monkeypatch):
    spans = []

    def search(bbox, a, b):
        spans.append((a, b))
        return _scenes(("S2_A", "2026-09-20", 5.0), ("S2_B", "2026-08-17", 1.0))

    def optical(scene, x, y, epsg):
        shape = (len(y), len(x))
        return {"water": np.zeros(shape, bool), "valid": np.ones(shape, bool), "window_cloud_share": 0.0,
                "invalid_share": 0.0}

    monkeypatch.setattr(lakecheck, "search_scenes", search)
    monkeypatch.setattr(lakecheck, "optical_on_grid", optical)
    row = lakecheck.absence_check(_absent_lake(), "2026-11-11", None, log=lambda *_: None)
    assert spans == [("2026-06-15", "2026-09-30")]
    assert (row["date"], row["s2_id"], row["water_share"], row["checked"]) == ("2026-09-20", "S2_A", 0.0, "2026-11-11")
    assert row["zone_valid_share"] == 1.0 and row["season"] == "15 Jun–30 Sep"


def test_absence_check_in_season_takes_the_newest_scene_whose_zone_is_clear(monkeypatch):
    monkeypatch.setattr(lakecheck, "search_scenes", lambda bbox, a, b: _scenes(
        ("S2_NEW_CLOUDY", "2026-08-20", 10.0), ("S2_CLEAR", "2026-08-10", 10.0)))

    def optical(scene, x, y, epsg):
        shape = (len(y), len(x))
        valid = np.ones(shape, bool) if scene["id"] == "S2_CLEAR" else np.zeros(shape, bool)
        water = np.zeros(shape, bool)
        water[: shape[0] // 2] = True  # half the grid is water
        return {"water": water & valid, "valid": valid, "window_cloud_share": 0.0, "invalid_share": 0.0}

    monkeypatch.setattr(lakecheck, "optical_on_grid", optical)
    prior = {"date": "2026-07-01", "s2_id": "S2_OLD", "water_share": 0.0}
    row = lakecheck.absence_check(_absent_lake(), "2026-08-25", prior, log=lambda *_: None)
    assert row["s2_id"] == "S2_CLEAR" and 0.3 < row["water_share"] < 0.7


def test_absence_check_with_no_clear_scene_keeps_the_prior(monkeypatch):
    monkeypatch.setattr(lakecheck, "search_scenes", lambda *a: _scenes(("S2_C", "2026-08-20", 10.0)))
    monkeypatch.setattr(lakecheck, "optical_on_grid", lambda scene, x, y, epsg: {
        "water": np.zeros((len(y), len(x)), bool), "valid": np.zeros((len(y), len(x)), bool),
        "window_cloud_share": 1.0, "invalid_share": 1.0})
    prior = {"date": "2026-07-01", "s2_id": "S2_OLD", "water_share": 0.0}
    assert lakecheck.absence_check(_absent_lake(), "2026-08-25", prior, log=lambda *_: None) is prior


def test_season_bounds():
    assert lakecheck.season_bounds("2026-11-11") is None
    assert lakecheck.season_bounds("2026-07-02") == ("2026-06-15", "2026-07-02")
    assert lakecheck.last_season_bounds("2026-03-01") == ("2025-06-15", "2025-09-30")
    assert lakecheck.last_season_bounds("2026-07-02") == ("2026-06-15", "2026-07-02")
