"""Is a lake probably frozen? Air temperature at the lake, Sentinel-2 when a clear scene shows it, and radar at ice-out.

L-band radar does not see a mountain lake freeze: new ice under dry snow stays as dark as open water, while frozen
ground around the lake darkens and reads as new water (Shazore read +44% after freeze-up). So the freeze state comes
from NASA POWER daily air temperature, moved to the lake's height (config.LAPSE_C_PER_KM), with a clear Sentinel-2
scene overriding it, and from radar only at break-up, when wet, rotting ice brightens the lake core
(.superpowers/sdd/post-merge/frozen-spike.md; docs/superpowers/specs/2026-11-11-lake-detail-and-frozen-design.md).

States (the `freeze` object of each lake in lakes.json):
- open: the freeze rule is not met (temperature alone never says a lake is open), or a clear Sentinel-2 scene shows
  open water on S2_OPEN_WATER_SHARE of the lake itself (unbuffered outline, or summer radar core), or the lake is open
  again after break-up.
- frozen_likely: daily mean below 0 C on FREEZE_COLD_RUN_DAYS days in a row and FREEZE_FDD freezing degree-days since
  1 Sep. Freeze-up starts only in the season (1 Sep-31 May); a frozen lake stays frozen after 31 May until the
  break-up and open-again rules release it.
- frozen_s2: snow or ice on S2_FROZEN_SNOW_SHARE of the lake zone in the clearest Sentinel-2 scene of the last
  S2_FREEZE_DAYS days (zone at least S2_FREEZE_CLEAR clear of cloud, shadow and their 100 m edge).
- breakup_likely: a frozen lake with BREAKUP_WARM_RUN_DAYS warm days in a row, or a radar pass whose core is
  BREAKUP_CONTRAST_DB brighter against its window than in summer in both HH and HV with its dark share
  BREAKUP_DARK_DROP below summer.
- not_assessed: no lake height, no POWER data, or the newest POWER day more than POWER_STALE_DAYS old.

Every pass also gets `frozen`, from the same rule on its own date: passes taken while frozen or breaking up keep their
area but enter no baseline or noise (lakestatus.is_valid).
"""
from __future__ import annotations

import time
from datetime import date as Date, timedelta
from pathlib import Path

import numpy as np
import requests

from sartale import config
from sartale.lakestatus import FREEZE_STATUS, day_text, frozen_status, is_valid, lake_status, open_water_status

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
DEFAULT_CACHE = Path(__file__).resolve().parents[2] / "data" / "lakes"  # the NISAR window cache lakes-fetch fills
POWER_SOURCE = "NASA POWER daily T2M and T2M_MIN (MERRA-2 based), moved to the lake's height at -6.5 C/km"
POWER_TIMEOUT_S = 60
POWER_FILL = -900  # POWER marks a missing day with -999
FROZEN_STATES = ("frozen_likely", "frozen_s2", "breakup_likely")


# --- the season ------------------------------------------------------------------------------------------------------

def in_freeze_season(d: Date) -> bool:
    """1 Sep-31 May (config.FREEZE_SEASON_START/END), any year."""
    return (d.month, d.day) >= config.FREEZE_SEASON_START or (d.month, d.day) <= config.FREEZE_SEASON_END


def season_start(d: Date) -> Date | None:
    """1 Sep that opens the freeze season holding `d`, or None outside the season (1 Jun-31 Aug)."""
    if not in_freeze_season(d):
        return None
    m, day = config.FREEZE_SEASON_START
    return Date(d.year if (d.month, d.day) >= (m, day) else d.year - 1, m, day)


def record_start(d: Date) -> Date:
    """The first day of air temperature needed to know the state on `d`: 1 Sep of its season, or, between 1 Jun and
    31 Aug (when a lake frozen in winter may still be frozen), 1 Sep of the season that just ended."""
    m, day = config.FREEZE_SEASON_START
    return season_start(d) or Date(d.year - 1, m, day)


# --- NASA POWER ------------------------------------------------------------------------------------------------------

def fetch_power(lon: float, lat: float, start: str, end: str, get=None, retries: int = 1,
                pause_s: float = 5.0) -> dict:
    """Daily T2M and T2M_MIN at a point from NASA POWER (no login), `start`..`end` (YYYY-MM-DD). Returns
    {"cell_elev_m": the POWER grid cell's height, "days": {iso: {"t2m": C or None, "t2m_min": C or None}}}; POWER's
    -999 (no value yet) becomes None. A failed request is tried again `retries` times, then raises."""
    params = {"parameters": "T2M,T2M_MIN", "community": "RE", "longitude": f"{lon:.4f}", "latitude": f"{lat:.4f}",
              "start": start.replace("-", ""), "end": end.replace("-", ""), "format": "JSON"}
    get = get or requests.get
    for attempt in range(retries + 1):
        try:
            r = get(POWER_URL, params=params, timeout=POWER_TIMEOUT_S)
            r.raise_for_status()
            doc = r.json()
            break
        except Exception:  # noqa: BLE001 - one retry, then the caller marks the lake "not assessed"
            if attempt == retries:
                raise
            time.sleep(pause_s)
    p = doc["properties"]["parameter"]

    def value(v):
        return None if v is None or v <= POWER_FILL else float(v)

    days = {f"{k[:4]}-{k[4:6]}-{k[6:]}": {"t2m": value(v), "t2m_min": value(p.get("T2M_MIN", {}).get(k))}
            for k, v in p["T2M"].items()}
    return {"cell_elev_m": float(doc["geometry"]["coordinates"][2]), "days": days}


