"""CMR search and track selection for NISAR GCOV passes over each lake."""
from dataclasses import dataclass
from typing import Literal

import requests

from sartale.catalog import CMR_URL, SHORT_NAME, parse_granule
from sartale.lakes import Lake

PAGE_SIZE = 2000
MODE = "4005"
CALIBRATED_FROM = "2026-06-17"  # earlier passes are not calibrated
MIN_LOOKS = 3  # same-track passes needed for a trend


@dataclass(frozen=True)
class Pass:
    granule: str
    url: str
    date: str  # YYYY-MM-DD, UTC
    start: str  # ISO
    track: str
    direction: Literal["A", "D"]
    frame: str
    mode: str
    crid: str

    @property
    def key(self) -> str:
        return f"{self.track}{self.direction}"


def pass_from_umm(item: dict) -> Pass | None:
    """One CMR umm_json item as a Pass. None when it has no .h5 URL or is not a GCOV granule name."""
    umm = item["umm"]
    url = next((u["URL"] for u in umm.get("RelatedUrls", []) if u.get("URL", "").endswith(".h5")), None)
    if url is None:
        return None
    try:
        g = parse_granule(umm["GranuleUR"])
    except ValueError:
        return None
    return Pass(
        granule=g.name, url=url, date=g.start.date().isoformat(), start=g.start.isoformat(),
        track=f"{g.track:03d}", direction=g.direction, frame=f"{g.frame:03d}", mode=g.mode, crid=g.crid,
    )


def search_lake_passes(lake: Lake, session=None) -> list[Pass]:
    """Every GCOV pass whose footprint contains the lake point, oldest first, each granule once."""
    http = session or requests
    passes, seen, page = [], set(), 1
    while True:
        r = http.get(CMR_URL, params={
            "short_name": SHORT_NAME, "point": f"{lake.lon},{lake.lat}",
            "page_size": PAGE_SIZE, "page_num": page,
        }, timeout=60)
        r.raise_for_status()
        items = r.json().get("items", [])
        for item in items:
            p = pass_from_umm(item)
            if p and p.granule not in seen:
                seen.add(p.granule)
                passes.append(p)
        if len(items) < PAGE_SIZE:
            return sorted(passes, key=lambda p: p.start)
        page += 1


def select_lake_passes(passes: list[Pass]) -> dict[str, list[Pass]]:
    """Calibrated mode-4005 passes grouped by track key, oldest first. Raises if one track mixes CRIDs."""
    by_key: dict[str, list[Pass]] = {}
    for p in sorted(passes, key=lambda p: p.start):
        if p.mode == MODE and p.date >= CALIBRATED_FROM:
            by_key.setdefault(p.key, []).append(p)
    for key, group in by_key.items():
        crids = sorted({p.crid for p in group})
        if len(crids) > 1:
            raise ValueError(f"Track {key} mixes CRIDs {', '.join(crids)}")
    return by_key


def coverage_report(lakes: list[Lake], passes: dict[str, dict[str, list[Pass]]]) -> list[dict]:
    """Per lake: looks per track, and whether any one track has enough for a trend."""
    rows = []
    for lake in lakes:
        tracks = {k: len(v) for k, v in passes.get(lake.id, {}).items()}
        rows.append({
            "id": lake.id, "role": lake.role, "tracks": tracks,
            "enough_looks": any(n >= MIN_LOOKS for n in tracks.values()),
        })
    return rows
