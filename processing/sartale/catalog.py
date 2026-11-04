"""NISAR GCOV granule names and the CMR collection Lake Watch searches."""
from dataclasses import dataclass
from datetime import datetime, timezone

CMR_URL = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"
SHORT_NAME = "NISAR_L2_GCOV_PROVISIONAL_V1"
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