def corrected(power: dict, lake_elev_m: float, lapse: float = config.LAPSE_C_PER_KM) -> dict[str, dict]:
    """The POWER days moved from the cell's height to the lake's: + lapse x (lake - cell) / 1000."""
    shift = lapse * (lake_elev_m - power["cell_elev_m"]) / 1000.0
    return {d: {k: (None if v is None else v + shift) for k, v in row.items()} for d, row in power["days"].items()}


# --- the rule --------------------------------------------------------------------------------------------------------

def _radar_test(p: dict, ref: dict | None) -> str | None:
    """"breakup" when a pass shows the ice-out signature against its track's summer level, "summer" when it is back
    within its summer range, else None. Only non-excluded passes with core numbers, on a track whose summer level is
    assessed (enough open-water-season passes), are tested; the test uses core-minus-window contrast only, so a
    processing-version change (which moves core and window together) cannot trigger it."""
    if not ref or not ref.get("assessed") or p.get("excluded") is not None or "core_dark_share" not in p:
        return None
    dhh = p["core_contrast_hh_db"] - ref["core_contrast_hh_db"]
    dhv = p["core_contrast_hv_db"] - ref["core_contrast_hv_db"]
    drop = ref["core_dark_share"] - p["core_dark_share"]
    if dhh >= config.BREAKUP_CONTRAST_DB and dhv >= config.BREAKUP_CONTRAST_DB and drop >= config.BREAKUP_DARK_DROP:
        return "breakup"
    if abs(dhh) <= config.SUMMER_CONTRAST_DB and abs(dhv) <= config.SUMMER_CONTRAST_DB and drop <= config.SUMMER_DARK_DROP:
        return "summer"
    return None


def _mean(vals: list) -> float | None:
    vals = [v for v in vals if v is not None]
    return round(float(np.mean(vals)), 1) if vals else None


def s2_kind(ev: dict | None) -> str | None:
    """What one Sentinel-2 reading shows about the lake itself: "snow" (snow or ice on S2_FROZEN_SNOW_SHARE of it seen
    clear), "water" (water on S2_OPEN_WATER_SHARE), or None (neither, or less than S2_TARGET_CLEAR of it seen clear)."""
    if not ev or ev.get("target_clear_share", 1.0) < config.S2_TARGET_CLEAR:
        return None
    if ev["snow_share"] >= config.S2_FROZEN_SNOW_SHARE:
        return "snow"
    if ev["water_share"] >= config.S2_OPEN_WATER_SHARE:
        return "water"
    return None


