"""The summary fields lakes.json carries for the overview and the lake page (sartale.lakesummary)."""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import pytest

from sartale.inventory import InventoryEntry, InventoryOutline, SuparcoMatch
from sartale.lakesummary import headline_counts, largest_extent, refresh_summary, share_fields, with_summary

HKH = "HKH-PK-2020 (PlanetScope outline, Sep 2020)"
HIMAG = "Hi-MAG (Landsat 30 m outline)"
OSM = "OpenStreetMap outline (undated)"


def entry(hkh=None, himag=None, osm=None, lake_id="x"):
    outlines = []
    if hkh is not None:
        outlines.append(InventoryOutline(HKH, 2020, hkh, "CC BY 4.0"))
    if himag is not None:
        outlines.append(InventoryOutline(HIMAG, 2017, himag, "CC BY 4.0"))
    if osm is not None:
        outlines.append(InventoryOutline(OSM, None, osm, "ODbL 1.0"))
    return InventoryEntry(lake_id, tuple(outlines), None, ())


def valid(date, km2, track="055A", crid="P05036"):
    return {"date": date, "track": track, "area_km2": km2, "observable_share": 1.0, "excluded": None, "crid": crid,
            "pass_id": f"{date}_{track}_{crid}"}


def ext(km2):
    return {"km2": km2, "source": "s", "year": 2020}


def status(name="No change", track="055A", latest="2026-08-05", noise=0.005):
    return {"status": name, "track": track, "latest_date": latest, "looks": 4, "noise_km2": noise}


def lake(area, noise, lid="x"):
    return {"id": lid, "lake_state": "lake", "status": status(noise=noise),
            "coverage": {"outline_in_window_share": 1.0, "zone_kind": "outline", "radius_m": None},
            "series": [valid("2026-08-05", area)]}


def lake_case(case):
    lk = lake(1.0, 0.005)
    if case == "no_lake":
        lk["lake_state"] = "no_lake"
        lk["status"]["status"] = "No lake now"
    elif case == "frozen":
        lk["status"]["status"] = "Frozen (likely)"
    elif case == "not_measurable":
        lk["status"]["status"] = "Not measurable"
        lk["status"]["noise_km2"] = None
    elif case == "forming":
        lk["lake_state"] = "lake_forming_check"
        lk["status"]["status"] = "Lake may be forming"
        lk["coverage"] = {"outline_in_window_share": None, "zone_kind": "circle", "radius_m": 1000.0}
    elif case == "circle":
        lk["coverage"] = {"outline_in_window_share": None, "zone_kind": "circle", "radius_m": 1000.0}
    elif case.startswith("window_"):
        lk["coverage"]["outline_in_window_share"] = float(case.split("_")[1])
    elif case == "no_reading":
        lk["series"] = [{**valid("2026-08-05", None), "excluded": "too bright"}]
    return lk


def doc_with(rows, built="2026-11-14T00:00:00Z"):
    lakes = []
    for lid, st in rows:
        lk = lake(0.5, 0.005, lid)
        lk["status"]["status"] = st
        lakes.append(lk)
    return {"version": 1, "built": built, "lakes": lakes}


def prev_doc(previous_build):
    """A published lakes.json whose summary is `previous_build`: built then, its lakes with those statuses."""
    d = doc_with(list(previous_build["statuses"].items()), built=previous_build["built"])
    d["counts"] = previous_build["counts"]
    return d


def set_status(doc, lid, st):
    d = copy.deepcopy(doc)
    next(lk for lk in d["lakes"] if lk["id"] == lid)["status"]["status"] = st
    return d


def by_id(doc, lid):
    return next(lk for lk in doc["lakes"] if lk["id"] == lid)


