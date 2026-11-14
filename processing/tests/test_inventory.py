import csv
import json
import re
from pathlib import Path

import pytest

from conftest import APP_DATA, PROCESSING, load_json
from sartale.districts import DISTRICT_SOURCE, district_of
from sartale.inventory import InventoryEntry, SuparcoMatch, load_inventory
from sartale.lakes import load_lakes

LAKES_IN = PROCESSING / "lakes_in.json"
OUTLINES = PROCESSING / "outlines"


def register_and_new():
    return load_json("processing/lakes_in.json") + load_json("inventory/new_lakes.json")


def test_the_committed_inventory_matches_its_tables():
    inv = load_inventory()
    assert len(load_json("inventory/new_lakes.json")) == 43
    assert {r["batch"] for r in load_json("inventory/new_lakes.json")} == {1, 2, 3, 4}
    k = inv["karambar_lake"].suparco
    assert (k.id, k.match) == (116, "probable") and k.source.strip()
    assert inv["godar_dhand"].suparco is None and {c.id for c in inv["godar_dhand"].suparco_candidates} == {7, 22}
    assert inv["passu"].suparco is None  # the "4" dot was rejected


def test_the_inventory_covers_the_new_lakes_and_three_sites_only():
    inv = load_inventory()
    new_ids = {r["id"] for r in load_json("inventory/new_lakes.json")}
    assert set(inv) == new_ids | {"passu", "shazore", "khurdopin"}
    assert all(isinstance(e, InventoryEntry) and e.lake_id == i and e.outlines for i, e in inv.items())
    assert all(o.km2 > 0 and o.licence in ("CC BY 4.0", "ODbL 1.0") and o.source.strip()
               for e in inv.values() for o in e.outlines)
    # a possible match, or several IDs read at one dot, is never the lake's SUPARCO ID
    assert all(e.suparco is None or e.suparco.match in ("probable", "official") for e in inv.values())
    assert inv["katora"].suparco is None and [c.id for c in inv["katora"].suparco_candidates] == [48]


def test_load_inventory_refuses_a_possible_match_as_the_suparco_id(tmp_path):
    doc = {"version": 1, "lakes": {"x": {"cand_id": "C999", "outlines": [
        {"source": "s", "year": 2020, "km2": 0.1, "licence": "CC BY 4.0"}],
        "suparco": {"id": 7, "match": "possible", "source": "s"}, "suparco_candidates": []}}}
    p = tmp_path / "inv.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="probable or official"):
        load_inventory(p)
    doc["lakes"]["x"]["suparco"] = None
    doc["lakes"]["x"]["suparco_candidates"] = [{"id": 7, "match": "possible", "source": "s"}]
    p.write_text(json.dumps(doc), encoding="utf-8")
    assert load_inventory(p)["x"].suparco_candidates == (SuparcoMatch(7, "possible", "s"),)


def test_no_name_or_id_carries_a_suparco_number():
    assert not [r for r in register_and_new() if "pdgl" in r["id"] or "PDGL" in r["name"]]


def test_unnamed_lakes_are_named_by_candidate():
    for r in load_json("inventory/new_lakes.json"):
        m = re.fullmatch(r"lake_c(\d{3})", r["id"])
        if m:
            assert r["name"] == f"Unnamed lake C{m.group(1)}"
    borith = next(r for r in load_json("inventory/new_lakes.json") if r["id"] == "borith")
    assert "GLOF lake" not in borith["coord_source"] and "glacial lake outburst" not in borith["coord_source"]


def test_each_new_outline_is_a_feature_with_source_and_licence():
    rows = load_json("inventory/new_lakes.json")
    for r in rows:
        f = json.loads((PROCESSING / r["outline"]).read_text(encoding="utf-8"))
        assert f["type"] == "Feature" and f["geometry"]["type"] in ("Polygon", "MultiPolygon")
        assert f["properties"]["source"].strip() and f["properties"]["licence"] in ("CC BY 4.0", "ODbL 1.0")
    assert len({r["outline"] for r in rows}) == 43


def test_district_of_maps_points_to_one_province():
    d, p = district_of(74.8810, 36.4580)                          # Passu
    assert p == "GB" and d.strip()
    assert district_of(72.1741, 35.7794)[1] == "KP"               # Shazore
    with pytest.raises(ValueError): district_of(73.5, 34.0)       # outside GB and KP
    assert "geoBoundaries" in DISTRICT_SOURCE


def test_district_of_places_lakes_just_outside_the_coarse_district_edges():
    # Karambar Lake sits on the Ghizer-Chitral divide, about 2 km outside the coarse ADM2 polygons but in Pakistan
    assert district_of(73.70413, 36.87936)[1] in ("GB", "KP")
    with pytest.raises(ValueError): district_of(77.5, 34.5)       # Ladakh, outside Pakistan
    with pytest.raises(ValueError): district_of(71.0, 37.5)       # Badakhshan, outside Pakistan


