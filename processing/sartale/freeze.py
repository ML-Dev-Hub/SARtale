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
from sartale.lakestatus import FREEZE_STATUS, day_text, frozen_status, lake_status, open_water_status

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
DEFAULT_CACHE = Path(__file__).resolve().parents[2] / "data" / "lakes"  # the NISAR window cache lakes-fetch fills
POWER_SOURCE = "NASA POWER daily T2M and T2M_MIN (MERRA-2 based), moved to the lake's height at -6.5 C/km"
POWER_TIMEOUT_S = 60
POWER_FILL = -900  # POWER marks a missing day with -999
FROZEN_STATES = ("frozen_likely", "frozen_s2", "breakup_likely")
ICE_STATES = ("frozen_likely", "breakup_likely")  # temperature/radar states a pass can carry


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


def freeze_history(temps: dict[str, dict], series: list[dict], summer_ref: dict, today: str) -> dict:
    """The freeze state day by day from the first freeze season that holds a pass (or today) to `today`, from the
    lake-height air temperature `temps` (iso -> {"t2m", "t2m_min"}, None for a missing day) and the passes in `series`
    (each tested by radar against `summer_ref` of its track).

    Freeze-up can start only in the season (1 Sep-31 May), but a lake that is frozen or breaking up stays so past
    31 May until the break-up and open-again rules release it (warm runs, a radar pass back within its summer range, or
    a clear Sentinel-2 image of water), so a high lake whose ice goes out in late June or July keeps its state. Each
    1 Sep resets the freezing degree-days to 0; a lake still frozen then stays frozen (`held_over_sep` says so). A
    missing day inside the record ends the cold and the warm run (the rule is late rather than early). Days after the
    newest POWER day keep its state; a pass more than POWER_STALE_DAYS after it gets no flag.

    Returns {"state", "since", "temp_through", "cold_run_days", "warm_run_days", "fdd_since_sep", "t2m_mean_7d",
    "t2m_min_mean_7d", "flags" (one bool per pass of `series`, in order), "breakup_pass" (the pass that set break-up by
    radar, or None), "radar_assessed", "held_over_sep"}; state "not_assessed" (with "why") without POWER data or when
    its newest day is more than POWER_STALE_DAYS before `today`."""
    t_end = Date.fromisoformat(today)
    known = sorted(d for d, row in temps.items() if row.get("t2m") is not None)
    radar_assessed = any(r.get("assessed") for r in (summer_ref or {}).values())
    flags = [False] * len(series)
    if not known:
        return {"state": "not_assessed", "why": "no NASA POWER air temperature for the lake", "since": None,
                "temp_through": None, "cold_run_days": None, "warm_run_days": None, "fdd_since_sep": None,
                "t2m_mean_7d": None, "t2m_min_mean_7d": None, "flags": flags, "breakup_pass": None,
                "radar_assessed": radar_assessed, "held_over_sep": False}
    through = Date.fromisoformat(known[-1])
    by_day: dict[str, list[int]] = {}
    for i, p in enumerate(series):
        by_day.setdefault(p["date"], []).append(i)
    first = min([Date.fromisoformat(known[0]), record_start(t_end)]
                + [record_start(Date.fromisoformat(p["date"])) for p in series])
    state, since, cold, warm, fdd, radar_back, breakup_pass = "open", None, 0, 0, 0.0, False, None
    held = False  # still frozen or breaking up when 1 Sep came
    d = first
    last = max([t_end] + [Date.fromisoformat(p["date"]) for p in series])
    while d <= last:
        iso = d.isoformat()
        season = in_freeze_season(d)
        if (d.month, d.day) == config.FREEZE_SEASON_START:
            fdd = 0.0
            held = state in ICE_STATES
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
            # Freeze-up (and freezing again during break-up) only in the season; break-up and open again all year.
            if season and state == "open" and cold >= config.FREEZE_COLD_RUN_DAYS and fdd >= config.FREEZE_FDD:
                state, since, held = "frozen_likely", iso, False
            elif state == "frozen_likely" and warm >= config.BREAKUP_WARM_RUN_DAYS:
                state, since, breakup_pass, held = "breakup_likely", iso, None, False
            elif season and state == "breakup_likely" and cold >= config.FREEZE_COLD_RUN_DAYS:
                state, since, radar_back, breakup_pass, held = "frozen_likely", iso, False, None, False
            elif state == "breakup_likely" and warm >= config.THAW_WARM_RUN_DAYS and (radar_back or not radar_assessed):
                state, since, breakup_pass, radar_back, held = "open", iso, None, False, False
        stale = (d - through).days > config.POWER_STALE_DAYS
        for i in by_day.get(iso, []):
            if stale:
                continue
            p = series[i]
            test = _radar_test(p, (summer_ref or {}).get(p["track"]))
            if test == "breakup" and state == "frozen_likely":
                # a new cold run (not the one still going) is needed to call it frozen again
                state, since, cold, held = "breakup_likely", iso, 0, False
                breakup_pass = {"date": iso, "track": p["track"],
                                "contrast_hh_change_db": round(p["core_contrast_hh_db"] - summer_ref[p["track"]]["core_contrast_hh_db"], 1),
                                "contrast_hv_change_db": round(p["core_contrast_hv_db"] - summer_ref[p["track"]]["core_contrast_hv_db"], 1),
                                "core_dark_share": p["core_dark_share"],
                                "summer_core_dark_share": summer_ref[p["track"]]["core_dark_share"]}
            elif test == "summer" and state == "breakup_likely":
                radar_back = True
                if warm >= config.THAW_WARM_RUN_DAYS and d <= through:
                    state, since, radar_back, held = "open", iso, False, False
            flags[i] = state in ICE_STATES
        d += timedelta(days=1)
    week = [(Date.fromisoformat(k) - through).days > -7 for k in known]
    recent = [k for k, w in zip(known, week) if w]
    out = {"state": state, "since": since, "temp_through": through.isoformat(), "cold_run_days": cold,
           "warm_run_days": warm, "fdd_since_sep": round(fdd, 1),
           "t2m_mean_7d": _mean([temps[k]["t2m"] for k in recent]),
           "t2m_min_mean_7d": _mean([temps[k].get("t2m_min") for k in recent]),
           "flags": flags, "breakup_pass": breakup_pass if state == "breakup_likely" else None,
           "radar_assessed": radar_assessed, "held_over_sep": held and state in ICE_STATES}
    if (t_end - through).days > config.POWER_STALE_DAYS:
        out.update(state="not_assessed", since=None,
                   why=f"the newest NASA POWER day is {day_text(through.isoformat())}, more than "
                       f"{config.POWER_STALE_DAYS} days before this build")
    return out


