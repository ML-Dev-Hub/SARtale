import re
from pathlib import Path

import pytest

from sartale.lake_catalog import Pass
from sartale.lake_requests import BANNED_CLAIMS, RequestError, coverage, find_banned_claims, validate
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


def test_validate_refuses_a_huge_integer_without_overflowing():
    assert err({**GOOD, "lat": 10**400}).status == 400


@pytest.mark.parametrize("bad", ["Line\nbreak", "Esc\x1bape", "Flip‮text"])
def test_validate_refuses_control_and_formatting_characters(bad):
    for key in ("name", "source"):
        e = err({**GOOD, key: bad + " more"})
        assert e.status == 400 and key in str(e)


def test_validate_allows_ordinary_spaces_and_accents():
    assert validate({**GOOD, "name": "Yaz Sam é"}, [], [])["name"] == "Yaz Sam é"



BANNED_NAME = 'The name uses a phrase SARtale does not use ("{}"); please use the lake\'s usual name.'


@pytest.mark.parametrize("name, phrase", [("Safe lake", "safe"), ("Lake of EARLY  warning", "early warning"),
                                          ("Damaged moraine", "damaged"), ("predict pond", "predict")])
def test_validate_refuses_a_name_with_a_banned_phrase(name, phrase):
    e = err({**GOOD, "name": name})
    assert e.status == 400 and str(e) == BANNED_NAME.format(phrase)


def test_banned_phrases_match_whole_words_only():
    assert validate({**GOOD, "name": "Safeguard lake"}, [], [])["name"] == "Safeguard lake"
    assert find_banned_claims("unsafe, predictable") == []
    assert find_banned_claims("SAFE and damage") == ["damage", "safe"]  # in list order, once each


def test_banned_list_matches_the_app():
    """BANNED_CLAIMS is a copy of the list in app/src/content.ts; the two must stay the same."""
    source = (Path(__file__).resolve().parents[2] / "app" / "src" / "content.ts").read_text(encoding="utf-8")
    block = re.search(r"export const BANNED_CLAIMS = \[(.*?)\] as const;", source, re.S)
    assert block, "content.ts no longer defines BANNED_CLAIMS as a literal list"
    assert tuple(re.findall(r'"([^"]*)"', block.group(1))) == BANNED_CLAIMS


@pytest.mark.parametrize("bad", ["3.62e1", "3_6.2", "٣٦.٢", "３６.２", "36.", ".5", "0x24"])
def test_validate_takes_only_plain_ascii_decimals_as_text(bad):
    e = err({**GOOD, "lat": bad})
    assert e.status == 400 and str(e) == "lat must be a number."


def test_validate_still_takes_numbers_and_plain_decimal_text():
    assert validate({**GOOD, "lat": " +35.5 ", "lon": 75}, [], [])["lat"] == 35.5


BANNED_SOURCE = ('The source uses a phrase SARtale does not use ("{}"); '
                 "please describe where the coordinates come from.")


@pytest.mark.parametrize("source, phrase", [("Safe-route survey 2020", "safe"), ("Change  detection study", "change detection")])
def test_validate_refuses_a_source_with_a_banned_phrase(source, phrase):
    e = err({**GOOD, "source": source})
    assert e.status == 400 and str(e) == BANNED_SOURCE.format(phrase)


def test_banned_source_comes_after_the_name_and_source_rules():
    assert str(err({**GOOD, "name": "Safe lake", "source": "A safe survey"})).startswith("The name uses")
    assert str(err({**GOOD, "source": "ok"})) == "source must be 3–200 characters."
    assert validate({**GOOD, "source": "Unsafe-slope inventory"}, [], [])["source"] == "Unsafe-slope inventory"