def freeze_history(temps: dict[str, dict], series: list[dict], summer_ref: dict, today: str,
                   s2_events: list[dict] | tuple = ()) -> dict:
    """The freeze state day by day from the first freeze season the record needs (`record_start` of each pass and of
    today) to `today`, from the lake-height air temperature `temps` (iso -> {"t2m", "t2m_min"}, None for a missing
    day), the passes in `series` (each tested by radar against `summer_ref` of its track) and the Sentinel-2 evidence
    `s2_events` (readings of the lake, `s2_kind`), each acting on its own date.

    - Freeze-up (by air: FREEZE_COLD_RUN_DAYS below 0 C and FREEZE_FDD since 1 Sep) starts only between 1 Sep and
      31 May; Sentinel-2 snow or ice on the lake makes it frozen on any date (frozen_s2, from the freeze-up date when
      there is one, else the scene date). A frozen lake stays frozen, past 31 May too, until released.
    - Break-up: BREAKUP_WARM_RUN_DAYS warm days, or the radar ice-out signature. Cold again in the season: frozen again,
      from the first freeze-up date.
    - Released (open): THAW_WARM_RUN_DAYS warm days plus a radar pass back within its summer range ("radar"), or the
      warm days alone when the lake has no radar summer level ("air"), or Sentinel-2 water on the lake ("s2"). After a
      Sentinel-2 water reading a new cold run is needed to call it frozen again.
    - 1 Sep resets the freezing degree-days; a lake still frozen then stays frozen (`held_over_sep`).
    - A missing day ends the cold and the warm run. Days after the newest POWER day keep its state; a pass more than
      POWER_STALE_DAYS after it gets no flag.

    Returns {"state" (open, frozen_likely, frozen_s2, breakup_likely or not_assessed with "why"), "since" (start of the
    state), "freeze_up", "released_by", "released_on", "s2_evidence" (the reading that set the state, if any),
    "temp_through", "cold_run_days", "warm_run_days", "fdd_since_sep", "t2m_mean_7d", "t2m_min_mean_7d", "flags" (one
    bool per pass of `series`), "breakup_pass", "radar_assessed", "held_over_sep"}."""
    t_end = Date.fromisoformat(today)
    known = sorted(d for d, row in temps.items() if row.get("t2m") is not None)
    radar_assessed = any(r.get("assessed") for r in (summer_ref or {}).values())
    flags = [False] * len(series)
    empty = {"since": None, "freeze_up": None, "released_by": None, "released_on": None, "s2_evidence": None,
             "temp_through": None, "cold_run_days": None, "warm_run_days": None, "fdd_since_sep": None,
             "t2m_mean_7d": None, "t2m_min_mean_7d": None, "flags": flags, "breakup_pass": None,
             "radar_assessed": radar_assessed, "held_over_sep": False}
    if not known:
        return {"state": "not_assessed", "why": "no NASA POWER air temperature for the lake", **empty}
    through = Date.fromisoformat(known[-1])
    by_day: dict[str, list[int]] = {}
    for i, p in enumerate(series):
        by_day.setdefault(p["date"], []).append(i)
    ev_by_day: dict[str, list[dict]] = {}
    for ev in s2_events or ():
        ev_by_day.setdefault(ev["date"], []).append(ev)
    first = min([Date.fromisoformat(known[0]), record_start(t_end)]
                + [record_start(Date.fromisoformat(p["date"])) for p in series])
    last = max([t_end] + [Date.fromisoformat(p["date"]) for p in series])
    # s: the running state. st is open, frozen or breakup; by says whether Sentinel-2 or the air set "frozen".
    s = {"st": "open", "by": None, "since": None, "freeze_up": None, "released_by": None, "released_on": None,
         "evidence": None, "radar_back": None, "breakup_pass": None, "held": False}
    cold, warm, fdd = 0, 0, 0.0

    def freeze(day: str, by: str, ev: dict | None = None) -> None:
        s.update(st="frozen", by=by, freeze_up=s["freeze_up"] or day, since=s["freeze_up"] or day, radar_back=None,
                 breakup_pass=None, held=False, released_by=None, released_on=None)
        if ev is not None:
            s["evidence"] = ev
        elif by == "air":
            s["evidence"] = None

    def release(day: str, by: str, on: str, ev: dict | None = None) -> None:
        s.update(st="open", by=None, since=day, freeze_up=None, released_by=by, released_on=on, radar_back=None,
                 breakup_pass=None, held=False, evidence=ev)

    d = first
    while d <= last:
        iso = d.isoformat()
        season = in_freeze_season(d)
        if (d.month, d.day) == config.FREEZE_SEASON_START:
            fdd = 0.0
            s["held"] = s["st"] != "open"
        if d <= through:
            v = (temps.get(iso) or {}).get("t2m")
            if v is None:
                cold = warm = 0
            elif v < 0:
                cold, warm = cold + 1, 0
                if season:
                    fdd += -v
            elif v > 0:
                cold, warm = 0, warm + 1
            else:
                cold = warm = 0
            if season and s["st"] == "open" and cold >= config.FREEZE_COLD_RUN_DAYS and fdd >= config.FREEZE_FDD:
                freeze(iso, "air")
            elif s["st"] == "frozen" and warm >= config.BREAKUP_WARM_RUN_DAYS:
                s.update(st="breakup", since=iso, breakup_pass=None, held=False)
            elif season and s["st"] == "breakup" and cold >= config.FREEZE_COLD_RUN_DAYS:
                freeze(iso, "air")
            elif (s["st"] == "breakup" and warm >= config.THAW_WARM_RUN_DAYS
                  and (s["radar_back"] or not radar_assessed)):
                if s["radar_back"]:
                    release(iso, "radar", s["radar_back"])
                else:
                    release(iso, "air", (d - timedelta(days=warm - 1)).isoformat())
        for ev in ev_by_day.get(iso, []):
            kind = s2_kind(ev)
            if kind == "snow":
                if s["st"] == "frozen":
                    s.update(by="s2", evidence=ev)
                else:
                    freeze(iso, "s2", ev)
                    warm = 0  # break-up needs warm days after the scene, not the ones before it
            elif kind == "water":
                release(iso, "s2", iso, ev)
                cold = 0  # a new cold run is needed to call it frozen again
        stale = (d - through).days > config.POWER_STALE_DAYS
        for i in by_day.get(iso, []):
            if stale:
                continue
            p = series[i]
            ref = (summer_ref or {}).get(p["track"])
            test = _radar_test(p, ref)
            if test == "breakup" and s["st"] == "frozen":
                s.update(st="breakup", since=iso, held=False, breakup_pass={
                    "date": iso, "track": p["track"],
                    "contrast_hh_change_db": round(p["core_contrast_hh_db"] - ref["core_contrast_hh_db"], 1),
                    "contrast_hv_change_db": round(p["core_contrast_hv_db"] - ref["core_contrast_hv_db"], 1),
                    "core_dark_share": p["core_dark_share"], "summer_core_dark_share": ref["core_dark_share"]})
                cold = 0  # a new cold run (not the one still going) is needed to call it frozen again
            elif test == "summer" and s["st"] == "breakup":
                s["radar_back"] = iso
                if warm >= config.THAW_WARM_RUN_DAYS and d <= through:
                    release(iso, "radar", iso)
            flags[i] = s["st"] != "open"
        d += timedelta(days=1)
    recent = [k for k in known if (Date.fromisoformat(k) - through).days > -7]
    state = {"open": "open", "breakup": "breakup_likely",
             "frozen": "frozen_s2" if s["by"] == "s2" else "frozen_likely"}[s["st"]]
    out = {"state": state, "since": s["since"], "freeze_up": s["freeze_up"], "released_by": s["released_by"],
           "released_on": s["released_on"], "s2_evidence": s["evidence"], "temp_through": through.isoformat(),
           "cold_run_days": cold, "warm_run_days": warm, "fdd_since_sep": round(fdd, 1),
           "t2m_mean_7d": _mean([temps[k]["t2m"] for k in recent]),
           "t2m_min_mean_7d": _mean([temps[k].get("t2m_min") for k in recent]),
           "flags": flags, "breakup_pass": s["breakup_pass"] if s["st"] == "breakup" else None,
           "radar_assessed": radar_assessed, "held_over_sep": s["held"] and s["st"] != "open"}
    if (t_end - through).days > config.POWER_STALE_DAYS:
        out.update(state="not_assessed", why=f"the newest NASA POWER day is {day_text(through.isoformat())}, more "
                                             f"than {config.POWER_STALE_DAYS} days before this build")
    return out


