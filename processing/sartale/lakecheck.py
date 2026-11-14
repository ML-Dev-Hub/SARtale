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
from scipy.ndimage import distance_transform_edt

STAC_URL = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-l2a"
MAX_CLOUD_PCT = 20.0
# Scene classification values that make a pixel unusable: no data, saturated, cloud shadow,
# medium and high cloud probability, thin cirrus (the window cloud share counts these).
SCL_BAD = (0, 1, 3, 8, 9, 10)
# Snow/ice is never water, and never a clear view either: a frozen or snow-covered lake reads as dry ground, so a
# pixel under snow or ice is left out of `valid` (and of the zone's clear share) as cloud is.
SCL_SNOW = 11
SCL_TERRAIN_SHADOW = 2  # shadow of the terrain on a clear day: not a clear view for the absence check
# Cloud shadow, medium and high cloud, thin cirrus: pixels within CLOUD_EDGE_BUFFER_M of these are not clear either.
# Their edges are often unflagged haze or shadow that MNDWI reads as water (Shisper, 16 Oct 2026: 14.5% "water" on
# bare soil next to cloud shadow, in a zone 80.6% clear).
SCL_CLOUD = (3, 8, 9, 10)
CLOUD_EDGE_BUFFER_M = 100.0
NO_SCENE = "no clear Sentinel-2 scene within 3 days"
# A pair compares water only when Sentinel-2 sees at least this share of the lake zone clear (not cloud, shadow, no
# data, snow or ice). The window cloud share alone can be 1% while cloud covers the whole of a small lake; the
# comparison would then report a measured 0 km2 of water where nothing was seen. The absence check uses it too.
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


def search_scenes(bbox, start: str, end: str, limit: int = 500, max_pages: int = 50) -> list[dict]:
    """Sentinel-2 L2A STAC items touching `bbox` (lon_min, lat_min, lon_max, lat_max) between two dates, every page:
    the STAC `next` link is followed (its method, href and body; `merge` adds its body to the last one) until a page
    has no `next` link or no items. More than `max_pages` pages raises, so a search never silently stops short."""
    body = {"collections": [COLLECTION], "bbox": list(bbox),
            "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z", "limit": limit}
    url, method = f"{STAC_URL}/search", "POST"
    items, seen = [], set()
    for _ in range(max_pages):
        r = requests.post(url, json=body, timeout=60) if method == "POST" else requests.get(url, timeout=60)
        r.raise_for_status()
        doc = r.json()
        page = doc.get("features") or []
        for f in page:
            if f["id"] not in seen:
                seen.add(f["id"])
                items.append(f)
        nxt = next((ln for ln in doc.get("links") or [] if ln.get("rel") == "next"), None)
        if not page or not nxt:
            return items
        url, method = nxt["href"], str(nxt.get("method", "GET")).upper()
        if method == "POST":
            body = {**body, **(nxt.get("body") or {})} if nxt.get("merge") else (nxt.get("body") or body)
    raise RuntimeError(f"Sentinel-2 search returned more than {max_pages} pages")


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


