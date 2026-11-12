from sartale.config import NOISE_FLOOR_KM2
from sartale.lakestatus import cloud_window_looks, lake_status, track_noise_km2


def pt(date, track, area, share=1.0, excluded=None):
    return {"date": date, "track": track, "area_km2": area,
            "observable_share": share, "excluded": excluded}


def flat(track, areas, start=1, share=1.0):
    return [pt(f"2026-09-{start + i:02d}", track, a, share) for i, a in enumerate(areas)]


NOISY = [1.00, 1.02, 0.99, 1.01, 1.00]


def test_status_growing():
    s = lake_status(flat("156A", NOISY + [1.5]))
    assert s["status"] == "Growing"
    assert s["track"] == "156A" and s["looks"] == 6
    assert s["latest_date"] == "2026-09-06"
    assert s["change_km2"] > 0.4


def test_status_shrinking():
    s = lake_status(flat("156A", NOISY + [0.5]))
    assert s["status"] == "Shrinking"
    assert s["change_km2"] < 0


def test_status_stable_within_noise():
    s = lake_status(flat("156A", NOISY + [1.01]))
    assert s["status"] == "Stable"


def test_status_not_observable_when_hidden():
    s = lake_status(flat("156A", NOISY, share=0.3))
    assert s["status"] == "Not observable"


def test_status_not_enough_looks():
    s = lake_status(flat("156A", [1.0, 1.1]))
    assert s["status"] == "Not enough NISAR looks yet"
    assert s["looks"] == 2


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
    assert s["status"] == "Stable"


def test_status_never_compares_across_tracks():
    series = flat("156A", [1.0, 1.0, 1.0, 1.0]) + [
        pt(f"2026-08-{i + 1:02d}", "063D", 3.0) for i in range(4)]
    s = lake_status(series)
    assert s["status"] == "Stable"
    assert s["track"] == "156A"  # newest latest valid point


def test_noise_floor():
    assert track_noise_km2([1.0, 1.0]) == NOISE_FLOOR_KM2
    assert track_noise_km2([1.0, 1.0, 1.0, 1.0]) == NOISE_FLOOR_KM2
    assert track_noise_km2([1.0, 1.1, 1.0, 1.1]) > NOISE_FLOOR_KM2


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


def test_status_growing_with_three_looks():
    s = lake_status(flat("156A", [1.0, 1.0, 1.5]))
    assert s["status"] == "Growing"
    assert s["noise_km2"] == NOISE_FLOOR_KM2


def test_status_observable_but_none_valid():
    series = [pt("2026-09-01", "156A", None, 0.8, excluded="bright outlier")]
    s = lake_status(series)
    assert s["status"] == "Not enough NISAR looks yet"
    assert s["track"] is None and s["looks"] == 0


def versioned(track, areas, crids, start=1):
    return [{**pt(f"2026-10-{start + i:02d}", track, a), "crid": c} for i, (a, c) in enumerate(zip(areas, crids))]


OLD5 = ["P05023"] * 5


def test_a_change_on_the_first_pass_of_a_new_processing_version_is_not_confirmed():
    from sartale.lakestatus import UNCONFIRMED
    s = lake_status(versioned("084A", NOISY + [1.5], OLD5 + ["P05036"]))
    assert s["status"] == UNCONFIRMED == "Change not confirmed yet"
    assert s["change_km2"] > 0.4 and s["noise_km2"] is not None and s["looks"] == 6 and s["new_crid"] == "P05036"
    assert s["reason"].startswith("Track 084A: 1.500 km2 on 2026-10-06 vs median 1.000 of 5 earlier looks (noise ")
    assert s["reason"].endswith("km2); this is the first pass on NISAR processing version P05036, so the change "
                                "waits for a second pass on that version.")
    shrink = lake_status(versioned("084A", NOISY + [0.5], OLD5 + ["P05036"]))
    assert shrink["status"] == UNCONFIRMED and shrink["change_km2"] < 0


def test_a_second_pass_on_the_new_version_confirms_the_change():
    s = lake_status(versioned("084A", NOISY + [1.5, 1.5], OLD5 + ["P05036", "P05036"]))
    assert s["status"] == "Growing" and s["new_crid"] is None
    assert s["reason"].endswith("km2).")


