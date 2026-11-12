import pytest

from sartale.config import NOISE_FLOOR_KM2
from sartale.lake_requests import find_banned_claims
from sartale.lakestatus import (
    ALERT,
    DECREASE,
    NO_CHANGE,
    WATCH,
    assess,
    cloud_window_looks,
    lake_status,
    pass_noise_km2,
    track_noise_km2,
)


def pt(date, track, area, share=1.0, excluded=None, crid=None, frozen=None):
    p = {"date": date, "track": track, "area_km2": area, "observable_share": share, "excluded": excluded}
    if crid:
        p["crid"] = crid
    if frozen is not None:
        p["frozen"] = frozen
    return p


def flat(track, areas, start=1, share=1.0, month="09", crid=None):
    return [pt(f"2026-{month}-{start + i:02d}", track, a, share, crid=crid) for i, a in enumerate(areas)]


NOISY = [1.00, 1.02, 0.99, 1.01, 1.00]  # track noise 1.4826 x 0.02 = 0.030 km2


def levels(series):
    """(date, track, level) of every pass that set a level, in time order."""
    _, out = assess(series)
    rows = sorted((p for p in out if p.get("level_contrib")), key=lambda p: (p["date"], p["track"]))
    return [(p["date"], p["track"], p["level_contrib"]) for p in rows]


# --- the comparison: baseline, noise, z -------------------------------------------------------------------------------

def test_noise_floor():
    assert track_noise_km2([1.0, 1.0]) == NOISE_FLOOR_KM2
    assert track_noise_km2([1.0, 1.0, 1.0, 1.0]) == NOISE_FLOOR_KM2
    assert track_noise_km2([1.0, 1.1, 1.0, 1.1]) > NOISE_FLOOR_KM2


def test_the_pass_noise_is_floored_at_2_percent_of_the_baseline_or_0_005_km2():
    # a steady large lake: 2% of a 1 km2 baseline (0.02) beats the 0.005 km2 floor
    assert pass_noise_km2([1.0] * 5, 1.0) == pytest.approx(0.02)
    # a steady small lake: 0.005 km2 beats 2% of 0.1 km2 (0.002)
    assert pass_noise_km2([0.1] * 5, 0.1) == NOISE_FLOOR_KM2
    # a noisy track keeps its own noise
    assert pass_noise_km2(NOISY, 1.0) == pytest.approx(1.4826 * 0.02)
    # only the 8 latest earlier passes count: an old jump falls out of the noise
    assert pass_noise_km2([1.0, 2.0, 1.0] + [1.0] * 8, 1.0) == pytest.approx(0.02)


def test_each_pass_is_compared_with_the_median_of_up_to_6_earlier_passes_on_its_own_track():
    series = flat("156A", [5.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.06])
    _, out = assess(series)
    last = out[-1]
    assert last["baseline_km2"] == 1.0  # the old 5.0 is the 7th pass back: out of the baseline
    assert last["noise_km2"] == pytest.approx(0.02) and last["z"] == pytest.approx(3.0)
    # the first three passes of a track have nothing to be compared with
    assert [p["z"] for p in out[:3]] == [None, None, None] and out[3]["z"] is not None


def test_status_never_compares_across_tracks():
    series = flat("156A", [1.0, 1.0, 1.0, 1.0]) + [pt(f"2026-08-{i + 1:02d}", "063D", 3.0) for i in range(4)]
    s = lake_status(series)
    assert s["status"] == NO_CHANGE and s["track"] == "156A"
    assert s["baseline_km2"] == 1.0


# --- the levels -------------------------------------------------------------------------------------------------------

def test_no_change_within_twice_the_noise():
    s = lake_status(flat("156A", NOISY + [1.01]))
    assert s["status"] == NO_CHANGE == s["level"] and s["message"] is None and s["level_passes"] == []
    assert s["change_km2"] == pytest.approx(0.01) and s["z"] == pytest.approx(0.0, abs=0.5)


