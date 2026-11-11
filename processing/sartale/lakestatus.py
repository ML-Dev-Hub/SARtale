"""Per-lake series and same-track status for Lake Watch."""
from __future__ import annotations

from statistics import median
from typing import NotRequired, TypedDict

from .config import (
    CHANGE_FACTOR,
    CLOUD_WINDOW,
    MIN_LOOKS,
    MIN_OBSERVABLE,
    NOISE_FLOOR_KM2,
)


UNCONFIRMED = "Change not confirmed yet"
# A site the register marks lake_state "no_lake": recent imagery shows no lake there (an ice-dammed lake's empty
# basin, say). It gets no growing/shrinking verdict and its dark radar area is not lake area.
NO_LAKE = "No lake now"
# A "no lake now" site where the latest Sentinel-2 absence check found water on more than config.FORMING_WATER_SHARE
# of the lake zone: a lake may be forming. No verdict; SARtale measures it as a lake from the next NISAR pass.
LAKE_FORMING = "Lake may be forming"
# Every status a lake can have, in the order the app lists them (app/src/lakes.ts STATUS_ORDER).
STATUS_NAMES = (
    LAKE_FORMING,
    "Growing",
    "Shrinking",
    UNCONFIRMED,
    "Not seen this pass",
    "Stable",
    "Not enough NISAR looks yet",
    "Not observable",
    NO_LAKE,
)


class SeriesPoint(TypedDict):
    date: str  # ISO YYYY-MM-DD
    track: str  # e.g. "156A"
    area_km2: float | None
    observable_share: float
    excluded: str | None  # reason, or None
    crid: NotRequired[str]  # NISAR processing version (composite release ID) of the pass, e.g. "P05036"


def track_noise_km2(areas: list[float]) -> float:
    """Robust pass-to-pass noise of one track: 1.4826 * median(|diff|), floored."""
    if len(areas) < 3:
        return NOISE_FLOOR_KM2
    diffs = [abs(b - a) for a, b in zip(areas, areas[1:])]
    return max(1.4826 * median(diffs), NOISE_FLOOR_KM2)


def is_valid(p: SeriesPoint) -> bool:
    """A pass the status may use: not excluded, has an area, and enough of the zone observable."""
    return (
        p["excluded"] is None
        and p["area_km2"] is not None
        and p["observable_share"] >= MIN_OBSERVABLE
    )


def _result(status, track=None, latest_date=None, looks=0, change=None, noise=None, reason="", new_crid=None):
    """`new_crid` is set only for UNCONFIRMED: the processing version of the latest pass that the baseline lacks."""
    return {
        "status": status,
        "track": track,
        "latest_date": latest_date,
        "looks": looks,
        "change_km2": change,
        "noise_km2": noise,
        "reason": reason,
        "new_crid": new_crid,
    }


def lake_status(
    series: list[SeriesPoint], latest_expected: dict[str, str] | None = None
) -> dict:
    """Status of one lake, comparing passes of a single track only.

    `latest_expected` maps track key -> date of that track's newest pass that
    exists (excluded or not). "Not seen this pass" fires when, for some track,
    that newest pass is newer than the best track's latest valid date and has
    no valid point in `series` (excluded, unobservable or missing).

    Noise is measured on the best track's EARLIER valid areas only (latest point
    excluded), so a real change cannot inflate its own threshold.

    A change past the threshold is "Change not confirmed yet" (UNCONFIRMED) when the latest valid pass is on a
    processing version (CRID) that none of the earlier valid passes it is compared with has: a calibration change
    between versions can look like growth or shrinkage. A second pass on that version makes the version part of
    the baseline, and the usual Growing or Shrinking applies again.
    """
    if not any(p["observable_share"] >= MIN_OBSERVABLE for p in series):
        return _result(
            "Not observable",
            reason=f"Under {MIN_OBSERVABLE:.0%} of the lake zone is observable on every pass.",
        )

    valid = [p for p in series if is_valid(p)]
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
    noise = track_noise_km2(areas[:-1])
    reason = (f"Track {best}: {areas[-1]:.3f} km2 on {latest['date']} vs median {ref:.3f} of "
              f"{looks - 1} earlier looks (noise {noise:.3f} km2)")
    if change > CHANGE_FACTOR * noise:
        status = "Growing"
    elif change < -CHANGE_FACTOR * noise:
        status = "Shrinking"
    else:
        status = "Stable"
    new_crid = latest.get("crid")
    baseline_crids = {p.get("crid") for p in pts[:-1]} - {None}
    if status != "Stable" and new_crid and baseline_crids and new_crid not in baseline_crids:
        return _result(
            UNCONFIRMED, best, latest["date"], looks, change, noise,
            f"{reason}; this is the first pass on NISAR processing version {new_crid}, so the change waits for "
            "a second pass on that version.",
            new_crid,
        )
    return _result(status, best, latest["date"], looks, change, noise, reason + ".")


def cloud_window_looks(
    series: list[SeriesPoint], start: str = CLOUD_WINDOW[0], end: str = CLOUD_WINDOW[1]
) -> int:
    """Valid, non-excluded points with enough observable zone, dated start..end inclusive."""
    return sum(1 for p in series if is_valid(p) and start <= p["date"] <= end)


_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def day_text(iso: str) -> str:
    """"2026-08-17" -> "17 Aug 2026" (the app's date style)."""
    y, m, d = (int(v) for v in iso.split("-"))
    return f"{d} {_MONTHS[m - 1]} {y}"


def share_text(share: float) -> str:
    """0.0004 -> "0.04%", 0.0123 -> "1.2%", 0 -> "0%"."""
    pct = 100 * share
    if pct == 0:
        return "0%"
    return f"{pct:.2f}%" if pct < 1 else f"{pct:.1f}%"


def absence_sentence(absence: dict | None) -> str:
    """The dated evidence of an absence check in words, or "" when there is none."""
    if not absence:
        return ""
    return (f"Last checked {day_text(absence['date'])} with Sentinel-2 ({absence['s2_id']}): water on "
            f"{share_text(absence['water_share'])} of the lake zone.")


def no_lake_status(computed: dict, source: str | None, absence: dict | None = None) -> dict:
    """The status of a site with no lake now: keeps the track, latest date and looks the passes give (so the site's
    picture and pass count still show), drops any change and noise, and says why, with the date of the last
    Sentinel-2 absence check when there is one."""
    why = f"No lake in recent imagery: {source.rstrip('.')}." if source else "No lake in recent imagery."
    checked = absence_sentence(absence)
    tail = "SARtale re-checks the site with Sentinel-2 in each open-water season for a lake forming."
    reason = " ".join(t for t in (why, checked, tail) if t)
    return _result(NO_LAKE, computed["track"], computed["latest_date"], computed["looks"], reason=reason)


def forming_status(computed: dict, absence: dict) -> dict:
    """The status of a "no lake now" site where Sentinel-2 found water: a lake may be forming. No growing or
    shrinking verdict; the track, latest date and looks are those the passes give."""
    reason = (f"Sentinel-2 on {day_text(absence['date'])} ({absence['s2_id']}) shows water on "
              f"{share_text(absence['water_share'])} of the lake zone ({absence['water_km2']:.3f} km2), where recent "
              "imagery had no lake. A lake may be forming; SARtale measures it from the next NISAR pass.")
    return _result(LAKE_FORMING, computed["track"], computed["latest_date"], computed["looks"], reason=reason)
