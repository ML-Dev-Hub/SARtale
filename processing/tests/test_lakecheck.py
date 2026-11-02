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
