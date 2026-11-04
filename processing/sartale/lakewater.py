"""Screen bad passes and find lake water with the two-view rule.

Per-pass water (ruling R2) is: dark in this pass, inside the lake zone, not shadow-prone, valid.
Shadow-prone pixels come from each track's season-median image: dark in one viewing direction
but not in the opposite one (radar shadow, not water).
"""
import numpy as np
from pyproj import Transformer
from rasterio.features import geometry_mask
from rasterio.transform import Affine
from scipy.ndimage import distance_transform_edt, uniform_filter

from sartale.config import (
    BRIGHT_PASS_DB,
    DROP_DB,
    OUTLIER_HV_FLOOR_DB,
    OUTLIER_MIN_PASSES,
    OUTLIER_SHARE_FLOOR,
    OUTLIER_Z,
    SPECKLE_BOX,
)
from sartale.lakes import Lake

OUTLINE_BUFFER_M = 200.0


def despeckle(power: np.ndarray, box: int = SPECKLE_BOX) -> np.ndarray:
    """NaN-aware boxcar mean of linear power: mean of the finite neighbours in a box x box window.

    The output is NaN where fewer than half of the box is finite.
    """
    p = np.asarray(power, dtype=np.float64)
    finite = np.isfinite(p)
    total = uniform_filter(np.where(finite, p, 0.0), size=box, mode="reflect")
    share = uniform_filter(finite.astype(np.float64), size=box, mode="reflect")
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = total / share
    return np.where(share >= 0.5 - 1e-9, mean, np.nan)


def screen_passes(hh_db_by_pass: dict[str, np.ndarray]) -> dict[str, str]:
    """For one track: exclude passes whose window-median HH is far from the track median.

    Returns excluded pass id -> reason. A badly calibrated pass (e.g. +25 dB) is never read as change.
    """
    medians = {k: float(np.nanmedian(v)) for k, v in hh_db_by_pass.items()}
    finite = [m for m in medians.values() if np.isfinite(m)]
    if not finite:
        return {}
    track_median = float(np.median(finite))
    excluded = {}
    for k, m in medians.items():
        if not np.isfinite(m):
            excluded[k] = "window has no valid HH pixels"
        elif abs(m - track_median) > BRIGHT_PASS_DB:
            excluded[k] = f"window median HH {abs(m - track_median):.1f} dB from the track median"
    return excluded


def robust_z(values: dict[str, float], floor: float) -> dict[str, float]:
    """(value - median) / max(1.4826 * MAD, floor) for each key. `floor` keeps a near-constant track
    from turning tiny differences into huge z-scores."""
    if not values:
        return {}
    v = np.array(list(values.values()), float)
    med = float(np.median(v))
    scale = max(1.4826 * float(np.median(np.abs(v - med))), floor)
    return {k: (x - med) / scale for k, x in values.items()}


def screen_outliers(dark_share: dict[str, float], hv_median_db: dict[str, float],
                    z_max: float = OUTLIER_Z, share_floor: float = OUTLIER_SHARE_FLOOR,
                    hv_floor_db: float = OUTLIER_HV_FLOOR_DB,
                    min_passes: int = OUTLIER_MIN_PASSES) -> dict[str, str]:
    """For one track: exclude passes whose window dark-pixel share or window-median HV is a robust
    outlier (|z| > z_max) among that track's passes. Returns excluded pass id -> reason.

    Catches passes that are not uniformly too bright but read far more (or less) of the window as dark,
    which would otherwise show up as a jump in lake area. Tracks with fewer than `min_passes` passes
    are not screened (the median and MAD are not meaningful).
    """
    keys = [k for k in dark_share if np.isfinite(dark_share[k]) and np.isfinite(hv_median_db.get(k, np.nan))]
    if len(keys) < min_passes:
        return {}
    zs = robust_z({k: dark_share[k] for k in keys}, share_floor)
    zh = robust_z({k: hv_median_db[k] for k in keys}, hv_floor_db)
    excluded = {}
    for k in keys:
        if abs(zs[k]) > z_max:
            excluded[k] = (f"window dark share {dark_share[k]:.1%} is an outlier on its track "
                           f"(robust z {zs[k]:+.1f}, limit {z_max})")
        elif abs(zh[k]) > z_max:
            excluded[k] = (f"window median HV {hv_median_db[k]:.1f} dB is an outlier on its track "
                           f"(robust z {zh[k]:+.1f}, limit {z_max})")
    return excluded


def window_stats(hh_db: np.ndarray, hv_db: np.ndarray) -> tuple[float, float]:
    """(dark-pixel share of the valid window pixels, window-median HV dB) of one despeckled pass."""
    dark, valid = dark_mask(hh_db, hv_db)
    n = int(valid.sum())
    if not n:
        return float("nan"), float("nan")
    return float(dark.sum() / n), float(np.nanmedian(np.where(valid, hv_db, np.nan)))