def is_cold(h: dict) -> bool:
    """A lake worth a Sentinel-2 look: frozen or breaking up, below 0 C on the newest day, or with nights below 0 C on
    average over the last week."""
    return (h["state"] in FROZEN_STATES or (h.get("cold_run_days") or 0) > 0
            or (h.get("t2m_min_mean_7d") is not None and h["t2m_min_mean_7d"] < 0))


# --- Sentinel-2 ------------------------------------------------------------------------------------------------------

def zone_shares(opt: dict, zone: np.ndarray, target: np.ndarray | None = None) -> dict:
    """One Sentinel-2 reading over a lake: the share of the lake zone clear of cloud, cloud shadow and their 100 m edge
    (snow and ice count as clear: they are what the check looks for), and, over the lake itself (`target`: its
    unbuffered outline or its summer radar core; the zone when not given), the share seen clear
    (`target_clear_share`) and, of those clear pixels, the share under snow or ice and the share of water."""
    zone = np.asarray(zone, bool)
    target = zone if target is None else np.asarray(target, bool)
    seen = opt["clear"] & target
    m = int(seen.sum())
    return {"clear_share": float((opt["clear"] & zone).sum() / zone.sum()) if zone.any() else 0.0,
            "snow_share": float((opt["snow"] & seen).sum() / m) if m else 0.0,
            "water_share": float((opt["water"] & seen).sum() / m) if m else 0.0,
            "target_clear_share": float(m / target.sum()) if target.any() else 0.0}


def _freeze_grid(lake, cache_dir, frozen=frozenset()) -> dict:
    """The grid and masks of the Sentinel-2 look: the lake's radar window with its zone and the lake itself
    (lakebuild.freeze_masks, leaving the passes in `frozen` out of the summer core), or, without a cached window, the
    absence check's 10 m grid with the zone standing in for the lake."""
    from sartale.lakebuild import _load_outline, freeze_masks
    from sartale.lakecheck import absence_grid
    from sartale.lakewater import lake_zone

    masks = freeze_masks(lake, Path(cache_dir), frozen) if cache_dir is not None else None
    if masks is not None:
        return masks
    x, y, epsg = absence_grid(lake)
    zone = lake_zone((len(y), len(x)), x, y, epsg, lake, outline_polygon=_load_outline(lake))
    return {"zone": zone, "target": zone, "target_kind": "lake zone", "x": x, "y": y, "epsg": epsg}