def test_a_within_noise_change_on_a_new_version_stays_stable():
    s = lake_status(versioned("084A", NOISY + [1.01], OLD5 + ["P05036"]))
    assert s["status"] == "Stable" and s["new_crid"] is None


def test_without_crids_or_on_the_same_version_the_usual_rule_applies():
    assert lake_status(flat("156A", NOISY + [1.5]))["status"] == "Growing"
    assert lake_status(versioned("156A", NOISY + [1.5], ["P05036"] * 6))["status"] == "Growing"


def test_the_status_names_list_every_status():
    from sartale.lakestatus import STATUS_NAMES
    assert len(STATUS_NAMES) == 12 and "Change not confirmed yet" in STATUS_NAMES and STATUS_NAMES[-1] == "No lake now"
    assert STATUS_NAMES[0] == "Lake may be forming"
    # the app lists the frozen statuses right after "Change not confirmed yet"
    at = STATUS_NAMES.index("Change not confirmed yet")
    assert STATUS_NAMES[at + 1:at + 4] == ("Frozen (likely)", "Frozen (seen by Sentinel-2)", "Break-up likely")


def frozen_pt(date, track, area, crid="P05036"):
    return {**pt(date, track, area), "crid": crid, "frozen": True}


def test_frozen_passes_keep_their_area_but_leave_the_baseline_and_noise():
    from sartale.lakestatus import is_valid, open_water_status
    # five open-water passes, then two passes taken while frozen that read the lake 50% larger
    series = flat("084A", NOISY) + [frozen_pt("2026-10-18", "084A", 1.5), frozen_pt("2026-10-30", "084A", 1.5)]
    assert not is_valid(series[-1]) and series[-1]["area_km2"] == 1.5
    s = open_water_status(series)
    assert s["status"] == "Stable" and s["latest_date"] == "2026-09-05" and s["looks"] == 5
    # the same passes without the flag would read as growth
    assert lake_status([{**p, "frozen": False} for p in series])["status"] in ("Growing", "Change not confirmed yet")
    # a frozen newest pass is left out, not missed: no "Not seen this pass"
    assert s["status"] != "Not seen this pass"


def test_frozen_status_takes_precedence_over_change_not_confirmed_yet():
    from sartale.lakestatus import FROZEN_LIKELY, UNCONFIRMED, frozen_status
    computed = lake_status(versioned("084A", NOISY + [1.5], OLD5 + ["P05036"]))
    assert computed["status"] == UNCONFIRMED
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


def test_the_app_lists_the_same_statuses_and_styles_the_unconfirmed_one_as_neutral():
    import re
    from pathlib import Path
    from sartale.lakestatus import STATUS_NAMES
    app = Path(__file__).resolve().parents[2] / "app" / "src"
    ts = (app / "lakes.ts").read_text(encoding="utf-8")
    order = re.search(r"STATUS_ORDER: LakeStatusName\[\] = \[(.*?)\];", ts, re.S).group(1)
    assert tuple(re.findall(r'"([^"]+)"', order)) == STATUS_NAMES
    css = (app / "styles.css").read_text(encoding="utf-8").splitlines()
    chip = next(line for line in css if ".lw-status-change-not-confirmed-yet" in line)
    pin = next(line for line in css if '.lw-marker[data-status="change-not-confirmed-yet"]' in line)
    assert "border-style: dashed" in chip and "--warm" not in chip
    assert "background: transparent" in pin and "--warm" not in pin
    for slug in ("no-lake-now",):  # a site with no lake is neutral too, never the change colour
        chip = next(line for line in css if f".lw-status-{slug}" in line)
        pin = next(line for line in css if f'.lw-marker[data-status="{slug}"]' in line)
        assert "border-style: dashed" in chip and "--warm" not in chip
        assert "background: transparent" in pin and "--warm" not in pin


def test_no_lake_status_carries_the_dated_absence_check():
    from sartale.lakestatus import NO_LAKE, no_lake_status
    computed = {"track": "156A", "latest_date": "2026-11-04", "looks": 6}
    ev = {"date": "2026-08-17", "s2_id": "S2B_43SFA_20260817_0_L2A", "water_share": 0.0004, "water_km2": 0.0012}
    s = no_lake_status(computed, "a dry basin", ev)
    assert s["status"] == NO_LAKE and s["change_km2"] is None
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
