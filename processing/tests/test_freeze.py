"""The frozen status: the air-temperature rule, the Sentinel-2 override, break-up, and how a lake's status follows."""
from datetime import date as Date, timedelta

import numpy as np
import pytest

from sartale import config
from sartale.freeze import (
    corrected,
    fetch_power,
    freeze_history,
    freeze_lake,
    freeze_reason,
    power_start,
    s2_kind,
    season_start,
    zone_shares,
)
from sartale.lakes import Lake


def temps_from(start: str, values) -> dict:
    """iso -> {"t2m", "t2m_min"} from `start`, one value per day; None is a missing day."""
    d = Date.fromisoformat(start)
    out = {}
    for i, v in enumerate(values):
        out[(d + timedelta(days=i)).isoformat()] = {"t2m": v, "t2m_min": None if v is None else v - 5}
    return out


def last_day(start: str, n: int) -> str:
    return (Date.fromisoformat(start) + timedelta(days=n - 1)).isoformat()


def history(values, start="2026-10-01", series=(), ref=None, today=None, s2_events=()):
    temps = temps_from(start, values)
    return freeze_history(temps, list(series), ref or {}, today or last_day(start, len(values)), list(s2_events))


# --- the temperature rule ---------------------------------------------------------------------------------------------

def test_seven_cold_days_and_thirty_degree_days_make_it_frozen_likely():
    warm = [3.0] * 10
    h = history(warm + [-5.0] * 7)
    assert h["state"] == "frozen_likely" and h["since"] == "2026-10-17"
    assert h["cold_run_days"] == 7 and h["fdd_since_sep"] == 35.0 and h["warm_run_days"] == 0
    # six cold days are not enough, however cold
    assert history(warm + [-20.0] * 6)["state"] == "open"


def test_the_degree_day_edge():
    # seven days in a row but only 28 degree-days: not yet; the eighth day takes it to 32
    assert history([-4.0] * 7)["state"] == "open"
    h = history([-4.0] * 8)
    assert h["state"] == "frozen_likely" and h["since"] == "2026-10-08"
    # exactly 30 and exactly 7 days: frozen (both thresholds are inclusive)
    h = history([-4.0] * 6 + [-6.0])
    assert h["fdd_since_sep"] == 30.0 and h["cold_run_days"] == 7 and h["state"] == "frozen_likely"
    # degree-days from earlier cold spells count: 20 days at -1 then 7 at -1.5 = 30.5
    h = history([-1.0] * 20 + [2.0] + [-1.5] * 7)
    assert h["fdd_since_sep"] == 30.5 and h["state"] == "frozen_likely"


def test_zero_and_above_end_the_cold_run():
    h = history([-5.0] * 6 + [0.0] + [-5.0] * 6)
    assert h["state"] == "open" and h["cold_run_days"] == 6


def test_the_1_sep_reset():
    # frozen in May; open all summer; on 1 Sep the degree-days start again from 0
    values = [-5.0] * 31 + [5.0] * 92 + [-3.0] * 7  # 1 May..31 May, 1 Jun..31 Aug, 1 Sep..7 Sep
    h = history(values, start="2026-05-01")
    assert h["temp_through"] == "2026-09-07"
    assert h["fdd_since_sep"] == 21.0 and h["cold_run_days"] == 7
    assert h["state"] == "open", "May's degree-days must not carry into the new season"
    # a pass in May was frozen, one in August was not (outside the season)
    series = [{"date": "2026-05-20", "track": "084A", "excluded": None},
              {"date": "2026-08-20", "track": "084A", "excluded": None}]
    assert history(values, start="2026-05-01", series=series)["flags"] == [True, False]


def test_no_freeze_up_starts_outside_the_season():
    assert season_start(Date(2026, 7, 1)) is None
    assert season_start(Date(2026, 11, 12)) == Date(2026, 9, 1)
    assert season_start(Date(2027, 3, 1)) == Date(2026, 9, 1)
    h = history([-8.0] * 20, start="2026-06-01")
    assert h["state"] == "open" and h["since"] is None


# A high lake's spring: frozen all winter (from 1 Oct 2025), then a June of thaw and frost by turns (+2, +2, -1: never
# seven warm days in a row), then a warm July.
WINTER = [-6.0] * 243  # 1 Oct 2025 .. 31 May 2026
JUNE = [2.0, 2.0, -1.0] * 10  # 1..30 Jun
JULY = [4.0] * 31


def test_a_lake_frozen_in_may_stays_frozen_through_june_and_opens_on_the_rule():
    series = [radar_pass(d) for d in ("2026-06-12", "2026-06-24")] + [radar_pass("2026-07-10", hh=-8.3, hv=-7.4, dark=0.86)]
    h = history(WINTER + JUNE + JULY, start="2025-10-01", series=series, ref=REF, today="2026-07-31")
    # June passes: still frozen after 31 May (no seven warm days, no radar ice-out signature)
    assert h["flags"][:2] == [True, True]
    # 7 Jul: seventh warm day -> break-up; 10 Jul: radar back within summer range; 14 Jul: fourteenth warm day -> open
    assert h["state"] == "open" and h["since"] == "2026-07-14" and h["flags"][2] is True
    mid_june = history(WINTER + JUNE[:20], start="2025-10-01", ref=REF, today="2026-06-20")
    assert mid_june["state"] == "frozen_likely" and mid_june["since"] == "2025-10-07"


