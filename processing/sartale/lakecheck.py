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
# A pair compares water only when Sentinel-2 sees at least this share of the lake zone clear (not cloud, shadow or
# no data). The window cloud share alone can be 1% while cloud covers the whole of a small lake; the comparison would
# then report a measured 0 km2 of water where nothing was seen.
MIN_ZONE_VALID = 0.8
NO_SEASON_PAIR = "no open-water-season pair"
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def season_text(season=None) -> str:
    """The open-water season in words, e.g. "15 Jun-30 Sep" (with an en dash)."""
    from sartale.config import OPEN_WATER_SEASON
    (m0, d0), (m1, d1) = season or OPEN_WATER_SEASON
    return f"{d0} {_MONTHS[m0 - 1]}\u2013{d1} {_MONTHS[m1 - 1]}"


def in_season(iso_date: str, season=None) -> bool:
    """True when `iso_date` (YYYY-MM-DD) falls in the open-water season (inclusive), whatever the year."""
    from sartale.config import OPEN_WATER_SEASON
    (m0, d0), (m1, d1) = season or OPEN_WATER_SEASON
    d = Date.fromisoformat(iso_date)
    return (m0, d0) <= (d.month, d.day) <= (m1, d1)
BOA_FLAG = "earthsearch:boa_offset_applied"  # item property: the DNs already have the BOA offset applied


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
            "days_apart": abs((day - target).days), "assets": f.get("assets", {}),
            "boa_offset_applied": bool(p.get(BOA_FLAG, False))}


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
    """Surface reflectance from DNs: DN * scale + offset, NaN where DN is 0 (no data).

    Earth Search items flagged `earthsearch:boa_offset_applied` already have the -0.1 BOA offset (processing
    baseline 04.00 and later) taken out of the DNs, so the offset is 0 for them; the band's scale still applies.
    Other items use the band's offset from `raster:bands`.
    """
    band = (scene["assets"][name].get("raster:bands") or [{}])[0]
    scale = band.get("scale", 1e-4)
    offset = 0.0 if scene.get("boa_offset_applied") else band.get("offset", -0.1)
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


def zone_valid_share(valid: np.ndarray, zone: np.ndarray) -> float:
    """Share of the lake zone's pixels that Sentinel-2 sees clear; 0.0 for an empty zone."""
    zone = np.asarray(zone, bool)
    return float(np.asarray(valid, bool)[zone].mean()) if zone.any() else 0.0


def _pair(a: dict) -> dict:
    return {"radar_km2": a["radar_km2"], "optical_km2": a["optical_km2"],
            "area_error_pct": a["area_error_pct"], "iou": a["iou"]}


