"""Cross-check radar lake water against Sentinel-2 optical water (MNDWI) for the same lake and date.

Sentinel-2 L2A scenes come from the Earth Search STAC API (no credentials). Only a window of the
B03, B11 and SCL cloud-optimised GeoTIFFs is read, never a whole tile.
"""
from datetime import date as Date, datetime, timedelta

import numpy as np
import rasterio
import requests
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.warp import reproject, transform_bounds
from rasterio.windows import Window

STAC_URL = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-l2a"
MAX_CLOUD_PCT = 20.0
# Scene classification values that make a pixel unusable: no data, saturated, cloud shadow,
# medium and high cloud probability, thin cirrus. Snow/ice (11) is usable but never water here.
SCL_BAD = (0, 1, 3, 8, 9, 10)
SCL_SNOW = 11
NO_SCENE = "no clear Sentinel-2 scene within 3 days"


def mndwi_water(green: np.ndarray, swir: np.ndarray, threshold: float = 0.0) -> np.ndarray:
    """Water where MNDWI = (green - swir) / (green + swir) is above `threshold`.

    NaN reflectance, or green + swir == 0, is never water.
    """
    g, s = np.asarray(green, float), np.asarray(swir, float)
    with np.errstate(invalid="ignore", divide="ignore"):
        idx = (g - s) / (g + s)
    return np.isfinite(idx) & (idx > threshold)


def compare_masks(radar: np.ndarray, optical: np.ndarray, pixel_m: float, valid: np.ndarray | None = None) -> dict:
    """Areas and overlap of two water masks on the same grid.

    `area_error_pct` is (radar - optical) / optical * 100, so a radar area above the optical one is
    positive; None when the optical area is zero. `iou` is None when both masks are empty.
    `valid` (optional) limits the comparison to pixels both sensors could see.
    """
    r, o = np.asarray(radar, bool), np.asarray(optical, bool)
    if valid is not None:
        r, o = r & valid, o & valid
    km2 = pixel_m ** 2 / 1e6
    union = int((r | o).sum())
    radar_km2, optical_km2 = float(r.sum() * km2), float(o.sum() * km2)
    return {
        "radar_km2": radar_km2,
        "optical_km2": optical_km2,
        "area_error_pct": None if optical_km2 == 0 else (radar_km2 - optical_km2) / optical_km2 * 100.0,
        "iou": None if union == 0 else float((r & o).sum() / union),
    }


def scl_cloud_share(scl: np.ndarray) -> float:
    """Share of pixels that are no-data, saturated, cloud, cloud shadow or cirrus."""
    scl = np.asarray(scl)
    return float(np.isin(scl, SCL_BAD).mean()) if scl.size else 1.0


def _scene(f: dict, target: Date) -> dict:
    p = f["properties"]
    day = datetime.fromisoformat(p["datetime"].replace("Z", "+00:00")).date()
    return {"id": f["id"], "date": day.isoformat(), "cloud": float(p.get("eo:cloud_cover", 100.0)),
            "days_apart": abs((day - target).days), "assets": f.get("assets", {})}


def search_scenes(bbox, start: str, end: str, limit: int = 500) -> list[dict]:
    """Sentinel-2 L2A STAC items touching `bbox` (lon_min, lat_min, lon_max, lat_max) between two dates."""
    body = {"collections": [COLLECTION], "bbox": list(bbox),
            "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z", "limit": limit}
    r = requests.post(f"{STAC_URL}/search", json=body, timeout=60)
    r.raise_for_status()
    return r.json()["features"]


def find_clear_scene(bbox, date: str, days: int = 3, max_cloud: float = MAX_CLOUD_PCT) -> dict | None:
    """The scene within `days` of `date` with tile cloud cover <= `max_cloud`, nearest in time (then
    clearest). None if there is none. Tile cloud cover is only a first filter; the lake window is
    checked separately with the scene classification band (`optical_on_grid`)."""
    target = Date.fromisoformat(date)
    start, end = (target - timedelta(days=days)).isoformat(), (target + timedelta(days=days)).isoformat()
    scenes = [_scene(f, target) for f in search_scenes(bbox, start, end)]
    scenes = [s for s in scenes if s["cloud"] <= max_cloud and s["days_apart"] <= days]
    return min(scenes, key=lambda s: (s["days_apart"], s["cloud"], s["id"])) if scenes else None


