"""Per-lake series and same-track status for Lake Watch."""
from __future__ import annotations

from statistics import median
from typing import TypedDict

from .config import (
    CHANGE_FACTOR,
    CLOUD_WINDOW,
    MIN_LOOKS,
    MIN_OBSERVABLE,
    NOISE_FLOOR_KM2,
)


class SeriesPoint(TypedDict):
    date: str  # ISO YYYY-MM-DD
    track: str  # e.g. "156A"
    area_km2: float | None
    observable_share: float
    excluded: str | None  # reason, or None


def track_noise_km2(areas: list[float]) -> float:
    """Robust pass-to-pass noise of one track: 1.4826 * median(|diff|), floored."""
    if len(areas) < 3:
        return NOISE_FLOOR_KM2
    diffs = [abs(b - a) for a, b in zip(areas, areas[1:])]
    return max(1.4826 * median(diffs), NOISE_FLOOR_KM2)


def _is_valid(p: SeriesPoint) -> bool:
    return (
        p["excluded"] is None
        and p["area_km2"] is not None
        and p["observable_share"] >= MIN_OBSERVABLE
    )


def _result(status, track=None, latest_date=None, looks=0, change=None, noise=None, reason=""):
    return {
        "status": status,
        "track": track,
        "latest_date": latest_date,
        "looks": looks,
        "change_km2": change,
        "noise_km2": noise,
        "reason": reason,
    }


def lake_status(
    series: list[SeriesPoint], latest_expected: dict[str, str] | None = None
) -> dict:
    """Status of one lake, comparing passes of a single track only.

    `latest_expected` maps track key -> date of that track's newest pass that
    exists (excluded or not). "Not seen this pass" fires when, for some track,
    that newest pass is newer than the best track's latest valid date and has
    no valid point in `series` (excluded, unobservable or missing).
    """
    if not any(p["observable_share"] >= MIN_OBSERVABLE for p in series):
        return _result(
            "Not observable",
            reason=f"Under {MIN_OBSERVABLE:.0%} of the lake zone is observable on every pass.",
        )

    valid = [p for p in series if _is_valid(p)]
    by_track: dict[str, list[SeriesPoint]] = {}
    for p in valid:
        by_track.setdefault(p["track"], []).append(p)
    if not by_track:
        return _result(
            "Not enough NISAR looks yet",
            reason="No valid pass yet (all excluded or without an area).",
        )
    for pts in by_track.values():
        pts.sort(key=lambda p: p["date"])

    best = max(by_track, key=lambda t: (by_track[t][-1]["date"], len(by_track[t])))
    pts = by_track[best]
    latest = pts[-1]
    looks = len(pts)

    if looks < MIN_LOOKS:
        return _result(
            "Not enough NISAR looks yet",
            best,
            latest["date"],
            looks,
            reason=f"{looks} valid look(s) on track {best}; {MIN_LOOKS} needed.",
        )

    if latest_expected:
        valid_keys = {(p["track"], p["date"]) for p in valid}
        for track in sorted(latest_expected):
            d = latest_expected[track]
            if d > latest["date"] and (track, d) not in valid_keys:
                return _result(
                    "Not seen this pass",
                    best,
                    latest["date"],
                    looks,
                    reason=f"Newest pass {track} {d} is excluded or has no valid reading.",
                )

    areas = [p["area_km2"] for p in pts]
    ref = median(areas[:-1])
    change = areas[-1] - ref
    noise = track_noise_km2(areas)
    if change > CHANGE_FACTOR * noise:
        status = "Growing"
    elif change < -CHANGE_FACTOR * noise:
        status = "Shrinking"
    else:
        status = "Stable"
    return _result(
        status,
        best,
        latest["date"],
        looks,
        change,
        noise,
        f"Track {best}: {areas[-1]:.3f} km2 on {latest['date']} vs median {ref:.3f} of "
        f"{looks - 1} earlier looks (noise {noise:.3f} km2).",
    )


def cloud_window_looks(
    series: list[SeriesPoint], start: str = CLOUD_WINDOW[0], end: str = CLOUD_WINDOW[1]
) -> int:
    """Valid, non-excluded points with enough observable zone, dated start..end inclusive."""
    return sum(1 for p in series if _is_valid(p) and start <= p["date"] <= end)
