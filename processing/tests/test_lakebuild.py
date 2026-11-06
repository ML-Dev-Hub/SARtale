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


def write_pass(cache, lake, date, key, bright_db=0.0, dx=0, dy=0):
    """A window with a dark disc (water) at the lake point; dx/dy shift the window in pixels."""
    cx, cy = Transformer.from_crs(4326, EPSG, always_xy=True).transform(lake.lon, lake.lat)
    x = cx - (N // 2) * PX + (np.arange(N) + dx) * PX
    y = cy + (N // 2) * PX - (np.arange(N) + dy) * PX
    xx, yy = np.meshgrid(x, y)
    water = (xx - cx) ** 2 + (yy - cy) ** 2 < 500.0 ** 2
    rng = np.random.default_rng(abs(hash((date, key))) % 10000)
    hh = np.where(water, 0.002, 0.1) * rng.uniform(0.95, 1.05, (N, N)) * 10 ** (bright_db / 10)
    hv = hh / 5
    d = Path(cache) / lake.id
    d.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(d / f"{date}_{key}_{config.CRID}.npz", hh=hh, hv=hv, looks=np.ones((N, N)),
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
    assert doc["version"] == 1 and doc["crid"] == config.CRID
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
    assert "north up; they are pictures, not map overlays" in doc["notes"] and "1 km search circle" in doc["notes"]


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