def _grid_bounds(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    dx, dy = float(x[1] - x[0]), float(y[1] - y[0])
    west, east = min(x[0], x[-1]) - abs(dx) / 2, max(x[0], x[-1]) + abs(dx) / 2
    south, north = min(y[0], y[-1]) - abs(dy) / 2, max(y[0], y[-1]) + abs(dy) / 2
    return west, south, east, north


def read_scene(scene: dict, x: np.ndarray, y: np.ndarray, epsg: int) -> dict:
    """The scene's B03 (10 m), and B11 and SCL resampled to it, over the NISAR window plus a margin wide enough for
    the cloud-edge buffer (cloud just outside the window still buffers into it). Returns green, swir, scl, the
    window's transform and CRS, and the pixel size in metres."""
    west, south, east, north = _grid_bounds(x, y)
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
                      GDAL_HTTP_MAX_RETRY="3", GDAL_HTTP_RETRY_DELAY="2"):
        with rasterio.open(_href(scene, "green")) as g:
            px = abs(g.transform.a)
            pad = int(np.ceil(CLOUD_EDGE_BUFFER_M / px)) + 2
            sb = transform_bounds(CRS.from_epsg(epsg), g.crs, west, south, east, north, densify_pts=21)
            win = _window(*sb, g.transform).round_offsets().round_lengths()
            win = Window(win.col_off - pad, win.row_off - pad, win.width + 2 * pad, win.height + 2 * pad)
            green = g.read(1, window=win, boundless=True, fill_value=0)
            src_tf, src_crs = g.window_transform(win), g.crs
            wb = (src_tf.c, src_tf.f + src_tf.e * win.height, src_tf.c + src_tf.a * win.width, src_tf.f)
        with rasterio.open(_href(scene, "swir16")) as s:
            swir = s.read(1, window=_window(*wb, s.transform), out_shape=green.shape,
                          resampling=Resampling.bilinear, boundless=True, fill_value=0)
        with rasterio.open(_href(scene, "scl")) as c:
            scl = c.read(1, window=_window(*wb, c.transform), out_shape=green.shape,
                         resampling=Resampling.nearest, boundless=True, fill_value=0)
    return {"green": green, "swir": swir, "scl": scl, "transform": src_tf, "crs": src_crs, "px": px}


def near_cloud(scl: np.ndarray, px: float, buffer_m: float) -> np.ndarray:
    """Pixels of cloud (SCL_CLOUD: cloud shadow, medium and high cloud, cirrus) or within `buffer_m` of one."""
    cloud = np.isin(scl, SCL_CLOUD)
    if buffer_m <= 0 or not cloud.any():
        return cloud
    return distance_transform_edt(~cloud, sampling=(px, px)) <= buffer_m


def grid_scene(scene: dict, raw: dict, x, y, epsg: int, buffer_m: float = None) -> dict:
    """Masks of one read scene (`read_scene`) on the NISAR grid; see `optical_on_grid`. `buffer_m` defaults to
    CLOUD_EDGE_BUFFER_M (0 gives the rule without the buffer, for comparison)."""
    buffer_m = CLOUD_EDGE_BUFFER_M if buffer_m is None else buffer_m
    x, y = np.asarray(x, float), np.asarray(y, float)
    dx, dy = float(x[1] - x[0]), float(y[1] - y[0])
    dst_tf = Affine(dx, 0, x[0] - dx / 2, 0, dy, y[0] - dy / 2)
    shape = (len(y), len(x))
    green, swir, scl = raw["green"], raw["swir"], raw["scl"]
    bad10 = np.isin(scl, SCL_BAD)
    # Not clear: no data, cloud, shadow, and the 100 m round cloud and cloud shadow, where unflagged haze and shadow
    # edges read as water in MNDWI.
    unclear10 = bad10 | near_cloud(scl, raw["px"], buffer_m)
    snow10 = scl == SCL_SNOW
    shadow10 = scl == SCL_TERRAIN_SHADOW
    water10 = mndwi_water(_reflectance(scene, "green", green), _reflectance(scene, "swir16", swir))
    water10 &= ~snow10 & ~unclear10

    def to_grid(a: np.ndarray) -> np.ndarray:
        dst = np.zeros(shape, np.float32)
        reproject(a.astype(np.float32), dst, src_transform=raw["transform"], src_crs=raw["crs"], dst_transform=dst_tf,
                  dst_crs=CRS.from_epsg(epsg), resampling=Resampling.average)
        return dst

    inside = to_grid(np.ones(green.shape, np.float32))  # >0 where the padded read covers the grid
    covered = to_grid((green > 0).astype(np.float32))  # scene pixels actually present
    bad, unclear, wfrac, sfrac = to_grid(bad10), to_grid(unclear10), to_grid(water10), to_grid(snow10)
    shadow_frac = to_grid(shadow10)
    present = covered >= 0.5
    # Snow or ice is not a clear view: a frozen or snow-covered lake reads as dry ground in MNDWI.
    valid = present & (unclear + sfrac < 0.5)
    snow = present & (sfrac >= 0.5)
    seen = inside > 0.5
    cloud_share = float(np.clip(bad[seen] / inside[seen], 0, 1).mean()) if seen.any() else 1.0
    # Clear of cloud, shadow, no data and the cloud edge, snow or not: what the freeze check (lakes-freeze) counts as seen.
    clear = present & (unclear < 0.5)
    # Terrain shadow stays in `valid` (the cross-check and the freeze check count it as seen); only the absence check
    # leaves it out of the clear view (`zone_water`), where a shadowed slope or a dark river reads as water.
    terrain_shadow = present & (shadow_frac >= 0.5)
    return {"water": (wfrac >= 0.5) & valid, "valid": valid, "snow": snow, "clear": clear,
            "terrain_shadow": terrain_shadow,
            "window_cloud_share": cloud_share, "invalid_share": float(1 - valid.mean())}