def _fixture_lakes():
    def one(lid, st, state="lake", above=None, suparco=None, previous=None):
        lk = lake(0.5, 0.005, lid)
        lk.update(lake_state=state, above_largest=above, suparco=suparco, previous_status=previous)
        lk["status"]["status"] = st
        return lk
    s = {"id": 1, "match": "probable", "source": "t"}
    return [
        one("alert", "Alert: growing", above=True, suparco=s),
        one("watch", "Watch", above=False, suparco=s, previous="No change"),
        one("decrease", "Decrease noted", above=False),
        one("still", "No change", above=False, previous="No change"),
        one("forming", "Lake may be forming", state="lake_forming_check"),
        one("ice1", "Frozen (likely)"),
        one("ice2", "Frozen (seen by Sentinel-2)"),
        one("gone1", "No lake now", state="no_lake"),
        one("gone2", "No lake now", state="no_lake"),
    ]


fixture_lakes = _fixture_lakes()

inventory_fixture = {"godar_dhand": InventoryEntry(
    "godar_dhand", (InventoryOutline(HKH, 2020, 0.4755, "CC BY 4.0"),), None,
    (SuparcoMatch(7, "possible", "dot could be 7 or 22"), SuparcoMatch(22, "possible", "dot could be 7 or 22")))}


def test_the_current_season_never_sets_its_own_largest_extent():
    ext_ = largest_extent(entry(hkh=0.139), series=[valid("2026-07-24", 0.149)], built="2026-11-20T00:00:00Z")
    assert ext_ == {"km2": 0.139, "source": HKH, "year": 2020}


def test_an_earlier_season_radar_reading_can_set_the_extent():
    ext_ = largest_extent(entry(hkh=0.139), series=[valid("2026-07-24", 0.149)], built="2027-02-01T00:00:00Z")
    assert ext_["km2"] == 0.149 and ext_["source"] == "NISAR radar, track 055A, 2026-07-24" and ext_["year"] == 2026


def test_out_of_season_frozen_or_invalid_readings_never_set_the_extent():
    series = [valid("2026-11-02", 0.9), {**valid("2026-07-12", 0.8), "frozen": True},
              {**valid("2026-07-24", 0.7), "observable_share": 0.2}, {**valid("2026-08-05", None), "excluded": "x"}]
    assert largest_extent(entry(osm=0.2), series, "2027-02-01T00:00:00Z") == {"km2": 0.2, "source": OSM, "year": None}


def test_the_largest_inventory_outline_wins_and_none_without_any():
    assert largest_extent(entry(hkh=0.1, himag=0.3, osm=0.2), [], "2026-11-20T00:00:00Z")["source"] == HIMAG
    assert largest_extent(None, [valid("2026-07-24", 0.149)], "2026-11-20T00:00:00Z") is None


def test_above_needs_two_noise_beyond_the_extent():
    assert share_fields(lake(area=1.0099, noise=0.005), ext(1.0))["above_largest"] is False
    assert share_fields(lake(area=1.0101, noise=0.005), ext(1.0))["above_largest"] is True
    edge = 1.0 * (1 + 2 * 0.005 / 1.0)  # the code's own expression, exactly on the line
    assert share_fields(lake(area=edge, noise=0.005), ext(1.0))["above_largest"] is True
    assert share_fields(lake(area=1.02, noise=None), ext(1.0))["above_largest"] is None
    assert share_fields(lake(area=0.9, noise=None), ext(1.0))["above_largest"] is False


def test_a_shown_share_is_the_latest_status_track_reading_over_the_extent():
    lk = lake(0.4, 0.005)
    lk["series"] = [valid("2026-07-24", 0.6), valid("2026-08-05", 0.4), valid("2026-08-09", 0.9, track="063D")]
    f = share_fields(lk, ext(0.8))
    assert f == {"share_of_largest": 0.5, "above_largest": False, "share_note": None}


@pytest.mark.parametrize("case,note", [("no_lake", "there is no lake here now"),
                                       ("frozen", "Not shown while the lake is frozen"),
                                       ("not_measurable", "did not pass the Sentinel-2 check"),
                                       ("forming", "only a search circle"),
                                       ("circle", "only a search circle"), ("window_0.89", "only 89% of the lake outline"),
                                       ("no_extent", "no inventory outline"),
                                       ("no_reading", "no valid open-water reading yet")])
