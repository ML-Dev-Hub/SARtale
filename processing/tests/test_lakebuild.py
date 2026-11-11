import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import numpy as np
import pytest
from pyproj import Transformer

from sartale import config
from sartale.lakebuild import POINT_LABEL, build_lakes
from sartale.lakes import Lake

EPSG = 32643
PX = 50.0
N = 80


def make_lake(lid, lon=74.86, lat=36.33, role="watch"):
    return Lake(id=lid, name=lid.title(), lon=lon, lat=lat, coord_source="test", outline=None,
                role=role, downstream=None, downstream_source=None)


def write_pass(cache, lake, date, key, bright_db=0.0, dx=0, dy=0, crid="P05023", water_m=500.0):
    """A window with a dark disc (water, radius `water_m`) at the lake point; dx/dy shift the window in pixels."""
    cx, cy = Transformer.from_crs(4326, EPSG, always_xy=True).transform(lake.lon, lake.lat)
    x = cx - (N // 2) * PX + (np.arange(N) + dx) * PX
    y = cy + (N // 2) * PX - (np.arange(N) + dy) * PX
    xx, yy = np.meshgrid(x, y)
    water = (xx - cx) ** 2 + (yy - cy) ** 2 < water_m ** 2
    rng = np.random.default_rng(abs(hash((date, key))) % 10000)
    hh = np.where(water, 0.002, 0.1) * rng.uniform(0.95, 1.05, (N, N)) * 10 ** (bright_db / 10)
    hv = hh / 5
    d = Path(cache) / lake.id
    d.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(d / f"{date}_{key}_{crid}.npz", hh=hh, hv=hv, looks=np.ones((N, N)),
                        mask=np.ones((N, N), np.uint8), x=x, y=y, epsg=EPSG)


@pytest.fixture
def built(tmp_path):
    cache, out = tmp_path / "cache", tmp_path / "out"
    a, b = make_lake("alpha"), make_lake("beta", 74.9, 36.4, "control")
    for i, d in enumerate(["2026-06-18", "2026-06-30", "2026-07-12", "2026-07-24", "2026-08-05"]):
        write_pass(cache, a, d, "156A")
        write_pass(cache, a, d, "063D")
        write_pass(cache, b, d, "055A", bright_db=25.0 if i == 2 else 0.0)
    doc = build_lakes([a, b, make_lake("gamma")], cache, out, "2026-11-02T00:00:00Z")
    return doc, out


def lake(doc, lid):
    return next(x for x in doc["lakes"] if x["id"] == lid)


def test_build_writes_schema_keys(built):
    doc, _ = built
    assert doc["version"] == 1 and doc["crid"] == "P05023"
    assert all(p["crid"] == "P05023" for lk in doc["lakes"] for p in lk["series"])
    assert doc["cloud_window"] == list(config.CLOUD_WINDOW)
    assert doc["constants"]["drop_db"] == config.DROP_DB
    keys = {"id", "name", "lon", "lat", "role", "coord_source", "outline_source", "area_label", "downstream",
            "downstream_source", "status", "cloud_window_looks", "directions", "limits", "series", "excluded",
            "images", "bounds"}
    for lk in doc["lakes"]:
        assert keys <= set(lk)
    alpha = lake(doc, "alpha")
    assert alpha["directions"] == ["A", "D"]
    assert alpha["status"]["status"] == "Stable"
    assert alpha["status"]["looks"] == 5
    assert 0.7 < alpha["series"][0]["area_km2"] < 0.9
    assert alpha["cloud_window_looks"] == 8  # 4 dates in the window, 2 tracks
    lo, la, hi, ha = alpha["bounds"]
    assert lo < alpha["lon"] < hi and la < alpha["lat"] < ha


def test_build_has_notes_field(built):
    doc, _ = built
    assert "north up; they are pictures, not map overlays" in doc["notes"] and "search circle (1 km unless" in doc["notes"]


def test_build_json_has_no_nan(built):
    doc, _ = built
    json.dumps(doc, allow_nan=False)


def test_build_labels_point_only_lake_area(built):
    doc, _ = built
    assert all(lk["area_label"] == POINT_LABEL for lk in doc["lakes"])
    assert all(lk["outline_source"] is None for lk in doc["lakes"])


def test_build_lists_excluded_passes_with_reason(built):
    doc, _ = built
    beta = lake(doc, "beta")
    assert [e["pass"] for e in beta["excluded"]] == ["2026-07-12_055A"]
    assert "dB" in beta["excluded"][0]["reason"]
    assert any(p["excluded"] and p["area_km2"] is None for p in beta["series"])
    assert "single viewing direction" in beta["limits"]


def test_build_images_exist_and_are_small(built):
    doc, out = built
    for lid in ("alpha", "beta"):
        imgs = lake(doc, lid)["images"]
        for rel in (imgs["latest_hh"], imgs["water"]):
            f = out / rel
            assert f.exists() and f.stat().st_size < 300_000


def test_build_lake_without_cache(built):
    doc, out = built
    g = lake(doc, "gamma")
    assert g["status"]["status"] == "Not enough NISAR looks yet"
    assert g["series"] == [] and g["bounds"] is None
    assert g["images"] == {"latest_hh": None, "water": None, "date": None, "track": None}
    assert "no NISAR windows fetched yet" in g["limits"]
    assert not (out / "lakes" / "gamma").exists()


def test_build_crops_offset_windows(tmp_path):
    cache, out = tmp_path / "c", tmp_path / "o"
    a = make_lake("alpha")
    for d in ["2026-06-18", "2026-06-30", "2026-07-12"]:
        write_pass(cache, a, d, "156A")
        write_pass(cache, a, d, "063D", dx=4, dy=-3)
    lk = build_lakes([a], cache, out, "t")["lakes"][0]
    assert len(lk["series"]) == 6
    assert lk["status"]["looks"] == 3
    assert all(0.6 < p["area_km2"] < 0.9 for p in lk["series"])
    assert lk["limits"] == []


def test_build_drops_track_with_no_overlap(tmp_path):
    cache, out = tmp_path / "c", tmp_path / "o"
    a = make_lake("alpha")
    for d in ["2026-06-18", "2026-06-30", "2026-07-12"]:
        write_pass(cache, a, d, "156A")
        write_pass(cache, a, d, "063D", dx=N + 5)
    lk = build_lakes([a], cache, out, "t")["lakes"][0]
    assert {p["track"] for p in lk["series"]} == {"156A"}
    assert any("063D" in s and "unusable" in s for s in lk["limits"])
    assert "single viewing direction" in lk["limits"]


def _outline_around(lake, half_m, shift_m=0.0):
    """A square outline (GeoJSON Feature) of half-width `half_m` around the lake, shifted east by `shift_m`."""
    to_ll = Transformer.from_crs(EPSG, 4326, always_xy=True)
    cx, cy = Transformer.from_crs(4326, EPSG, always_xy=True).transform(lake.lon, lake.lat)
    cx += shift_m
    ring = [to_ll.transform(cx + sx * half_m, cy + sy * half_m) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1))]
    return {"type": "Feature", "properties": {"source": "Test outline, 4 Nov 2026"},
            "geometry": {"type": "Polygon", "coordinates": [[list(p) for p in ring]]}}


