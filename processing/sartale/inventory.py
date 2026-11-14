"""What the open lake inventories say about each watched lake: its outline areas and its SUPARCO list match.

Read from processing/inventory/watched_inventory.json, which processing/inventory/make_tables.py writes from the
11 Nov 2026 inventory investigation (HKH-PK-2020, Hi-MAG, OpenStreetMap; SUPARCO's GLOF posts). SUPARCO publishes
no coordinates for its list of potentially dangerous glacial lakes, so every SUPARCO ID here is SARtale's
reconstruction from SUPARCO's status map and area table, never a SUPARCO-supplied location. Only one "probable"
(or, once SUPARCO shares its table, "official") ID becomes a lake's `suparco`; a "possible" match, or a map dot
whose label could be several IDs, stays in `suparco_candidates`."""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

INVENTORY_JSON = Path(__file__).resolve().parents[1] / "inventory" / "watched_inventory.json"
MATCHES = ("probable", "possible", "official")
LICENCES = ("CC BY 4.0", "ODbL 1.0")


@dataclass(frozen=True)
class InventoryOutline:
    source: str  # e.g. "HKH-PK-2020 (PlanetScope outline, Sep 2020)"
    year: int | None  # the year the outline shows; None when undated (OpenStreetMap)
    km2: float
    licence: str


@dataclass(frozen=True)
class SuparcoMatch:
    id: int
    match: Literal["probable", "possible", "official"]
    source: str  # how the match was made


@dataclass(frozen=True)
class InventoryEntry:
    lake_id: str
    outlines: tuple[InventoryOutline, ...]
    suparco: SuparcoMatch | None
    suparco_candidates: tuple[SuparcoMatch, ...]


def _match(lake_id: str, row) -> SuparcoMatch:
    bad = f"Inventory {lake_id}: SUPARCO match"
    if not isinstance(row, dict):
        raise ValueError(f"{bad} must be an object")
    sid, match, source = row.get("id"), row.get("match"), row.get("source")
    if isinstance(sid, bool) or not isinstance(sid, int) or sid < 1:
        raise ValueError(f"{bad}: id must be a positive integer, got {sid!r}")
    if match not in MATCHES:
        raise ValueError(f"{bad}: match must be one of {MATCHES}, got {match!r}")
    if not isinstance(source, str) or not source.strip():
        raise ValueError(f"{bad} {sid} needs a source")
    return SuparcoMatch(sid, match, source)


def _outline(lake_id: str, row) -> InventoryOutline:
    bad = f"Inventory {lake_id}: outline"
    if not isinstance(row, dict) or not str(row.get("source") or "").strip():
        raise ValueError(f"{bad} needs a source")
    km2, year = row.get("km2"), row.get("year")
    if isinstance(km2, bool) or not isinstance(km2, (int, float)) or not km2 > 0:
        raise ValueError(f"{bad}: km2 must be a positive number, got {km2!r}")
    if year is not None and (isinstance(year, bool) or not isinstance(year, int)):
        raise ValueError(f"{bad}: year must be an integer or null, got {year!r}")
    if row.get("licence") not in LICENCES:
        raise ValueError(f"{bad}: licence must be one of {LICENCES}, got {row.get('licence')!r}")
    return InventoryOutline(row["source"], year, float(km2), row["licence"])


def load_inventory(path: Path = INVENTORY_JSON) -> dict[str, InventoryEntry]:
    """The inventory entry of each watched lake that has one, by lake id."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {}
    for lake_id, row in doc["lakes"].items():
        suparco = None if row.get("suparco") is None else _match(lake_id, row["suparco"])
        if suparco is not None and suparco.match not in ("probable", "official"):
            raise ValueError(f"Inventory {lake_id}: only a probable or official match can be the lake's SUPARCO ID; "
                             f"{suparco.match} matches go in suparco_candidates")
        out[lake_id] = InventoryEntry(
            lake_id=lake_id,
            outlines=tuple(_outline(lake_id, o) for o in row.get("outlines") or []),
            suparco=suparco,
            suparco_candidates=tuple(_match(lake_id, c) for c in row.get("suparco_candidates") or []))
    return out