def test_no_share_says_why(case, note):
    f = share_fields(lake_case(case), None if case == "no_extent" else ext(1.0))
    assert f["share_of_largest"] is None and f["above_largest"] is None and note in f["share_note"]


def test_the_share_notes_are_the_pinned_sentences():
    notes = {c: share_fields(lake_case(c), ext(1.0))["share_note"] for c in ("no_lake", "frozen", "circle", "window_0.89",
                                                                              "no_reading")}
    assert notes == {
        "no_lake": "Not shown: there is no lake here now.",
        "frozen": "Not shown while the lake is frozen: the radar area is not an open-water measurement.",
        "circle": "Not shown: this lake has no mapped outline, only a search circle.",
        "window_0.89": "Not shown: only 89% of the lake outline is inside the radar window (at least 90% needed).",
        "no_reading": "Not shown: no valid open-water reading yet."}
    assert share_fields(lake_case("circle"), None)["share_note"] == notes["circle"]  # in that order
    assert (share_fields(lake(1.0, 0.005), None)["share_note"]
            == "Not shown: no inventory outline or earlier-season radar reading for this lake.")


def test_mapped_count_comes_from_the_mapped_lakes_file(tmp_path):
    doc = doc_with([("a", "No change")])
    (tmp_path / "mapped_lakes.json").write_text(json.dumps({"lakes": [{}, {}, {}]}), encoding="utf-8")
    assert with_summary(doc, None, {}, mapped_path=tmp_path / "mapped_lakes.json")["mapped_count"] == 3
    assert with_summary(doc, None, {}, mapped_path=tmp_path / "missing.json")["mapped_count"] is None
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    assert with_summary(doc, None, {}, mapped_path=tmp_path / "bad.json")["mapped_count"] is None


def test_counts_agree_with_the_lakes():
    c = headline_counts(fixture_lakes)
    assert c == {"watched": 9, "alert": 1, "watch": 1, "decrease": 1, "forming": 1, "needs_attention": 4,
                 "open_water": 4, "frozen": 2, "no_lake": 2, "above_largest": 1, "suparco_listed": 2, "changed": 1}


def test_changed_counts_only_lakes_in_both_builds(tmp_path):
    prev = {"built": "2026-11-09T00:00:00Z", "counts": {}, "statuses": {"a": "No change", "b": "Watch"}}
    d = with_summary(doc_with([("a", "Watch"), ("b", "Watch"), ("new", "Alert: growing")]), prev_doc(prev), {},
                     mapped_path=tmp_path / "none.json")
    assert d["counts"]["changed"] == 1 and by_id(d, "new")["previous_status"] is None
    assert by_id(d, "a")["previous_status"] == "No change"
    assert d["previous_build"] == prev


def test_the_summary_has_the_newest_pass_and_no_previous_build_on_a_first_build(tmp_path):
    doc = doc_with([("a", "No change"), ("b", "Watch")])
    by_id(doc, "b")["status"]["latest_date"] = "2026-11-09"
    by_id(doc, "a")["status"]["latest_date"] = None
    d = with_summary(doc, None, {}, mapped_path=tmp_path / "none.json")
    assert d["newest_pass"] == "2026-11-09" and d["previous_build"] is None
    assert all(lk["previous_status"] is None for lk in d["lakes"])
    json.dumps(d, allow_nan=False)


def test_lakes_freeze_and_lakes_check_refresh_the_counts(tmp_path):
    d = refresh_summary(set_status(doc_with([("a", "No change")]), "a", "Frozen (likely)"))
    assert d["counts"]["frozen"] == 1 and d["counts"]["open_water"] == 0