def _window(west, south, east, north, tf: Affine) -> Window:
    """Pixel window of a north-up raster for map bounds (affine arithmetic only; no linear solve)."""
    c0, c1 = (west - tf.c) / tf.a, (east - tf.c) / tf.a
    r0, r1 = (north - tf.f) / tf.e, (south - tf.f) / tf.e
    return Window(c0, r0, c1 - c0, r1 - r0)


def _href(scene: dict, name: str) -> str:
    return scene["assets"][name]["href"]


def _reflectance(scene: dict, name: str, dn: np.ndarray) -> np.ndarray:
    band = (scene["assets"][name].get("raster:bands") or [{}])[0]
    scale, offset = band.get("scale", 1e-4), band.get("offset", -0.1)
    return np.where(dn == 0, np.nan, dn.astype(np.float64) * scale + offset)


def optical_on_grid(scene: dict, x: np.ndarray, y: np.ndarray, epsg: int) -> dict:
    """Read the scene's B03, B11 and SCL over the NISAR window; put MNDWI water on the NISAR grid.

    MNDWI is computed at 10 m (B11 and SCL, 20 m, are resampled to the B03 grid), then averaged onto
    the NISAR grid: a NISAR pixel is optical water when at least half of it is, and unusable when at
    least half of it is cloud/shadow/no-data or lies outside the scene. Snow and ice are never water.
    Returns water and valid (bool grids on the NISAR window), window_cloud_share (SCL cloud share over
    the whole window) and invalid_share.
    """
    x, y = np.asarray(x, float), np.asarray(y, float)
    dx, dy = float(x[1] - x[0]), float(y[1] - y[0])
    dst_tf = Affine(dx, 0, x[0] - dx / 2, 0, dy, y[0] - dy / 2)
    shape = (len(y), len(x))
    west, east = min(x[0], x[-1]) - abs(dx) / 2, max(x[0], x[-1]) + abs(dx) / 2
    south, north = min(y[0], y[-1]) - abs(dy) / 2, max(y[0], y[-1]) + abs(dy) / 2
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
                      GDAL_HTTP_MAX_RETRY="3", GDAL_HTTP_RETRY_DELAY="2"):
        with rasterio.open(_href(scene, "green")) as g:
            sb = transform_bounds(CRS.from_epsg(epsg), g.crs, west, south, east, north, densify_pts=21)
            win = _window(*sb, g.transform).round_offsets().round_lengths()
            win = Window(win.col_off - 2, win.row_off - 2, win.width + 4, win.height + 4)
            green = g.read(1, window=win, boundless=True, fill_value=0)
            src_tf, src_crs = g.window_transform(win), g.crs
            t = g.window_transform(win)
            wb = (t.c, t.f + t.e * win.height, t.c + t.a * win.width, t.f)
        with rasterio.open(_href(scene, "swir16")) as s:
            swir = s.read(1, window=_window(*wb, s.transform), out_shape=green.shape,
                          resampling=Resampling.bilinear, boundless=True, fill_value=0)
        with rasterio.open(_href(scene, "scl")) as c:
            scl = c.read(1, window=_window(*wb, c.transform), out_shape=green.shape,
                         resampling=Resampling.nearest, boundless=True, fill_value=0)
    bad10 = np.isin(scl, SCL_BAD)
    water10 = mndwi_water(_reflectance(scene, "green", green), _reflectance(scene, "swir16", swir))
    water10 &= (scl != SCL_SNOW) & ~bad10

    def to_grid(a: np.ndarray) -> np.ndarray:
        dst = np.zeros(shape, np.float32)
        reproject(a.astype(np.float32), dst, src_transform=src_tf, src_crs=src_crs, dst_transform=dst_tf,
                  dst_crs=CRS.from_epsg(epsg), resampling=Resampling.average)
        return dst

    inside = to_grid(np.ones(green.shape, np.float32))  # >0 where the padded read covers the grid
    covered = to_grid((green > 0).astype(np.float32))  # scene pixels actually present
    bad, wfrac = to_grid(bad10), to_grid(water10)
    valid = (covered >= 0.5) & (bad < 0.5)
    seen = inside > 0.5
    cloud_share = float(np.clip(bad[seen] / inside[seen], 0, 1).mean()) if seen.any() else 1.0
    return {"water": (wfrac >= 0.5) & valid, "valid": valid, "window_cloud_share": cloud_share,
            "invalid_share": float(1 - valid.mean())}


