"""Screen bad passes and find lake water (method D17).

Per-pass water is: valid, inside the lake zone, and HH (Lee-filtered, 7x7, on linear power) at least DROP_DB below the
window-median HH. The window median leaves out terrain in radar layover or shadow (sartale.demmask); inside the zone
nothing is masked. HV is not used for water. The pass screens keep the 3x3 boxcar and the HH-and-HV dark share.

`shadow_prone` (the two-view rule) no longer removes water; the freeze check's summer core still leaves those pixels
out, as it did when its break-up numbers were set (sartale.freeze).
"""
import warnings

import numpy as np
from pyproj import Transformer
from rasterio.features import geometry_mask
from rasterio.transform import Affine
from scipy.ndimage import distance_transform_edt, uniform_filter

from sartale.config import (
    BRIGHT_PASS_DB,
    DROP_DB,
    LEE_BOX,
    LEE_ENL,
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


def lee_filter(power: np.ndarray, box: int = LEE_BOX, enl: float = LEE_ENL) -> np.ndarray:
    """NaN-aware Lee filter of linear power: local mean m and variance v over a box x box window (finite neighbours
    only, `despeckle`), then m + w (p - m) with w = clip(1 - (1 / enl) / (v / m^2), 0, 1). A flat (speckle-only)
    neighbourhood gets its mean; an edge or a bright point keeps its own value.

    A NaN pixel with enough finite neighbours (half the box) takes the local mean, as `despeckle` fills it; with fewer
    it stays NaN."""
    p = np.asarray(power, dtype=np.float64)
    finite = np.isfinite(p)
    m = despeckle(p, box)
    m2 = despeckle(np.where(finite, p * p, np.nan), box)
    with np.errstate(invalid="ignore", divide="ignore"):
        ci2 = (m2 - m * m) / (m * m)
        w = np.clip(1.0 - (1.0 / enl) / ci2, 0.0, 1.0)
        out = m + w * (np.where(finite, p, m) - m)
    return np.where(np.isfinite(m), out, np.nan)


def water_reference(hh_db: np.ndarray, valid: np.ndarray, stat_mask: np.ndarray | None = None) -> float | None:
    """The window-median HH (dB, Lee-filtered) D17 measures water against: over the valid pixels that `stat_mask` leaves
    in (True = left out of the statistics: layover and shadow), or over every valid pixel without one (or when it
    would leave none). None when no pixel is valid."""
    valid = np.asarray(valid, bool)
    use = valid if stat_mask is None else valid & ~np.asarray(stat_mask, bool)
    if not use.any():
        use = valid
    if not use.any():
        return None
    return float(np.median(np.asarray(hh_db)[use]))


def water_mask(hh_db: np.ndarray, valid: np.ndarray, stat_mask: np.ndarray | None = None,
               drop_db: float = DROP_DB, ref_db: float | None = None) -> np.ndarray:
    """D17 water: `valid` and HH (dB, Lee-filtered) at least `drop_db` below the window-median HH (`water_reference`).
    `ref_db`, when given, is that median as measured on the full 6 km window before the cache cropped it
    (`lakebuild.window_reference`); `stat_mask` is then not used."""
    valid = np.asarray(valid, bool)
    ref = ref_db if ref_db is not None and np.isfinite(ref_db) else water_reference(hh_db, valid, stat_mask)
    if ref is None:
        return np.zeros(valid.shape, bool)
    with np.errstate(invalid="ignore"):
        return valid & (hh_db <= ref - drop_db)


def screen_passes(hh_db_by_pass: dict[str, np.ndarray]) -> dict[str, str]:
    """For one track: exclude passes whose window-median HH is far from the track median.

    Returns excluded pass id -> reason. A badly calibrated pass (e.g. +25 dB) is never read as change.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # a window with no valid pixel has a NaN median
        return screen_medians({k: float(np.nanmedian(v)) for k, v in hh_db_by_pass.items()})


def screen_medians(medians: dict[str, float]) -> dict[str, str]:
    """`screen_passes` on each pass's window-median HH (dB, despeckled; NaN for a window with no valid pixel)."""
    finite = [m for m in medians.values() if np.isfinite(m)]
    if not finite:  # no pass of the track has a valid pixel (e.g. the window lies in mask-0 coverage)
        return {k: "window has no valid HH pixels" for k in medians}
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


def dark_medians(hh_db: np.ndarray, hv_db: np.ndarray) -> tuple[float, float] | None:
    """The window medians (HH, HV dB) `dark_mask` compares with, over the pixels valid in both; None when none is."""
    valid = np.isfinite(hh_db) & np.isfinite(hv_db)
    if not valid.any():
        return None
    return float(np.median(np.asarray(hh_db)[valid])), float(np.median(np.asarray(hv_db)[valid]))


def dark_mask(hh_db: np.ndarray, hv_db: np.ndarray, drop_db: float = DROP_DB,
              ref: tuple[float, float] | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Dark = HH and HV both at least `drop_db` below their window medians (`dark_medians`, or `ref` when given: the
    medians of the full 6 km window before the cache cropped it). Returns (dark, valid).

    NaN pixels are valid=False and dark=False.
    """
    valid = np.isfinite(hh_db) & np.isfinite(hv_db)
    if not valid.any():
        return np.zeros(hh_db.shape, bool), valid
    hh_med, hv_med = ref if ref is not None else dark_medians(hh_db, hv_db)
    with np.errstate(invalid="ignore"):
        dark = valid & (hh_db <= hh_med - drop_db) & (hv_db <= hv_med - drop_db)
    return dark, valid


def shadow_prone(median_dark_by_track: dict[str, np.ndarray], directions: dict[str, str],
                 median_valid_by_track: dict[str, np.ndarray] | None = None) -> np.ndarray | None:
    """Pixels dark in some view's median and seen, valid and not dark, in the opposite direction.

    A pixel the opposite direction never measured (NaN, outside its swath) is not shadow: missing coverage is no
    evidence of anything, so it keeps whatever the view that does see it says. `median_valid_by_track` gives each
    track's valid median pixels (default: every pixel valid). Returns None when only one viewing direction exists
    (the lake is "single viewing direction").
    """
    dark_by: dict[str, np.ndarray] = {}
    valid_by: dict[str, np.ndarray] = {}
    for track, dark in median_dark_by_track.items():
        d = directions[track]
        valid = (np.ones(dark.shape, bool) if median_valid_by_track is None
                 else np.asarray(median_valid_by_track[track], bool))
        dark_by[d] = dark_by[d] | dark if d in dark_by else dark.copy()
        valid_by[d] = valid_by[d] | valid if d in valid_by else valid.copy()
    if len(dark_by) < 2:
        return None
    asc, desc = dark_by["A"], dark_by["D"]
    seen_light_asc = valid_by["A"] & ~asc
    seen_light_desc = valid_by["D"] & ~desc
    return (asc & seen_light_desc) | (desc & seen_light_asc)


def outline_rings(outline_polygon) -> list[list]:
    """The exterior ring (lon, lat vertices) of each part of an outline: a list of vertices (one ring), a GeoJSON
    Polygon (one part) or a GeoJSON MultiPolygon (one ring per part). Holes are not used: an island counts as part
    of its lake's zone, as it always has."""
    if isinstance(outline_polygon, dict):
        kind = outline_polygon.get("type")
        if kind == "Polygon":
            return [outline_polygon["coordinates"][0]]
        if kind == "MultiPolygon":
            return [part[0] for part in outline_polygon["coordinates"]]
        raise ValueError(f"an outline must be a Polygon or MultiPolygon, got {kind!r}")
    return [list(outline_polygon)]


def outline_mask(shape, x, y, epsg, outline_polygon) -> np.ndarray:
    """The outline itself, without the buffer, rasterised on the window grid: the union of its parts (pixel centres
    inside a part; a part narrower than a pixel takes every pixel it touches). Empty when the outline misses the
    grid."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    dx = float(x[1] - x[0]) if len(x) > 1 else 1.0
    dy = float(y[1] - y[0]) if len(y) > 1 else -1.0
    to_utm = Transformer.from_crs(4326, epsg, always_xy=True)
    transform = Affine(dx, 0, x[0] - dx / 2, 0, dy, y[0] - dy / 2)
    inside = np.zeros(tuple(shape), bool)
    for ring_ll in outline_rings(outline_polygon):
        poly = {"type": "Polygon", "coordinates": [[to_utm.transform(lon, lat) for lon, lat in ring_ll]]}
        part = geometry_mask([poly], out_shape=tuple(shape), transform=transform, invert=True)
        if not part.any():
            # A part narrower than a pixel can hold no pixel centre and still lie on the grid: take every pixel it
            # touches instead (the 200 m buffer of the zone dwarfs the difference).
            part = geometry_mask([poly], out_shape=tuple(shape), transform=transform, invert=True, all_touched=True)
        inside |= part
    return inside


def lake_zone(shape, x, y, epsg, lake: Lake, outline_polygon=None, half_km: float | None = None) -> np.ndarray:
    """Boolean mask of the lake zone on the window grid.

    With `outline_polygon`: the outline rasterised and buffered by 200 m. It is either a list of
    (lon, lat) WGS84 vertices (exterior ring), a GeoJSON Polygon dict {"type": "Polygon",
    "coordinates": [[[lon, lat], ...]]} or a GeoJSON MultiPolygon, whose zone is the union of its parts, each
    buffered by 200 m. Without it: a circle around the lake's point (water area "in the
    search window") of radius `half_km`, by default the lake's own `zone_radius_km` (1 km unless set).
    `x`, `y` are the window's UTM coordinate vectors (metres, pixel centres) in `epsg`.
    """
    x, y = np.asarray(x, float), np.asarray(y, float)
    dx = float(x[1] - x[0]) if len(x) > 1 else 1.0
    dy = float(y[1] - y[0]) if len(y) > 1 else -1.0
    to_utm = Transformer.from_crs(4326, epsg, always_xy=True)
    if outline_polygon is None:
        if half_km is None:
            half_km = getattr(lake, "zone_radius_km", 1.0)
        cx, cy = to_utm.transform(lake.lon, lake.lat)
        xx, yy = np.meshgrid(x, y)
        return ((xx - cx) ** 2 + (yy - cy) ** 2) <= (half_km * 1000.0) ** 2
    inside = outline_mask(shape, x, y, epsg, outline_polygon)
    if not inside.any():
        # With no outline pixel on the grid the distance transform measures from nothing and draws a phantom zone
        # in a corner. An outline that misses the window (an old outline after the point moved) is an error.
        raise ValueError(f"{lake.id}: the outline does not cover any pixel of the radar window; check that the "
                         "outline belongs to the lake point")
    dist = distance_transform_edt(~inside, sampling=(abs(dy), abs(dx)))
    return dist <= OUTLINE_BUFFER_M


def outline_window_share(x, y, epsg, outline_polygon) -> float:
    """Share of the outline's area (without the buffer) that lies on the window grid, 0 to 1. For a MultiPolygon,
    the share of the union of its parts (their areas summed; a part narrower than a pixel counts the pixels it
    touches, as lake_zone does)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    dx, dy = float(x[1] - x[0]), float(y[1] - y[0])
    to_utm = Transformer.from_crs(4326, epsg, always_xy=True)
    area = 0.0
    for ring_ll in outline_rings(outline_polygon):
        ring = [to_utm.transform(lon, lat) for lon, lat in ring_ll]
        xs, ys = np.array([p[0] for p in ring]), np.array([p[1] for p in ring])
        area += 0.5 * abs(float(np.dot(xs, np.roll(ys, 1)) - np.dot(ys, np.roll(xs, 1))))  # shoelace, m²
    if area == 0:
        return 0.0
    inside = outline_mask((len(y), len(x)), x, y, epsg, outline_polygon)
    return min(1.0, float(inside.sum()) * abs(dx * dy) / area)


def outline_in_window_share(x, y, epsg, outline_polygon) -> float | None:
    """Share of the outline (without the buffer) inside the window, 0 to 1, counted in pixels on both sides: the
    outline is rasterised (`outline_mask`) on the window grid extended, with the same pixel size and pixel centres, to
    cover the outline's bounds, and its pixels inside the window are divided by all of its pixels. None when the
    outline takes no pixel at all."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    to_utm = Transformer.from_crs(4326, epsg, always_xy=True)
    pts = [to_utm.transform(lon, lat) for ring in outline_rings(outline_polygon) for lon, lat in ring]
    bx, by = [p[0] for p in pts], [p[1] for p in pts]

    def extended(axis: np.ndarray, lo: float, hi: float) -> tuple[np.ndarray, int]:
        step = float(axis[1] - axis[0]) if len(axis) > 1 else 1.0
        before = max(0, int(np.ceil(max((axis[0] - lo) / step, (axis[0] - hi) / step)))) + 1
        after = max(0, int(np.ceil(max((lo - axis[-1]) / step, (hi - axis[-1]) / step)))) + 1
        return axis[0] + step * np.arange(-before, len(axis) + after), before

    ex, ix = extended(x, min(bx), max(bx))
    ey, iy = extended(y, min(by), max(by))
    mask = outline_mask((len(ey), len(ex)), ex, ey, epsg, outline_polygon)
    total = int(mask.sum())
    if total == 0:
        return None
    return int(mask[iy:iy + len(y), ix:ix + len(x)].sum()) / total


def pass_water(hh_db: np.ndarray, valid: np.ndarray, zone: np.ndarray, pixel_m: float,
               stat_mask: np.ndarray | None = None, ref_db: float | None = None) -> dict:
    """Water in one pass (D17, `water_mask`): Lee-filtered HH `hh_db`, its `valid` pixels, the lake `zone`, and the
    layover/shadow `stat_mask` left out of the window median.

    Returns area_km2; observable_share (valid share of the zone pixels, 0.0 for an empty zone); valid (count of
    observable zone pixels); water (the water mask over the whole window).
    """
    water = water_mask(hh_db, valid, stat_mask, ref_db=ref_db)
    observable = zone & np.asarray(valid, bool)
    n_zone = int(zone.sum())
    return {
        "area_km2": float((water & zone).sum() * pixel_m ** 2 / 1e6),
        "observable_share": float(observable.sum() / n_zone) if n_zone else 0.0,
        "valid": int(observable.sum()),
        "water": water,
    }