def test_a_shazore_like_2026_spring_reads_ice_out_from_radar_in_late_june():
    # the radar ice-out signature of 25 Jun and 2 Jul 2026 (+3.2 to +3.7 dB HH, +2.9 to +3.4 dB HV, dark share 0.32-0.50
    # against 0.89-0.95), then a pass back within its summer range in mid July
    series = [radar_pass("2026-06-13"),
              radar_pass("2026-06-25", track="164D", hh=-4.6, hv=-4.0, dark=0.32),
              radar_pass("2026-07-02", hh=-4.4, hv=-3.6, dark=0.50),
              radar_pass("2026-07-21", hh=-8.2, hv=-7.3, dark=0.88),
              radar_pass("2026-07-25")]
    ref = {**REF, "164D": {**REF["084A"], "core_contrast_hh_db": -7.9, "core_contrast_hv_db": -6.9, "core_dark_share": 0.95}}
    june = [2.0, 2.0, -1.0] * 10
    july = [2.0, 2.0, -1.0] * 3 + [4.0] * 22  # cool to 9 Jul, warm from 10 Jul
    h = history(WINTER + june + july, start="2025-10-01", series=series, ref=ref, today="2026-07-31")
    assert h["flags"] == [True, True, True, True, False]
    # break-up from radar on 25 Jun (not from the air); open again on the fourteenth warm day after the radar pass back
    flags_at_jul2 = history(WINTER + june + july[:2], start="2025-10-01", series=series[:3], ref=ref, today="2026-07-02")
    assert flags_at_jul2["state"] == "breakup_likely" and flags_at_jul2["since"] == "2026-06-25"
    assert flags_at_jul2["breakup_pass"]["track"] == "164D"
    assert h["state"] == "open" and h["since"] == "2026-07-23"


def test_a_lake_still_frozen_on_1_sep_stays_frozen_and_says_so():
    summer = [2.0, 2.0, 2.0, -1.0] * 23  # 1 Jun .. 31 Aug: never seven warm days in a row
    h = history(WINTER + summer + [-1.0] * 5, start="2025-10-01", today="2026-09-05")
    assert h["state"] == "frozen_likely" and h["since"] == "2025-10-07" and h["held_over_sep"]
    assert h["fdd_since_sep"] == 5.0, "the degree-days still start again on 1 Sep"
    f = {**h, "s2": None, "s2_searched": True, "in_season": True}
    assert "still frozen or breaking up on 1 Sep" in freeze_reason(f, 4188)


def test_a_missing_day_ends_the_runs():
    values = [-5.0] * 3 + [None] + [-5.0] * 6
    h = history(values)
    assert h["state"] == "open" and h["cold_run_days"] == 6
    assert h["fdd_since_sep"] == 45.0  # a missing day adds nothing
    h = history(values + [-5.0])
    assert h["state"] == "frozen_likely" and h["since"] == "2026-10-11"


def test_power_lag_up_to_ten_days_keeps_the_newest_state_and_more_is_not_assessed():
    values = [-5.0] * 10  # 1..10 Oct
    for lag, state in ((3, "frozen_likely"), (10, "frozen_likely"), (11, "not_assessed")):
        today = (Date(2026, 10, 10) + timedelta(days=lag)).isoformat()
        h = history(values, today=today)
        assert h["state"] == state, lag
        assert h["temp_through"] == "2026-10-10"
    h = history(values, today="2026-10-21")
    assert "10 Oct 2026" in h["why"] and "more than 10 days" in h["why"]
    assert freeze_history({}, [], {}, "2026-10-21")["state"] == "not_assessed"


def test_each_pass_gets_the_state_on_its_own_date():
    series = [{"date": d, "track": "084A", "excluded": None}
              for d in ("2026-10-05", "2026-10-07", "2026-10-15", "2026-10-25")]
    h = history([-5.0] * 15, series=series, today="2026-10-25")  # POWER to 15 Oct; frozen from 7 Oct
    # before freeze-up: not frozen; on the crossing day and after: frozen; 10 days past POWER: newest state;
    assert h["flags"] == [False, True, True, True]
    late = [{"date": "2026-10-26", "track": "084A", "excluded": None}]
    assert history([-5.0] * 15, series=late, today="2026-10-26")["flags"] == [False]  # 11 days past: no flag


def test_seven_day_means():
    h = history([10.0] * 5 + [-1.0] * 7)
    assert h["t2m_mean_7d"] == -1.0 and h["t2m_min_mean_7d"] == -6.0


# --- break-up --------------------------------------------------------------------------------------------------------

REF = {"084A": {"passes": 5, "core_px": 120, "assessed": True, "core_contrast_hh_db": -8.0,
                "core_contrast_hv_db": -7.0, "core_dark_share": 0.9}}


def radar_pass(day, hh=-8.0, hv=-7.0, dark=0.9, track="084A", excluded=None):
    return {"date": day, "track": track, "excluded": excluded, "core_contrast_hh_db": hh, "core_contrast_hv_db": hv,
            "core_dark_share": dark}


