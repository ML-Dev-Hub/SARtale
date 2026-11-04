import pytest

from sartale.lake_catalog import Pass
from sartale.lake_requests import RATE_PER_HOUR, RequestError, RequestStore, coverage, validate
from sartale.lakes import Lake

ATTABAD = Lake(id="attabad", name="Attabad Lake", lon=74.8, lat=36.3, coord_source="s", outline=None,
               role="watch", downstream=None, downstream_source=None)
GOOD = {"name": "  Some Lake ", "lat": "35.5", "lon": 75.0, "source": " https://example.org/paper "}


def err(payload, watched=(), open_requests=()):
    with pytest.raises(RequestError) as e:
        validate(payload, list(watched), list(open_requests))
    return e.value


def test_validate_cleans_a_good_request():
    clean = validate(GOOD, [ATTABAD], [])
    assert clean == {"name": "Some Lake", "lat": 35.5, "lon": 75.0, "source": "https://example.org/paper"}
    assert isinstance(clean["lat"], float)


def test_validate_refuses_out_of_bounds():
    e = err({**GOOD, "lat": 33.0})
    assert e.status == 400
    assert "34.4–37.6 °N, 70.8–76.6 °E" in str(e)


def test_validate_refuses_short_name_and_missing_source():
    assert err({**GOOD, "name": " a "}).status == 400
    assert err({**GOOD, "source": "  "}).status == 400
    assert err({**GOOD, "source": None}).status == 400
    assert err({**GOOD, "name": "x" * 81}).status == 400


def test_validate_refuses_non_numbers():
    assert err({**GOOD, "lat": "abc"}).status == 400
    assert err({**GOOD, "lon": None}).status == 400
    assert err({**GOOD, "lat": float("nan")}).status == 400


def test_validate_refuses_a_point_within_1_km_of_a_watched_lake():
    e = err({**GOOD, "lat": 36.305, "lon": 74.8}, [ATTABAD])
    assert e.status == 409 and str(e) == "Already watched: Attabad Lake."


def test_validate_refuses_a_point_near_an_open_request():
    other = {"id": 1, "name": "Earlier", "lat": 35.5, "lon": 75.005, "state": "queued"}
    e = err(GOOD, [ATTABAD], [other])
    assert e.status == 409 and str(e) == "Already requested: Earlier."


def clean(name="A lake", lat=35.0, lon=75.0):
    return {"name": name, "lat": lat, "lon": lon, "source": "a source"}


def test_store_round_trip_and_states(tmp_path):
    s = RequestStore(tmp_path / "r.sqlite")
    row = s.add(clean(), "1.2.3.4", 1000.0)
    assert row["state"] == "queued" and row["tracks"] == [] and row["passes"] is None
    assert s.get(row["id"])["name"] == "A lake" and s.get(99) is None
    s.set_searched(row["id"], 7, ["055A", "156A"], "2026-06-20", "2026-07-01")
    got = s.get(row["id"])
    assert (got["state"], got["passes"], got["tracks"], got["first"], got["last"]) == (
        "searched", 7, ["055A", "156A"], "2026-06-20", "2026-07-01")
    s.set_failed(row["id"], "CMR down")
    assert s.get(row["id"])["state"] == "search_failed" and s.get(row["id"])["reason"] == "CMR down"
    assert s.open_count() == 1
    second = s.add(clean("B lake", 36.0), "1.2.3.4", 1001.0)
    assert [r["id"] for r in s.list_open()] == [second["id"], row["id"]]
    s.set_state(row["id"], "accepted")
    assert [r["id"] for r in s.list_open()] == [second["id"]] and s.open_count() == 1
    s.set_state(second["id"], "rejected", "not a lake")
    assert s.list_open() == [] and s.get(second["id"])["reason"] == "not a lake"
    with pytest.raises(ValueError):
        s.set_state(row["id"], "bogus")


def test_recent_count_counts_only_that_address_after_since(tmp_path):
    s = RequestStore(tmp_path / "r.sqlite")
    s.add(clean("one"), "a", 100.0)
    s.add(clean("two", 35.1), "a", 5000.0)
    s.add(clean("three", 35.2), "b", 5000.0)
    assert s.recent_count("a", 1000.0) == 1
    assert s.recent_count("a", 0.0) == 2
    assert s.recent_count("b", 0.0) == 1
    assert RATE_PER_HOUR == 5


def mk(track, d, date):
    return Pass(granule=f"g{track}{date}", url="u", date=date, start=date + "T01:00:00", track=track,
                direction=d, frame="020", mode="4005", crid="P05023")


def test_coverage_counts_calibrated_passes_by_track():
    passes = [mk("156", "A", "2026-06-25"), mk("156", "A", "2026-07-07"), mk("055", "A", "2026-06-20"),
              mk("156", "A", "2026-06-01")]
    got = coverage(35.0, 75.0, search=lambda lake: passes)
    assert got == {"passes": 3, "tracks": ["055A", "156A"], "first": "2026-06-20", "last": "2026-07-07"}


def test_coverage_with_no_passes_is_zero_and_none():
    assert coverage(35.0, 75.0, search=lambda lake: []) == {"passes": 0, "tracks": [], "first": None, "last": None}