def dark_mask(hh_db: np.ndarray, hv_db: np.ndarray, drop_db: float = DROP_DB) -> tuple[np.ndarray, np.ndarray]:
    """Dark = HH and HV both at least `drop_db` below their window medians. Returns (dark, valid).

    NaN pixels are valid=False and dark=False.
    """
    valid = np.isfinite(hh_db) & np.isfinite(hv_db)
    if not valid.any():
        return np.zeros(hh_db.shape, bool), valid
    hh_med = np.nanmedian(np.where(valid, hh_db, np.nan))
    hv_med = np.nanmedian(np.where(valid, hv_db, np.nan))
    with np.errstate(invalid="ignore"):
        dark = valid & (hh_db <= hh_med - drop_db) & (hv_db <= hv_med - drop_db)
    return dark, valid


def shadow_prone(median_dark_by_track: dict[str, np.ndarray], directions: dict[str, str]) -> np.ndarray | None:
    """Pixels dark in some view's median but not dark in any view of the opposite direction.

    Returns None when only one viewing direction exists (the lake is "single viewing direction").
    """
    by_dir: dict[str, np.ndarray] = {}
    for track, dark in median_dark_by_track.items():
        d = directions[track]
        by_dir[d] = by_dir[d] | dark if d in by_dir else dark.copy()
    if len(by_dir) < 2:
        return None
    asc, desc = by_dir["A"], by_dir["D"]
    return (asc & ~desc) | (desc & ~asc)


def _ring(outline_polygon) -> list:
    if isinstance(outline_polygon, dict):  # GeoJSON Polygon
        return outline_polygon["coordinates"][0]
    return list(outline_polygon)


def lake_zone(shape, x, y, epsg, lake: Lake, outline_polygon=None, half_km: float = 1.0) -> np.ndarray:
    """Boolean mask of the lake zone on the window grid.

    With `outline_polygon`: the outline rasterised and buffered by 200 m. It is either a list of
    (lon, lat) WGS84 vertices (exterior ring) or a GeoJSON Polygon dict {"type": "Polygon",
    "coordinates": [[[lon, lat], ...]]}. Without it: a circle of radius `half_km` around the
    lake's point (water area "in the search window").
    `x`, `y` are the window's UTM coordinate vectors (metres, pixel centres) in `epsg`.
    """
    x, y = np.asarray(x, float), np.asarray(y, float)
    dx = float(x[1] - x[0]) if len(x) > 1 else 1.0
    dy = float(y[1] - y[0]) if len(y) > 1 else -1.0
    to_utm = Transformer.from_crs(4326, epsg, always_xy=True)
    if outline_polygon is None:
        cx, cy = to_utm.transform(lake.lon, lake.lat)
        xx, yy = np.meshgrid(x, y)
        return ((xx - cx) ** 2 + (yy - cy) ** 2) <= (half_km * 1000.0) ** 2
    ring = [to_utm.transform(lon, lat) for lon, lat in _ring(outline_polygon)]
    transform = Affine(dx, 0, x[0] - dx / 2, 0, dy, y[0] - dy / 2)
    poly = {"type": "Polygon", "coordinates": [ring]}
    inside = geometry_mask([poly], out_shape=tuple(shape), transform=transform, invert=True)
    dist = distance_transform_edt(~inside, sampling=(abs(dy), abs(dx)))
    return dist <= OUTLINE_BUFFER_M


def outline_window_share(x, y, epsg, outline_polygon) -> float:
    """Share of the outline's area (without the buffer) that lies on the window grid, 0 to 1."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    dx, dy = float(x[1] - x[0]), float(y[1] - y[0])
    to_utm = Transformer.from_crs(4326, epsg, always_xy=True)
    ring = [to_utm.transform(lon, lat) for lon, lat in _ring(outline_polygon)]
    xs, ys = np.array([p[0] for p in ring]), np.array([p[1] for p in ring])
    area = 0.5 * abs(float(np.dot(xs, np.roll(ys, 1)) - np.dot(ys, np.roll(xs, 1))))  # shoelace, m²
    if area == 0:
        return 0.0
    transform = Affine(dx, 0, x[0] - dx / 2, 0, dy, y[0] - dy / 2)
    inside = geometry_mask([{"type": "Polygon", "coordinates": [ring]}], out_shape=(len(y), len(x)),
                           transform=transform, invert=True)
    return min(1.0, float(inside.sum()) * abs(dx * dy) / area)


def pass_water(hh_db: np.ndarray, hv_db: np.ndarray, zone: np.ndarray, shadow: np.ndarray | None,
               pixel_m: float) -> dict:
    """Water in one pass: dark, inside the zone, not shadow-prone, valid.

    Returns area_km2; observable_share (valid, non-shadow share of the zone pixels, 0.0 for an
    empty zone); valid (count of observable zone pixels).
    """
    dark, valid = dark_mask(hh_db, hv_db)
    not_shadow = np.ones(zone.shape, bool) if shadow is None else ~shadow
    observable = zone & valid & not_shadow
    n_zone = int(zone.sum())
    return {
        "area_km2": float((dark & observable).sum() * pixel_m ** 2 / 1e6),
        "observable_share": float(observable.sum() / n_zone) if n_zone else 0.0,
        "valid": int(observable.sum()),
    }