def test_one_pass_beyond_twice_the_noise_is_a_watch_with_its_reason():
    s = lake_status(flat("156A", NOISY + [1.5]), name="Passu Lake")
    assert s["status"] == WATCH and s["track"] == "156A" and s["looks"] == 6 and s["latest_date"] == "2026-09-06"
    assert s["change_km2"] == pytest.approx(0.5) and s["z"] > 2
    assert s["reason"].endswith("one pass beyond 2× noise.")
    assert [p["date"] for p in s["level_passes"]] == ["2026-09-06"] and s["level_since"] == "2026-09-06"
    m = s["message"]
    assert m["level"] == WATCH and m["title"] == "Watch: one radar pass of Passu Lake is beyond 2× noise."
    assert m["what"] == ("Radar water area of Passu Lake: 1.500 km² on 6 Sep 2026 (156A), +0.500 km² (+50%) against its "
                         "baseline of 1.000 km² from earlier 156A passes.")
    assert "One pass only (z = +16.9" in m["how_sure"] and "not confirmed" in m["how_sure"]
    shrink = lake_status(flat("156A", NOISY + [0.5]))
    assert shrink["status"] == WATCH and shrink["change_km2"] < 0
    # a Watch on a falling area says how little of a drawdown radar sees
    assert "a tenth to a fifth" in shrink["message"]["not"]


def test_two_passes_in_a_row_beyond_twice_the_noise_are_an_alert_growing():
    s = lake_status(flat("156A", NOISY + [1.5, 1.5]), name="Passu Lake")
    assert s["status"] == ALERT == "Alert: growing"
    assert [p["date"] for p in s["level_passes"]] == ["2026-09-06", "2026-09-07"]
    assert s["level_since"] == "2026-09-07"
    m = s["message"]
    assert m["title"] == "Alert: growing: the radar water area of Passu Lake rose on two passes in a row."
    assert "on the pass before, 1.500 km² on 6 Sep 2026 (156A)" in m["what"]
    assert m["how_sure"].startswith("Two passes in a row beyond 2× their track's noise: z = +16.9 and +16.7 (noise ±0.030 and "
                                      "±0.030 km²).")


def test_a_two_pass_alert_can_span_two_tracks_each_against_its_own_baseline():
    a = [pt(f"2026-08-{d:02d}", "156A", v) for d, v in zip((1, 13, 25), (1.0, 1.02, 0.99))]
    b = [pt(f"2026-08-{d:02d}", "063D", v) for d, v in zip((6, 18, 30), (0.50, 0.51, 0.49))]
    grow = [pt("2026-09-06", "156A", 1.3), pt("2026-09-11", "063D", 0.65)]
    s = lake_status(a + b + grow)
    assert s["status"] == ALERT and [p["track"] for p in s["level_passes"]] == ["156A", "063D"]
    assert all(p["z"] >= 2 for p in s["level_passes"])
    # the same areas on the other track would be no growth: each pass is measured against its own track
    assert lake_status(a + b + [pt("2026-09-06", "156A", 0.65)])["status"] != ALERT


def test_a_decrease_on_two_passes_is_decrease_noted_and_never_an_alert():
    s = lake_status(flat("156A", NOISY + [0.5, 0.5]), name="Attabad Lake")
    assert s["status"] == DECREASE == "Decrease noted"
    m = s["message"]
    assert m["title"] == "Decrease noted: the radar water area of Attabad Lake fell on two passes in a row."
    assert m["not"].startswith("Information only, not an Alert: the radar sees a drawdown onto wet sediment at only "
                               "about a tenth to a fifth of its size")
    assert "check optical imagery" in m["not"].lower()
    # however large and however long, a falling area never makes an Alert
    big = lake_status(flat("156A", NOISY + [0.1, 0.1, 0.05, 0.05]))
    assert big["status"] == DECREASE
    assert ALERT not in [lv for *_, lv in levels(flat("156A", NOISY + [0.1, 0.1, 0.05, 0.05]))]
    # a rise and a fall in a row are no pair
    assert lake_status(flat("156A", NOISY + [1.5, 0.5]))["status"] == WATCH