def _build_with_outline(tmp_path, feature, rel=False):
    from dataclasses import replace
    cache, out = tmp_path / "cache", tmp_path / "out"
    base = make_lake("alpha")
    for d in ["2026-06-18", "2026-06-30", "2026-07-12", "2026-07-24"]:
        write_pass(cache, base, d, "156A")
    poly = tmp_path / "alpha.geojson"
    poly.write_text(json.dumps(feature(base)), encoding="utf-8")
    doc = build_lakes([replace(base, outline=str(poly))], cache, out, "2026-11-04T00:00:00Z")
    return lake(doc, "alpha")


def test_an_outline_lake_reports_its_source_and_counts_the_outline(tmp_path):
    lk = _build_with_outline(tmp_path, lambda b: _outline_around(b, 600))
    assert lk["outline_source"] == "Test outline, 4 Nov 2026"
    assert lk["area_label"].startswith("water area in the lake outline")
    assert not any("radar window" in m for m in lk["limits"])


def test_an_outline_past_the_window_edge_says_how_much_is_counted(tmp_path):
    # The window is 80 x 50 m = 4 km wide; a 3 km square shifted 2 km east is about half outside it.
    lk = _build_with_outline(tmp_path, lambda b: _outline_around(b, 1500, shift_m=2000))
    note = next(m for m in lk["limits"] if "radar window" in m)
    pct = int(note.split("%")[0].split()[-1])
    assert 35 <= pct <= 65
    assert "only that part is counted" in note


