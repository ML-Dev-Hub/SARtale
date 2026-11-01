"""CMR search and stack selection for NISAR GCOV granules."""
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sartale.config import BBOX, GAP_END, GAP_START

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


def search_cmr() -> list[Granule]:
    """Search CMR for GCOV granules over the study bbox, paging as needed."""
    granules, page = [], 1
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
                granules.append(parse_granule(item["umm"]["GranuleUR"]))
            except ValueError:
                continue
        if len(items) < PAGE_SIZE:
            return granules
        page += 1


def _utc(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def select_stack(granules: list[Granule], stack_id: str, mode: str, pole: str) -> list[Granule]:
    track, direction, frame = stack_id.split("_")
    gap_start, gap_end = _utc(GAP_START), _utc(GAP_END)
    out = [
        g for g in granules
        if (g.track, g.direction, g.frame) == (int(track), direction, int(frame))
        and g.mode == mode and g.pole == pole and g.coverage == "F"
        and not gap_start <= g.start <= gap_end
    ]
    crids = sorted({g.crid for g in out})
    if len(crids) > 1:
        raise ValueError(f"Mixed CRID in stack {stack_id}: {', '.join(crids)}")
    return sorted(out, key=lambda g: g.start)


def write_manifest(granules: list[Granule], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "searched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "granules": [
            {"name": g.name, "start": g.start.isoformat(), "crid": g.crid,
             "accuracy": g.accuracy, "coverage": g.coverage, "cycle": g.cycle}
            for g in granules
        ],
    }
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