def optical_on_grid(scene: dict, x: np.ndarray, y: np.ndarray, epsg: int) -> dict:
    """Read the scene's B03, B11 and SCL over the NISAR window; put MNDWI water on the NISAR grid.

    MNDWI is computed at 10 m (B11 and SCL, 20 m, are resampled to the B03 grid), then averaged onto
    the NISAR grid: a NISAR pixel is optical water when at least half of it is, and unusable when at
    least half of it is cloud/shadow/no-data/snow/ice, within CLOUD_EDGE_BUFFER_M of cloud or cloud shadow, or lies
    outside the scene. Snow and ice are never water and never clear. Returns water, valid and snow (bool grids on the
    NISAR window: snow where at least half the pixel is snow or ice), clear (present and less than half cloud, shadow,
    no data or cloud edge, snow or not), window_cloud_share (SCL cloud share over the whole window, without the buffer)
    and invalid_share.
    """
    return grid_scene(scene, read_scene(scene, x, y, epsg), x, y, epsg)


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
    share is at most `max_cloud` percent and Sentinel-2 sees at least MIN_ZONE_VALID of the lake zone clear of cloud,
    shadow, snow and ice (a clouded or snow-covered lake zone is not measured as zero water; the row is then a note).
    Outside the season a lake can be frozen or under snow, which optical water never counts, so such a pair is no
    test of radar water. Without a valid in-season pass the row is a note
    (NO_SEASON_PAIR); without a clear scene, NO_SCENE. Every row carries `season`, the season in words.

    The headline numbers (`radar_km2`, `optical_km2`, `area_error_pct`, `iou`) are for the lake
    zone, the area the app reports. `window_*` repeat them over the whole ~6 km window, where the radar
    side is every dark, non-shadow pixel and so includes non-lake dark ground.
    """
    from sartale.lakebuild import radar_water_context
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
    radar_of = radar_water_context(lake, cache_dir)  # the windows are read and analysed once per lake
    optical: dict[str, dict] = {}  # each scene is read once: every pass of a lake is on the same grid
    for apart, tile_cloud, d, track, scene in cands:
        pass_id = f"{d}_{track}"
        if (scene["id"], d) in tried:
            continue
        tried.add((scene["id"], d))
        if pass_id not in masks:
            masks[pass_id] = radar_of(pass_id)
        radar = masks[pass_id]
        x, y, epsg = radar["x"], radar["y"], radar["epsg"]
        if scene["id"] not in optical:
            try:
                optical[scene["id"]] = optical_on_grid(scene, x, y, epsg)
            except Exception as e:  # noqa: BLE001 - a scene that will not read is skipped, and said so
                log(f"{lake.id} {pass_id} vs {scene['id']}: unreadable ({type(e).__name__})")
                optical[scene["id"]] = None
        opt = optical[scene["id"]]
        if opt is None:
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

ABSENCE_MAX_SCENES = 12  # newest scenes tried per run (more than a week of scenes); the first that qualifies is used
ABSENCE_FIRST_SCENES = 60  # a site without evidence yet: newest scenes tried, enough to reach back past a winter
ABSENCE_FIRST_LOOKBACK_DAYS = 400  # a site without evidence yet: how far back to search (the last summer included)
ABSENCE_MAX_TILE_CLOUD = 60.0  # tile cloud cover a scene may have and still be tried (the zone is checked itself)
# Snow or ice on more than this share of the lake zone disqualifies a scene, even when 80% of the zone is clear: a
# frozen or snow-covered pond reads as dry ground in MNDWI and would hide the very water the check looks for. Not
# quite zero, so a few bright pixels the scene classification calls snow do not void every summer view; well under
# every site's forming share (4% to 16%), so snow that small cannot hide a lake that would change the verdict.
ABSENCE_MAX_SNOW_SHARE = 0.01
# Evidence older than this many days at the last search says so on the site: no clear, snow-free view since.
ABSENCE_STALE_DAYS = 7
# A site's state changes only on two qualifying scenes on the other side of its threshold, on dates at least this many
# days apart (`step`): one scene of cloud-edge haze or a high river is not a lake forming, and one dry scene does not
# end one.
ABSENCE_CONFIRM_DAYS = 5
ABSENCE_PIXEL_M = 10.0
ABSENCE_SOURCE = "Sentinel-2 L2A (Earth Search), MNDWI water in the lake zone"
# What a scene must show to count, stored with the evidence (`rule`).
ABSENCE_RULE = (f"at least {MIN_ZONE_VALID:.0%} of the lake zone clear of cloud, shadow, snow and ice, and snow or ice "
                f"on no more than {ABSENCE_MAX_SNOW_SHARE:.0%} of it, pixels within {CLOUD_EDGE_BUFFER_M:.0f} m of cloud or "
                f"cloud shadow, and pixels the scene classes as terrain shadow (SCL 2), not clear; the state changes on two such scenes at least {ABSENCE_CONFIRM_DAYS} days "
                "apart")


def no_view_since(date: str, searched: str) -> bool:
    """True when the last search (`searched`) is more than ABSENCE_STALE_DAYS after the evidence's scene (`date`):
    every newer scene was cloudy, snowy or unreadable."""
    return (Date.fromisoformat(searched) - Date.fromisoformat(date)).days > ABSENCE_STALE_DAYS


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


def zone_water(lake, opt: dict, x, y, epsg, exclude: np.ndarray | None = None) -> dict:
    """Water share and area of the lake zone in one optical reading, over the zone pixels seen clear, with the share
    of the zone seen clear (not cloud, shadow, terrain shadow, no data, snow or ice) and the share under snow or ice.
    The zone is the lake's zone without `exclude` (a bool grid: water that is always there, such as a river)."""
    from sartale.lakebuild import _load_outline
    from sartale.lakewater import lake_zone
    zone = lake_zone((len(y), len(x)), x, y, epsg, lake, outline_polygon=_load_outline(lake))
    if exclude is not None:
        zone = zone & ~np.asarray(exclude, bool)
    px = float(abs(x[1] - x[0]))
    clear = opt["valid"]
    if opt.get("terrain_shadow") is not None:
        clear = clear & ~np.asarray(opt["terrain_shadow"], bool)
    seen = zone & clear
    n_seen = int(seen.sum())
    water = int((opt["water"] & seen).sum())
    snow = opt.get("snow")
    return {"zone_valid_share": zone_valid_share(clear, zone),
            "snow_share": zone_valid_share(snow, zone) if snow is not None else 0.0,
            "water_share": (water / n_seen) if n_seen else 0.0,
            "water_km2": water * px ** 2 / 1e6}