def test_a_relative_outline_path_is_read_from_the_processing_folder():
    from sartale.lakebuild import _load_outline
    from dataclasses import replace
    lk = replace(make_lake("attabad"), outline="outlines/attabad_osm.geojson")
    poly = _load_outline(lk)
    assert poly is not None and poly["type"] == "Polygon"


COLLECTIONS = {"P05023": "NISAR_L2_GCOV_PROVISIONAL_V1", "P05036": "NISAR_L2_GCOV_V1"}


def test_a_status_track_that_mixes_crids_is_built_with_a_limit(tmp_path):
    cache, out = tmp_path / "c", tmp_path / "o"
    a = make_lake("alpha")
    for d in ["2026-09-17", "2026-09-29", "2026-10-11"]:
        write_pass(cache, a, d, "156A", crid="P05023")
    for d in ["2026-10-23", "2026-11-04"]:
        write_pass(cache, a, d, "156A", crid="P05036")
    doc = build_lakes([a], cache, out, "t", collections=COLLECTIONS)
    lk = doc["lakes"][0]
    assert [(p["date"], p["crid"]) for p in lk["series"]][-2:] == [("2026-10-23", "P05036"), ("2026-11-04", "P05036")]
    assert lk["status"]["track"] == "156A" and lk["status"]["latest_date"] == "2026-11-04"
    assert ("Track 156A mixes NISAR processing versions P05023 (provisional) and P05036 (standard); a calibration "
            "change between them can shift areas.") in lk["limits"]
    assert doc["crid"] == "P05023, P05036"
    assert doc["collections"] == ["NISAR_L2_GCOV_PROVISIONAL_V1", "NISAR_L2_GCOV_V1"]


def test_one_crid_on_the_status_track_has_no_mixing_limit(built):
    doc, _ = built
    assert not any("mixes NISAR processing versions" in m for lk in doc["lakes"] for m in lk["limits"])


def test_a_pass_cached_under_two_crids_is_counted_once_from_the_later(tmp_path):
    cache, out = tmp_path / "c", tmp_path / "o"
    a = make_lake("alpha")
    for d in ["2026-09-29", "2026-10-11", "2026-10-23"]:
        write_pass(cache, a, d, "156A", crid="P05023")
    write_pass(cache, a, "2026-10-23", "156A", crid="P05036")
    (cache / "alpha" / "notes.npz").write_bytes(b"")  # a name that does not parse is skipped
    lk = build_lakes([a], cache, out, "t", collections={})["lakes"][0]
    assert [(p["date"], p["crid"]) for p in lk["series"]] == [
        ("2026-09-29", "P05023"), ("2026-10-11", "P05023"), ("2026-10-23", "P05036")]
    assert "ignored 2026-10-23_156A_P05023.npz: the same pass is cached as P05036" in lk["limits"]
    assert "Track 156A mixes NISAR processing versions P05023 and P05036; a calibration change between them can " \
           "shift areas." in lk["limits"]


def test_collections_come_from_the_search_manifest(tmp_path):
    from sartale.lakebuild import read_collections
    p = tmp_path / "passes.json"
    p.write_text(json.dumps({"lakes": {"alpha": {"156A": [
        {"crid": "P05023", "collection": "NISAR_L2_GCOV_PROVISIONAL_V1"},
        {"crid": "P05036", "collection": "NISAR_L2_GCOV_V1"}, {"crid": "P09999"}]}}}), encoding="utf-8")
    assert read_collections(p) == COLLECTIONS
    assert read_collections(tmp_path / "missing.json") == {}


