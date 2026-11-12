"""Per-lake series, alert levels and status for Lake Watch.

Every valid pass, on any track, is compared with the median of up to config.BASELINE_PASSES earlier valid passes on its
own track: z = (area - baseline) / noise (`compare_passes`). The levels, in this order:

- Alert: growing: two valid passes in a row, on any tracks, with z >= +CHANGE_FACTOR. Neither may be a track's first
  pass on a processing version (CRID) its baseline lacks, or one of the first passes after the lake opened (those
  only rebuild the baseline). Passes flagged frozen (frozen or breaking up, lakes-freeze) are not compared at all.
- Watch: one valid pass with |z| >= CHANGE_FACTOR, or a CUSUM over the z stream (k = CUSUM_K) reaching CUSUM_H.
- Decrease noted: the two-pass rule with z <= -CHANGE_FACTOR. Information only, never an Alert: radar sees a lake
  drawing down onto wet sediment at only about a tenth to a fifth of its size. It is the two-pass form of a Watch on
  a falling area, so it replaces that Watch.
- No change: none of these.

The status of a lake, in order of precedence: No lake now (and Lake may be forming), Frozen / Break-up likely (both set
by the callers), Not observable, Not measurable, Not enough NISAR looks yet, Not seen this pass, then the level.
Method study and rules: .superpowers/sdd/post-merge/method-study.md and step2b-brief.md.
"""
from __future__ import annotations

from statistics import median
from typing import NotRequired, TypedDict

from .config import (
    AFTER_OPEN_PASSES,
    BASELINE_PASSES,
    CHANGE_FACTOR,
    CLOUD_WINDOW,
    CUSUM_H,
    CUSUM_K,
    MIN_LOOKS,
    MIN_OBSERVABLE,
    MIN_VALIDATION_IOU,
    NOISE_FLOOR_KM2,
    NOISE_PASSES,
    NOISE_REL_FLOOR,
)


# The levels a measured lake can have, highest first.
ALERT = "Alert: growing"
WATCH = "Watch"
DECREASE = "Decrease noted"
NO_CHANGE = "No change"
LEVELS = (ALERT, WATCH, DECREASE, NO_CHANGE)
# No level is given: the Sentinel-2 check of the method at this lake overlapped too little (lakes-check IoU below
# config.MIN_VALIDATION_IOU). The area is shown as information only.
NOT_MEASURABLE = "Not measurable"
NOT_OBSERVABLE = "Not observable"
NOT_ENOUGH = "Not enough NISAR looks yet"
NOT_SEEN = "Not seen this pass"
# A site the register marks lake_state "no_lake": recent imagery shows no lake there (an ice-dammed lake's empty
# basin, say). It gets no level and its dark radar area is not lake area.
NO_LAKE = "No lake now"
# A "no lake now" site where the latest Sentinel-2 absence check found water on more than config.FORMING_WATER_SHARE
# of the lake zone: a lake may be forming. No level, and its radar dark area is shown but not treated as lake area:
# the SARtale team reviews the site and adds it to the register as a measured lake (no automatic promotion).
LAKE_FORMING = "Lake may be forming"
# A lake probably under ice (lakes-freeze, sartale.freeze): from air temperature, or seen under snow or ice on a clear
# Sentinel-2 scene, or (in spring) with its ice probably breaking up. L-band radar cannot tell new ice from open water,
# and frozen ground around a lake reads as water, so there is no level while it lasts. These take precedence over every
# status but "No lake now" (and "Lake may be forming", which only a no-lake site has).
FROZEN_LIKELY = "Frozen (likely)"
FROZEN_S2 = "Frozen (seen by Sentinel-2)"
BREAKUP = "Break-up likely"
FREEZE_STATUS = {"frozen_likely": FROZEN_LIKELY, "frozen_s2": FROZEN_S2, "breakup_likely": BREAKUP}
# Every status a lake can have, in the order the app lists them (app/src/lakes.ts STATUS_ORDER): an Alert first.
STATUS_NAMES = (
    ALERT,
    LAKE_FORMING,
    WATCH,
    DECREASE,
    FROZEN_LIKELY,
    FROZEN_S2,
    BREAKUP,
    NOT_SEEN,
    NO_CHANGE,
    NOT_ENOUGH,
    NOT_MEASURABLE,
    NOT_OBSERVABLE,
    NO_LAKE,
)
# What the levels are not, and what to do: the same words in every message.
LATENCY_TEXT = "5–12 days"
NOT_TEXT = (f"This is not an outburst forecast. Radar sees a lake drawing down onto wet sediment poorly, and a change "
            f"shows here {LATENCY_TEXT} after it begins.")
