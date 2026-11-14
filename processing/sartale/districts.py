"""The district and province a point lies in, from geoBoundaries (processing/inventory/districts.geojson).

The file holds the geoBoundaries PAK ADM2 districts around the study area, each with its province (`adm1`), and
Pakistan's outline (ADM0, from OpenStreetMap). The ADM2 edges are coarse (drawn from Wikipedia maps): some lakes on
the outer border, Karambar Lake on the Ghizer-Chitral divide for one, lie up to a few km outside every district
polygon. A point inside Pakistan's outline but outside every district takes the nearest district within SNAP_KM.
Pure Python, so the rebuild needs no GIS library."""
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Literal

DISTRICTS_GEOJSON = Path(__file__).resolve().parents[1] / "inventory" / "districts.geojson"
DISTRICT_SOURCE = ("geoBoundaries gbOpen PAK ADM2 and ADM1 (release 9469f09, built 12 Dec 2023, public domain), "
                   "simplified to 0.001°")
PROVINCES = ("GB", "KP")
OUTSIDE = "The point is outside Gilgit-Baltistan and Khyber Pakhtunkhwa."
SNAP_KM = 10.0
_KM_PER_DEG = 111.32


def _rings(geometry: dict) -> list[list[list[list[float]]]]:
    """A Polygon or MultiPolygon as a list of polygons, each a list of rings."""
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"]]
    if geometry["type"] == "MultiPolygon":
        return geometry["coordinates"]
    raise ValueError(f"districts: unexpected geometry {geometry['type']}")


def _in_ring(x: float, y: float, ring) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _contains(polygons, x: float, y: float) -> bool:
    return any(_in_ring(x, y, rings[0]) and not any(_in_ring(x, y, hole) for hole in rings[1:])
               for rings in polygons)


def _edge_km(polygons, lon: float, lat: float) -> float:
    """Distance in km from the point to the nearest polygon edge (local flat approximation)."""
    kx = _KM_PER_DEG * math.cos(math.radians(lat))
    best = math.inf
    for rings in polygons:
        for ring in rings:
            for (x1, y1), (x2, y2) in zip((p[:2] for p in ring), (p[:2] for p in ring[1:])):
                ax, ay = (x1 - lon) * kx, (y1 - lat) * _KM_PER_DEG
                bx, by = (x2 - lon) * kx, (y2 - lat) * _KM_PER_DEG
                dx, dy = bx - ax, by - ay
                t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / (dx * dx + dy * dy)))
                best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best


@lru_cache(maxsize=4)
def _load(path: str):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    districts, country = [], []
    for f in doc["features"]:
        props, polygons = f["properties"], _rings(f["geometry"])
        if props.get("level") == "ADM0":
            country.extend(polygons)
        else:
            districts.append((props["name"], props["adm1"], polygons))
    if not districts or not country:
        raise ValueError(f"{path} must hold ADM2 districts and the ADM0 outline")
    return districts, country


def locate(lon: float, lat: float, path: Path = DISTRICTS_GEOJSON) -> tuple[str, str, float]:
    """(district, province code, km outside the district polygon: 0 when inside). Raises ValueError with OUTSIDE
    when the point is not in a Gilgit-Baltistan or Khyber Pakhtunkhwa district."""
    districts, country = _load(str(path))
    for name, adm1, polygons in districts:
        if _contains(polygons, lon, lat):
            if adm1 not in PROVINCES:
                raise ValueError(OUTSIDE)
            return name, adm1, 0.0
    if not _contains(country, lon, lat):
        raise ValueError(OUTSIDE)
    km, name, adm1 = min((_edge_km(polygons, lon, lat), name, adm1) for name, adm1, polygons in districts)
    if km > SNAP_KM or adm1 not in PROVINCES:
        raise ValueError(OUTSIDE)
    return name, adm1, km


def district_of(lon: float, lat: float) -> tuple[str, Literal["GB", "KP"]]:
    """The district and province ("GB" or "KP") of a point; ValueError outside Gilgit-Baltistan and KP."""
    name, adm1, _ = locate(lon, lat)
    return name, adm1
