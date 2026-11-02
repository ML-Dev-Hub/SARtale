"""Build lakes.json and the per-lake images from the cached windows."""
import json
import warnings
from pathlib import Path

import numpy as np
from PIL import Image
from pyproj import Transformer

from sartale import config
from sartale.lakes import Lake
from sartale.lakestatus import SeriesPoint, cloud_window_looks, lake_status
from sartale.lakewater import dark_mask, lake_zone, pass_water, screen_passes, shadow_prone
from sartale.products import render_frame, shared_stretch
from sartale.radiometry import to_db

POINT_LABEL = "water area in the search window"
OUTLINE_LABEL = "water area in the lake outline (buffered 200 m)"
WATER_RGBA = (0x2b, 0x8c, 0xff, 200)
SHADOW_RGBA = (128, 128, 128, 120)
NO_LOOKS_REASON = "No valid NISAR pass yet."


def _nanmedian0(stack: np.ndarray) -> np.ndarray:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN pixels are legitimately NaN
        return np.nanmedian(stack, axis=0)


def _load_outline(lake: Lake):
    """The outline polygon if `lake.outline` is a readable local GeoJSON file, else None."""
    if not lake.outline:
        return None
    p = Path(lake.outline)
    if not p.is_file():
        return None
    doc = json.loads(p.read_text(encoding="utf-8"))
    if doc.get("type") == "FeatureCollection":
        doc = doc["features"][0]
    if doc.get("type") == "Feature":
        doc = doc["geometry"]
    return doc if doc.get("type") == "Polygon" else None


def _read_cache(lake_dir: Path, limits: list[str]) -> list[dict]:
    passes = []
    for f in sorted(lake_dir.glob("*.npz")):
        parts = f.stem.split("_")
        if len(parts) != 3:
            continue
        date, key, crid = parts
        if crid != config.CRID:
            limits.append(f"ignored {f.name}: CRID {crid} is not {config.CRID}")
            continue
        with np.load(f) as z:
            passes.append({"date": date, "key": key, "id": f"{date}_{key}",
                           "hh": z["hh"], "hv": z["hv"], "x": np.asarray(z["x"], float),
                           "y": np.asarray(z["y"], float), "epsg": int(z["epsg"])})
    return passes


def _common_axis(axes: list[np.ndarray]) -> np.ndarray:
    common = np.round(axes[0], 2)
    for a in axes[1:]:
        common = common[np.isin(common, np.round(a, 2))]
    return common