def test_seven_warm_days_after_freeze_up_make_break_up_likely():
    h = history([-5.0] * 10 + [2.0] * 7)
    assert h["state"] == "breakup_likely" and h["since"] == "2026-10-17" and h["breakup_pass"] is None
    assert history([-5.0] * 10 + [2.0] * 6)["state"] == "frozen_likely"


def test_a_bright_core_while_frozen_makes_break_up_likely():
    bright = radar_pass("2026-10-12", hh=-5.8, hv=-4.9, dark=0.5)  # +2.2 / +2.1 dB, dark share down 0.4
    h = history([-5.0] * 15, series=[bright], ref=REF)
    assert h["state"] == "breakup_likely" and h["since"] == "2026-10-12" and h["flags"] == [True]
    b = h["breakup_pass"]
    assert (b["contrast_hh_change_db"], b["contrast_hv_change_db"], b["core_dark_share"]) == (2.2, 2.1, 0.5)


@pytest.mark.parametrize("p", [
    radar_pass("2026-10-12", hh=-5.8, hv=-5.2, dark=0.5),  # HV only +1.8 dB
    radar_pass("2026-10-12", hh=-5.8, hv=-4.9, dark=0.65),  # dark share down only 0.25
    radar_pass("2026-10-12", hh=-5.8, hv=-4.9, dark=0.5, excluded="bright pass"),  # an excluded pass is not tested
    radar_pass("2026-10-12", hh=-5.8, hv=-4.9, dark=0.5, track="055A"),  # no summer level on that track
])
def test_the_radar_test_needs_both_bands_the_dark_drop_and_a_summer_level(p):
    assert history([-5.0] * 15, series=[p], ref=REF)["state"] == "frozen_likely"


def test_fewer_than_three_summer_passes_means_no_radar_test():
    ref = {"084A": {**REF["084A"], "passes": 2, "assessed": False}}
    bright = radar_pass("2026-10-12", hh=-5.0, hv=-4.0, dark=0.3)
    assert history([-5.0] * 15, series=[bright], ref=ref)["state"] == "frozen_likely"


def test_a_bright_core_on_an_open_lake_is_not_break_up():
    bright = radar_pass("2026-10-03", hh=-5.0, hv=-4.0, dark=0.3)
    assert history([3.0] * 10, series=[bright], ref=REF)["state"] == "open"


def test_open_again_needs_fourteen_warm_days_and_a_radar_pass_back_in_its_summer_range():
    cold, warm = [-5.0] * 10, [3.0] * 14  # frozen 7 Oct, break-up 17 Oct, 14th warm day 24 Oct
    h = history(cold + warm, ref=REF)
    assert h["state"] == "breakup_likely", "no radar pass back within its summer range yet"
    back = radar_pass("2026-10-20", hh=-8.3, hv=-7.4, dark=0.85)
    h = history(cold + warm, series=[back], ref=REF)
    assert h["state"] == "open" and h["since"] == "2026-10-24" and h["flags"] == [True]
    # a pass back in range after the fourteenth warm day opens it that day, and that pass is open water
    late = radar_pass("2026-10-26", hh=-8.3, hv=-7.4, dark=0.85)
    h = history(cold + warm + [3.0] * 2, series=[late], ref=REF)
    assert h["state"] == "open" and h["since"] == "2026-10-26" and h["flags"] == [False]
    # without any summer level on the lake, the radar test is not assessed and the warm days alone reopen it
    assert history(cold + warm)["state"] == "open"


def test_cold_again_during_break_up_is_frozen_again():
    h = history([-5.0] * 10 + [2.0] * 7 + [-3.0] * 7)
    assert h["state"] == "frozen_likely" and h["since"] == "2026-10-07"  # M1: the freeze-up date is kept


# --- Sentinel-2 ------------------------------------------------------------------------------------------------------

S2_SNOW = {"date": "2026-11-08", "s2_id": "S2A_43SCV_20261108_0_L2A", "clear_share": 0.97, "snow_share": 0.94,
           "water_share": 0.0}


def test_what_a_sentinel2_reading_shows():
    assert s2_kind(S2_SNOW) == "snow"
    assert s2_kind({**S2_SNOW, "snow_share": 0.8}) == "snow"
    assert s2_kind({**S2_SNOW, "snow_share": 0.79}) is None
    assert s2_kind({**S2_SNOW, "snow_share": 0.1, "water_share": 0.5}) == "water"
    assert s2_kind({**S2_SNOW, "snow_share": 0.5, "water_share": 0.3}) is None
    # M3: less than half of the lake itself seen clear: no evidence either way
    assert s2_kind({**S2_SNOW, "target_clear_share": 0.49}) is None
    assert s2_kind({**S2_SNOW, "snow_share": 0.0, "water_share": 0.9, "target_clear_share": 0.4}) is None
    assert s2_kind(None) is None


def snow(day, share=0.94):
    return {**S2_SNOW, "date": day, "s2_id": f"S2_{day}", "snow_share": share, "water_share": 0.0}


def water(day, share=0.7):
    return {**S2_SNOW, "date": day, "s2_id": f"S2_{day}", "snow_share": 0.0, "water_share": share}