def test_the_two_pass_decrease_replaces_the_watch_of_its_first_pass():
    got = levels(flat("156A", NOISY + [0.5, 0.5]))
    assert got[-2:] == [("2026-09-06", "156A", WATCH), ("2026-09-07", "156A", DECREASE)]


def test_a_cusum_reaching_4_is_a_watch_when_no_single_pass_is_beyond_twice_the_noise():
    # baseline 1.0 with no spread: noise 2% of 1.0 = 0.02; +0.038 a pass is z = 1.9 (< 2), CUSUM 1.4, 2.8, 4.2
    series = flat("156A", [1.0] * 6 + [1.038] * 3)
    got = levels(series)
    assert [lv for *_, lv in got[-3:]] == [NO_CHANGE, NO_CHANGE, WATCH]
    s = lake_status(series)
    assert s["status"] == WATCH and s["z"] == pytest.approx(1.9)
    assert "the CUSUM of the z values reached 4.2 (a Watch at 4)" in s["reason"]
    assert s["message"]["title"].startswith("Watch: small changes in the radar water area")
    assert "(CUSUM, k = 0.5) reached 4.2, at least 4" in s["message"]["how_sure"]
    assert s["cusum"] == {"up": 0.0, "down": 0.0}  # it starts again once it has made a Watch


def test_level_since_is_the_first_pass_of_the_current_level():
    s = lake_status(flat("156A", NOISY + [1.5, 1.5, 1.5]))
    assert s["status"] == ALERT and s["level_since"] == "2026-09-07"
    s = lake_status(flat("156A", NOISY + [1.0, 1.01]))
    assert s["status"] == NO_CHANGE and s["level_since"] == "2026-09-04"


# --- the version rule -------------------------------------------------------------------------------------------------

def versioned(track, areas, crids, start=1):
    return [{**pt(f"2026-10-{start + i:02d}", track, a), "crid": c} for i, (a, c) in enumerate(zip(areas, crids))]


OLD5 = ["P05023"] * 5


def test_the_first_pass_on_a_new_processing_version_can_watch_but_not_alert():
    s = lake_status(versioned("084A", NOISY + [1.5], OLD5 + ["P05036"]))
    assert s["status"] == WATCH and s["alerts_paused"] == {"crid": "P05036", "track": "084A", "date": "2026-10-06"}
    assert ("Alerts are paused: this is the first 084A pass on NISAR processing version P05036, which its baseline "
            "lacks") in s["reason"]
    assert "it can raise a Watch but not an Alert" in s["message"]["how_sure"]
    assert s["level_passes"][0]["new_version"] is True
    # the second pass on the new version: its baseline has the version now, but its pair is the first pass: no Alert
    two = lake_status(versioned("084A", NOISY + [1.5, 1.5], OLD5 + ["P05036"] * 2))
    assert two["status"] == WATCH and two["alerts_paused"] is None
    # the third: both passes of the pair have the version in their baselines
    three = lake_status(versioned("084A", NOISY + [1.5, 1.5, 1.5], OLD5 + ["P05036"] * 3))
    assert three["status"] == ALERT


def test_when_every_track_switches_version_alerts_wait_for_a_second_pass_on_a_track():
    a = [{**pt(f"2026-09-{d:02d}", "156A", 1.0), "crid": "P05023"} for d in (1, 5, 9, 13)]
    b = [{**pt(f"2026-09-{d:02d}", "063D", 1.0), "crid": "P05023"} for d in (3, 7, 11, 15)]
    new = [{**pt("2026-09-17", "156A", 1.5), "crid": "P05036"}, {**pt("2026-09-19", "063D", 1.5), "crid": "P05036"}]
    s = lake_status(a + b + new)
    assert s["status"] == WATCH and s["alerts_paused"]["crid"] == "P05036"
    more = new + [{**pt("2026-09-21", "156A", 1.5), "crid": "P05036"}, {**pt("2026-09-23", "063D", 1.5), "crid": "P05036"}]
    assert lake_status(a + b + more)["status"] == ALERT