def _crop(p: dict, xs: np.ndarray, ys: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    ix = np.flatnonzero(np.isin(np.round(p["x"], 2), xs))
    iy = np.flatnonzero(np.isin(np.round(p["y"], 2), ys))
    sel = np.ix_(iy, ix)
    return p["hh"][sel], p["hv"][sel]


def _align(passes: list[dict], limits: list[str], lake: Lake):
    """Crop every pass to the x/y intersection of the usable tracks. Returns (passes, xs, ys).

    A track whose window shares no pixel coordinates with the others is dropped and noted. Tracks whose
    window holds the lake point are taken first, then those with more passes.
    """
    epsg = passes[0]["epsg"]
    lx, ly = Transformer.from_crs(4326, epsg, always_xy=True).transform(lake.lon, lake.lat)
    tracks: dict[str, list[dict]] = {}
    for p in passes:
        if p["epsg"] != epsg:
            limits.append(f"ignored {p['id']}: UTM zone differs from the rest of the lake")
            continue
        tracks.setdefault(p["key"], []).append(p)
    xs = ys = None
    kept = []
    def holds_lake(k: str) -> bool:
        ax, ay = _common_axis([p["x"] for p in tracks[k]]), _common_axis([p["y"] for p in tracks[k]])
        return len(ax) > 0 and len(ay) > 0 and ax.min() <= lx <= ax.max() and ay.min() <= ly <= ay.max()

    for k in sorted(tracks, key=lambda k: (not holds_lake(k), -len(tracks[k]), k)):
        tx = _common_axis([p["x"] for p in tracks[k]])
        ty = _common_axis([p["y"] for p in tracks[k]])
        nx = tx if xs is None else tx[np.isin(tx, xs)]
        ny = ty if ys is None else ty[np.isin(ty, ys)]
        if len(nx) == 0 or len(ny) == 0:
            limits.append(f"track {k} unusable: its window does not overlap the other tracks' windows")
            continue
        xs, ys = nx, ny
        kept.append(k)
    out = []
    for k in kept:
        for p in tracks[k]:
            hh, hv = _crop(p, xs, ys)
            out.append({**p, "hh": hh, "hv": hv})
    return out, xs, ys


def _bounds(xs, ys, epsg, px) -> list[float]:
    """WGS84 [lon_min, lat_min, lon_max, lat_max] of the common window's outer pixel edges."""
    to_ll = Transformer.from_crs(epsg, 4326, always_xy=True)
    h = px / 2
    pts = [to_ll.transform(x, y) for x in (xs.min() - h, xs.max() + h) for y in (ys.min() - h, ys.max() + h)]
    lons, lats = [p[0] for p in pts], [p[1] for p in pts]
    return [float(min(lons)), float(min(lats)), float(max(lons)), float(max(lats))]


def _north_up(a: np.ndarray, ys: np.ndarray) -> np.ndarray:
    return a if ys[0] > ys[-1] else a[::-1]


def _save_webp(arr: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.ascontiguousarray(arr), "RGBA").save(path, "WEBP", lossless=True, method=6)


def _write_images(lake_out: Path, good: list[dict], latest: dict, zone, shadow, ys) -> dict:
    stretch = shared_stretch(np.stack([p["hh_db"] for p in good]))
    grey = render_frame(latest["hh_db"], stretch)
    rgba = np.dstack([grey, grey, grey, np.where(grey > 0, 255, 0).astype(np.uint8)])
    _save_webp(_north_up(rgba, ys), lake_out / "latest_hh.webp")

    dark, valid = dark_mask(latest["hh_db"], latest["hv_db"])
    water = np.zeros(zone.shape + (4,), np.uint8)
    not_shadow = np.ones(zone.shape, bool) if shadow is None else ~shadow
    if shadow is not None:
        rows, cols = np.indices(zone.shape)
        water[shadow & (((rows + cols) % 4) < 2)] = SHADOW_RGBA  # diagonal hatching
    water[dark & valid & zone & not_shadow] = WATER_RGBA
    _save_webp(_north_up(water, ys), lake_out / "water.webp")
    rel = f"lakes/{lake_out.name}"
    return {"latest_hh": f"{rel}/latest_hh.webp", "water": f"{rel}/water.webp"}


def _no_looks() -> dict:
    return {"status": "Not enough NISAR looks yet", "track": None, "latest_date": None, "looks": 0,
            "change_km2": None, "noise_km2": None, "reason": NO_LOOKS_REASON}


def _empty(entry: dict, limits: list[str]) -> dict:
    return {**entry, "status": _no_looks(), "cloud_window_looks": 0, "directions": [], "limits": limits,
            "series": [], "excluded": [], "images": {"latest_hh": None, "water": None}, "bounds": None}


def build_lake(lake: Lake, cache_dir: Path, out_dir: Path) -> dict:
    limits: list[str] = []
    outline = _load_outline(lake)
    if lake.outline and outline is None:
        limits.append("outline could not be read; the point circle is used")
    entry = {
        "id": lake.id, "name": lake.name, "lon": lake.lon, "lat": lake.lat, "role": lake.role,
        "coord_source": lake.coord_source, "outline_source": lake.outline,
        "area_label": OUTLINE_LABEL if outline else POINT_LABEL,
        "downstream": lake.downstream, "downstream_source": lake.downstream_source,
    }
    lake_dir = Path(cache_dir) / lake.id
    if not lake_dir.is_dir():
        return _empty(entry, limits + ["no NISAR windows fetched yet"])
    raw = _read_cache(lake_dir, limits)
    passes, xs, ys = _align(raw, limits, lake) if raw else ([], None, None)
    if not passes:
        return _empty(entry, limits + ["no usable NISAR window"])

    epsg = passes[0]["epsg"]
    px = float(abs(xs[1] - xs[0])) if len(xs) > 1 else 1.0
    for p in passes:
        p["hh_db"], p["hv_db"] = to_db(p["hh"]), to_db(p["hv"])
    by_track: dict[str, list[dict]] = {}
    for p in passes:
        by_track.setdefault(p["key"], []).append(p)

    excluded: dict[str, str] = {}
    for ps in by_track.values():
        excluded.update(screen_passes({p["id"]: p["hh_db"] for p in ps}))

    # Two-view rule on each track's season medians (R2), non-excluded passes only.
    medians_dark = {}
    for k, ps in by_track.items():
        ok = [p for p in ps if p["id"] not in excluded]
        if ok:
            med_hh = _nanmedian0(np.stack([p["hh_db"] for p in ok]))
            med_hv = _nanmedian0(np.stack([p["hv_db"] for p in ok]))
            medians_dark[k] = dark_mask(med_hh, med_hv)[0]
    directions = {k: k[-1] for k in by_track}
    shadow = shadow_prone(medians_dark, directions) if medians_dark else None
    if shadow is None:
        limits.append("single viewing direction")

    zone = lake_zone((len(ys), len(xs)), xs, ys, epsg, lake, outline_polygon=outline)
    series: list[SeriesPoint] = []
    for p in sorted(passes, key=lambda q: (q["date"], q["key"])):
        w = pass_water(p["hh_db"], p["hv_db"], zone, shadow, px)
        reason = excluded.get(p["id"])
        series.append({"date": p["date"], "track": p["key"],
                       "area_km2": None if reason else w["area_km2"],
                       "observable_share": w["observable_share"], "excluded": reason})

    latest_expected: dict[str, str] = {}  # R-P2: newest cached pass per track, excluded or not
    for p in passes:
        latest_expected[p["key"]] = max(latest_expected.get(p["key"], ""), p["date"])

    good = [p for p in passes if p["id"] not in excluded]
    images = {"latest_hh": None, "water": None}
    if good:
        latest = max(good, key=lambda q: (q["date"], q["key"]))
        images = _write_images(Path(out_dir) / "lakes" / lake.id, good, latest, zone, shadow, ys)
    return {**entry, "status": lake_status(series, latest_expected),
            "cloud_window_looks": cloud_window_looks(series),
            "directions": sorted(set(directions.values())), "limits": limits, "series": series,
            "excluded": [{"pass": k, "reason": v} for k, v in sorted(excluded.items())],
            "images": images, "bounds": _bounds(xs, ys, epsg, px)}


def build_lakes(lakes: list[Lake], cache_dir: Path, out_dir: Path, built: str) -> dict:
    return {
        "version": 1, "built": built, "crid": config.CRID, "cloud_window": list(config.CLOUD_WINDOW),
        "constants": {"drop_db": config.DROP_DB, "min_looks": config.MIN_LOOKS,
                      "min_observable": config.MIN_OBSERVABLE, "noise_floor_km2": config.NOISE_FLOOR_KM2,
                      "change_factor": config.CHANGE_FACTOR},
        "lakes": [build_lake(lake, Path(cache_dir), Path(out_dir)) for lake in lakes],
    }