def test_sentinel2_snow_or_ice_makes_it_frozen_from_the_freeze_up_date_or_the_scene_date():
    frozen = history([-5.0] * 20, s2_events=[snow("2026-10-15")])  # frozen by the air on 7 Oct
    assert frozen["state"] == "frozen_s2" and frozen["since"] == "2026-10-07" and frozen["freeze_up"] == "2026-10-07"
    assert frozen["s2_evidence"]["date"] == "2026-10-15"
    warm = history([3.0] * 20, s2_events=[snow("2026-10-15")])
    assert warm["state"] == "frozen_s2" and warm["since"] == "2026-10-15" and warm["freeze_up"] == "2026-10-15"
    assert history([3.0] * 20, s2_events=[snow("2026-10-15", 0.79)])["state"] == "open"


def test_frozen_s2_after_break_up_keeps_the_freeze_up_date():
    # M1: frozen by the air 7 Oct, break-up by seven warm days on 17 Oct, then a clear scene with snow on the lake
    h = history([-5.0] * 10 + [2.0] * 9, s2_events=[snow("2026-10-19")])
    assert h["state"] == "frozen_s2" and h["since"] == "2026-10-07" and h["freeze_up"] == "2026-10-07"


def test_sentinel2_open_water_releases_and_partial_views_change_nothing():
    h = history([-5.0] * 20, s2_events=[water("2026-10-15")])
    assert h["state"] == "open" and h["released_by"] == "s2" and h["released_on"] == "2026-10-15"
    partial = {**water("2026-10-15"), "water_share": 0.3}
    assert history([-5.0] * 20, s2_events=[partial])["state"] == "frozen_likely"
    assert history([-5.0] * 20)["state"] == "frozen_likely"
    assert freeze_history({}, [], {}, "2026-10-20", [snow("2026-10-15")])["state"] == "not_assessed"


def test_sentinel2_evidence_holds_without_new_evidence():
    # M4: frozen_s2 holds until a clear open-water scene or the rules release it; no flip back week to week while the
    # air neither freezes nor thaws for seven days in a row
    hovering = [1.0, 1.0, -1.0] * 12  # 1 Oct .. 5 Nov
    for today_n in (12, 24, 36):
        assert history(hovering[:today_n], s2_events=[snow("2026-10-05")])["state"] == "frozen_s2", today_n
        assert history(hovering[:today_n])["state"] == "open"
    # seven warm days after the scene (not the ones before it) call break-up, as for any frozen lake
    assert history([3.0] * 21, s2_events=[snow("2026-10-15")])["state"] == "frozen_s2"
    h = history([3.0] * 22, s2_events=[snow("2026-10-15")])
    assert h["state"] == "breakup_likely" and h["since"] == "2026-10-22"
    # an open reading holds until a new seven-day cold run (degree-days are already past 30)
    cold = [-5.0] * 20  # frozen by the air on 7 Oct
    for n in (0, 3, 6):
        assert history(cold + [-5.0] * n, s2_events=[water("2026-10-20")])["state"] == "open", n
    h = history(cold + [-5.0] * 7, s2_events=[water("2026-10-20")])
    assert h["state"] == "frozen_likely" and h["since"] == "2026-10-27"


def test_open_water_is_measured_over_the_outline_or_core_and_the_clear_gate_over_the_zone():
    zone = np.zeros((20, 20), bool)
    zone[2:18, 2:18] = True  # 256 px: the outline buffered, or the circle
    target = np.zeros((20, 20), bool)
    target[8:12, 8:12] = True  # 16 px: the unbuffered outline, or the summer radar core
    clear = np.ones((20, 20), bool)
    clear[2:5, 2:18] = False  # 48 zone pixels under cloud: zone 81% clear
    water = target.copy()
    water[8, 8] = False  # 15 of the 16 target pixels are water; none of the shore is
    s = zone_shares({"clear": clear, "snow": np.zeros((20, 20), bool), "water": water}, zone, target)
    assert s["clear_share"] == pytest.approx(208 / 256) and s["water_share"] == pytest.approx(15 / 16)
    assert s["target_clear_share"] == 1.0
    # over the whole zone the same lake reads under the 50% open-water line
    assert zone_shares({"clear": clear, "snow": np.zeros((20, 20), bool), "water": water}, zone)["water_share"] < 0.1
    # a target under cloud reads no water, whatever the zone shows
    cloudy = clear & ~target
    assert zone_shares({"clear": cloudy, "snow": np.zeros((20, 20), bool), "water": water}, zone, target) == {
        "clear_share": pytest.approx(192 / 256), "snow_share": 0.0, "water_share": 0.0, "target_clear_share": 0.0}