def s2_scene_check(lake, today: str, log=print, days: int = config.S2_FREEZE_DAYS, cache_dir=DEFAULT_CACHE,
                   since: str | None = None, frozen=frozenset()) -> dict | None:
    """The clearest Sentinel-2 L2A scene of the last `days` days (or from `since`) whose lake zone is at least
    S2_FREEZE_CLEAR clear and the lake itself at least S2_TARGET_CLEAR clear (ties: the newest), with the snow/ice and
    water shares of the lake seen clear (`zone_shares`, `_freeze_grid`); None when none is clear. The scene search
    (every page), the BOA offset handling and the 100 m cloud-edge buffer are lakecheck's."""
    from sartale.lakecheck import ABSENCE_MAX_TILE_CLOUD, _scene, optical_on_grid, search_scenes
    from sartale.lakes import lake_bbox

    t = Date.fromisoformat(today)
    start = since or (t - timedelta(days=days)).isoformat()
    scenes = [_scene(f, t) for f in search_scenes(lake_bbox(lake), start, today)]
    scenes = [s for s in scenes if s["cloud"] <= ABSENCE_MAX_TILE_CLOUD
              and all(k in s["assets"] for k in ("green", "swir16", "scl"))]
    scenes.sort(key=lambda s: (s["date"], -s["cloud"], s["id"]), reverse=True)
    g = _freeze_grid(lake, cache_dir, frozen)
    best = None
    for scene in scenes:
        try:
            opt = optical_on_grid(scene, g["x"], g["y"], g["epsg"])
        except Exception as e:  # noqa: BLE001 - an unreadable scene is skipped, and said so
            log(f"{lake.id} freeze vs {scene['id']}: unreadable ({type(e).__name__})")
            continue
        s = zone_shares(opt, g["zone"], g["target"])
        ok = s["clear_share"] >= config.S2_FREEZE_CLEAR and s["target_clear_share"] >= config.S2_TARGET_CLEAR
        log(f"{lake.id} freeze vs {scene['id']} ({scene['date']}): zone clear {100 * s['clear_share']:.1f}%, "
            f"{g['target_kind']} clear {100 * s['target_clear_share']:.0f}%: snow/ice {100 * s['snow_share']:.1f}%, "
            f"water {100 * s['water_share']:.1f}% of it: {'clear' if ok else 'not clear enough'}")
        if ok and (best is None or (round(s["clear_share"], 3), scene["date"]) > (best["clear_share"], best["date"])):
            best = {"date": scene["date"], "s2_id": scene["id"], "clear_share": round(s["clear_share"], 3),
                    "target_clear_share": round(s["target_clear_share"], 3),
                    "snow_share": round(s["snow_share"], 3), "water_share": round(s["water_share"], 3),
                    "water_over": g["target_kind"]}
    return best


# --- words -----------------------------------------------------------------------------------------------------------

def _pct(v: float) -> str:
    return f"{round(100 * v)}%"


def _run_text(cold: int | None, warm: int | None) -> str:
    if cold:
        return f"below 0 °C for {cold} {'day' if cold == 1 else 'days'} in a row"
    if warm:
        return f"above 0 °C for {warm} {'day' if warm == 1 else 'days'} in a row"
    return "at 0 °C or without a value on the newest day"


def _air_text(f: dict, elevation_m: float) -> str:
    return (f"The daily mean air temperature at the lake has been {_run_text(f['cold_run_days'], f['warm_run_days'])}, "
            f"with {f['fdd_since_sep']:.0f} freezing degree-days since 1 Sep (NASA POWER to "
            f"{day_text(f['temp_through'])}, adjusted to the lake's height of {round(elevation_m):,} m).")


RULE_TEXT = (f"the freeze rule ({config.FREEZE_COLD_RUN_DAYS} days in a row below 0 °C and {config.FREEZE_FDD:.0f} "
             "freezing degree-days since 1 Sep)")
NO_VERDICT = ("Radar cannot tell new ice from open water, and frozen ground around a lake can read as water, so SARtale "
              "gives no growing or shrinking verdict while the lake is frozen.")
NO_OPEN_CLAIM = "Open water not confirmed by radar or Sentinel-2."


def _where(ev: dict) -> str:
    return f"the {ev.get('water_over', 'lake zone')} seen clear"


def s2_text(f: dict) -> str:
    """This build's Sentinel-2 look in words, and the last evidence when it is older."""
    s, ev = f.get("s2"), f.get("s2_evidence")
    out = []
    if s:
        out.append(f"Clearest Sentinel-2 view of the last {config.S2_FREEZE_DAYS} days: {day_text(s['date'])} "
                   f"({s['s2_id']}), snow or ice on {_pct(s['snow_share'])} and water on {_pct(s['water_share'])} of "
                   f"{_where(s)}.")
    elif f.get("s2_searched"):
        out.append(f"No clear Sentinel-2 view of the lake in the last {config.S2_FREEZE_DAYS} days.")
    if ev and (not s or ev["date"] != s["date"]):
        what = (f"snow or ice on {_pct(ev['snow_share'])}" if s2_kind(ev) == "snow"
                else f"water on {_pct(ev['water_share'])}")
        out.append(f"Last Sentinel-2 evidence: {day_text(ev['date'])} ({ev['s2_id']}), {what} of {_where(ev)}.")
    return " ".join(out)


def open_headline(f: dict) -> str | None:
    """How an open lake was released this season, in the words the card and the brief use; None when it never froze
    this season. Never says the lake is open from air temperature alone."""
    by, on = f.get("released_by"), f.get("released_on")
    if by == "s2":
        return f"Open water seen by Sentinel-2 on {day_text(on)}"
    if by == "radar":
        return f"Radar back within its summer range on {day_text(on)}"
    if by == "air":
        return f"No freeze signal in air temperature since {day_text(on)}; open water not confirmed by radar or Sentinel-2"
    return None