def _manifest(cache, rows_by_lake):
    """A passes.json as lakes-search writes it: rows_by_lake maps lake id -> [(date, key, crid)]."""
    lakes = {}
    for lid, rows in rows_by_lake.items():
        by_key = lakes.setdefault(lid, {})
        for date, key, crid in rows:
            by_key.setdefault(key, []).append({"granule": "g", "url": "u", "date": date, "start": date,
                                               "track": key[:-1], "direction": key[-1], "frame": "020",
                                               "mode": "4005", "crid": crid, "collection": COLLECTIONS.get(crid, "")})
    (Path(cache) / "passes.json").write_text(json.dumps({"lakes": lakes}), encoding="utf-8")


def test_only_passes_the_catalogue_lists_are_built_and_unlisted_windows_stay_on_disk(tmp_path):
    from sartale.lakebuild import read_listed, unlisted_windows
    cache, out = tmp_path / "c", tmp_path / "o"
    a = make_lake("alpha")
    dates = ["2026-09-17", "2026-09-29", "2026-10-11", "2026-10-23"]
    for d in dates:
        write_pass(cache, a, d, "156A")
    listed_rows = [(d, "156A", "P05023") for d in dates[:3]]  # NASA withdrew the 23 Oct granule
    _manifest(cache, {"alpha": listed_rows})
    lk = build_lakes([a], cache, out, "t")["lakes"][0]
    assert [p["date"] for p in lk["series"]] == dates[:3]
    assert lk["status"]["latest_date"] == "2026-10-11"
    assert (cache / "alpha" / "2026-10-23_156A_P05023.npz").exists()  # ignored, not deleted
    listed = read_listed(cache / "passes.json")
    assert unlisted_windows(cache / "alpha", listed["alpha"]) == ["2026-10-23_156A_P05023.npz"]

    # a fresh cache holding only the listed windows builds the same lake
    fresh = tmp_path / "fresh"
    for d in dates[:3]:
        write_pass(fresh, a, d, "156A")
    _manifest(fresh, {"alpha": listed_rows})
    lk2 = build_lakes([a], fresh, tmp_path / "o2", "t")["lakes"][0]
    assert lk2["series"] == lk["series"] and lk2["status"] == lk["status"]


def test_a_lake_the_manifest_lists_without_passes_builds_empty(tmp_path):
    cache, out = tmp_path / "c", tmp_path / "o"
    a = make_lake("alpha")
    for d in ["2026-09-17", "2026-09-29", "2026-10-11"]:
        write_pass(cache, a, d, "156A")
    _manifest(cache, {})
    lk = build_lakes([a], cache, out, "t")["lakes"][0]
    assert lk["series"] == [] and "no usable NISAR window" in lk["limits"]


def test_radar_water_masks_ignores_a_pass_the_catalogue_no_longer_lists(tmp_path):
    from sartale.lakebuild import radar_water_masks
    cache = tmp_path / "c"
    a = make_lake("alpha")
    dates = ["2026-09-17", "2026-09-29", "2026-10-11", "2026-10-23"]
    for d in dates:
        write_pass(cache, a, d, "156A")
    _manifest(cache, {"alpha": [(d, "156A", "P05023") for d in dates[:3]]})
    assert radar_water_masks(a, cache, "2026-10-11_156A")["zone_mask"].any()
    with pytest.raises(KeyError):
        radar_water_masks(a, cache, "2026-10-23_156A")


def test_a_first_pass_on_a_new_processing_version_does_not_confirm_a_change(tmp_path):
    cache, out = tmp_path / "c", tmp_path / "o"
    a = make_lake("alpha")
    old = ["2026-09-05", "2026-09-17", "2026-09-29", "2026-10-11"]
    for d in old:
        write_pass(cache, a, d, "156A", crid="P05023")
    write_pass(cache, a, "2026-10-23", "156A", crid="P05036", water_m=560.0)
    lk = build_lakes([a], cache, out, "t", collections=COLLECTIONS)["lakes"][0]
    st = lk["status"]
    assert st["status"] == "Change not confirmed yet" and st["change_km2"] > 0 and st["new_crid"] == "P05036"
    assert "first pass on NISAR processing version P05036" in st["reason"]