DO_TEXT = ("Check recent optical imagery (Sentinel-2 or Landsat) or the site, and contact GBDMA or PDMA. Official "
           "warnings come from PMD, NDMA, GBDMA and PDMA.")
DRAWDOWN_TEXT = ("Information only, not an Alert: the radar sees a drawdown onto wet sediment at only about a tenth to a "
                 "fifth of its size, so the real change can be much larger. Check optical imagery.")
DRAWDOWN_WATCH = ("The radar sees a drawdown onto wet sediment at only about a tenth to a fifth of its size, so a real "
                  "decrease can be much larger: check optical imagery.")
# The per-pass fields `compare_passes` writes (and strips before writing them again).
PASS_FIELDS = ("z", "baseline_km2", "noise_km2", "level_contrib", "new_version", "after_open")


class SeriesPoint(TypedDict):
    date: str  # ISO YYYY-MM-DD
    track: str  # e.g. "156A"
    area_km2: float | None
    observable_share: float
    excluded: str | None  # reason, or None
    crid: NotRequired[str]  # NISAR processing version (composite release ID) of the pass, e.g. "P05036"
    frozen: NotRequired[bool]  # taken while the lake was probably frozen (lakes-freeze): kept, but in no baseline
    z: NotRequired[float | None]  # (area - baseline) / noise; None until its track has MIN_LOOKS earlier valid passes
    baseline_km2: NotRequired[float | None]  # median of up to BASELINE_PASSES earlier valid passes on its track
    noise_km2: NotRequired[float | None]  # its track's noise then, with the floors
    level_contrib: NotRequired[str | None]  # the level this pass set (LEVELS), None when it set none
    new_version: NotRequired[bool]  # first pass of its track on a CRID its baseline lacks: can Watch, not Alert
    after_open: NotRequired[bool]  # one of the first passes of its track after the lake opened: rebuilds the baseline


def track_noise_km2(areas: list[float]) -> float:
    """Robust pass-to-pass noise of one track: 1.4826 * median(|diff|), floored."""
    if len(areas) < 3:
        return NOISE_FLOOR_KM2
    diffs = [abs(b - a) for a, b in zip(areas, areas[1:])]
    return max(1.4826 * median(diffs), NOISE_FLOOR_KM2)


def pass_noise_km2(areas: list[float], baseline: float) -> float:
    """The noise a pass is measured against: its track's noise on up to NOISE_PASSES of the latest earlier valid passes,
    floored at max(NOISE_FLOOR_KM2, NOISE_REL_FLOOR x baseline)."""
    return max(track_noise_km2(areas[-NOISE_PASSES:]), NOISE_REL_FLOOR * baseline)


def is_valid(p: SeriesPoint) -> bool:
    """A pass the status may use: not excluded, has an area, enough of the zone observable, and not taken while the
    lake was probably frozen (`frozen`, set by lakes-freeze: its area is kept but enters no baseline or noise)."""
    return (
        p["excluded"] is None
        and p["area_km2"] is not None
        and p["observable_share"] >= MIN_OBSERVABLE
        and not p.get("frozen")
    )


def _strip(p: dict) -> dict:
    return {k: v for k, v in p.items() if k not in PASS_FIELDS}