def test_without_crids_or_on_the_same_version_the_usual_rule_applies():
    assert lake_status(flat("156A", NOISY + [1.5, 1.5]))["status"] == ALERT
    assert lake_status(versioned("156A", NOISY + [1.5, 1.5], ["P05036"] * 7))["status"] == ALERT


# --- frozen passes and the first passes after the lake opened ----------------------------------------------------------

def frozen_pt(date, track, area, crid="P05036"):
    return {**pt(date, track, area), "crid": crid, "frozen": True}


def test_frozen_passes_keep_their_area_but_are_never_compared():
    from sartale.lakestatus import is_valid, open_water_status
    # five open-water passes, then two passes taken while frozen that read the lake 50% larger
    series = flat("084A", NOISY) + [frozen_pt("2026-10-18", "084A", 1.5), frozen_pt("2026-10-30", "084A", 1.5)]
    assert not is_valid(series[-1]) and series[-1]["area_km2"] == 1.5
    s, out = assess(series)
    assert s["status"] == NO_CHANGE and s["latest_date"] == "2026-09-05" and s["looks"] == 5
    assert "z" not in out[-1] and "level_contrib" not in out[-1]
    assert open_water_status(series)["status"] == NO_CHANGE
    # the same passes without the flag would make a level
    assert lake_status([{**p, "frozen": False} for p in series])["status"] in (WATCH, ALERT)
    # a frozen newest pass is left out, not missed: no "Not seen this pass"
    assert open_water_status(series)["status"] != "Not seen this pass"


def test_the_first_two_passes_per_track_after_the_lake_opened_only_rebuild_the_baseline():
    # summer, a frozen winter, then the lake opens bigger than last summer on two passes
    series = (flat("084A", NOISY, month="09") + [frozen_pt("2026-11-01", "084A", 1.6)]
              + [pt("2027-06-01", "084A", 1.5), pt("2027-06-13", "084A", 1.5)])
    s, out = assess(series)
    assert [p.get("after_open") for p in out[-2:]] == [True, True]
    assert [p["level_contrib"] for p in out[-2:]] == [None, None] and all(p["z"] > 2 for p in out[-2:])
    assert s["status"] == NO_CHANGE and "only rebuilds the baseline after the lake opened" in s["reason"]
    # the third pass after opening is compared as usual, but its pair is a rebuilding pass: a Watch, not an Alert
    third = series + [pt("2027-06-25", "084A", 1.5)]
    assert lake_status(third)["status"] == WATCH
    # the fourth pairs with the third: both are ordinary passes now
    assert lake_status(third + [pt("2027-07-07", "084A", 1.5)])["status"] == ALERT


def test_a_frozen_spell_breaks_a_pass_pair_and_restarts_the_cusum():
    # z of about +1.9 a pass: the CUSUM is at 2.8 after two passes, then the lake freezes
    before = flat("084A", [1.0] * 6 + [1.038] * 2, month="09")
    assert lake_status(before)["cusum"]["up"] == pytest.approx(2.8)
    s = lake_status(before + [frozen_pt("2026-10-20", "084A", 1.2)])
    assert s["cusum"]["up"] == pytest.approx(2.8)  # the status is the last open pass's
    after = before + [frozen_pt("2026-10-20", "084A", 1.2), pt("2027-06-01", "084A", 1.038),
                      pt("2027-06-13", "084A", 1.038), pt("2027-06-25", "084A", 1.038)]
    _, out = assess(after)
    # the passes after the freeze rebuild, then the CUSUM starts from zero: no Watch from the sum before the freeze
    assert [p.get("level_contrib") for p in out[-3:]] == [None, None, NO_CHANGE]
    # a Watch before the freeze cannot pair with an open pass after it
    got = levels(flat("084A", NOISY + [1.5], month="09") + [frozen_pt("2026-10-20", "084A", 1.5),
                                                            pt("2027-06-01", "084A", 1.5)])
    assert got[-1] == ("2026-09-06", "084A", WATCH)