def check_lake(lake, cache_dir, series: list[dict], days: int = 3, max_cloud: float = MAX_CLOUD_PCT,
               log=print, season=None) -> dict:
    """One check row for a lake: among the (valid NISAR pass, Sentinel-2 scene) pairs within `days` of each other
    whose NISAR pass falls in the open-water season (`config.OPEN_WATER_SEASON` unless `season` is given), the one
    whose lake window is clearest (lowest SCL cloud share, then fewest days apart, then the latest), provided that
    share is at most `max_cloud` percent and Sentinel-2 sees at least MIN_ZONE_VALID of the lake zone clear (a
    clouded lake zone is not measured as zero water; the row is then a note). Outside the season a lake can be frozen or under snow, which optical water
    never counts, so such a pair is no test of radar water. Without a valid in-season pass the row is a note
    (NO_SEASON_PAIR); without a clear scene, NO_SCENE. Every row carries `season`, the season in words.

    The headline numbers (`radar_km2`, `optical_km2`, `area_error_pct`, `iou`) are for the lake
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
    words = season_text(season)
    passes = [(d, t) for d, t in passes if in_season(d, season)]
    if not passes:
        return {"lake": lake.id, "note": f"{NO_SEASON_PAIR} ({words})", "season": words}
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
    tried, clear = set(), []
    masks: dict[str, dict] = {}
    for apart, tile_cloud, d, track, scene in cands:
        pass_id = f"{d}_{track}"
        if (scene["id"], d) in tried:
            continue
        tried.add((scene["id"], d))
        if pass_id not in masks:
            masks[pass_id] = radar_water_masks(lake, cache_dir, pass_id)
        radar = masks[pass_id]
        x, y, epsg = radar["x"], radar["y"], radar["epsg"]
        try:
            opt = optical_on_grid(scene, x, y, epsg)
        except Exception as e:  # noqa: BLE001 - a scene that will not read is skipped, and said so
            log(f"{lake.id} {pass_id} vs {scene['id']}: unreadable ({type(e).__name__})")
            continue
        pct = 100 * opt["window_cloud_share"]
        zone_valid = zone_valid_share(opt["valid"], radar["zone"])
        log(f"{lake.id} {pass_id} vs {scene['id']} ({apart} d apart): window cloud/no-data {pct:.1f}%, "
            f"lake zone seen clear {100 * zone_valid:.1f}%")
        if pct <= max_cloud and zone_valid >= MIN_ZONE_VALID:
            clear.append((round(pct, 1), apart, -Date.fromisoformat(d).toordinal(), track, scene, radar, opt, d, pct))
    if clear:
        _, apart, _, track, scene, radar, opt, d, pct = min(clear, key=lambda c: c[:4] + (c[4]["id"],))
        x = radar["x"]
        px = float(abs(x[1] - x[0]))
        zone = radar["zone"]  # the exact zone the radar side used (outline or circle)
        zone_cmp = compare_masks(radar["zone_mask"], opt["water"], px, valid=opt["valid"] & zone)
        win_cmp = compare_masks(radar["window"], opt["water"], px, valid=opt["valid"])
        return {"lake": lake.id, "nisar_date": d, "nisar_track": track, "s2_date": scene["date"],
                "s2_id": scene["id"], "days_apart": apart, "s2_window_cloud_pct": round(pct, 1),
                "scope": "zone", "season": words, **_pair(zone_cmp),
                "zone_valid_share": zone_valid_share(opt["valid"], zone),
                **{f"window_{k}": v for k, v in _pair(win_cmp).items()}}
    return {"lake": lake.id, "note": f"{NO_SCENE} in the open-water season ({words})", "season": words}


# --- absence check: is a site with no lake still empty? ------------------------------------------------------------

ABSENCE_MAX_SCENES = 12  # newest scenes tried per check; the first whose lake zone is clear enough is used
ABSENCE_MAX_TILE_CLOUD = 60.0  # tile cloud cover a scene may have and still be tried (the zone is checked itself)
ABSENCE_PIXEL_M = 10.0
ABSENCE_SOURCE = "Sentinel-2 L2A (Earth Search), MNDWI water in the lake zone"


def season_bounds(today: str, season=None) -> tuple[str, str] | None:
    """(first day of this year's season, today) when `today` is in the open-water season, else None (outside the
    season the last evidence stands)."""
    from sartale.config import OPEN_WATER_SEASON
    (m0, d0), _ = season or OPEN_WATER_SEASON
    if not in_season(today, season):
        return None
    t = Date.fromisoformat(today)
    return Date(t.year, m0, d0).isoformat(), t.isoformat()


def last_season_bounds(today: str, season=None) -> tuple[str, str]:
    """The most recent open-water season that has started by `today`, up to today: this year's when it has begun,
    else last year's. Used once, to give a site its first dated evidence."""
    from sartale.config import OPEN_WATER_SEASON
    (m0, d0), (m1, d1) = season or OPEN_WATER_SEASON
    t = Date.fromisoformat(today)
    year = t.year if (t.month, t.day) >= (m0, d0) else t.year - 1
    end = min(Date(year, m1, d1), t)
    return Date(year, m0, d0).isoformat(), end.isoformat()