def test_mapped_lakes_file_is_small_attributed_and_excludes_watched_lakes():
    doc = load_json(APP_DATA / "mapped_lakes.json")
    assert (APP_DATA / "mapped_lakes.json").stat().st_size < 300_000
    assert "ODbL" in doc["notice"]["odbl"] and "CC BY 4.0" in doc["notice"]["cc_by"]
    assert 480 <= len(doc["lakes"]) <= 520
    assert not any("geometry" in l or "outline" in l for l in doc["lakes"])
    assert all(l["suparco"] is None or l["suparco"]["match"] == "probable" for l in doc["lakes"])


def test_mapped_lakes_rows_have_the_documented_shape():
    doc = load_json(APP_DATA / "mapped_lakes.json")
    assert doc["version"] == 1 and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", doc["built"])
    assert {s["id"] for s in doc["sources"]} == {"hkhpk2020", "himag", "osm"}
    assert all(s["licence"] and s["attribution"] and s["url"].startswith("https://") for s in doc["sources"])
    ids = [l["id"] for l in doc["lakes"]]
    assert len(set(ids)) == len(ids) and all(re.fullmatch(r"m\d{4}", i) for i in ids)
    for l in doc["lakes"]:
        assert set(l) == {"id", "lon", "lat", "km2", "year", "source", "suparco"}
        assert l["source"] in ("hkhpk2020", "himag", "osm") and l["km2"] > 0
        assert (l["year"] is None) == (l["source"] == "osm")
    # no mapped lake sits on a watched lake
    watched = [(r["lon"], r["lat"]) for r in register_and_new()]
    assert not [l for l in doc["lakes"] for lon, lat in watched if abs(l["lon"] - lon) < 1e-4 and abs(l["lat"] - lat) < 1e-4]


def test_sources_pin_a_url_and_sha256_for_every_download():
    for s in load_json("inventory/sources.json"):
        assert s["url"].startswith("https://") and re.fullmatch(r"[0-9a-f]{64}", s["sha256"]) and s["licence"].strip()
    osm = next(s for s in load_json("inventory/sources.json") if s["id"] == "osm")
    assert "snapshot" in osm["note"] and osm["query"].strip() and osm["fetched"]


ODBL = ("This file is published under the Open Database Licence (ODbL) 1.0 "
        "(https://opendatacommons.org/licenses/odbl/1-0/): it contains data from OpenStreetMap, "
        "© OpenStreetMap contributors (https://www.openstreetmap.org/copyright).")
CC_BY = ("Lake points and areas from HKH-PK-2020 (Siddique et al. 2023, Zenodo 15476013; rows with source "
         "hkhpk2020) and Hi-MAG (Chen et al. 2021, ESSD 13:741, Zenodo 4275164; rows with source himag) are "
         "used under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).")


def test_the_whole_mapped_lakes_file_is_odbl_with_the_cc_by_attribution_kept():
    doc = load_json(APP_DATA / "mapped_lakes.json")
    assert doc["licence"] == "ODbL 1.0"
    assert doc["notice"]["odbl"] == ODBL and doc["notice"]["cc_by"] == CC_BY


def test_no_shown_register_text_names_a_suparco_id():
    # SUPARCO links live only in the inventory's suparco field (probable shown, possible kept as candidates)
    for r in register_and_new():
        for key in ("id", "name", "coord_source"):
            assert "SUPARCO" not in r[key].upper() and "PDGL" not in r[key].upper(), (r["id"], key)
    for r in load_json("inventory/new_lakes.json"):
        props = json.loads((PROCESSING / r["outline"]).read_text(encoding="utf-8"))["properties"]
        assert not any("SUPARCO" in str(v).upper() or "PDGL" in str(v).upper() for v in props.values())


def test_suparco_match_csv_holds_only_matched_inventory_lakes_without_coordinates():
    with open(PROCESSING / "inventory" / "suparco_match.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    cols = set(rows[0])
    assert not [c for c in cols if re.search(r"lon|lat|dot_x|dot_y|coord", c)]
    assert {r["match"] for r in rows} <= {"probable", "possible"}
    new_ids = {r["id"] for r in load_json("inventory/new_lakes.json")}
    mapped = {l["id"] for l in load_json(APP_DATA / "mapped_lakes.json")["lakes"]}
    assert all(r["lake_id"] in new_ids | mapped | {"passu", "shazore", "khurdopin"} and r["method"] for r in rows)
    assert {(r["lake_id"], int(r["suparco_id"])) for r in rows if r["lake_id"] == "godar_dhand"} == {
        ("godar_dhand", 7), ("godar_dhand", 22)}
    # no georeferenced position of SUPARCO's map dots anywhere in the committed tables
    for name in ("suparco_match.csv", "lake_candidates.csv", "watched_inventory.json"):
        text = (PROCESSING / "inventory" / name).read_text(encoding="utf-8")
        assert not re.search(r"map dot \d+\.\d+,\d+\.\d+|dot at \d", text), name


@pytest.mark.parametrize("batch", [1, 2])
def test_a_registered_batch_is_complete(batch):
    reg = {l.id: l for l in load_lakes(LAKES_IN)}
    rows = [r for r in load_json("inventory/new_lakes.json") if r["batch"] == batch]
    for r in rows:
        lk = reg[r["id"]]
        assert (lk.lon, lk.lat, lk.outline, lk.province) == (r["lon"], r["lat"], r["outline"], r["province"])
        assert (OUTLINES / Path(lk.outline).name).is_file()