def freeze_reason(f: dict, elevation_m: float | None) -> str:
    """What the freeze state rests on, in words: the temperature run and its date, the Sentinel-2 scene when one was
    used, the radar pass at break-up or release. It never says the radar saw ice, how thick ice is, or that a lake is
    open from air temperature alone."""
    state = f["state"]
    if state == "not_assessed":
        return f"Freeze not assessed: {f['why']}. The usual assessment applies."
    air = _air_text(f, elevation_m)
    s2 = s2_text(f)
    held = ""
    if state in FROZEN_STATES and f.get("held_over_sep"):
        held = ("It was still frozen or breaking up on 1 Sep, which should not happen; it stays so until the break-up "
                "and open-again rules release it.")
    elif state in FROZEN_STATES and f.get("in_season") is False:
        held = ("The freeze season ended on 31 May, but a frozen lake stays so until the break-up and open-again rules "
                "release it.")
    if state == "frozen_s2":
        ev = f["s2_evidence"]
        lead = (f"Snow or ice covers {_pct(ev['snow_share'])} of {_where(ev)} in a Sentinel-2 scene of "
                f"{day_text(ev['date'])} ({ev['s2_id']}).")
        if f.get("since") and f["since"] != ev["date"]:
            lead += f" The lake has probably been frozen since {day_text(f['since'])}."
        if not f.get("s2") or f["s2"]["date"] != ev["date"]:
            lead += (" That view stands until a clear one shows open water or the air-temperature rules call "
                     "break-up.")
        return " ".join(t for t in (lead, air, held, NO_VERDICT) if t)
    if state == "frozen_likely":
        return " ".join(t for t in (f"Probably frozen since {day_text(f['since'])}, when the air at the lake met "
                                    f"{RULE_TEXT}.", air, s2, held, NO_VERDICT) if t)
    if state == "breakup_likely":
        b = f.get("breakup_pass")
        froze = f" (frozen since {day_text(f['freeze_up'])})" if f.get("freeze_up") else ""
        if b:
            lead = (f"Ice probably breaking up since {day_text(f['since'])}: on the {b['track']} pass that day the lake "
                    f"core was {b['contrast_hh_change_db']:+.1f} dB (HH) and {b['contrast_hv_change_db']:+.1f} dB (HV) "
                    f"brighter against its surroundings than in summer, and {_pct(b['core_dark_share'])} of it was "
                    f"dark (summer {_pct(b['summer_core_dark_share'])}), a brightening that matches ice going out.")
        else:
            lead = (f"Ice probably breaking up since {day_text(f['since'])}: the lake was probably frozen{froze}, and "
                    f"the air at the lake has since been above 0 °C for {config.BREAKUP_WARM_RUN_DAYS} days in a row.")
        return " ".join(t for t in (lead, air, s2, held, "SARtale gives no growing or shrinking verdict until the "
                                    "lake is released by radar or Sentinel-2, or by the warm days where the lake has "
                                    "no radar summer level.") if t)
    # open
    how = open_headline(f)
    if how:
        if f.get("released_by") == "air":
            lead = (f"{how}: {config.THAW_WARM_RUN_DAYS} days in a row above 0 °C after break-up, and this lake has no "
                    "radar summer level to check against. It is no longer counted as frozen, so the usual assessment "
                    "applies.")
        elif f.get("released_by") == "radar":
            lead = (f"{how}, after {config.THAW_WARM_RUN_DAYS} days in a row above 0 °C: the lake is no longer counted "
                    "as frozen, so the usual assessment applies.")
        else:
            lead = f"{how}, so the usual assessment applies."
        return " ".join(t for t in (lead, air, s2) if t)
    if not f.get("in_season"):
        return " ".join(t for t in ("Outside the freeze season (1 Sep–31 May) no freeze-up is called: the usual "
                                    "assessment applies.", air, s2) if t)
    lead = (f"Not frozen by {RULE_TEXT}, so the usual assessment applies. Air temperature alone cannot show that the "
            "lake is open.")
    return " ".join(t for t in (lead, air, s2) if t)


# --- one lake --------------------------------------------------------------------------------------------------------

def _not_assessed(why: str, checked: str) -> dict:
    f = {"state": "not_assessed", "why": why, "since": None, "freeze_up": None, "released_by": None,
         "released_on": None, "temp_through": None, "checked": checked, "cold_run_days": None, "warm_run_days": None,
         "fdd_since_sep": None, "t2m_mean_7d": None, "t2m_min_mean_7d": None, "s2": None, "s2_evidence": None,
         "s2_events": [], "s2_searched": False, "breakup_pass": None, "frozen_passes": 0, "source": POWER_SOURCE}
    f["reason"] = f["fresh_reason"] = freeze_reason(f, None)
    return f


def unflagged(series: list[dict]) -> list[dict]:
    return [{k: v for k, v in p.items() if k != "frozen"} for p in series]