def test_the_sentinel2_look_uses_the_lakes_own_target(monkeypatch):
    from sartale import freeze, lakebuild, lakecheck
    zone = np.ones((10, 10), bool)
    target = np.zeros((10, 10), bool)
    target[4:6, 4:6] = True
    monkeypatch.setattr(lakebuild, "freeze_masks", lambda lake, cache, frozen=(): {"zone": zone, "target": target,
                        "target_kind": "summer radar water core", "x": np.arange(10.0), "y": np.arange(10.0), "epsg": 32643})
    scene = {"type": "Feature", "id": "S2X", "properties": {"datetime": "2026-11-10T06:00:00Z", "eo:cloud_cover": 5},
             "assets": {"green": {}, "swir16": {}, "scl": {}}}
    monkeypatch.setattr(lakecheck, "search_scenes", lambda *a, **k: [scene])
    monkeypatch.setattr(lakecheck, "optical_on_grid", lambda *a: {"clear": zone, "snow": np.zeros((10, 10), bool),
                                                                   "water": target})
    got = freeze.s2_scene_check(SHAZORE, "2026-11-12", log=lambda m: None, cache_dir="anywhere")
    assert got == {"date": "2026-11-10", "s2_id": "S2X", "clear_share": 1.0, "target_clear_share": 1.0,
                   "snow_share": 0.0, "water_share": 1.0, "water_over": "summer radar water core"}
    assert s2_kind(got) == "water"
    assert "water on 100% of the summer radar water core seen clear" in freeze.s2_text({"s2": got})
    # M2/M3: snow is measured over the lake itself too, and a lake under cloud gives no reading
    monkeypatch.setattr(lakecheck, "optical_on_grid", lambda *a: {"clear": zone & ~target, "snow": zone,
                                                                   "water": np.zeros((10, 10), bool)})
    assert freeze.s2_scene_check(SHAZORE, "2026-11-12", log=lambda m: None, cache_dir="anywhere") is None


def test_zone_shares_count_snow_as_seen_and_cloud_edges_as_not():
    zone = np.zeros((10, 10), bool)
    zone[:, :5] = True  # 50 pixels
    clear = np.ones((10, 10), bool)
    clear[:2, :5] = False  # 10 zone pixels under cloud or its edge
    snow = np.zeros((10, 10), bool)
    snow[2:, :4] = True  # 32 of the 40 clear zone pixels
    water = np.zeros((10, 10), bool)
    water[2:6, 4] = True  # 4
    s = zone_shares({"clear": clear, "snow": snow, "water": water}, zone)
    assert s == {"clear_share": 0.8, "snow_share": 0.8, "water_share": 0.1, "target_clear_share": 0.8}
    # M2: snow on the shore alone does not make the lake itself snow-covered
    lake = np.zeros((10, 10), bool)
    lake[6:10, 4] = True  # 4 px, open water
    shore_snow = zone & ~lake
    w = zone_shares({"clear": zone, "snow": shore_snow, "water": lake}, zone, lake)
    assert w["snow_share"] == 0.0 and w["water_share"] == 1.0


# --- one lake end to end --------------------------------------------------------------------------------------------

SHAZORE = Lake(id="shazore", name="Shazore", lon=72.1741, lat=35.7794, coord_source="x", outline=None, role="watch",
               downstream=None, downstream_source=None, elevation_m=4181, elevation_source="Copernicus DEM GLO-30")


def power_like(values, start="2026-09-01", cell=3719.0, lake=4181):
    """A fake fetch_power whose lake-height values are `values` (shifted back to the cell's height)."""
    shift = config.LAPSE_C_PER_KM * (lake - cell) / 1000.0

    def fetch(lon, lat, s, e):
        days = temps_from(start, values)
        return {"cell_elev_m": cell, "days": {d: {k: (None if v is None else v - shift) for k, v in row.items()}
                                              for d, row in days.items()}}
    return fetch


def shazore_entry():
    """Five summer passes near 0.16 km2, then two cold passes that read 0.225 (frozen ground reads as water)."""
    def p(d, a, crid="P05023"):
        return {"date": d, "track": "084A", "area_km2": a, "observable_share": 1.0, "excluded": None, "crid": crid}
    series = [p("2026-08-01", 0.158), p("2026-08-13", 0.162), p("2026-08-25", 0.160), p("2026-09-06", 0.161),
              p("2026-09-18", 0.159), p("2026-10-18", 0.225, "P05036"), p("2026-10-30", 0.226, "P05036")]
    return {"id": "shazore", "lake_state": "lake", "series": series, "summer_ref": {},
            "status": {"status": "Stable", "track": "084A", "latest_date": "2026-10-30", "looks": 7}}


# Shazore-like air: mild in September, cold from 12 Oct (the spike's corrected run started 12 Oct)
SHAZORE_AIR = [2.0] * 41 + [-5.0] * 30  # 1 Sep..11 Oct, 12 Oct..10 Nov


def test_a_cold_lake_is_frozen_with_its_date_and_its_frozen_passes_leave_the_baseline():
    seen = []
    out = freeze_lake(SHAZORE, shazore_entry(), "2026-11-12", power=power_like(SHAZORE_AIR),
                      s2_check=lambda lake, today, log, **k: seen.append(today) or None, log=lambda m: None)
    f = out["freeze"]
    assert f["state"] == "frozen_likely" and f["since"] == "2026-10-18" and f["temp_through"] == "2026-11-10"
    assert f["cold_run_days"] == 30 and f["fdd_since_sep"] == 150.0 and f["s2"] is None and f["s2_searched"]
    assert seen == ["2026-11-12"], "a cold lake gets a Sentinel-2 look"
    assert [p["frozen"] for p in out["series"]] == [False] * 5 + [True, True] and f["frozen_passes"] == 2
    assert [p["area_km2"] for p in out["series"]][-2:] == [0.225, 0.226], "frozen passes keep their area"
    st = out["status"]
    assert st["status"] == "Frozen (likely)" and st["change_km2"] is None
    assert st["latest_date"] == "2026-10-30" and st["track"] == "084A"
    assert "Probably frozen since 18 Oct 2026" in st["reason"] and "below 0 °C for 30 days in a row" in st["reason"]
    assert "No clear Sentinel-2 view of the lake in the last 7 days." in st["reason"]
    assert "4,181 m" in st["reason"] and "NASA POWER to 10 Nov 2026" in st["reason"]