# --- what gets no level -------------------------------------------------------------------------------------------------

def test_status_not_observable_when_hidden():
    s = lake_status(flat("156A", NOISY, share=0.3))
    assert s["status"] == "Not observable" and s["level"] is None


def test_status_not_enough_looks():
    s = lake_status(flat("156A", [1.0, 1.1, 1.0]))
    assert s["status"] == "Not enough NISAR looks yet"
    assert s["looks"] == 3 and "a pass is compared once its track has 3 earlier valid looks" in s["reason"]


def test_status_observable_but_none_valid():
    series = [pt("2026-09-01", "156A", None, 0.8, excluded="bright outlier")]
    s = lake_status(series)
    assert s["status"] == "Not enough NISAR looks yet"
    assert s["track"] is None and s["looks"] == 0


def test_a_lake_whose_sentinel2_check_overlaps_under_0_4_is_not_measurable():
    v = {"iou": 0.31, "nisar_date": "2026-08-29", "s2_date": "2026-08-29"}
    s = lake_status(flat("156A", NOISY + [1.5, 1.5]), validation=v)
    assert s["status"] == "Not measurable" and s["level"] is None and s["message"] is None
    assert s["change_km2"] is None and s["noise_km2"] is None
    assert s["reason"] == ("Radar water area 1.500 km² on 7 Sep 2026 (156A), shown as information only: in its "
                           "Sentinel-2 check (29 Aug 2026 against Sentinel-2 of 29 Aug 2026) the radar water overlapped "
                           "optical water with IoU 0.31, under the 0.4 SARtale needs to give a level.")
    assert lake_status(flat("156A", NOISY + [1.5, 1.5]), validation={"iou": 0.4})["status"] == ALERT
    assert lake_status(flat("156A", NOISY + [1.5, 1.5]), validation=None)["status"] == ALERT
    # a check without an IoU (a note) is no evidence either way
    assert lake_status(flat("156A", NOISY + [1.5, 1.5]), validation={"iou": None})["status"] == ALERT
    # and under 50% of the zone observable is "Not observable", ahead of it
    assert lake_status(flat("156A", NOISY, share=0.3), validation=v)["status"] == "Not observable"


def test_status_not_seen_when_latest_excluded():
    series = flat("156A", NOISY + [1.0]) + [
        pt("2026-09-10", "063D", None, 0.0, excluded="bright outlier")]
    expected = {"156A": "2026-09-06", "063D": "2026-09-10"}
    s = lake_status(series, latest_expected=expected)
    assert s["status"] == "Not seen this pass"
    assert "063D" in s["reason"] and "2026-09-10" in s["reason"]
    # missing entirely from the series also counts
    s = lake_status(flat("156A", NOISY + [1.0]), latest_expected=expected)
    assert s["status"] == "Not seen this pass"
    # up to date: no flag
    s = lake_status(flat("156A", NOISY + [1.0]), latest_expected={"156A": "2026-09-06"})
    assert s["status"] == NO_CHANGE


def test_the_status_precedence():
    """No lake now > Frozen / Break-up > Not observable / Not measurable / Not enough looks / Not seen > Alert > Watch >
    Decrease noted > No change. (No lake now and Frozen are set by their callers, over any of these.)"""
    from sartale.lakestatus import frozen_status, no_lake_status
    alert = flat("156A", NOISY + [1.5, 1.5])
    assert lake_status(alert)["status"] == ALERT
    expected = {"156A": "2026-09-07", "063D": "2026-09-10"}
    assert lake_status(alert, latest_expected=expected)["status"] == "Not seen this pass"
    assert lake_status(alert, validation={"iou": 0.2}, latest_expected=expected)["status"] == "Not measurable"
    assert lake_status([{**p, "observable_share": 0.2} for p in alert], validation={"iou": 0.2})["status"] == \
        "Not observable"
    frozen = frozen_status(lake_status(alert), {"state": "frozen_likely", "reason": "r"})
    assert frozen["status"] == "Frozen (likely)" and frozen["level"] is None and frozen["message"] is None
    assert no_lake_status(lake_status(alert), "dry basin")["status"] == "No lake now"
    # among the levels: an Alert beats the Watch its second pass would be alone
    assert levels(alert)[-1][2] == ALERT