def absence_grid(lake, pixel_m: float = ABSENCE_PIXEL_M):
    """A UTM grid (x, y, epsg) of `pixel_m` pixels over the lake's 6 km search box, north up."""
    from pyproj import Transformer
    from sartale.lakes import lake_bbox
    zone = int((lake.lon + 180) // 6) + 1
    epsg = (32600 if lake.lat >= 0 else 32700) + zone
    lon0, lat0, lon1, lat1 = lake_bbox(lake)
    tr = Transformer.from_crs(4326, epsg, always_xy=True)
    xs, ys = tr.transform([lon0, lon0, lon1, lon1], [lat0, lat1, lat0, lat1])
    x = np.arange(np.floor(min(xs) / pixel_m) * pixel_m + pixel_m / 2, max(xs), pixel_m)
    y = np.arange(np.ceil(max(ys) / pixel_m) * pixel_m - pixel_m / 2, min(ys), -pixel_m)
    return x, y, epsg


def zone_water(lake, opt: dict, x, y, epsg) -> dict:
    """Water share and area of the lake zone in one optical reading, over the zone pixels seen clear."""
    from sartale.lakebuild import _load_outline
    from sartale.lakewater import lake_zone
    zone = lake_zone((len(y), len(x)), x, y, epsg, lake, outline_polygon=_load_outline(lake))
    px = float(abs(x[1] - x[0]))
    seen = zone & opt["valid"]
    n_seen = int(seen.sum())
    water = int((opt["water"] & seen).sum())
    return {"zone_valid_share": zone_valid_share(opt["valid"], zone),
            "water_share": (water / n_seen) if n_seen else 0.0,
            "water_km2": water * px ** 2 / 1e6}


def absence_check(lake, today: str, prior: dict | None = None, log=print, season=None, bootstrap: bool = True,
                  max_scenes: int = ABSENCE_MAX_SCENES) -> dict | None:
    """Dated evidence on whether a site with no lake now is still empty: the newest Sentinel-2 scene of the
    open-water season whose lake zone is at least MIN_ZONE_VALID clear, with the water share of the zone.

    In the season, the season so far is searched on every run. Outside it, `prior` (the last evidence) is kept
    unchanged; only a site without any evidence yet (`bootstrap`) is checked against the last season. When no
    scene qualifies, `prior` is kept. Returns {"date", "s2_id", "water_share", "water_km2", "zone_valid_share",
    "checked", "season", "source"}, or None when there is no evidence at all.
    """
    from sartale.lakes import lake_bbox
    words = season_text(season)
    span = season_bounds(today, season)
    if span is None:
        if prior is not None or not bootstrap:
            return prior
        span = last_season_bounds(today, season)
    x, y, epsg = absence_grid(lake)
    scenes = [_scene(f, Date.fromisoformat(span[1])) for f in search_scenes(lake_bbox(lake), *span)]
    scenes = [s for s in scenes if s["cloud"] <= ABSENCE_MAX_TILE_CLOUD
              and all(k in s["assets"] for k in ("green", "swir16", "scl"))]
    scenes.sort(key=lambda s: (s["date"], -s["cloud"], s["id"]), reverse=True)
    for scene in scenes[:max_scenes]:
        try:
            opt = optical_on_grid(scene, x, y, epsg)
        except Exception as e:  # noqa: BLE001 - an unreadable scene is skipped, and said so
            log(f"{lake.id} absence vs {scene['id']}: unreadable ({type(e).__name__})")
            continue
        w = zone_water(lake, opt, x, y, epsg)
        log(f"{lake.id} absence vs {scene['id']} ({scene['date']}): zone seen clear "
            f"{100 * w['zone_valid_share']:.1f}%, water {100 * w['water_share']:.2f}% of the zone "
            f"({w['water_km2']:.4f} km2)")
        if w["zone_valid_share"] >= MIN_ZONE_VALID:
            return {"date": scene["date"], "s2_id": scene["id"], "water_share": round(w["water_share"], 4),
                    "water_km2": round(w["water_km2"], 4), "zone_valid_share": round(w["zone_valid_share"], 3),
                    "checked": today, "season": words, "source": ABSENCE_SOURCE}
    log(f"{lake.id} absence: no scene with the lake zone clear in {span[0]}..{span[1]}; the last evidence stands")
    return prior