def test_a_lake_frozen_today_is_frozen_even_when_its_last_pass_came_before_freeze_up():
    entry = shazore_entry()
    entry["series"] = entry["series"][:5]  # last pass 18 Sep
    out = freeze_lake(SHAZORE, entry, "2026-11-12", power=power_like(SHAZORE_AIR), s2_check=lambda *a, **k: None,
                      log=lambda m: None)
    assert out["status"]["status"] == "Frozen (likely)" and out["status"]["latest_date"] == "2026-09-18"
    assert not any(p["frozen"] for p in out["series"])


def test_a_clear_snow_covered_scene_makes_it_seen_by_sentinel2():
    out = freeze_lake(SHAZORE, shazore_entry(), "2026-11-12", power=power_like(SHAZORE_AIR),
                      s2_check=lambda *a, **k: S2_SNOW, log=lambda m: None)
    assert out["freeze"]["state"] == "frozen_s2" and out["freeze"]["since"] == "2026-10-18"
    st = out["status"]
    assert st["status"] == "Frozen (seen by Sentinel-2)"
    assert st["reason"].startswith("Snow or ice covers 94% of the lake zone seen clear in a Sentinel-2 scene of "
                                   "8 Nov 2026 (S2A_43SCV_20261108_0_L2A).")
    assert "probably been frozen since 18 Oct 2026" in st["reason"]


def test_without_the_frozen_status_the_cold_passes_would_read_as_growth():
    from sartale.lakestatus import open_water_status
    entry = shazore_entry()
    assert open_water_status(entry["series"])["status"] in ("Growing", "Change not confirmed yet")
    out = freeze_lake(SHAZORE, entry, "2026-11-12", power=power_like(SHAZORE_AIR), s2_check=lambda *a, **k: None,
                      log=lambda m: None)
    assert open_water_status(out["series"])["status"] == "Stable"


def test_a_warm_lake_stays_open_and_its_status_is_the_usual_one():
    air = [6.0] * 71
    called = []
    out = freeze_lake(SHAZORE, shazore_entry(), "2026-11-12", power=power_like(air),
                      s2_check=lambda *a, **k: called.append(1), log=lambda m: None)
    f = out["freeze"]
    assert f["state"] == "open" and f["since"] is None and not f["s2_searched"] and called == []
    assert out["status"]["status"] in ("Growing", "Change not confirmed yet")
    assert "Not frozen by the freeze rule" in f["reason"]
    assert "Air temperature alone cannot show that the lake is open." in f["reason"]


def test_no_lake_now_sites_get_no_freeze_state():
    entry = {**shazore_entry(), "lake_state": "no_lake", "freeze": {"state": "frozen_likely"},
             "status": {"status": "No lake now", "track": "084A", "latest_date": "2026-10-30", "looks": 7}}
    entry["series"] = [{**p, "frozen": True} for p in entry["series"]]
    lake = Lake(**{**SHAZORE.__dict__, "lake_state": "no_lake", "lake_state_source": "dry"})
    out = freeze_lake(lake, entry, "2026-11-12", power=lambda *a: pytest.fail("no POWER call"), log=lambda m: None)
    assert "freeze" not in out and out["status"]["status"] == "No lake now"
    assert not any("frozen" in p for p in out["series"])


@pytest.mark.parametrize("lake,power,why", [
    (Lake(**{**SHAZORE.__dict__, "elevation_m": None, "elevation_source": None}), None, "no lake height"),
    (SHAZORE, "fail", "could not be fetched"),
])
def test_not_assessed_keeps_the_usual_assessment(lake, power, why):
    def fail(*a):
        raise TimeoutError("POWER")
    out = freeze_lake(lake, shazore_entry(), "2026-11-12", power=fail if power else power_like(SHAZORE_AIR),
                      log=lambda m: None)
    assert out["freeze"]["state"] == "not_assessed" and why in out["freeze"]["reason"]
    assert out["freeze"]["reason"].startswith("Freeze not assessed:")
    assert out["status"]["status"] in ("Growing", "Change not confirmed yet")


def _first_check():
    return freeze_lake(SHAZORE, shazore_entry(), "2026-11-12", power=power_like(SHAZORE_AIR),
                       s2_check=lambda *a, **k: S2_SNOW, log=lambda m: None)


def _next_week(first):
    """The next build of the same lake: the build carries the last freeze object and flags, and adds a new pass."""
    new = {"date": "2026-11-11", "track": "084A", "area_km2": 0.23, "observable_share": 1.0, "excluded": None,
           "crid": "P05036"}
    return {**first, "series": first["series"] + [new]}