def test_a_refresh_hides_the_share_of_a_lake_that_froze_and_keeps_the_mapped_count(tmp_path):
    (tmp_path / "m.json").write_text(json.dumps({"lakes": [{}]}), encoding="utf-8")
    d = with_summary(doc_with([("a", "No change")]), None, {"a": InventoryEntry("a", (InventoryOutline(
        HKH, 2020, 0.4, "CC BY 4.0"),), None, ())}, mapped_path=tmp_path / "m.json")
    assert by_id(d, "a")["share_of_largest"] == 1.25 and by_id(d, "a")["above_largest"] is True
    r = refresh_summary(set_status(d, "a", "Frozen (likely)"), inventory={"a": InventoryEntry("a", (InventoryOutline(
        HKH, 2020, 0.4, "CC BY 4.0"),), None, ())})
    a = by_id(r, "a")
    assert a["share_of_largest"] is None and a["above_largest"] is None and "frozen" in a["share_note"]
    assert r["mapped_count"] == 1 and r["counts"]["above_largest"] == 0


def test_the_status_carries_its_threshold_and_latest_pass_id(tmp_path):
    d = with_summary(doc_with([("a", "No change")]), None, {}, mapped_path=tmp_path / "none.json")
    st = by_id(d, "a")["status"]
    assert st["threshold_km2"] == pytest.approx(0.01) and st["latest_pass_id"] == "2026-08-05_055A_P05036"
    assert st["noise_floor_applied"] is None  # not decided by these hand-made passes


def test_possible_matches_are_kept_but_not_shown(tmp_path):
    lk = by_id(with_summary(doc_with([("godar_dhand", "No change")]), None, inventory_fixture,
                            mapped_path=tmp_path / "none.json"), "godar_dhand")
    assert lk["suparco"] is None and {c["id"] for c in lk["suparco_candidates"]} == {7, 22}
    assert all(c["match"] == "possible" for c in lk["suparco_candidates"])


def test_a_probable_match_is_the_lakes_suparco_id(tmp_path):
    inv = {"a": InventoryEntry("a", (), SuparcoMatch(59, "probable", "dot 0.93 km away"), ())}
    lk = by_id(with_summary(doc_with([("a", "No change")]), None, inv, mapped_path=tmp_path / "n.json"), "a")
    assert lk["suparco"] == {"id": 59, "match": "probable", "source": "dot 0.93 km away"}
    assert lk["suparco_candidates"] == []


def test_the_committed_inventory_feeds_the_summary(tmp_path):
    from sartale.inventory import load_inventory
    inv = load_inventory()
    d = with_summary(doc_with([("godar_dhand", "No change")]), None, inv, mapped_path=tmp_path / "n.json")
    assert by_id(d, "godar_dhand")["largest_extent"] == {"km2": 0.4755, "source": HKH, "year": 2020}


def test_a_lake_whose_radar_water_failed_the_sentinel2_check_gets_no_share():
    f = share_fields(lake_case("not_measurable"), ext(0.5))
    assert f == {"share_of_largest": None, "above_largest": None,
                 "share_note": "Not shown: the radar water did not pass the Sentinel-2 check."}
    # after the no-lake and frozen notes, before the circle note
    circle = lake_case("not_measurable")
    circle["coverage"] = {"outline_in_window_share": None, "zone_kind": "circle", "radius_m": 1000.0}
    assert "Sentinel-2 check" in share_fields(circle, ext(0.5))["share_note"]
    frozen = lake_case("not_measurable")
    frozen["status"]["status"] = "Frozen (likely)"
    assert "frozen" in share_fields(frozen, ext(0.5))["share_note"]


def test_a_forming_site_is_not_told_there_is_no_lake():
    f = share_fields(lake_case("forming"), ext(1.0))
    assert f["share_note"] == "Not shown: this lake has no mapped outline, only a search circle."
    assert headline_counts([{**lake_case("forming"), "suparco": None}])["no_lake"] == 0


def test_attabad_takes_its_osm_outline_as_largest_extent(tmp_path):
    from sartale.inventory import load_inventory
    d = with_summary(doc_with([("attabad", "No change")]), None, load_inventory(), mapped_path=tmp_path / "n.json")
    assert by_id(d, "attabad")["largest_extent"] == {"km2": 7.2385, "source": OSM, "year": None}
