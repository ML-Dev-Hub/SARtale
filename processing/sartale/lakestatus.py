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
# of the lake zone: a lake may be forming. No verdict, and its radar dark area is shown but not treated as lake area:
# the SARtale team reviews the site and adds it to the register as a measured lake (no automatic promotion).
LAKE_FORMING = "Lake may be forming"
# A lake probably under ice (lakes-freeze, sartale.freeze): from air temperature, or seen under snow or ice on a clear
# Sentinel-2 scene, or (in spring) with its ice probably breaking up. L-band radar cannot tell new ice from open water,
# and frozen ground around a lake reads as water, so there is no growing/shrinking verdict while it lasts. These take
# precedence over every status but "No lake now" (and "Lake may be forming", which only a no-lake site has).
FROZEN_LIKELY = "Frozen (likely)"
FROZEN_S2 = "Frozen (seen by Sentinel-2)"
BREAKUP = "Break-up likely"
FREEZE_STATUS = {"frozen_likely": FROZEN_LIKELY, "frozen_s2": FROZEN_S2, "breakup_likely": BREAKUP}
# Every status a lake can have, in the order the app lists them (app/src/lakes.ts STATUS_ORDER).
STATUS_NAMES = (
    LAKE_FORMING,
    "Growing",
    "Shrinking",
    UNCONFIRMED,
    FROZEN_LIKELY,
    FROZEN_S2,
    BREAKUP,
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
    frozen: NotRequired[bool]  # taken while the lake was probably frozen (lakes-freeze): kept, but in no baseline


def track_noise_km2(areas: list[float]) -> float:
    """Robust pass-to-pass noise of one track: 1.4826 * median(|diff|), floored."""
    if len(areas) < 3:
        return NOISE_FLOOR_KM2
    diffs = [abs(b - a) for a, b in zip(areas, areas[1:])]
    return max(1.4826 * median(diffs), NOISE_FLOOR_KM2)


def is_valid(p: SeriesPoint) -> bool:
    """A pass the status may use: not excluded, has an area, enough of the zone observable, and not taken while the
    lake was probably frozen (`frozen`, set by lakes-freeze: its area is kept but enters no baseline or noise)."""
    return (
        p["excluded"] is None
        and p["area_km2"] is not None
        and p["observable_share"] >= MIN_OBSERVABLE
        and not p.get("frozen")
    )


def open_water_status(series: list[SeriesPoint]) -> dict:
    """`lake_status` of the passes not flagged frozen, with "Not seen this pass" judged against the newest of those
    passes on each track (a frozen pass is left out of the comparison, not missed)."""
    kept = [p for p in series if not p.get("frozen")]
    latest_expected: dict[str, str] = {}
    for p in kept:
        latest_expected[p["track"]] = max(latest_expected.get(p["track"], ""), p["date"])
    return lake_status(kept, latest_expected)


def frozen_status(computed: dict, freeze: dict) -> dict:
    """The status of a lake whose freeze state is frozen or break-up (`FREEZE_STATUS`): no growing or shrinking
    verdict, whatever the passes show, and the freeze check's reason (the temperature run and its date, and the
    Sentinel-2 scene when one was used). Keeps the track, latest date and looks of `computed` (the status of every
    pass), so the lake's picture and pass count still show."""
    return _result(FREEZE_STATUS[freeze["state"]], computed["track"], computed["latest_date"], computed["looks"],
                   reason=freeze["reason"])


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


NO_VIEW_SINCE = "no clear, snow-free Sentinel-2 view of the zone since"
RECHECK = ("SARtale re-checks the site with Sentinel-2 at every data refresh, all year, using only views where the lake "
           "zone is clear of cloud, snow and ice; the status changes only when two such views at least 5 days apart "
           "agree.")
FORMING_NEXT = ("Its radar dark area is shown but not yet treated as lake area; the SARtale team reviews the site to add "
                "it as a measured lake.")


def stale_text(absence: dict) -> str:
    """"; no clear, snow-free Sentinel-2 view of the zone since (searched to 12 Nov 2026)" when the last search found
    nothing newer that qualified for a while (`no_view_since`), else ""."""
    if not absence.get("no_view_since"):
        return ""
    searched = absence.get("searched") or absence.get("checked")
    return f"; {NO_VIEW_SINCE} (searched to {day_text(searched)})" if searched else f"; {NO_VIEW_SINCE}"


def absence_sentence(absence: dict | None) -> str:
    """The dated evidence of an absence check in words, or "" when there is none. When no clear, snow-free scene has
    come since, it says so, so an old view never reads as a recent check."""
    if not absence:
        return ""
    return (f"Last checked {day_text(absence['date'])} with Sentinel-2 ({absence['s2_id']}): water on "
            f"{share_text(absence['water_share'])} of the lake zone{stale_text(absence)}.")


def pending_sentence(absence: dict | None) -> str:
    """What the one scene waiting for confirmation (`pending_scene`) showed, or "" when none waits. At a site with no
    lake now it was above the site's threshold; at a site where a lake may be forming, below it."""
    p = (absence or {}).get("pending_scene")
    if not p:
        return ""
    level = f"this site's {share_text(absence['threshold'])} level" if absence.get("threshold") is not None \
        else "this site's level"
    seen = f"One recent clear scene ({day_text(p['date'])}, {p['s2_id']}) showed water on {share_text(p['water_share'])} " \
           "of the lake zone"
    if absence.get("forming"):
        return f"{seen}, below {level}; SARtale is checking the next clear, snow-free scene before saying there is no lake."
    return f"{seen}, above {level}; SARtale is checking the next clear, snow-free scene before saying a lake may be forming."


def no_lake_status(computed: dict, source: str | None, absence: dict | None = None) -> dict:
    """The status of a site with no lake now: keeps the track, latest date and looks the passes give (so the site's
    picture and pass count still show), drops any change and noise, and says why, with the date of the last
    Sentinel-2 absence check when there is one, and a scene above the threshold that waits for a second one."""
    why = f"No lake in recent imagery: {source.rstrip('.')}." if source else "No lake in recent imagery."
    checked = absence_sentence(absence)
    reason = " ".join(t for t in (why, checked, pending_sentence(absence), RECHECK) if t)
    return _result(NO_LAKE, computed["track"], computed["latest_date"], computed["looks"], reason=reason)


def forming_status(computed: dict, absence: dict) -> dict:
    """The status of a "no lake now" site where Sentinel-2 found water: a lake may be forming. No growing or
    shrinking verdict; the track, latest date and looks are those the passes give. Nothing promotes the site to a
    measured lake automatically: the reason says that the team reviews it."""
    pair = absence.get("confirmed")
    if pair:
        level = f"above this site's {share_text(absence['threshold'])} level" if absence.get("threshold") is not None \
            else "above this site's level"
        seen = (f"Two clear, snow-free Sentinel-2 scenes at least 5 days apart showed water {level} where recent "
                f"imagery had no lake: {day_text(pair[0]['date'])} ({share_text(pair[0]['water_share'])} of the lake "
                f"zone) and {day_text(pair[1]['date'])} ({share_text(pair[1]['water_share'])}). Latest: "
                f"{day_text(absence['date'])} ({absence['s2_id']}), water on {share_text(absence['water_share'])} "
                f"({absence['water_km2']:.3f} km2){stale_text(absence)}.")
    else:
        seen = (f"Sentinel-2 on {day_text(absence['date'])} ({absence['s2_id']}) shows water on "
                f"{share_text(absence['water_share'])} of the lake zone ({absence['water_km2']:.3f} km2), where recent "
                f"imagery had no lake{stale_text(absence)}.")
    reason = " ".join(t for t in (seen, pending_sentence(absence), f"A lake may be forming. {FORMING_NEXT}") if t)
    return _result(LAKE_FORMING, computed["track"], computed["latest_date"], computed["looks"], reason=reason)