def compare_passes(series: list[SeriesPoint]) -> list[dict]:
    """The series (same order) with each valid pass compared with its own track's earlier valid passes and given its
    level (module docstring): `z`, `baseline_km2`, `noise_km2` and `level_contrib`, plus `new_version` and `after_open`
    when they hold. A pass that is not valid gets none of these; a valid pass whose track has fewer than MIN_LOOKS earlier
    valid passes gets z None. Internal keys (`_z` unrounded, `_why`, `_prev`, `_cusum`, `_cusum_at`) ride along for
    `assess`; `public` drops them."""
    out = [_strip(p) for p in series]
    order = sorted(range(len(out)), key=lambda i: (out[i]["date"], out[i]["track"]))
    hist: dict[str, list[tuple[float, str | None]]] = {}
    since_open: dict[str, int] | None = None  # passes per track since the last frozen pass; None: never frozen
    up = down = 0.0
    prev: int | None = None  # the previous compared pass (any track)
    for i in order:
        p = out[i]
        if p.get("frozen"):
            # A frozen spell: every track rebuilds its baseline after it, and the CUSUM and the pass pairs start again.
            since_open, prev, up, down = {}, None, 0.0, 0.0
            continue
        if not is_valid(p):
            continue
        t, area, crid = p["track"], p["area_km2"], p.get("crid")
        h = hist.setdefault(t, [])
        after_open = since_open is not None and since_open.get(t, 0) < AFTER_OPEN_PASSES
        if since_open is not None:
            since_open[t] = since_open.get(t, 0) + 1
        if after_open:
            p["after_open"] = True
        if len(h) < MIN_LOOKS:
            p.update(z=None, baseline_km2=None, noise_km2=None, level_contrib=None)
            h.append((area, crid))
            continue
        base = h[-BASELINE_PASSES:]
        ref = median(a for a, _ in base)
        noise = pass_noise_km2([a for a, _ in h], ref)
        z = (area - ref) / noise
        base_crids = {c for _, c in base} - {None}
        if crid and base_crids and crid not in base_crids:
            p["new_version"] = True
        p.update(z=round(z, 2), baseline_km2=round(ref, 6), noise_km2=round(noise, 6), _z=z)
        h.append((area, crid))
        if after_open:
            p["level_contrib"] = None  # only rebuilds the baseline
            prev = i
            continue
        up, down = max(0.0, up + z - CUSUM_K), max(0.0, down - z - CUSUM_K)
        cusum_at = max(up, down)
        cusum_hit = cusum_at >= CUSUM_H
        eligible = not p.get("new_version")
        q = out[prev] if prev is not None else None
        pair = q is not None and eligible and not q.get("new_version") and not q.get("after_open")
        if pair and q["_z"] >= CHANGE_FACTOR and z >= CHANGE_FACTOR:
            level, why = ALERT, "pair"
        elif pair and q["_z"] <= -CHANGE_FACTOR and z <= -CHANGE_FACTOR:
            level, why = DECREASE, "pair"
        elif abs(z) >= CHANGE_FACTOR:
            level, why = WATCH, "pass"
        elif cusum_hit:
            level, why = WATCH, "cusum"
        else:
            level, why = NO_CHANGE, None
        p.update(level_contrib=level, _why=why, _prev=prev if why == "pair" else None, _cusum_at=round(cusum_at, 2))
        if cusum_hit:
            up = down = 0.0  # the CUSUM starts again once it has made a Watch
        p["_cusum"] = {"up": round(up, 2), "down": round(down, 2)}
        prev = i
    return out


def public(series: list[dict]) -> list[dict]:
    """The series without `compare_passes`' internal keys, as lakes.json stores it."""
    return [{k: v for k, v in p.items() if not k.startswith("_")} for p in series]


def _result(status, track=None, latest_date=None, looks=0, change=None, noise=None, reason="", **level) -> dict:
    """A status object. The level keys (`level`, `level_since`, `level_passes`, `cusum`, `z`, `baseline_km2`,
    `alerts_paused`, `message`) are None (or empty) unless the status is a level."""
    out = {
        "status": status,
        "track": track,
        "latest_date": latest_date,
        "looks": looks,
        "change_km2": change,
        "noise_km2": noise,
        "reason": reason,
        "level": None,
        "level_since": None,
        "level_passes": [],
        "cusum": None,
        "z": None,
        "baseline_km2": None,
        "alerts_paused": None,
        "message": None,
    }
    out.update(level)
    return out