def is_cold(h: dict) -> bool:
    """A lake worth a Sentinel-2 look: frozen or breaking up by the rule, below 0 C on the newest day, or with nights
    below 0 C on average over the last week."""
    return (h["state"] in ICE_STATES or (h.get("cold_run_days") or 0) > 0
            or (h.get("t2m_min_mean_7d") is not None and h["t2m_min_mean_7d"] < 0))


def combine(h: dict, s2: dict | None) -> tuple[str, str | None]:
    """(state, since) once the Sentinel-2 scene is taken into account: snow or ice on S2_FROZEN_SNOW_SHARE of the clear
    zone makes it frozen_s2 (since the freeze date when the temperature rule already had one), water on
    S2_OPEN_WATER_SHARE makes it open; otherwise the temperature/radar state stands."""
    state, since = h["state"], h.get("since")
    if state == "not_assessed" or not s2:
        return state, since
    if s2["snow_share"] >= config.S2_FROZEN_SNOW_SHARE:
        return "frozen_s2", since if state in ICE_STATES and since else s2["date"]
    if s2["water_share"] >= config.S2_OPEN_WATER_SHARE:
        return "open", s2["date"]
    return state, since


# --- Sentinel-2 ------------------------------------------------------------------------------------------------------

def zone_shares(opt: dict, zone: np.ndarray, target: np.ndarray | None = None) -> dict:
    """One Sentinel-2 reading over a lake: the share of the lake zone clear of cloud, cloud shadow and their 100 m edge
    (snow and ice count as clear here: they are what the check looks for); of those clear zone pixels, the share
    under snow or ice; and the share of water over the clear pixels of `target` (where open water is looked for: the
    unbuffered outline or the summer radar core; the zone when not given), with `target_clear_share`."""
    zone = np.asarray(zone, bool)
    target = zone if target is None else np.asarray(target, bool)
    clear = opt["clear"] & zone
    n = int(clear.sum())
    seen = opt["clear"] & target
    m = int(seen.sum())
    return {"clear_share": float(clear.sum() / zone.sum()) if zone.any() else 0.0,
            "snow_share": float((opt["snow"] & clear).sum() / n) if n else 0.0,
            "water_share": float((opt["water"] & seen).sum() / m) if m else 0.0,
            "target_clear_share": float(m / target.sum()) if target.any() else 0.0}