def test_stale_and_failed_power_keep_the_last_check_the_same_way():
    """M6: one behaviour. With NASA POWER stale (its newest day 15 days old) or unreachable, the last check stands:
    its state, its flags (a new pass of a frozen lake is flagged too) and its reason, marked "not refreshed since"; the
    status's latest date never moves back."""
    first = _first_check()
    assert first["freeze"]["state"] == "frozen_s2" and first["status"]["latest_date"] == "2026-10-30"

    def fail(*a):
        raise TimeoutError("POWER")
    outs = [freeze_lake(SHAZORE, _next_week(first), "2026-11-25", power=p, s2_check=lambda *a, **k: pytest.fail("no"),
                        log=lambda m: None) for p in (power_like(SHAZORE_AIR), fail)]
    for out in outs:
        f = out["freeze"]
        assert f["state"] == "frozen_s2" and f["since"] == "2026-10-18" and f["not_refreshed_since"] == "2026-11-12"
        assert f["reason"].startswith(first["freeze"]["reason"])
        assert "Not refreshed since 12 Nov 2026:" in f["reason"]
        assert [p["frozen"] for p in out["series"]] == [False] * 5 + [True, True, True]
        assert out["status"]["status"] == "Frozen (seen by Sentinel-2)"
        assert out["status"]["latest_date"] >= first["status"]["latest_date"]
    assert outs[0]["series"] == outs[1]["series"]
    assert {**outs[0]["status"], "reason": ""} == {**outs[1]["status"], "reason": ""}  # only the "why" differs
    assert "more than 10 days" in outs[0]["freeze"]["refresh_problem"]
    assert "could not be fetched" in outs[1]["freeze"]["refresh_problem"]
    # kept twice, it still says since when, once
    again = freeze_lake(SHAZORE, outs[1], "2026-12-02", power=fail, log=lambda m: None)
    assert again["freeze"]["reason"].count("Not refreshed since") == 1
    assert again["freeze"]["not_refreshed_since"] == "2026-11-12"
    # without a last check both paths give "not assessed" and no flags
    bare = _next_week({**shazore_entry()})
    for p in (power_like(SHAZORE_AIR), fail):
        out = freeze_lake(SHAZORE, bare, "2026-11-25", power=p, log=lambda m: None)
        assert out["freeze"]["state"] == "not_assessed" and not any(q.get("frozen") for q in out["series"])


def test_sentinel2_evidence_is_carried_from_the_last_check():
    """M4: the next build's check, with no clear scene that week, keeps the Sentinel-2 evidence of the last one."""
    first = _first_check()
    nxt = freeze_lake(SHAZORE, _next_week(first), "2026-11-15", power=power_like(SHAZORE_AIR + [-5.0] * 3),
                      s2_check=lambda *a, **k: None, log=lambda m: None)
    f = nxt["freeze"]
    assert f["state"] == "frozen_s2" and f["s2"] is None and f["s2_evidence"]["date"] == "2026-11-08"
    assert "Snow or ice covers 94% of the lake zone seen clear in a Sentinel-2 scene of 8 Nov 2026" in f["reason"]
    assert "stands until a clear one shows open water" in f["reason"]


def test_the_summer_level_leaves_out_the_passes_flagged_frozen():
    """M7: a late ice-out pass flagged frozen does not pull the summer level it is compared with."""
    from sartale.freeze import refreshed_summer_ref

    def p(day, hh, dark, frozen=False):
        return {"date": day, "track": "084A", "excluded": None, "core_contrast_hh_db": hh, "core_contrast_hv_db": hh,
                "core_dark_share": dark, "frozen": frozen}
    series = [p("2026-06-25", -3.0, 0.4, True), p("2026-07-02", -3.0, 0.4, True), p("2026-07-19", -8.0, 0.95),
              p("2026-08-12", -8.0, 0.96), p("2026-08-31", -8.2, 0.97)]
    ref = refreshed_summer_ref(series, {"084A": {"core_px": 900}})["084A"]
    assert ref["passes"] == 3 and ref["core_contrast_hh_db"] == -8.0 and ref["core_dark_share"] == 0.96
    unflagged_ref = refreshed_summer_ref([{**q, "frozen": False} for q in series], {"084A": {"core_px": 900}})["084A"]
    assert unflagged_ref["passes"] == 5 and unflagged_ref["core_dark_share"] == 0.95


def test_power_start_reaches_back_to_the_season_each_pass_needs():
    # a June pass needs the winter before it: a lake frozen then may still be frozen in June
    series = [{"date": "2026-06-20"}, {"date": "2026-10-18"}]
    assert power_start(series, "2026-11-12") == "2025-09-01"
    assert power_start([{"date": "2026-10-18"}], "2027-11-12") == "2026-09-01"
    assert power_start([], "2026-07-15") == "2025-09-01"


