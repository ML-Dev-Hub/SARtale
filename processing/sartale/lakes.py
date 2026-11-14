"""The glacial-lake register: where each lake is, where that came from, and its search box."""
import json
import math
from dataclasses import dataclass
from datetime import date as Date
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
class FormingSeason:
    """A stretch of the year (`start` to `end`, both "MM-DD", inclusive; it may wrap the year end) in which a no-lake
    site's forming check uses its own water share, or none (`share` None: not assessed, so the season's scenes never
    move the state). Needs a `source` that shows why."""
    start: str
    end: str
    share: float | None
    source: str


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
    # For a "no_lake" site: seasons with their own forming share (or none), and an outline (a GeoJSON file under
    # processing/outlines/) of water that is always there (a river) and is left out of the zone. Each needs a source.
    forming_seasons: tuple[FormingSeason, ...] = ()
    forming_exclude: str | None = None
    forming_exclude_source: str | None = None
    limits: tuple[str, ...] = ()  # the site's own sourced limits, shown with the lake (e.g. a past partial drainage)
    # Height of the lake surface in metres, measured once (lakes-elevation); the freeze check moves the air temperature
    # to it. Needs a source.
    elevation_m: float | None = None
    elevation_source: str | None = None


def _season_days(start: str, end: str) -> set[int]:
    """The days of the year (numbered in a leap year) from MM-DD `start` to `end`, wrapping the year end."""
    a = Date.fromisoformat(f"2000-{start}").timetuple().tm_yday
    b = Date.fromisoformat(f"2000-{end}").timetuple().tm_yday
    return set(range(a, b + 1)) if a <= b else set(range(a, 367)) | set(range(1, b + 1))


def _forming_seasons(lake_id, rows, state: str) -> tuple[FormingSeason, ...]:
    if rows is None:
        return ()
    bad = f"Lake {lake_id}: forming_seasons"
    if not isinstance(rows, list):
        raise ValueError(f"{bad} must be a list")
    if rows and state != "no_lake":
        raise ValueError(f"{bad} apply only to a no_lake site")
    seasons, taken = [], set()
    for r in rows:
        if not isinstance(r, dict):
            raise ValueError(f"{bad} entries must be objects")
        start, end, share = r.get("start"), r.get("end"), r.get("share")
        try:
            if not (isinstance(start, str) and isinstance(end, str) and len(start) == 5 and len(end) == 5):
                raise ValueError
            days = _season_days(start, end)
        except ValueError:
            raise ValueError(f"{bad}: start and end must be MM-DD dates, got {start!r} and {end!r}") from None
        if share is not None and (isinstance(share, bool) or not isinstance(share, (int, float)) or not 0 < share < 1):
            raise ValueError(f"{bad}: share must be null or a number between 0 and 1, got {share!r}")
        if not str(r.get("source") or "").strip():
            raise ValueError(f"{bad}: every season needs a source")
        if days & taken:
            raise ValueError(f"{bad} must not overlap ({start} to {end})")
        taken |= days
        seasons.append(FormingSeason(start, end, None if share is None else float(share), r["source"]))
    return tuple(seasons)


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
        seasons = _forming_seasons(lake_id, row.get("forming_seasons"), state)
        exclude = row.get("forming_exclude")
        if exclude is not None and not str(row.get("forming_exclude_source") or "").strip():
            raise ValueError(f"Lake {lake_id}: forming_exclude needs a forming_exclude_source")
        limits = row.get("limits", [])
        if not isinstance(limits, list) or not all(isinstance(t, str) and t.strip() for t in limits):
            raise ValueError(f"Lake {lake_id}: limits must be a list of non-empty strings")
        elev = row.get("elevation_m")
        if elev is not None:
            if isinstance(elev, bool) or not isinstance(elev, (int, float)) or not -500 < elev < 9000:
                raise ValueError(f"Lake {lake_id}: elevation_m must be a height in metres, got {elev!r}")
            if not str(row.get("elevation_source") or "").strip():
                raise ValueError(f"Lake {lake_id}: elevation_m needs an elevation_source")
        seen.add(lake_id)
        lakes.append(Lake(
            id=lake_id, name=row["name"], lon=float(row["lon"]), lat=float(row["lat"]),
            coord_source=row["coord_source"], outline=row.get("outline"), role=row["role"],
            downstream=row.get("downstream"), downstream_source=row.get("downstream_source"),
            zone_radius_km=float(radius), lake_state=state, lake_state_source=row.get("lake_state_source"),
            forming_share=None if forming is None else float(forming),
            forming_share_source=row.get("forming_share_source"), forming_seasons=seasons,
            forming_exclude=exclude, forming_exclude_source=row.get("forming_exclude_source"), limits=tuple(limits),
            elevation_m=None if elev is None else float(elev), elevation_source=row.get("elevation_source"),
        ))
    return lakes


def lake_bbox(lake: Lake, half_km: float = 3.0) -> tuple[float, float, float, float]:
    """(lon_min, lat_min, lon_max, lat_max) of a square `half_km` each side of the lake point."""
    dlat = half_km / KM_PER_DEG_LAT
    dlon = half_km / (KM_PER_DEG_LAT * math.cos(math.radians(lake.lat)))
    return (lake.lon - dlon, lake.lat - dlat, lake.lon + dlon, lake.lat + dlat)
