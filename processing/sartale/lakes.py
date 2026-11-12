"""The glacial-lake register: where each lake is, where that came from, and its search box."""
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ROLES = ("watch", "control", "story")
KM_PER_DEG_LAT = 111.32
# What recent imagery shows at the site. "lake": a lake is there. "unconfirmed": the dark radar area may not be a
# lake; the status is still computed and the site carries a limit. "no_lake": there is no lake now (an ice-dammed
# lake's empty basin, say); the site is kept to watch for a lake forming, with no growing/shrinking verdict.
LAKE_STATES = ("lake", "unconfirmed", "no_lake")
DEFAULT_ZONE_KM = 1.0  # radius of the circle zone when a lake has no outline
MAX_ZONE_KM = 2.5  # the cached window is 6 km across, so a circle must stay inside it


@dataclass(frozen=True)
class Lake:
    id: str
    name: str
    lon: float
    lat: float
    coord_source: str
    outline: str | None  # path or URL of a published polygon
    role: Literal["watch", "control", "story"]
    downstream: str | None
    downstream_source: str | None
    zone_radius_km: float = DEFAULT_ZONE_KM  # circle zone radius when there is no outline
    lake_state: Literal["lake", "unconfirmed", "no_lake"] = "lake"
    lake_state_source: str | None = None  # what shows the state and when; required unless lake_state is "lake"
    # For a "no_lake" site: water share of the zone above which the Sentinel-2 absence check says a lake may be
    # forming (default config.FORMING_WATER_SHARE); set where the empty zone holds other water. Needs a source.
    forming_share: float | None = None
    forming_share_source: str | None = None
    limits: tuple[str, ...] = ()  # the site's own sourced limits, shown with the lake (e.g. a past partial drainage)


def load_lakes(path: Path) -> list[Lake]:
    """Read the register. Every lake needs a coordinate source and a known role; ids are unique."""
    lakes, seen = [], set()
    for row in json.loads(Path(path).read_text(encoding="utf-8")):
        lake_id = row.get("id")
        if not str(row.get("coord_source") or "").strip():
            raise ValueError(f"Lake {lake_id}: coord_source is required")
        if row.get("role") not in ROLES:
            raise ValueError(f"Lake {lake_id}: role must be one of {ROLES}, got {row.get('role')!r}")
        if lake_id in seen:
            raise ValueError(f"Duplicate lake id {lake_id}")
        if row.get("downstream") and not row.get("downstream_source"):
            raise ValueError(f"Lake {lake_id}: downstream needs a downstream_source")
        radius = row.get("zone_radius_km", DEFAULT_ZONE_KM)
        if isinstance(radius, bool) or not isinstance(radius, (int, float)) or not 0 < radius <= MAX_ZONE_KM:
            raise ValueError(f"Lake {lake_id}: zone_radius_km must be a number above 0 and at most {MAX_ZONE_KM}, "
                             f"got {radius!r}")
        state = row.get("lake_state", "lake")
        if state not in LAKE_STATES:
            raise ValueError(f"Lake {lake_id}: lake_state must be one of {LAKE_STATES}, got {state!r}")
        if state != "lake" and not str(row.get("lake_state_source") or "").strip():
            raise ValueError(f"Lake {lake_id}: lake_state {state!r} needs a lake_state_source")
        forming = row.get("forming_share")
        if forming is not None:
            if isinstance(forming, bool) or not isinstance(forming, (int, float)) or not 0 < forming < 1:
                raise ValueError(f"Lake {lake_id}: forming_share must be a number between 0 and 1, got {forming!r}")
            if state != "no_lake":
                raise ValueError(f"Lake {lake_id}: forming_share applies only to a no_lake site")
            if not str(row.get("forming_share_source") or "").strip():
                raise ValueError(f"Lake {lake_id}: forming_share needs a forming_share_source")
        limits = row.get("limits", [])
        if not isinstance(limits, list) or not all(isinstance(t, str) and t.strip() for t in limits):
            raise ValueError(f"Lake {lake_id}: limits must be a list of non-empty strings")
        seen.add(lake_id)
        lakes.append(Lake(
            id=lake_id, name=row["name"], lon=float(row["lon"]), lat=float(row["lat"]),
            coord_source=row["coord_source"], outline=row.get("outline"), role=row["role"],
            downstream=row.get("downstream"), downstream_source=row.get("downstream_source"),
            zone_radius_km=float(radius), lake_state=state, lake_state_source=row.get("lake_state_source"),
            forming_share=None if forming is None else float(forming),
            forming_share_source=row.get("forming_share_source"), limits=tuple(limits),
        ))
    return lakes


def lake_bbox(lake: Lake, half_km: float = 3.0) -> tuple[float, float, float, float]:
    """(lon_min, lat_min, lon_max, lat_max) of a square `half_km` each side of the lake point."""
    dlat = half_km / KM_PER_DEG_LAT
    dlon = half_km / (KM_PER_DEG_LAT * math.cos(math.radians(lake.lat)))
    return (lake.lon - dlon, lake.lat - dlat, lake.lon + dlon, lake.lat + dlat)