def qualifies(w: dict) -> bool:
    """A scene counts for the absence check: the lake zone at least MIN_ZONE_VALID clear (snow and ice are not clear)
    and at most ABSENCE_MAX_SNOW_SHARE of it under snow or ice."""
    return w["zone_valid_share"] >= MIN_ZONE_VALID and w["snow_share"] <= ABSENCE_MAX_SNOW_SHARE


def scene_row(scene: dict, w: dict, threshold: float | None = None) -> dict:
    """One qualifying scene as the evidence records it, with the threshold it was judged by (None: the site's season
    at that date is not assessed)."""
    return {"date": scene["date"], "s2_id": scene["id"], "water_share": round(w["water_share"], 4),
            "water_km2": round(w["water_km2"], 4), "zone_valid_share": round(w["zone_valid_share"], 3),
            "snow_share": round(w["snow_share"], 4), "threshold": threshold}


def _brief(row: dict) -> dict:
    return {k: row[k] for k in ("date", "s2_id", "water_share")}


def start_state() -> dict:
    """The state of a site the register holds as having no lake now, before any scene: no lake, nothing pending."""
    return {"forming": False, "pending_scene": None, "confirmed": None}


def step(state: dict, row: dict, threshold: float) -> dict:
    """The forming state after one more qualifying scene (scenes taken oldest first).

    The state changes only on two qualifying scenes on the other side of `threshold`, at least ABSENCE_CONFIRM_DAYS
    apart, with no scene on the current side between them: "No lake now" turns into "Lake may be forming" when the
    two most recent qualifying scenes are both above it, and back when two are both below it. A single scene on the
    other side becomes `pending_scene`, which the next qualifying scene confirms (far enough apart) or clears (back on
    the current side); a scene too close to the pending one leaves it pending. `confirmed` is the pair that set the
    current state."""
    above = row["water_share"] > threshold
    if above == state["forming"]:
        return {**state, "pending_scene": None}
    pending = state["pending_scene"]
    if pending is None:
        return {**state, "pending_scene": _brief(row)}
    if (Date.fromisoformat(row["date"]) - Date.fromisoformat(pending["date"])).days >= ABSENCE_CONFIRM_DAYS:
        return {"forming": above, "pending_scene": None, "confirmed": [pending, _brief(row)]}
    return state