def test_cloud_window_counts_only_valid_points_in_dates():
    series = [
        pt("2026-06-16", "156A", 1.0),
        pt("2026-06-17", "156A", 1.0),
        pt("2026-07-01", "156A", 1.0, share=0.4),
        pt("2026-07-05", "156A", None, excluded="bright"),
        pt("2026-07-10", "063D", 1.0),
        pt("2026-08-04", "063D", 1.0),
        pt("2026-08-05", "063D", 1.0),
    ]
    assert cloud_window_looks(series) == 3


def test_a_look_at_a_frozen_lake_still_counts_in_the_cloud_window():
    series = [{**pt("2026-06-25", "164D", 0.07), "frozen": True}, pt("2026-07-19", "164D", 0.09)]
    assert cloud_window_looks(series) == 2


# --- the message --------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("areas", [NOISY + [1.5], NOISY + [1.5, 1.5], NOISY + [0.5, 0.5], [1.0] * 6 + [1.038] * 3,
                                   NOISY + [0.5]])
def test_every_message_says_what_changed_what_it_is_not_and_what_to_do(areas):
    s = lake_status(flat("156A", areas), name="Attabad Lake")
    m = s["message"]
    assert m["level"] == s["status"] and m["level"] in (ALERT, WATCH, DECREASE)
    assert "Radar water area of Attabad Lake" in m["what"] and "km²" in m["what"] and "2026" in m["what"]
    assert "%" in m["what"] and "baseline" in m["what"] and "z = " in m["how_sure"]
    assert "This is not an outburst forecast." in m["not"] and "5–12 days" in m["not"]
    assert "drawing down onto wet sediment poorly" in m["not"]
    assert m["do"] == ("Check recent optical imagery (Sentinel-2 or Landsat) or the site, and contact GBDMA or PDMA. "
                       "Official warnings come from PMD, NDMA, GBDMA and PDMA.")
    assert m["text"] == " ".join(m[k] for k in ("title", "what", "how_sure", "not", "do"))
    assert find_banned_claims(m["text"]) == []
    for word in ("hazard", "risk", "predict", "safe", "danger", "early warning"):
        assert word not in m["text"].lower()


# --- statuses shared with the app ----------------------------------------------------------------------------------------

def test_the_status_names_list_every_status():
    from sartale.lakestatus import STATUS_NAMES
    assert STATUS_NAMES == ("Alert: growing", "Lake may be forming", "Watch", "Decrease noted", "Frozen (likely)",
                            "Frozen (seen by Sentinel-2)", "Break-up likely", "Not seen this pass", "No change",
                            "Not enough NISAR looks yet", "Not measurable", "Not observable", "No lake now")
    assert "Change not confirmed yet" not in STATUS_NAMES


def test_frozen_status_takes_precedence_over_a_watch():
    from sartale.lakestatus import FROZEN_LIKELY, frozen_status
    computed = lake_status(versioned("084A", NOISY + [1.5], OLD5 + ["P05036"]))
    assert computed["status"] == WATCH
    freeze = {"state": "frozen_likely", "reason": "Probably frozen since 18 Oct 2026, ..."}
    s = frozen_status(computed, freeze)
    assert s["status"] == FROZEN_LIKELY and s["change_km2"] is None and s["noise_km2"] is None
    assert s["track"] == "084A" and s["latest_date"] == "2026-10-06" and s["reason"] == freeze["reason"]