def test_a_no_lake_site_keeps_its_passes_but_gets_no_verdict_and_no_water_layer(tmp_path):
    from dataclasses import replace

    from sartale.lakebuild import NO_LAKE_LABEL
    from sartale.lakestatus import NO_LAKE, STATUS_NAMES

    cache, out = tmp_path / "cache", tmp_path / "out"
    base = make_lake("basin")
    days = ["2026-06-18", "2026-06-30", "2026-07-12", "2026-07-24"]
    for d in days:
        write_pass(cache, base, d, "156A")
    src = "Sentinel-2 shows a dry basin on 17 Aug 2026"
    gone = replace(base, lake_state="no_lake", lake_state_source=src)
    lk = build_lakes([gone], cache, out, "2026-11-10T00:00:00Z")["lakes"][0]
    st = lk["status"]
    assert NO_LAKE in STATUS_NAMES and st["status"] == NO_LAKE
    assert (st["change_km2"], st["noise_km2"]) == (None, None)
    assert (st["track"], st["latest_date"], st["looks"]) == ("156A", "2026-07-24", 4)
    assert st["reason"] == ("No lake in recent imagery: Sentinel-2 shows a dry basin on 17 Aug 2026. "
                            "SARtale keeps the site to watch for a lake forming.")
    assert lk["lake_state"] == "no_lake" and lk["lake_state_source"] == src
    assert lk["area_label"] == NO_LAKE_LABEL
    assert len(lk["series"]) == 4 and lk["cloud_window_looks"] == 4  # passes are still read and counted
    assert lk["images"]["latest_hh"] and lk["images"]["water"] is None
    assert not (out / "lakes" / "basin" / "water.webp").exists()
    # with no fetched window the site still says it has no lake
    empty = build_lakes([replace(gone, id="other")], cache, out, "2026-11-10T00:00:00Z")["lakes"][0]
    assert empty["status"]["status"] == NO_LAKE and empty["status"]["looks"] == 0


def test_an_unconfirmed_lake_keeps_its_status_and_carries_a_limit(tmp_path):
    from dataclasses import replace

    cache, out = tmp_path / "cache", tmp_path / "out"
    base = make_lake("strip")
    for d in ["2026-06-18", "2026-06-30", "2026-07-12"]:
        write_pass(cache, base, d, "156A")
    lk = build_lakes([replace(base, lake_state="unconfirmed", lake_state_source="narrow ice and water strip.")],
                     cache, out, "2026-11-10T00:00:00Z")["lakes"][0]
    assert lk["status"]["status"] == "Stable" and lk["lake_state"] == "unconfirmed"
    assert lk["limits"][0] == "Lake not confirmed in recent imagery: narrow ice and water strip."
    assert lk["images"]["water"]


def test_a_smaller_zone_radius_measures_a_smaller_circle(tmp_path):
    from dataclasses import replace

    cache, out = tmp_path / "cache", tmp_path / "out"
    wide, small = make_lake("pond"), replace(make_lake("pond300"), zone_radius_km=0.3)
    for lk in (wide, small):
        for d in ["2026-06-18", "2026-06-30", "2026-07-12"]:
            write_pass(cache, lk, d, "156A", water_m=900.0)
    a, b = build_lakes([wide, small], cache, out, "2026-11-10T00:00:00Z")["lakes"]
    assert a["area_label"] == POINT_LABEL and b["area_label"] == f"{POINT_LABEL} (300 m circle)"
    # the 900 m water disc fills the whole 300 m circle: about pi * 0.3^2 km2
    assert b["series"][0]["area_km2"] == pytest.approx(3.14159 * 0.09, rel=0.1)
    assert 2.0 < a["series"][0]["area_km2"] < 2.8  # the 900 m disc inside the 1 km circle
