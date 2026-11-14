"""The summary lakes.json carries for the overview and the lake page: each lake's SUPARCO match, largest recorded
extent and the share of it the lake fills now, the status's change threshold and latest pass, and the headline counts
with the build this one replaced. Written by Python so that the page, the CSV and the brief agree.

`with_summary` adds it all to a fresh build (`lakebuild.build_lakes`); `refresh_summary` sets it again after
lakes-freeze or lakes-check have changed statuses in place, keeping the record of the previous build."""
import json
import math
from dataclasses import asdict
from pathlib import Path

from sartale.config import CHANGE_FACTOR
from sartale.inventory import InventoryEntry, load_inventory
from sartale.lakecheck import in_season
from sartale.lakestatus import ALERT, DECREASE, FREEZE_STATUS, NOT_MEASURABLE, WATCH, is_valid

APP_DATA = Path(__file__).resolve().parents[2] / "app" / "public" / "data"
FORMING_STATE = "lake_forming_check"  # lakebuild.FORMING_STATE (not imported: lakebuild imports this module)
# A forming site (a search circle) is not "no lake now": it falls through to the circle note.
NO_LAKE_STATES = ("no_lake",)
FROZEN_STATUSES = frozenset(FREEZE_STATUS.values())
MIN_OUTLINE_IN_WINDOW = 0.9  # an outline less inside the radar window than this gets no share

NOTE_NO_LAKE = "Not shown: there is no lake here now."
NOTE_FROZEN = "Not shown while the lake is frozen: the radar area is not an open-water measurement."
NOTE_NOT_MEASURABLE = "Not shown: the radar water did not pass the Sentinel-2 check."
NOTE_CIRCLE = "Not shown: this lake has no mapped outline, only a search circle."
NOTE_WINDOW = "Not shown: only {n}% of the lake outline is inside the radar window (at least 90% needed)."
NOTE_NO_EXTENT = "Not shown: no inventory outline or earlier-season radar reading for this lake."
NOTE_NO_READING = "Not shown: no valid open-water reading yet."

COUNT_KEYS = ("watched", "alert", "watch", "decrease", "forming", "needs_attention", "open_water", "frozen", "no_lake",
              "above_largest", "suparco_listed", "changed")


def _year(iso: str | None) -> int | None:
    try:
        return int(str(iso)[:4])
    except (TypeError, ValueError):
        return None


def largest_extent(entry: InventoryEntry | None, series: list[dict], built: str) -> dict | None:
    """The largest recorded extent of a lake, {"km2", "source", "year"}: the largest of its inventory outline areas
    and its valid radar readings not flagged frozen from the open-water season (config.OPEN_WATER_SEASON) of a year
    before the build's, so the current season never sets its own maximum. None with neither. An inventory outline
    wins a tie."""
    found = [{"km2": o.km2, "source": o.source, "year": o.year} for o in (entry.outlines if entry else ())]
    build_year = _year(built)
    for p in series or []:
        year = _year(p.get("date"))
        if (build_year is not None and year is not None and year < build_year and is_valid(p)
                and in_season(p["date"])):
            found.append({"km2": p["area_km2"], "source": f"NISAR radar, track {p['track']}, {p['date']}",
                          "year": year})
    if not found:
        return None
    best = found[0]
    for f in found[1:]:
        if f["km2"] > best["km2"]:
            best = f
    return best


def latest_reading(lake: dict) -> dict | None:
    """The latest valid open-water reading (`lakestatus.is_valid`: not excluded, observable, not flagged frozen) on
    the lake's status track, or None."""
    track = (lake.get("status") or {}).get("track")
    rows = [p for p in lake.get("series") or [] if p.get("track") == track and is_valid(p)] if track else []
    return max(rows, key=lambda p: p["date"]) if rows else None


def share_fields(lake: dict, extent: dict | None) -> dict:
    """{"share_of_largest", "above_largest", "share_note"}: the latest valid open-water reading on the status track
    over the largest recorded extent, whether it is above that extent by more than radar noise (at least
    1 + 2 x noise / extent; None while the noise is unknown and the share is 100% or more), and, when no share is
    shown, why (in the order of the NOTE_ sentences)."""
    st = lake.get("status") or {}
    cov = lake.get("coverage") or {}
    kind = cov.get("zone_kind") or ("circle" if lake.get("zone_radius_km") is not None else "outline")
    inside = cov.get("outline_in_window_share")
    note = None
    if lake.get("lake_state") in NO_LAKE_STATES:
        note = NOTE_NO_LAKE
    elif st.get("status") in FROZEN_STATUSES:
        note = NOTE_FROZEN
    elif st.get("status") == NOT_MEASURABLE:
        note = NOTE_NOT_MEASURABLE
    elif kind == "circle":
        note = NOTE_CIRCLE
    elif inside is not None and inside < MIN_OUTLINE_IN_WINDOW:
        note = NOTE_WINDOW.format(n=math.floor(inside * 100 + 1e-9))
    elif extent is None:
        note = NOTE_NO_EXTENT
    else:
        reading = latest_reading(lake)
        if reading is None:
            note = NOTE_NO_READING
    if note is not None:
        return {"share_of_largest": None, "above_largest": None, "share_note": note}
    share = reading["area_km2"] / extent["km2"]
    noise = st.get("noise_km2")
    if noise is None:
        above = None if share >= 1 else False
    else:
        above = share >= 1 + 2 * noise / extent["km2"]
    return {"share_of_largest": round(share, 4), "above_largest": above, "share_note": None}