def _freeze_grid(lake, cache_dir) -> dict:
    """The grid and masks of the Sentinel-2 look: the lake's radar window with its zone and open-water target
    (lakebuild.freeze_masks), or, without a cached window, the absence check's 10 m grid with the zone as target."""
    from sartale.lakebuild import _load_outline, freeze_masks
    from sartale.lakecheck import absence_grid
    from sartale.lakewater import lake_zone

    masks = freeze_masks(lake, Path(cache_dir)) if cache_dir is not None else None
    if masks is not None:
        return masks
    x, y, epsg = absence_grid(lake)
    zone = lake_zone((len(y), len(x)), x, y, epsg, lake, outline_polygon=_load_outline(lake))
    return {"zone": zone, "target": zone, "target_kind": "lake zone", "x": x, "y": y, "epsg": epsg}


def s2_scene_check(lake, today: str, log=print, days: int = config.S2_FREEZE_DAYS, cache_dir=DEFAULT_CACHE,
                   since: str | None = None) -> dict | None:
    """The clearest Sentinel-2 L2A scene of the last `days` days (or from `since`) whose lake zone is at least
    S2_FREEZE_CLEAR clear (ties: the newest), with the snow/ice share of the clear zone and the water share of the clear
    open-water target (`zone_shares`, `_freeze_grid`); None when none is clear. The scene search (every page), the BOA
    offset handling and the 100 m cloud-edge buffer are lakecheck's."""
    from sartale.lakecheck import ABSENCE_MAX_TILE_CLOUD, _scene, optical_on_grid, search_scenes
    from sartale.lakes import lake_bbox

    t = Date.fromisoformat(today)
    start = since or (t - timedelta(days=days)).isoformat()
    scenes = [_scene(f, t) for f in search_scenes(lake_bbox(lake), start, today)]
    scenes = [s for s in scenes if s["cloud"] <= ABSENCE_MAX_TILE_CLOUD
              and all(k in s["assets"] for k in ("green", "swir16", "scl"))]
    scenes.sort(key=lambda s: (s["date"], -s["cloud"], s["id"]), reverse=True)
    g = _freeze_grid(lake, cache_dir)
    best = None
    for scene in scenes:
        try:
            opt = optical_on_grid(scene, g["x"], g["y"], g["epsg"])
        except Exception as e:  # noqa: BLE001 - an unreadable scene is skipped, and said so
            log(f"{lake.id} freeze vs {scene['id']}: unreadable ({type(e).__name__})")
            continue
        s = zone_shares(opt, g["zone"], g["target"])
        ok = s["clear_share"] >= config.S2_FREEZE_CLEAR
        log(f"{lake.id} freeze vs {scene['id']} ({scene['date']}): zone clear {100 * s['clear_share']:.1f}%, "
            f"snow/ice {100 * s['snow_share']:.1f}% of the clear zone, water {100 * s['water_share']:.1f}% of the "
            f"clear {g['target_kind']} ({100 * s['target_clear_share']:.0f}% of it clear): "
            f"{'clear' if ok else 'not clear enough'}")
        if ok and (best is None or (round(s["clear_share"], 3), scene["date"]) > (best["clear_share"], best["date"])):
            best = {"date": scene["date"], "s2_id": scene["id"], "clear_share": round(s["clear_share"], 3),
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


def s2_text(f: dict) -> str:
    """The Sentinel-2 evidence in words."""
    s = f.get("s2")
    if s:
        return (f"Clearest Sentinel-2 view of the last {config.S2_FREEZE_DAYS} days: {day_text(s['date'])} "
                f"({s['s2_id']}), snow or ice on {_pct(s['snow_share'])} of the lake zone seen clear, water on "
                f"{_pct(s['water_share'])} of the {s.get('water_over', 'lake zone')} seen clear.")
    if f.get("s2_searched"):
        return f"No clear Sentinel-2 view of the lake zone in the last {config.S2_FREEZE_DAYS} days."
    return ""


def freeze_reason(f: dict, elevation_m: float | None, temp_state: str | None = None) -> str:
    """What the freeze state rests on, in words: the temperature run and its date, the Sentinel-2 scene when one was
    used, the radar pass at break-up. It never says the radar saw ice, how thick ice is, or that a lake is open from
    temperature alone."""
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
        s = f["s2"]
        lead = (f"Snow or ice covers {_pct(s['snow_share'])} of the lake zone seen clear in a Sentinel-2 scene of "
                f"{day_text(s['date'])} ({s['s2_id']}).")
        if temp_state in ICE_STATES and f.get("since") and f["since"] != s["date"]:
            lead += f" By {RULE_TEXT} the lake has probably been frozen since {day_text(f['since'])}."
        return " ".join(t for t in (lead, air, held, NO_VERDICT) if t)
    if state == "frozen_likely":
        return " ".join(t for t in (f"Probably frozen since {day_text(f['since'])}, when the air at the lake met "
                                    f"{RULE_TEXT}.", air, s2, held, NO_VERDICT) if t)
    if state == "breakup_likely":
        b = f.get("breakup_pass")
        if b:
            lead = (f"Ice probably breaking up since {day_text(f['since'])}: on the {b['track']} pass that day the lake "
                    f"core was {b['contrast_hh_change_db']:+.1f} dB (HH) and {b['contrast_hv_change_db']:+.1f} dB (HV) "
                    f"brighter against its surroundings than in summer, and {_pct(b['core_dark_share'])} of it was "
                    f"dark (summer {_pct(b['summer_core_dark_share'])}), as melting ice looks on radar.")
        else:
            lead = (f"Ice probably breaking up since {day_text(f['since'])}: the lake was probably frozen, and the air "
                    f"at the lake has since been above 0 °C for {config.BREAKUP_WARM_RUN_DAYS} days in a row.")
        return " ".join(t for t in (lead, air, s2, held, "SARtale gives no growing or shrinking verdict until the lake "
                                    "is open again.") if t)
    # open
    s = f.get("s2")
    if s and s["water_share"] >= config.S2_OPEN_WATER_SHARE:
        lead = (f"Open water on {_pct(s['water_share'])} of the {s.get('water_over', 'lake zone')} seen clear in a "
                f"Sentinel-2 scene of "
                f"{day_text(s['date'])} ({s['s2_id']}), so the usual assessment applies.")
        return " ".join((lead, air))
    if not f.get("in_season") and not f.get("since"):
        return " ".join(t for t in ("Outside the freeze season (1 Sep–31 May) no freeze-up is called: the usual "
                                    "assessment applies.", air, s2) if t)
    if f.get("since"):
        lead = (f"Open again since {day_text(f['since'])} by the air-temperature rule ({config.THAW_WARM_RUN_DAYS} days "
                "in a row above 0 °C" + (" and a radar pass back within its summer range" if f.get("radar_assessed") else "")
                + "), so the usual assessment applies.")
    else:
        lead = (f"Not frozen by {RULE_TEXT}, so the usual assessment applies. Air temperature alone cannot show that "
                "the lake is open.")
    return " ".join(t for t in (lead, air, s2) if t)


# --- one lake --------------------------------------------------------------------------------------------------------

def _not_assessed(why: str, checked: str) -> dict:
    f = {"state": "not_assessed", "why": why, "since": None, "temp_through": None, "checked": checked,
         "cold_run_days": None, "warm_run_days": None, "fdd_since_sep": None, "t2m_mean_7d": None,
         "t2m_min_mean_7d": None, "s2": None, "s2_searched": False, "breakup_pass": None, "frozen_passes": 0,
         "source": POWER_SOURCE}
    f["reason"] = freeze_reason(f, None)
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


def freeze_lake(lake, entry: dict, today: str, power=None, s2_check=None, log=print) -> dict:
    """A built lakes.json entry with its freeze state (`freeze`), each pass's `frozen` flag and its status again.

    Only sites the register holds as lakes are assessed. A site with no lake now (or where a lake may be forming)
    gets no freeze state and no flags; an unconfirmed lake is "not assessed". Never raises for a failed download: the
    lake is then "not assessed" and keeps the usual assessment. `power` and `s2_check` default to fetch_power and
    s2_scene_check."""
    power, s2_check = power or fetch_power, s2_check or s2_scene_check
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
    try:
        raw = power(lake.lon, lake.lat, power_start(series, today), today)
    except Exception as e:  # noqa: BLE001 - the usual assessment stands, and the lake says why
        log(f"{lake.id}: NASA POWER failed ({type(e).__name__})")
        return with_status(entry, series, _not_assessed("NASA POWER air temperature could not be fetched", today))
    temps = corrected(raw, lake.elevation_m)
    h = freeze_history(temps, series, entry.get("summer_ref") or {}, today)
    s2, searched = None, False
    if h["state"] != "not_assessed" and is_cold(h):
        try:
            s2, searched = s2_check(lake, today, log), True
        except Exception as e:  # noqa: BLE001 - the temperature state stands
            log(f"{lake.id}: Sentinel-2 search failed ({type(e).__name__})")
    state, since = combine(h, s2)
    flags = list(h["flags"])
    if state == "open" and s2 and s2["water_share"] >= config.S2_OPEN_WATER_SHARE:
        flags = [f and p["date"] < s2["date"] for f, p in zip(flags, series)]
    series = [{**p, "frozen": bool(f)} for p, f in zip(series, flags)]
    f = {"state": state, "since": since, "temp_through": h["temp_through"], "checked": today,
         "cold_run_days": h["cold_run_days"], "warm_run_days": h["warm_run_days"],
         "fdd_since_sep": h["fdd_since_sep"], "t2m_mean_7d": h["t2m_mean_7d"], "t2m_min_mean_7d": h["t2m_min_mean_7d"],
         "power_cell_elev_m": raw["cell_elev_m"], "s2": s2, "s2_searched": searched,
         "breakup_pass": h["breakup_pass"] if state == "breakup_likely" else None,
         "frozen_passes": sum(1 for p in series if p["frozen"]), "radar_assessed": h["radar_assessed"],
         "in_season": in_freeze_season(Date.fromisoformat(today)), "held_over_sep": h.get("held_over_sep", False),
         "source": POWER_SOURCE}
    if state == "not_assessed":
        f["why"] = h["why"]
    f["reason"] = freeze_reason(f, lake.elevation_m, h["state"])
    return with_status(entry, series, f)
