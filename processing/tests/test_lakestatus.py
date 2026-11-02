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