_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def day_text(iso: str) -> str:
    """"2026-08-17" -> "17 Aug 2026" (the app's date style)."""
    y, m, d = (int(v) for v in iso.split("-"))
    return f"{d} {_MONTHS[m - 1]} {y}"


def _signed(v: float, digits: int = 3) -> str:
    """"+0.012" or "−0.012" (a true minus sign); a value that rounds to zero has no sign."""
    t = f"{abs(v):.{digits}f}"
    if float(t) == 0:
        return t
    return ("+" if v > 0 else "−") + t


def _pct(change: float, base: float) -> str:
    if not base:
        return "n/a"
    v = round(100 * change / base)
    return "0%" if v == 0 else f"{'+' if v > 0 else '−'}{abs(v)}%"


def pass_line(p: dict) -> str:
    """"2.640 km² on 9 Nov 2026 (055A), −0.012 km² (−0%) against its baseline of 2.652 km²"."""
    change = p["area_km2"] - p["baseline_km2"]
    return (f"{p['area_km2']:.3f} km² on {day_text(p['date'])} ({p['track']}), {_signed(change)} km² "
            f"({_pct(change, p['baseline_km2'])}) against its baseline of {p['baseline_km2']:.3f} km²")


def level_message(level: str, name: str | None, passes: list[dict], why: str | None,
                  cusum_at: float | None = None) -> dict:
    """The initial message of a Watch, an Alert or a Decrease noted, in plain words, from the decision values: what
    changed and by how much, over which passes and dates, how sure SARtale is, what it is not, and what to do. `passes`
    are the passes that set the level, oldest first (each with date, track, crid, area_km2, baseline_km2, noise_km2, z
    and new_version when it holds). `text` joins the other fields."""
    last = passes[-1]
    lake = name or "this lake"
    if level in (ALERT, DECREASE):
        first = passes[0]
        verb = "rose" if level == ALERT else "fell"
        title = f"{level}: the radar water area of {lake} {verb} on two passes in a row."
        what = (f"Radar water area of {lake}: {pass_line(last)} from earlier {last['track']} passes; on the pass "
                f"before, {pass_line(first)} from earlier {first['track']} passes.")
        sure = (f"Two passes in a row beyond {CHANGE_FACTOR:g}× their track's noise: z = {_signed(first['z'], 1)} and "
                f"{_signed(last['z'], 1)} (noise ±{first['noise_km2']:.3f} and ±{last['noise_km2']:.3f} km²).")
    else:
        if why == "cusum":
            title = f"Watch: small changes in the radar water area of {lake} have added up over recent passes."
            sure = (f"No single pass is beyond {CHANGE_FACTOR:g}× noise (latest z = {_signed(last['z'], 1)}), but the "
                    f"running sum of the z values (CUSUM, k = {CUSUM_K:g}) reached {cusum_at:.1f}, at least "
                    f"{CUSUM_H:g}. Not confirmed by two passes; the next passes show whether it holds.")
        else:
            title = f"Watch: one radar pass of {lake} is beyond {CHANGE_FACTOR:g}× noise."
            sure = (f"One pass only (z = {_signed(last['z'], 1)}, noise ±{last['noise_km2']:.3f} km²), so it is not "
                    "confirmed; the next pass shows whether it holds.")
        what = f"Radar water area of {lake}: {pass_line(last)} from earlier {last['track']} passes."
        if last.get("new_version"):
            sure += (f" This is the first {last['track']} pass on NISAR processing version {last.get('crid')}, which "
                     "its baseline lacks: it can raise a Watch but not an Alert.")
    falling = level == DECREASE or (level == WATCH and last["z"] < 0)
    not_ = f"{DRAWDOWN_TEXT if level == DECREASE else DRAWDOWN_WATCH} {NOT_TEXT}" if falling else NOT_TEXT
    msg = {"level": level, "title": title, "what": what, "how_sure": sure, "not": not_, "do": DO_TEXT}
    msg["text"] = " ".join(msg[k] for k in ("title", "what", "how_sure", "not", "do"))
    return msg


