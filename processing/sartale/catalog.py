"""CMR search and stack selection for NISAR GCOV granules."""
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from sartale.config import BBOX, CRID, GAP_END, GAP_START, SOURCE

CMR_URL = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"
SHORT_NAME = "NISAR_L2_GCOV_PROVISIONAL_V1"
PAGE_SIZE = 200
_TIME = "%Y%m%dT%H%M%S"


@dataclass(frozen=True)
class Granule:
    cycle: int
    track: int
    direction: str
    frame: int
    mode: str
    pole: str
    source: str
    start: datetime
    crid: str
    accuracy: str
    coverage: str
    name: str
    size: int | None = None  # bytes of the .h5, from CMR (None when CMR gave none)
    md5: str | None = None  # MD5 of the .h5, from CMR


def parse_granule(name: str) -> Granule:
    """Parse NISAR_L2_PT_GCOV_CYL_REL_P_FRM_MODE_POLE_S_Start_End_CRID_A_C_LOC_CTR."""
    stem = name.rsplit(".", 1)[0] if name.endswith((".h5", ".xml")) else name
    p = stem.split("_")
    if len(p) != 18 or p[3] != "GCOV":
        raise ValueError(f"Not a NISAR GCOV granule name: {name}")
    return Granule(
        cycle=int(p[4]), track=int(p[5]), direction=p[6], frame=int(p[7]),
        mode=p[8], pole=p[9], source=p[10],
        start=datetime.strptime(p[11], _TIME).replace(tzinfo=timezone.utc),
        crid=p[13], accuracy=p[14], coverage=p[15], name=stem,
    )


def _file_info(umm: dict, name: str) -> tuple[int | None, str | None]:
    """(size in bytes, MD5) of `<name>.h5` from DataGranule.ArchiveAndDistributionInformation, or (None, None)."""
    infos = (umm.get("DataGranule") or {}).get("ArchiveAndDistributionInformation") or []
    for info in infos:
        if info.get("Name") != f"{name}.h5":
            continue
        size = info.get("SizeInBytes")
        checksum = info.get("Checksum") or {}
        md5 = checksum.get("Value") if str(checksum.get("Algorithm", "MD5")).upper() == "MD5" else None
        return (int(size) if size is not None else None), md5
    return None, None


def search_cmr() -> list[Granule]:
    """Search CMR for GCOV granules over the study bbox, paging as needed. Each granule appears once."""
    granules, seen, page = [], set(), 1
    while True:
        query = urllib.parse.urlencode({
            "short_name": SHORT_NAME,
            "bounding_box": ",".join(str(v) for v in BBOX),
            "page_size": PAGE_SIZE,
            "page_num": page,
        })
        with urllib.request.urlopen(f"{CMR_URL}?{query}", timeout=60) as r:
            items = json.load(r).get("items", [])
        for item in items:
            try:
                g = parse_granule(item["umm"]["GranuleUR"])
            except ValueError:
                continue
            if g.name in seen:
                continue
            seen.add(g.name)
            size, md5 = _file_info(item["umm"], g.name)
            granules.append(replace(g, size=size, md5=md5))
        if len(items) < PAGE_SIZE:
            return granules
        page += 1


def _utc(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def select_stack(granules: list[Granule], stack_id: str, mode: str, pole: str) -> list[Granule]:
    """The full-frame granules of one stack, all with config.CRID, one per name, oldest first.

    Granules of the stack with another CRID are left out and listed on stdout, so a repeat search that
    finds a newer processing version does not block the pipeline. Raises only if nothing remains.
    """
    track, direction, frame = stack_id.split("_")
    gap_start, gap_end = _utc(GAP_START), _utc(GAP_END)
    unique = {g.name: g for g in granules}.values()
    in_stack = [
        g for g in unique
        if (g.track, g.direction, g.frame) == (int(track), direction, int(frame))
        and g.mode == mode and g.pole == pole and g.source == SOURCE
        and g.coverage == "F"
        and not gap_start <= g.start <= gap_end
    ]
    out = [g for g in in_stack if g.crid == CRID]
    other = sorted((g for g in in_stack if g.crid != CRID), key=lambda g: g.start)
    if other:
        print(f"Excluded {len(other)} granule(s) of stack {stack_id} whose CRID is not {CRID}:")
        for g in other:
            print(f"  {g.start.date()} {g.crid} {g.name}")
    if not out:
        found = ", ".join(sorted({g.crid for g in in_stack})) or "none"
        raise ValueError(f"No granule of stack {stack_id} with CRID {CRID} (CRIDs found: {found})")
    return sorted(out, key=lambda g: g.start)


def utc_date(entry: dict) -> str:
    """UTC calendar date (YYYY-MM-DD) of a search-manifest granule entry."""
    return datetime.fromisoformat(entry["start"]).astimezone(timezone.utc).date().isoformat()


def granule_for_date(granules: list[dict], date: str) -> dict:
    """The one search-manifest entry that starts on `date` (UTC). Raises ValueError for none or several."""
    matches = [g for g in granules if utc_date(g) == date]
    if not matches:
        raise ValueError(f"Date {date} is not in the search manifest")
    if len(matches) > 1:
        raise ValueError(f"Date {date} matches {len(matches)} granules in the search manifest")
    return matches[0]


def write_manifest(granules: list[Granule], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "searched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "granules": [
            {"name": g.name, "start": g.start.isoformat(), "crid": g.crid,
             "accuracy": g.accuracy, "coverage": g.coverage, "cycle": g.cycle,
             "size": g.size, "md5": g.md5}
            for g in granules
        ],
    }
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