def test_frozen_status_takes_precedence_over_the_data_statuses():
    from sartale.lakestatus import BREAKUP, FROZEN_S2, frozen_status
    for computed in (lake_status(flat("156A", [1.0, 1.1])), lake_status(flat("156A", NOISY, share=0.3))):
        assert computed["status"] in ("Not enough NISAR looks yet", "Not observable")
        assert frozen_status(computed, {"state": "frozen_s2", "reason": "r"})["status"] == FROZEN_S2
        assert frozen_status(computed, {"state": "breakup_likely", "reason": "r"})["status"] == BREAKUP


def test_the_app_lists_the_same_statuses_and_styles_the_levels_apart():
    import re
    from pathlib import Path
    from sartale.lakestatus import STATUS_NAMES
    app = Path(__file__).resolve().parents[2] / "app" / "src"
    ts = (app / "lakes.ts").read_text(encoding="utf-8")
    order = re.search(r"STATUS_ORDER: LakeStatusName\[\] = \[(.*?)\];", ts, re.S).group(1)
    assert tuple(re.findall(r'"([^"]+)"', order)) == STATUS_NAMES
    css = (app / "styles.css").read_text(encoding="utf-8").splitlines()
    # an Alert is told apart by more than colour: a solid fill and a heavier border
    chip = next(line for line in css if line.startswith(".lw-status-alert-growing"))
    assert "background" in chip and "border-width" in chip
    for slug in ("no-lake-now", "not-measurable"):  # no level here: neutral, never a level colour
        chip = next(line for line in css if f".lw-status-{slug}" in line)
        pin = next(line for line in css if f'.lw-marker[data-status="{slug}"]' in line)
        assert "border-style: dashed" in chip and "--warm" not in chip and "--alert" not in chip
        assert "background: transparent" in pin and "--warm" not in pin
    assert "change-not-confirmed-yet" not in "\n".join(css)


def test_no_lake_status_carries_the_dated_absence_check():
    from sartale.lakestatus import NO_LAKE, no_lake_status
    computed = {"track": "156A", "latest_date": "2026-11-04", "looks": 6}
    ev = {"date": "2026-08-17", "s2_id": "S2B_43SFA_20260817_0_L2A", "water_share": 0.0004, "water_km2": 0.0012}
    s = no_lake_status(computed, "a dry basin", ev)
    assert s["status"] == NO_LAKE and s["change_km2"] is None and s["level"] is None
    assert "Last checked 17 Aug 2026 with Sentinel-2 (S2B_43SFA_20260817_0_L2A): water on 0.04% of the lake zone." in s["reason"]
    assert "at every data refresh, all year" in s["reason"] and "open-water season" not in s["reason"]
    # I1/I2: when no clear, snow-free view has come since, the site says so instead of implying a recent check
    stale = no_lake_status(computed, "a dry basin", {**ev, "searched": "2026-11-12", "no_view_since": True})
    assert ("Last checked 17 Aug 2026 with Sentinel-2 (S2B_43SFA_20260817_0_L2A): water on 0.04% of the lake zone; "
            "no clear, snow-free Sentinel-2 view of the zone since (searched to 12 Nov 2026).") in stale["reason"]


def test_forming_status_says_a_lake_may_be_forming_without_a_verdict():
    from sartale.lakestatus import LAKE_FORMING, forming_status
    computed = {"track": "156A", "latest_date": "2026-09-04", "looks": 6}
    ev = {"date": "2026-09-01", "s2_id": "S2A_X", "water_share": 0.05, "water_km2": 0.157}
    s = forming_status(computed, ev)
    assert s["status"] == LAKE_FORMING and s["change_km2"] is None and s["noise_km2"] is None
    assert s["reason"].startswith("Sentinel-2 on 1 Sep 2026 (S2A_X) shows water on 5.0% of the lake zone (0.157 km2)")
    # I3: says what happens; nothing measures the site automatically
    assert "next NISAR pass" not in s["reason"] and "measures it" not in s["reason"]
    assert s["reason"].endswith("A lake may be forming. Its radar dark area is shown but not yet treated as lake "
                                "area; the SARtale team reviews the site to add it as a measured lake.")
