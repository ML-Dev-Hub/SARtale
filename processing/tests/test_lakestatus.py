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
    assert len(STATUS_NAMES) == 7 and "Change not confirmed yet" in STATUS_NAMES


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