def status_fields(lake: dict) -> dict:
    """The lake's status with `threshold_km2` (CHANGE_FACTOR x its noise), `latest_pass_id` (the `pass_id` of the
    status track's pass on the status's latest date) and `noise_floor_applied` (kept as `lakestatus.assess` set it;
    None when the status did not come from a compared pass)."""
    st = dict(lake.get("status") or {})
    noise = st.get("noise_km2")
    st["threshold_km2"] = None if noise is None else round(CHANGE_FACTOR * noise, 6)
    st.setdefault("noise_floor_applied", None)
    hit = next((p for p in lake.get("series") or []
                if p.get("track") == st.get("track") and p.get("date") == st.get("latest_date") and p.get("pass_id")),
               None) if st.get("track") and st.get("latest_date") else None
    st["latest_pass_id"] = hit["pass_id"] if hit else None
    return st


def _status(lake: dict) -> str | None:
    return (lake.get("status") or {}).get("status")


def headline_counts(lakes: list[dict]) -> dict:
    """The headline numbers of the overview (COUNT_KEYS), from the lakes as written."""
    c = dict.fromkeys(COUNT_KEYS, 0)
    c["watched"] = len(lakes)
    for lk in lakes:
        s, state = _status(lk), lk.get("lake_state")
        frozen = s in FROZEN_STATUSES
        c["alert"] += s == ALERT
        c["watch"] += s == WATCH
        c["decrease"] += s == DECREASE
        c["forming"] += state == FORMING_STATE
        c["needs_attention"] += s in (ALERT, WATCH, DECREASE) or state == FORMING_STATE
        c["frozen"] += frozen
        c["no_lake"] += state == "no_lake"
        c["open_water"] += state in ("lake", "unconfirmed") and not frozen
        c["above_largest"] += lk.get("above_largest") is True
        c["suparco_listed"] += lk.get("suparco") is not None
        c["changed"] += lk.get("previous_status") is not None and lk.get("previous_status") != s
    return {k: int(v) for k, v in c.items()}


def previous_build_of(previous: dict | None) -> dict | None:
    """What the overview keeps of the lakes.json a build replaces: when it was built, its counts (counted again when
    it carries none) and each lake's status."""
    if not isinstance(previous, dict) or not isinstance(previous.get("lakes"), list):
        return None
    counts = previous.get("counts")
    return {"built": previous.get("built"),
            "counts": counts if isinstance(counts, dict) else headline_counts(previous["lakes"]),
            "statuses": {lk["id"]: _status(lk) for lk in previous["lakes"] if isinstance(lk, dict) and "id" in lk}}


def mapped_count(path: Path) -> int | None:
    """The number of lakes in mapped_lakes.json, or None when the file is missing or not a list of lakes."""
    try:
        lakes = json.loads(Path(path).read_text(encoding="utf-8"))["lakes"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return len(lakes) if isinstance(lakes, list) else None


SUMMARY_KEYS = ("suparco", "suparco_candidates", "largest_extent", "share_of_largest", "above_largest", "share_note",
                "previous_status")


def _lake_summary(lk: dict, entry: InventoryEntry | None, built: str | None, statuses: dict | None) -> dict:
    # The summary keys always come last, so that setting them again (lakes-freeze moves `last_open` to the end) gives
    # the same file.
    out = {k: v for k, v in lk.items() if k not in SUMMARY_KEYS}
    out["status"] = status_fields(lk)
    out["suparco"] = asdict(entry.suparco) if entry and entry.suparco else None
    out["suparco_candidates"] = [asdict(c) for c in entry.suparco_candidates] if entry else []
    out["largest_extent"] = largest_extent(entry, out.get("series") or [], built)
    out.update(share_fields(out, out["largest_extent"]))
    out["previous_status"] = (statuses or {}).get(lk.get("id"))
    return out


def refresh_summary(doc: dict, inventory: dict[str, InventoryEntry] | None = None) -> dict:
    """`doc` with every lake's summary fields and the headline counts set again from what it holds now (after
    lakes-freeze or lakes-check changed statuses or frozen flags), `previous_status` from `doc["previous_build"]`,
    and `newest_pass` (the newest status date). `mapped_count` and `previous_build` are kept. `inventory`: by default
    the committed one (`inventory.load_inventory`)."""
    inventory = load_inventory() if inventory is None else inventory
    prev = doc.get("previous_build")
    statuses = prev.get("statuses") if isinstance(prev, dict) else None
    lakes = [_lake_summary(lk, inventory.get(lk.get("id")), doc.get("built"), statuses) for lk in doc.get("lakes", [])]
    dates = [d for lk in lakes for d in [(lk.get("status") or {}).get("latest_date")] if d]
    return {**doc, "lakes": lakes, "counts": headline_counts(lakes), "newest_pass": max(dates) if dates else None,
            "previous_build": prev if isinstance(prev, dict) else None, "mapped_count": doc.get("mapped_count")}


def with_summary(doc: dict, previous: dict | None, inventory: dict[str, InventoryEntry],
                 mapped_path: Path = APP_DATA / "mapped_lakes.json") -> dict:
    """A fresh build `doc` with the summary: per lake (`refresh_summary`) and at the top, `counts`, `newest_pass`,
    `previous_build` (from `previous`, the published lakes.json this build replaces; None on a first build) and
    `mapped_count` (from `mapped_path`)."""
    base = {**doc, "previous_build": previous_build_of(previous), "mapped_count": mapped_count(mapped_path)}
    return refresh_summary(base, inventory)