def _validation_iou(validation: dict | None) -> float | None:
    v = (validation or {}).get("iou")
    return float(v) if isinstance(v, (int, float)) else None


def assess(series: list[SeriesPoint], latest_expected: dict[str, str] | None = None,
           validation: dict | None = None, name: str | None = None) -> tuple[dict, list[dict]]:
    """(status, series): the status of one lake and its series with every pass compared (`compare_passes`).

    `latest_expected` maps track key -> date of that track's newest pass that exists (excluded or not, not frozen).
    "Not seen this pass" fires when, for some track, that newest pass is newer than the lake's latest valid pass and
    has no valid point in `series` (excluded, unobservable or missing).

    `validation` is the lake's Sentinel-2 check (a lakes-check row, with `iou`): below MIN_VALIDATION_IOU the lake is
    "Not measurable" and gets no level; its latest area is given as information. `name` is the lake's name, for the
    message a Watch, an Alert or a Decrease noted carries.
    """
    compared = compare_passes(series)
    annotated = public(compared)
    if not any(p["observable_share"] >= MIN_OBSERVABLE for p in series):
        return _result(NOT_OBSERVABLE, reason=f"Under {MIN_OBSERVABLE:.0%} of the lake zone is observable on every "
                                              "pass."), annotated
    valid = sorted((p for p in compared if is_valid(p)), key=lambda p: (p["date"], p["track"]))
    if not valid:
        return _result(NOT_ENOUGH, reason="No valid pass yet (all excluded or without an area)."), annotated
    by_track: dict[str, list[dict]] = {}
    for p in valid:
        by_track.setdefault(p["track"], []).append(p)
    latest = valid[-1]
    stream = [p for p in valid if p.get("z") is not None]
    iou = _validation_iou(validation)
    if iou is not None and iou < MIN_VALIDATION_IOU:
        t = latest["track"]
        v = validation or {}
        checked = (f" ({day_text(v['nisar_date'])} against Sentinel-2 of {day_text(v['s2_date'])})"
                   if v.get("nisar_date") and v.get("s2_date") else "")
        return _result(NOT_MEASURABLE, t, latest["date"], len(by_track[t]), reason=(
            f"Radar water area {latest['area_km2']:.3f} km² on {day_text(latest['date'])} ({t}), shown as information "
            f"only: in its Sentinel-2 check{checked} the radar water overlapped optical water with IoU {iou:.2f}, under "
            f"the {MIN_VALIDATION_IOU:g} SARtale needs to give a level.")), annotated
    if not stream:
        best = max(by_track, key=lambda k: (by_track[k][-1]["date"], len(by_track[k])))
        n = len(by_track[best])
        return _result(NOT_ENOUGH, best, by_track[best][-1]["date"], n, reason=(
            f"{n} valid look(s) on track {best}; a pass is compared once its track has {MIN_LOOKS} earlier valid "
            "looks.")), annotated
    last = stream[-1]
    t = last["track"]
    looks = len(by_track[t])
    if latest_expected:
        seen = {(p["track"], p["date"]) for p in valid}
        for track in sorted(latest_expected):
            d = latest_expected[track]
            if d > latest["date"] and (track, d) not in seen:
                return _result(NOT_SEEN, t, last["date"], looks,
                               reason=f"Newest pass {track} {d} is excluded or has no valid reading."), annotated
    change = last["area_km2"] - last["baseline_km2"]
    reason = (f"Track {t}: {last['area_km2']:.3f} km2 on {last['date']} vs baseline {last['baseline_km2']:.3f} km2 "
              f"(median of up to {BASELINE_PASSES} earlier {t} passes), noise {last['noise_km2']:.3f} km2: "
              f"z = {last['z']:+.1f}")
    level = last.get("level_contrib") or NO_CHANGE
    run = []
    for p in reversed(stream):
        if (p.get("level_contrib") or NO_CHANGE) != level:
            break
        run.append(p)
    since = run[-1]["date"]
    why = last.get("_why")
    trig = [compared[last["_prev"]], last] if level in (ALERT, DECREASE) else [last] if level == WATCH else []
    keep = ("date", "track", "crid", "area_km2", "baseline_km2", "noise_km2", "z", "new_version")
    level_passes = [{k: p.get(k) for k in keep if k != "new_version" or p.get(k)} for p in trig]
    cusum = next((p["_cusum"] for p in reversed(stream) if "_cusum" in p), {"up": 0.0, "down": 0.0})
    if last.get("after_open"):
        reason += "; this pass only rebuilds the baseline after the lake opened, so it sets no level."
    elif level == ALERT:
        reason += f"; two passes in a row at or above +{CHANGE_FACTOR:g}× noise."
    elif level == DECREASE:
        reason += f"; two passes in a row at or below −{CHANGE_FACTOR:g}× noise (information only)."
    elif level == WATCH and why == "cusum":
        reason += f"; the CUSUM of the z values reached {last['_cusum_at']:.1f} (a Watch at {CUSUM_H:g})."
    elif level == WATCH:
        reason += f"; one pass beyond {CHANGE_FACTOR:g}× noise."
    else:
        reason += f"; within {CHANGE_FACTOR:g}× noise."
    paused = None
    if last.get("new_version"):
        paused = {"crid": last.get("crid"), "track": t, "date": last["date"]}
        reason += (f" Alerts are paused: this is the first {t} pass on NISAR processing version {last.get('crid')}, "
                   "which its baseline lacks, so it can raise a Watch but not an Alert; Alerts resume once a second "
                   "pass on that version enters the baseline.")
    message = level_message(level, name, level_passes, why, last.get("_cusum_at")) if level != NO_CHANGE else None
    return _result(level, t, last["date"], looks, round(change, 6), last["noise_km2"], reason,
                   level=level, level_since=since, level_passes=level_passes, cusum=cusum, z=last["z"],
                   baseline_km2=last["baseline_km2"], alerts_paused=paused, message=message), annotated