def with_status(entry: dict, series: list[dict], freeze: dict | None) -> dict:
    """The entry with `series` (frozen flags set) and its status again: the usual one from the passes not flagged
    frozen, or, while the lake is frozen or breaking up today, the frozen status, which takes precedence over every
    status but "No lake now" (a no-lake site never gets here)."""
    if freeze and freeze["state"] in FREEZE_STATUS:
        everything = unflagged(series)
        latest: dict[str, str] = {}
        for p in everything:
            latest[p["track"]] = max(latest.get(p["track"], ""), p["date"])
        status = frozen_status(lake_status(everything, latest), freeze)
    elif series:
        status = open_water_status(series)
    else:
        status = entry["status"]  # no pass at all: the build's own status ("Not enough NISAR looks yet") stands
    return {**entry, "series": series, "status": status, "freeze": freeze}


def power_start(series: list[dict], today: str) -> str:
    """The first day to fetch: the record start (`record_start`) of the earliest pass or today, so every pass gets its
    flag from the record of the season it falls in, or (1 Jun-31 Aug) of the season just before it, when a lake frozen
    in winter may still be frozen."""
    return min(record_start(Date.fromisoformat(d)) for d in [p["date"] for p in series] + [today]).isoformat()


def _kept(prior: dict, prior_flags: dict, series: list[dict], why: str, today: str) -> tuple[dict, list[dict]]:
    """The last freeze check kept, when NASA POWER is stale or cannot be read: its state, its pass flags (a pass it did
    not see is flagged when the lake was frozen or breaking up and the pass came after its newest air temperature) and
    its reason, marked as not refreshed since its own check."""
    since = prior.get("not_refreshed_since") or prior.get("checked")
    f = {**prior, "not_refreshed_since": since, "refresh_problem": why, "checked": today}
    base = prior.get("fresh_reason") or prior.get("reason", "")
    f["reason"] = f"{base} Not refreshed since {day_text(since)}: {why}."
    frozen_now = prior.get("state") in FROZEN_STATES
    through = prior.get("temp_through") or ""
    flagged = [{**p, "frozen": prior_flags.get((p["date"], p["track"]), frozen_now and p["date"] > through)}
               for p in series]
    f["frozen_passes"] = sum(1 for p in flagged if p["frozen"])
    return f, flagged


def _usable(prior) -> bool:
    return isinstance(prior, dict) and prior.get("state") in ("open",) + FROZEN_STATES and bool(prior.get("checked"))


def refreshed_summer_ref(series: list[dict], summer_ref: dict) -> dict:
    """The summer level again from the passes' own core numbers, leaving out the passes now flagged frozen (the
    build's summer core and level left out only the passes the last check flagged)."""
    from sartale.lakebuild import summer_reference
    return summer_reference(series, {k: v.get("core_px", 0) for k, v in (summer_ref or {}).items()})


def needs_last_open(entry: dict) -> bool:
    """True when the lake is frozen or breaking up, or its pictured pass was taken while it was: then no view may
    present that pass as a water measurement, and `last_open` gives the pass they show instead."""
    if ((entry.get("freeze") or {}).get("state")) in FROZEN_STATES:
        return True
    im = entry.get("images") or {}
    return any(p.get("frozen") and p["date"] == im.get("date") and p["track"] == im.get("track")
               for p in entry.get("series", []))


def last_open(entry: dict) -> dict | None:
    """The lake's latest open-water pass on its status track (valid, not flagged frozen) with the assessment it had
    then (`lake_status` of that track's open-water passes up to it): {"date", "track", "crid", "area_km2", "status",
    "change_km2", "noise_km2", "looks", "ref_km2", "images": None}; lakes-freeze draws its pictures. None without one."""
    track = (entry.get("status") or {}).get("track") or (entry.get("images") or {}).get("track")
    pts = sorted((p for p in entry.get("series", []) if p["track"] == track and is_valid(p)), key=lambda p: p["date"])
    if not pts:
        return None
    p = pts[-1]
    st = lake_status(pts)
    change = st["change_km2"]
    return {"date": p["date"], "track": p["track"], "crid": p.get("crid"), "area_km2": p["area_km2"],
            "status": st["status"], "change_km2": change, "noise_km2": st["noise_km2"], "looks": st["looks"],
            "ref_km2": None if change is None else round(p["area_km2"] - change, 6), "images": None}


def freeze_lake(lake, entry: dict, today: str, power=None, s2_check=None, log=print) -> dict:
    """`_freeze_lake`, then `last_open` when a view must not show the newest pass as water (`needs_last_open`)."""
    out = {k: v for k, v in _freeze_lake(lake, entry, today, power, s2_check, log).items() if k != "last_open"}
    if out.get("freeze") is not None and needs_last_open(out):
        out["last_open"] = last_open(out)
    return out