def absence_check(lake, today: str, prior: dict | None = None, log=print, max_scenes: int | None = None,
                  zone: dict | None = None, rule_lake=None) -> dict | None:
    """Dated evidence on whether a site with no lake now is still empty, from the Sentinel-2 scenes whose lake zone is
    clear and snow-free (`qualifies`), and the site's forming state (`step`): one scene above the site's threshold is
    only pending; two at least ABSENCE_CONFIRM_DAYS apart make "Lake may be forming". Runs all year: the lake that
    matters most can form in spring (Shisper's 2022 lake filled in March-April and burst on 7 May), and a winter
    scene counts when the zone is clear of cloud, snow and ice.

    The forming rule (`lakebuild.forming_rule`: share, seasons and excluded outline) is the register's for `lake`, or
    that of `rule_lake` (a trial lake, for a back-test). A scene in a season with no share is recorded and counts as a
    clear view, but never moves the state.

    With `prior` (the last evidence, from the same rule, zone and forming rule), the scenes after its date are tried,
    newest first, up to ABSENCE_MAX_SCENES, and every qualifying one is applied to its state, oldest first. Without
    it, the last ABSENCE_FIRST_LOOKBACK_DAYS are searched, newest first, until the newest qualifying scene and one at
    least ABSENCE_CONFIRM_DAYS older are found (or ABSENCE_FIRST_SCENES are tried), and those are applied to the
    register's state (no lake). When no scene qualifies, `prior` is kept with this run's date as `searched` (and
    `no_view_since` set once it is more than ABSENCE_STALE_DAYS old), so the site never implies a recent check.

    Returns the newest qualifying scene ({"date", "s2_id", "water_share", "water_km2", "zone_valid_share",
    "snow_share"}) with "forming", "pending_scene", "confirmed", "threshold" (the newest scene's; None when not assessed),
    "forming_rule", "checked" (the run that found the
    scene), "searched" (the last run that searched), "no_view_since", "rule", "source" and "zone" (the zone key,
    `lakebuild.absence_zone`), or None when there is no evidence at all.
    """
    from sartale.lakebuild import absence_zone, exclude_mask, forming_rule, forming_threshold
    from sartale.lakes import lake_bbox
    rule_lake = rule_lake or lake
    zone = zone if zone is not None else absence_zone(lake)
    t = Date.fromisoformat(today)
    if prior:
        start, limit = prior["date"], max_scenes or ABSENCE_MAX_SCENES
    else:
        start, limit = (t - timedelta(days=ABSENCE_FIRST_LOOKBACK_DAYS)).isoformat(), max_scenes or ABSENCE_FIRST_SCENES
    x, y, epsg = absence_grid(lake)
    exclude = exclude_mask(rule_lake, x, y, epsg)
    scenes = [_scene(f, t) for f in search_scenes(lake_bbox(lake), start, today)]
    scenes = [s for s in scenes if s["cloud"] <= ABSENCE_MAX_TILE_CLOUD and (not prior or s["date"] > prior["date"])
              and all(k in s["assets"] for k in ("green", "swir16", "scl"))]
    scenes.sort(key=lambda s: (s["date"], -s["cloud"], s["id"]), reverse=True)
    rows = []
    for scene in scenes[:limit]:
        try:
            opt = optical_on_grid(scene, x, y, epsg)
        except Exception as e:  # noqa: BLE001 - an unreadable scene is skipped, and said so
            log(f"{lake.id} absence vs {scene['id']}: unreadable ({type(e).__name__})")
            continue
        w = zone_water(lake, opt, x, y, epsg, exclude=exclude)
        ok = qualifies(w)
        log(f"{lake.id} absence vs {scene['id']} ({scene['date']}): zone seen clear "
            f"{100 * w['zone_valid_share']:.1f}%, snow/ice {100 * w['snow_share']:.2f}%, water "
            f"{100 * w['water_share']:.2f}% of the clear zone ({w['water_km2']:.4f} km2): "
            f"{'used' if ok else 'skipped (the zone is not both clear and snow-free)'}")
        if ok:
            rows.append(scene_row(scene, w, forming_threshold(rule_lake, scene["date"])))
            # A first check needs the newest scene and one far enough before it to know the state.
            if not prior and (Date.fromisoformat(rows[0]["date"]) - Date.fromisoformat(rows[-1]["date"])).days \
                    >= ABSENCE_CONFIRM_DAYS:
                break
    if not rows:
        log(f"{lake.id} absence: no clear, snow-free scene in {start}..{today}"
            + ("; the last evidence stands" if prior else "; no evidence yet"))
        if not prior:
            return None
        return {**prior, "searched": today, "no_view_since": no_view_since(prior["date"], today)}
    state = ({k: prior.get(k) for k in ("pending_scene", "confirmed")} | {"forming": bool(prior.get("forming"))}
             if prior else start_state())
    for row in sorted(rows, key=lambda r: (r["date"], r["s2_id"])):
        if row["threshold"] is not None:  # a season with no share is only a clear view
            state = step(state, row, row["threshold"])
    latest = rows[0]
    return {**latest, **state, "forming_rule": forming_rule(rule_lake), "checked": today, "searched": today,
            "no_view_since": no_view_since(latest["date"], today), "rule": ABSENCE_RULE, "source": ABSENCE_SOURCE,
            "zone": zone}