def lake_status(series: list[SeriesPoint], latest_expected: dict[str, str] | None = None,
                validation: dict | None = None, name: str | None = None) -> dict:
    """The status of `assess`, without the compared series."""
    return assess(series, latest_expected, validation, name)[0]


def open_water_assess(series: list[SeriesPoint], validation: dict | None = None,
                      name: str | None = None) -> tuple[dict, list[dict]]:
    """`assess` with "Not seen this pass" judged against the newest pass not flagged frozen on each track (a frozen
    pass is left out of the comparison, not missed). Frozen passes stay in the series: after them each track rebuilds
    its baseline."""
    latest_expected: dict[str, str] = {}
    for p in series:
        if not p.get("frozen"):
            latest_expected[p["track"]] = max(latest_expected.get(p["track"], ""), p["date"])
    return assess(series, latest_expected, validation, name)


def open_water_status(series: list[SeriesPoint], validation: dict | None = None, name: str | None = None) -> dict:
    """The status of `open_water_assess`."""
    return open_water_assess(series, validation, name)[0]


def frozen_status(computed: dict, freeze: dict) -> dict:
    """The status of a lake whose freeze state is frozen or break-up (`FREEZE_STATUS`): no level, whatever the passes
    show, and the freeze check's reason (the temperature run and its date, and the Sentinel-2 scene when one was used).
    Keeps the track, latest date and looks of `computed` (the status of every pass), so the lake's picture and pass
    count still show."""
    return _result(FREEZE_STATUS[freeze["state"]], computed["track"], computed["latest_date"], computed["looks"],
                   reason=freeze["reason"])


def cloud_window_looks(
    series: list[SeriesPoint], start: str = CLOUD_WINDOW[0], end: str = CLOUD_WINDOW[1]
) -> int:
    """Valid, non-excluded points with enough observable zone, dated start..end inclusive. A look at a lake that was
    frozen then still counts: it is a valid look, only not an open-water measurement."""
    return sum(1 for p in series if is_valid({**p, "frozen": False}) and start <= p["date"] <= end)


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