def _freeze_lake(lake, entry: dict, today: str, power=None, s2_check=None, log=print) -> dict:
    """A built lakes.json entry with its freeze state (`freeze`), each pass's `frozen` flag, its summer level and its
    status again.

    Only sites the register holds as lakes are assessed. A site with no lake now (or where a lake may be forming)
    gets no freeze state and no flags; an unconfirmed lake is "not assessed". The last check (carried by the build in
    `freeze`, its flags on the passes) gives the Sentinel-2 evidence that still holds; when NASA POWER is stale or
    cannot be read, it is kept whole, marked "not refreshed since" (`_kept`), or, without one, the lake is "not
    assessed" with no flags. Never raises for a failed download. `power` and `s2_check` default to fetch_power and
    s2_scene_check."""
    power, s2_check = power or fetch_power, s2_check or s2_scene_check
    prior = entry.get("freeze")
    prior_flags = {(p["date"], p["track"]): bool(p.get("frozen")) for p in entry.get("series", []) if "frozen" in p}
    series = unflagged(entry.get("series", []))
    state = entry.get("lake_state", "lake")
    if state != "lake" or lake.lake_state != "lake":
        out = {k: v for k, v in entry.items() if k != "freeze"}
        if state == "unconfirmed":
            return with_status(out, series, _not_assessed("the site is not a confirmed lake", today))
        return {**out, "series": series}
    # The register's lake height is what the check uses; the entry shows it even when the build ran before it existed.
    entry = {**entry, "elevation_m": lake.elevation_m, "elevation_source": lake.elevation_source}
    if lake.elevation_m is None:
        return with_status(entry, series, _not_assessed(
            "no lake height in the register yet (the Copernicus DEM could not be read for it; lakes-elevation tries "
            "again at the next refresh)", today))

    def unrefreshed(why: str) -> dict:
        if _usable(prior):
            f, flagged = _kept(prior, prior_flags, series, why, today)
            return with_status(entry, flagged, f)
        return with_status(entry, series, _not_assessed(why, today))

    start = power_start(series, today)
    try:
        raw = power(lake.lon, lake.lat, start, today)
    except Exception as e:  # noqa: BLE001 - the last check stands, or the usual assessment, and the lake says why
        log(f"{lake.id}: NASA POWER failed ({type(e).__name__})")
        return unrefreshed("NASA POWER air temperature could not be fetched")
    temps = corrected(raw, lake.elevation_m)
    events = [ev for ev in ((prior or {}).get("s2_events") or []) if ev.get("date", "") >= start]
    ref = entry.get("summer_ref") or {}
    h = freeze_history(temps, series, ref, today, events)
    if h["state"] == "not_assessed":
        return unrefreshed(h["why"])
    # The summer level without the passes now flagged frozen (late ice-out passes are not open water), then again.
    ref = refreshed_summer_ref([{**p, "frozen": f} for p, f in zip(series, h["flags"])], ref)
    h = freeze_history(temps, series, ref, today, events)
    s2, searched = None, False
    if is_cold(h):
        frozen_ids = {f"{p['date']}_{p['track']}" for p, f in zip(series, h["flags"]) if f}
        try:
            s2, searched = s2_check(lake, today, log, frozen=frozen_ids), True
        except Exception as e:  # noqa: BLE001 - the temperature state stands
            log(f"{lake.id}: Sentinel-2 search failed ({type(e).__name__})")
    if s2_kind(s2) and not any(ev["date"] == s2["date"] and ev.get("s2_id") == s2["s2_id"] for ev in events):
        events = sorted(events + [s2], key=lambda ev: (ev["date"], ev.get("s2_id", "")))
        h = freeze_history(temps, series, ref, today, events)
    # A release from an earlier season says nothing about this one.
    if h["state"] == "open" and h.get("released_on") and h["released_on"] < record_start(Date.fromisoformat(today)).isoformat():
        h = {**h, "since": None, "released_by": None, "released_on": None, "s2_evidence": None}
    series = [{**p, "frozen": bool(f)} for p, f in zip(series, h["flags"])]
    f = {"state": h["state"], "since": h["since"], "freeze_up": h["freeze_up"], "released_by": h["released_by"],
         "released_on": h["released_on"], "temp_through": h["temp_through"], "checked": today,
         "cold_run_days": h["cold_run_days"], "warm_run_days": h["warm_run_days"],
         "fdd_since_sep": h["fdd_since_sep"], "t2m_mean_7d": h["t2m_mean_7d"], "t2m_min_mean_7d": h["t2m_min_mean_7d"],
         "power_cell_elev_m": raw["cell_elev_m"], "s2": s2, "s2_searched": searched,
         "s2_evidence": h["s2_evidence"], "s2_events": events,
         "breakup_pass": h["breakup_pass"], "frozen_passes": sum(1 for p in series if p["frozen"]),
         "radar_assessed": h["radar_assessed"], "in_season": in_freeze_season(Date.fromisoformat(today)),
         "held_over_sep": h.get("held_over_sep", False), "source": POWER_SOURCE}
    f["reason"] = f["fresh_reason"] = freeze_reason(f, lake.elevation_m)
    return with_status({**entry, "summer_ref": ref}, series, f)