def test_the_reason_never_claims_what_the_evidence_cannot_show():
    from sartale.lakestatus import day_text  # noqa: F401
    base = {"since": "2026-10-18", "temp_through": "2026-11-10", "cold_run_days": 30, "warm_run_days": 0,
            "fdd_since_sep": 150.0, "s2": None, "s2_searched": True, "in_season": True, "radar_assessed": True}
    texts = [freeze_reason({**base, "state": s, "since": None if s == "open" else base["since"]}, 4181)
             for s in ("frozen_likely", "breakup_likely", "open")]
    texts.append(freeze_reason({**base, "state": "frozen_s2", "s2": S2_SNOW, "s2_evidence": S2_SNOW}, 4181))
    # I3: a release is worded by what released it, never as open water from the air
    for by, words in (("air", "No freeze signal in air temperature since 24 Oct 2026; open water not confirmed by radar "
                              "or Sentinel-2"),
                      ("radar", "Radar back within its summer range on 24 Oct 2026"),
                      ("s2", "Open water seen by Sentinel-2 on 24 Oct 2026")):
        r = freeze_reason({**base, "state": "open", "released_by": by, "released_on": "2026-10-24"}, 4181)
        assert r.startswith(words), r
        assert "Open again" not in r and "open again since" not in r.lower()
        texts.append(r)
    for t in texts:
        low = t.lower()
        for word in ("safe", "thick", "radar shows ice", "radar saw ice", "predict", "risk"):
            assert word not in low, (word, t)
    assert "Air temperature alone cannot show that the lake is open." in texts[2]


def test_the_lakes_freeze_command_sets_each_lake_again_and_is_idempotent(tmp_path, monkeypatch, capsys):
    import json

    from sartale import freeze, run_pipeline
    lakes_in = tmp_path / "lakes_in.json"
    lakes_in.write_text(json.dumps([
        {"id": "shazore", "name": "Shazore", "lon": 72.1741, "lat": 35.7794, "role": "watch", "coord_source": "x",
         "outline": None, "downstream": None, "downstream_source": None, "elevation_m": 4181,
         "elevation_source": "Copernicus DEM GLO-30"},
        {"id": "dry", "name": "Dry", "lon": 72.0, "lat": 35.7, "role": "watch", "coord_source": "x",
         "outline": None, "downstream": None, "downstream_source": None, "lake_state": "no_lake",
         "lake_state_source": "a dry basin"}]), encoding="utf-8")
    dry = {**shazore_entry(), "id": "dry", "lake_state": "no_lake",
           "status": {"status": "No lake now", "track": "084A", "latest_date": "2026-10-30", "looks": 7, "reason": "r"}}
    out = tmp_path / "out"
    out.mkdir()
    (out / "lakes.json").write_text(json.dumps({"lakes": [shazore_entry(), dry]}), encoding="utf-8")
    monkeypatch.setattr(freeze, "fetch_power", power_like(SHAZORE_AIR))
    monkeypatch.setattr(freeze, "s2_scene_check", lambda lake, today, log, **k: S2_SNOW)
    args = ["lakes-freeze", "--lakes-in", str(lakes_in), "--out", str(out), "--today", "2026-11-12"]
    run_pipeline.main(args)
    first = (out / "lakes.json").read_text(encoding="utf-8")
    doc = json.loads(first)
    assert doc["lakes"][0]["status"]["status"] == "Frozen (seen by Sentinel-2)"
    assert "freeze" not in doc["lakes"][1] and doc["lakes"][1]["status"]["status"] == "No lake now"
    log = capsys.readouterr().out
    assert "shazore: frozen_s2 since 2026-10-18" in log and "S2 2026-11-08 S2A_43SCV_20261108_0_L2A" in log
    run_pipeline.main(args)
    assert (out / "lakes.json").read_text(encoding="utf-8") == first


# --- NASA POWER ------------------------------------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, doc=None, fail=False):
        self.doc, self.fail = doc, fail

    def raise_for_status(self):
        if self.fail:
            raise RuntimeError("HTTP 503")

    def json(self):
        return self.doc


POWER_DOC = {"geometry": {"coordinates": [72.17, 35.78, 3718.79]},
             "properties": {"parameter": {"T2M": {"20261109": -2.5, "20261110": -999.0},
                                          "T2M_MIN": {"20261109": -8.0, "20261110": -999.0}}}}


def test_fetch_power_reads_the_cell_height_marks_missing_days_and_retries_once():
    calls = []

    def get(url, params, timeout):
        calls.append((url, params, timeout))
        return FakeResponse(fail=True) if len(calls) == 1 else FakeResponse(POWER_DOC)
    p = fetch_power(72.1741, 35.7794, "2026-09-01", "2026-11-12", get=get, pause_s=0)
    assert len(calls) == 2 and calls[0][2] == 60
    assert calls[0][1]["start"] == "20260901" and calls[0][1]["end"] == "20261112"
    assert calls[0][1]["parameters"] == "T2M,T2M_MIN"
    assert p["cell_elev_m"] == 3718.79
    assert p["days"] == {"2026-11-09": {"t2m": -2.5, "t2m_min": -8.0}, "2026-11-10": {"t2m": None, "t2m_min": None}}
    with pytest.raises(RuntimeError):
        fetch_power(0, 0, "2026-09-01", "2026-09-02", get=lambda *a, **k: FakeResponse(fail=True), pause_s=0)


def test_the_lapse_correction_moves_air_to_the_lake_height():
    p = {"cell_elev_m": 4491.0, "days": {"2026-10-01": {"t2m": -11.0, "t2m_min": None}}}
    c = corrected(p, 2365.0)  # Attabad: 2.1 km below its POWER cell, +13.8 C
    assert c["2026-10-01"]["t2m"] == pytest.approx(-11.0 + 13.819, abs=1e-3) and c["2026-10-01"]["t2m_min"] is None