def _pair(a: dict) -> dict:
    return {"radar_km2": a["radar_km2"], "optical_km2": a["optical_km2"],
            "area_error_pct": a["area_error_pct"], "iou": a["iou"]}


def check_lake(lake, cache_dir, series: list[dict], days: int = 3, max_cloud: float = MAX_CLOUD_PCT,
               log=print) -> dict:
    """One check row for a lake: the (valid NISAR pass, Sentinel-2 scene) pair closest in time whose
    lake window is clear (SCL cloud share <= `max_cloud` percent), or a row saying there is none.

    The headline numbers (`radar_km2`, `optical_km2`, `area_error_pct`, `iou`) are for the 1 km lake
    zone, the area the app reports. `window_*` repeat them over the whole ~6 km window, where the radar
    side is every dark, non-shadow pixel and so includes non-lake dark ground.
    """
    from sartale.lakebuild import radar_water_masks
    from sartale.lakes import lake_bbox
    from sartale.lakestatus import is_valid

    # Same validity rule as the status (not excluded, has an area, observable share >= MIN_OBSERVABLE).
    passes = sorted({(p["date"], p["track"]) for p in series if is_valid(p)})
    if not passes:
        return {"lake": lake.id, "note": "no valid NISAR pass"}
    bbox = lake_bbox(lake)
    first = Date.fromisoformat(passes[0][0]) - timedelta(days=days)
    last = Date.fromisoformat(passes[-1][0]) + timedelta(days=days)
    items = search_scenes(bbox, first.isoformat(), last.isoformat())
    cands = []
    for d, track in passes:
        for f in items:
            s = _scene(f, Date.fromisoformat(d))
            if s["days_apart"] <= days and "green" in s["assets"] and "scl" in s["assets"]:
                cands.append((s["days_apart"], s["cloud"], d, track, s))
    cands.sort(key=lambda c: c[:4] + (c[4]["id"],))
    tried = set()
    for apart, tile_cloud, d, track, scene in cands:
        pass_id = f"{d}_{track}"
        if (scene["id"], d) in tried:
            continue
        tried.add((scene["id"], d))
        radar = radar_water_masks(lake, cache_dir, pass_id)
        x, y, epsg = radar["x"], radar["y"], radar["epsg"]
        try:
            opt = optical_on_grid(scene, x, y, epsg)
        except Exception as e:  # noqa: BLE001 - a scene that will not read is skipped, and said so
            log(f"{lake.id} {pass_id} vs {scene['id']}: unreadable ({type(e).__name__})")
            continue
        pct = 100 * opt["window_cloud_share"]
        log(f"{lake.id} {pass_id} vs {scene['id']} ({apart} d apart): window cloud/no-data {pct:.1f}%")
        if pct > max_cloud:
            continue
        px = float(abs(x[1] - x[0]))
        zone = radar["zone"]  # the exact zone the radar side used (outline or circle)
        zone_cmp = compare_masks(radar["zone_mask"], opt["water"], px, valid=opt["valid"] & zone)
        win_cmp = compare_masks(radar["window"], opt["water"], px, valid=opt["valid"])
        return {"lake": lake.id, "nisar_date": d, "nisar_track": track, "s2_date": scene["date"],
                "s2_id": scene["id"], "days_apart": apart, "s2_window_cloud_pct": round(pct, 1),
                "scope": "zone", **_pair(zone_cmp),
                "zone_valid_share": float(opt["valid"][zone].mean()),
                **{f"window_{k}": v for k, v in _pair(win_cmp).items()}}
    return {"lake": lake.id, "note": NO_SCENE}
