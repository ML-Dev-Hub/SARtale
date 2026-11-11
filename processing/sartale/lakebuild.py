"""Build lakes.json and the per-lake images from the cached windows."""
import json
import warnings
from pathlib import Path

import numpy as np
from PIL import Image
from pyproj import Transformer

from sartale import config
from sartale.catalog import PROVISIONAL, STANDARD
from sartale.lakes import Lake
from sartale.lakes import DEFAULT_ZONE_KM
from sartale.lakestatus import SeriesPoint, cloud_window_looks, is_valid, lake_status, no_lake_status
from sartale.lakewater import (
    dark_mask,
    despeckle,
    lake_zone,
    outline_window_share,
    pass_water,
    screen_outliers,
    screen_passes,
    shadow_prone,
    window_stats,
)
from sartale.render import render_frame, shared_stretch
from sartale.radiometry import to_db

POINT_LABEL = "water area in the search window"
OUTLINE_LABEL = "water area in the lake outline (buffered 200 m)"
NO_LAKE_LABEL = "dark radar area in the search circle; there is no lake here now, so it is not lake area"
WATER_RGBA = (0x2b, 0x8c, 0xff, 200)
SHADOW_RGBA = (128, 128, 128, 120)
NOTES = ("Areas are water within a lake's outline (buffered 200 m) or, without one, a search circle (1 km unless "
         "the lake sets a smaller one), and underestimate lakes whose shores sit in radar shadow; images are crops "
         "on the UTM grid, north up; they are pictures, not map overlays.")
NO_LOOKS_REASON = "No valid NISAR pass yet."
OUTLINE_ROOT = Path(__file__).resolve().parents[1]  # processing/


def _nanmedian0(stack: np.ndarray) -> np.ndarray:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN pixels are legitimately NaN
        return np.nanmedian(stack, axis=0)


def _outline_feature(lake: Lake) -> dict | None:
    """The outline as a GeoJSON Feature if `lake.outline` is a readable local GeoJSON file, else None.

    A relative path is read from the processing folder (where lakes_in.json lives), wherever the command runs.
    """
    if not lake.outline:
        return None
    p = Path(lake.outline)
    if not p.is_absolute():
        p = OUTLINE_ROOT / p
    if not p.is_file():
        return None
    doc = json.loads(p.read_text(encoding="utf-8"))
    if doc.get("type") == "FeatureCollection":
        doc = doc["features"][0]
    if doc.get("type") != "Feature":
        doc = {"type": "Feature", "properties": {}, "geometry": doc}
    return doc if doc["geometry"].get("type") == "Polygon" else None


def _load_outline(lake: Lake):
    """The outline polygon if `lake.outline` is a readable local GeoJSON file, else None."""
    f = _outline_feature(lake)
    return f["geometry"] if f else None


PASSES_JSON = "passes.json"  # written by lakes-search into the cache folder


def read_listed(passes_json: Path) -> dict[str, set[tuple[str, str, str]]] | None:
    """Per lake id, the (date, track key, CRID) of every pass the last lakes-search listed. None if there is no
    passes.json. Only these passes are built: a cached window of a pass the catalogue no longer lists is ignored
    (kept on disk), so a build from a long-lived cache equals a build from a fresh one."""
    p = Path(passes_json)
    if not p.is_file():
        return None
    out: dict[str, set[tuple[str, str, str]]] = {}
    for lake_id, by_key in json.loads(p.read_text(encoding="utf-8")).get("lakes", {}).items():
        out[lake_id] = {(row["date"], f"{row['track']}{row['direction']}", row["crid"])
                        for rows in by_key.values() for row in rows}
    return out


def unlisted_windows(lake_dir: Path, listed: set[tuple[str, str, str]] | None) -> list[str]:
    """Names of the cached windows in `lake_dir` that `listed` leaves out (empty when there is no list)."""
    if listed is None or not Path(lake_dir).is_dir():
        return []
    out = []
    for f in sorted(Path(lake_dir).glob("*.npz")):
        parts = f.stem.split("_")
        if len(parts) == 3 and all(parts) and tuple(parts) not in listed:
            out.append(f.name)
    return out


def _read_cache(lake_dir: Path, limits: list[str], listed: set[tuple[str, str, str]] | None = None) -> list[dict]:
    """Every cached window `<date>_<key>_<CRID>.npz`, whatever its CRID. A file whose name does not have those three
    parts is skipped, and so is one whose (date, key, CRID) is not in `listed` (when a list is given: the passes
    the catalogue lists now). When one date and track is cached under more than one CRID (a pass reprocessed into
    a newer release), the latest CRID is used and the others are noted."""
    files: dict[tuple[str, str], dict[str, Path]] = {}
    for f in sorted(lake_dir.glob("*.npz")):
        parts = f.stem.split("_")
        if len(parts) != 3 or not all(parts):
            continue
        if listed is not None and tuple(parts) not in listed:
            continue
        date, key, crid = parts
        files.setdefault((date, key), {})[crid] = f
    passes = []
    for (date, key), by_crid in sorted(files.items()):
        crid = max(by_crid)
        for other in sorted(set(by_crid) - {crid}):
            limits.append(f"ignored {by_crid[other].name}: the same pass is cached as {crid}")
        with np.load(by_crid[crid]) as z:
            passes.append({"date": date, "key": key, "id": f"{date}_{key}", "crid": crid,
                           "hh": z["hh"], "hv": z["hv"], "x": np.asarray(z["x"], float),
                           "y": np.asarray(z["y"], float), "epsg": int(z["epsg"])})
    return passes


def read_collections(passes_json: Path) -> dict[str, str]:
    """CRID -> CMR short name, from the passes.json lakes-search wrote. Empty if the file is missing or older."""
    p = Path(passes_json)
    if not p.is_file():
        return {}
    out: dict[str, str] = {}
    for by_key in json.loads(p.read_text(encoding="utf-8")).get("lakes", {}).values():
        for rows in by_key.values():
            for row in rows:
                if row.get("crid") and row.get("collection"):
                    out.setdefault(row["crid"], row["collection"])
    return out


def _release_word(short_name: str | None) -> str | None:
    if short_name == PROVISIONAL:
        return "provisional"
    if short_name == STANDARD:
        return "standard"
    return None


def mixed_crid_limit(track: str, crids: list[str], collections: dict[str, str]) -> str:
    """The limit a lake carries when its status track mixes processing versions."""
    named = []
    for c in sorted(crids):
        word = _release_word(collections.get(c))
        named.append(f"{c} ({word})" if word else c)
    listed = ", ".join(named[:-1]) + " and " + named[-1]
    return (f"Track {track} mixes NISAR processing versions {listed}; a calibration change between them can "
            "shift areas.")


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


def screen_all(by_track: dict[str, list[dict]], manual: dict[str, str] | None = None) -> dict[str, str]:
    """Every pass exclusion of one lake, pass id -> reason, in order of precedence:
    1. too bright or dark overall (`screen_passes`, window-median HH);
    2. robust outlier in window dark share or window-median HV (`screen_outliers`, ruling R-F1),
       computed on the passes that survived step 1;
    3. the hand list `config.MANUAL_EXCLUSIONS` for passes not already excluded.
    Passes carry despeckled `hh_db`/`hv_db`.
    """
    manual = config.MANUAL_EXCLUSIONS if manual is None else manual
    excluded: dict[str, str] = {}
    for ps in by_track.values():
        excluded.update(screen_passes({p["id"]: p["hh_db"] for p in ps}))
    for ps in by_track.values():
        stats = {p["id"]: window_stats(p["hh_db"], p["hv_db"]) for p in ps if p["id"] not in excluded}
        excluded.update(screen_outliers({k: v[0] for k, v in stats.items()}, {k: v[1] for k, v in stats.items()}))
    for ps in by_track.values():
        for p in ps:
            if p["id"] in manual and p["id"] not in excluded:
                excluded[p["id"]] = manual[p["id"]]
    return excluded


def season_dark(by_track: dict[str, list[dict]], excluded: dict[str, str]) -> dict[str, np.ndarray]:
    """Dark mask of each track's season-median image (two-view rule, R2), from non-excluded passes only."""
    out = {}
    for k, ps in by_track.items():
        ok = [p for p in ps if p["id"] not in excluded]
        if ok:
            med_hh = _nanmedian0(np.stack([p["hh_db"] for p in ok]))
            med_hv = _nanmedian0(np.stack([p["hv_db"] for p in ok]))
            out[k] = dark_mask(med_hh, med_hv)[0]
    return out


def _analyse(passes: list[dict], xs, ys, limits: list[str]):
    """Despeckle, screen, and apply the two-view rule. Adds hh_db/hv_db to each pass in place.

    Returns (epsg, px, by_track, excluded, directions, shadow).
    """
    epsg = passes[0]["epsg"]
    px = float(abs(xs[1] - xs[0])) if len(xs) > 1 else 1.0
    for p in passes:
        p["hh_db"], p["hv_db"] = to_db(despeckle(p["hh"])), to_db(despeckle(p["hv"]))
    by_track: dict[str, list[dict]] = {}
    for p in passes:
        by_track.setdefault(p["key"], []).append(p)

    excluded = screen_all(by_track)
    medians_dark = season_dark(by_track, excluded)
    directions = {k: k[-1] for k in by_track}
    shadow = shadow_prone(medians_dark, directions) if medians_dark else None
    if shadow is None:
        limits.append("single viewing direction")
    return epsg, px, by_track, excluded, directions, shadow


def pictured_pass(series: list[SeriesPoint], track: str | None) -> str | None:
    """Pass id of the picture a lake shows: the status track's latest valid pass (same rule as the status:
    not excluded, has an area, observable share >= MIN_OBSERVABLE). Without a status track, the latest
    valid pass on any track; None if there is no valid pass."""
    valid = [p for p in series if is_valid(p)]
    on_track = [p for p in valid if p["track"] == track] if track else []
    pool = on_track or valid
    if not pool:
        return None
    p = max(pool, key=lambda q: (q["date"], q["track"]))
    return f"{p['date']}_{p['track']}"


def area_label(lake: Lake, has_outline: bool) -> str:
    """What a lake's area measures, in words the app shows."""
    if lake.lake_state == "no_lake":
        return NO_LAKE_LABEL
    if has_outline:
        return OUTLINE_LABEL
    r = lake.zone_radius_km
    if r == DEFAULT_ZONE_KM:
        return POINT_LABEL
    size = f"{round(r * 1000)} m" if r < 1 else f"{r:g} km"
    return f"{POINT_LABEL} ({size} circle)"


def state_limits(lake: Lake) -> list[str]:
    """The limit an unconfirmed lake carries (its status is still computed)."""
    if lake.lake_state == "unconfirmed":
        return [f"Lake not confirmed in recent imagery: {(lake.lake_state_source or '').rstrip('.')}."]
    return []


def _no_looks() -> dict:
    return {"status": "Not enough NISAR looks yet", "track": None, "latest_date": None, "looks": 0,
            "change_km2": None, "noise_km2": None, "reason": NO_LOOKS_REASON, "new_crid": None}


def _empty(entry: dict, limits: list[str], lake: Lake) -> dict:
    status = _no_looks()
    if lake.lake_state == "no_lake":
        status = no_lake_status(status, lake.lake_state_source)
    return {**entry, "status": status, "cloud_window_looks": 0, "directions": [], "limits": limits,
            "series": [], "excluded": [], "images": {"latest_hh": None, "water": None, "date": None, "track": None},
            "bounds": None}


def build_lake(lake: Lake, cache_dir: Path, out_dir: Path, collections: dict[str, str] | None = None,
               listed: set[tuple[str, str, str]] | None = None) -> dict:
    """`listed`: the (date, key, CRID) of the passes lakes-search listed for this lake; None reads every window."""
    limits: list[str] = state_limits(lake)
    feature = _outline_feature(lake)
    outline = feature["geometry"] if feature else None
    if lake.outline and outline is None:
        limits.append("outline could not be read; the point circle is used")
    entry = {
        "id": lake.id, "name": lake.name, "lon": lake.lon, "lat": lake.lat, "role": lake.role,
        "coord_source": lake.coord_source,
        "outline_source": (feature["properties"].get("source") or lake.outline) if feature else None,
        "area_label": area_label(lake, outline is not None),
        "lake_state": lake.lake_state, "lake_state_source": lake.lake_state_source,
        "downstream": lake.downstream, "downstream_source": lake.downstream_source,
    }
    lake_dir = Path(cache_dir) / lake.id
    if not lake_dir.is_dir():
        return _empty(entry, limits + ["no NISAR windows fetched yet"], lake)
    raw = _read_cache(lake_dir, limits, listed)
    passes, xs, ys = _align(raw, limits, lake) if raw else ([], None, None)
    if not passes:
        return _empty(entry, limits + ["no usable NISAR window"], lake)

    epsg, px, by_track, excluded, directions, shadow = _analyse(passes, xs, ys, limits)
    zone = lake_zone((len(ys), len(xs)), xs, ys, epsg, lake, outline_polygon=outline)
    if outline is not None:
        share = outline_window_share(xs, ys, epsg, outline)
        if share < 0.99:
            limits.append(f"the outline runs past the 6 km radar window; {round(share * 100)}% of it is inside "
                          "and only that part is counted")
    series: list[SeriesPoint] = []
    for p in sorted(passes, key=lambda q: (q["date"], q["key"])):
        w = pass_water(p["hh_db"], p["hv_db"], zone, shadow, px)
        reason = excluded.get(p["id"])
        series.append({"date": p["date"], "track": p["key"],
                       "area_km2": None if reason else w["area_km2"],
                       "observable_share": w["observable_share"], "excluded": reason, "crid": p["crid"]})

    latest_expected: dict[str, str] = {}  # R-P2: newest cached pass per track, excluded or not
    for p in passes:
        latest_expected[p["key"]] = max(latest_expected.get(p["key"], ""), p["date"])

    good = [p for p in passes if p["id"] not in excluded]
    status = lake_status(series, latest_expected)
    if status["track"]:
        track_crids = sorted({p["crid"] for p in series if p["track"] == status["track"]})
        if len(track_crids) > 1:
            limits.append(mixed_crid_limit(status["track"], track_crids, collections or {}))
    images = {"latest_hh": None, "water": None, "date": None, "track": None}
    pictured = pictured_pass(series, status["track"])
    if good and pictured:
        latest = next(p for p in good if p["id"] == pictured)
        images = {**_write_images(Path(out_dir) / "lakes" / lake.id, good, latest, zone, shadow, ys),
                  "date": latest["date"], "track": latest["key"]}
    if lake.lake_state == "no_lake":
        # No verdict, and no blue "water" layer: the dark pixels at an empty basin are not a lake.
        status = no_lake_status(status, lake.lake_state_source)
        if images["water"]:
            (Path(out_dir) / images["water"]).unlink(missing_ok=True)
            images = {**images, "water": None}
    return {**entry, "status": status,
            "cloud_window_looks": cloud_window_looks(series),
            "directions": sorted(set(directions.values())), "limits": limits, "series": series,
            "excluded": [{"pass": k, "reason": v} for k, v in sorted(excluded.items())],
            "images": images, "bounds": _bounds(xs, ys, epsg, px)}


def _track_medians(lk: dict) -> dict[str, float]:
    """Per track key: median over non-excluded passes of the per-pass zone water area."""
    by: dict[str, list[float]] = {}
    for p in lk["series"]:
        if p["excluded"] is None and p["area_km2"] is not None:
            by.setdefault(p["track"], []).append(p["area_km2"])
    return {k: float(np.median(v)) for k, v in by.items()}


def attabad_gate(doc: dict) -> dict:
    """Attabad sanity check (R-T5e): on every track both lakes have, attabad's median pass area must
    beat shisper's, and the median of the per-track ratios must be >= 2."""
    by_id = {lk["id"]: lk for lk in doc["lakes"]}
    a, s = by_id.get("attabad"), by_id.get("shisper")
    am = _track_medians(a) if a else {}
    sm = _track_medians(s) if s else {}
    tracks = sorted(set(am) & set(sm))
    ratios = {k: am[k] / max(sm[k], config.NOISE_FLOOR_KM2) for k in tracks}
    status = a["status"]["status"] if a else None
    cw = a["cloud_window_looks"] if a else 0
    median_ratio = float(np.median(list(ratios.values()))) if ratios else None
    ok = (bool(tracks) and all(am[k] > sm[k] for k in tracks) and median_ratio >= 2
          and status not in ("Not observable", "Not enough NISAR looks yet") and cw >= 3)
    return {"tracks": {k: {"attabad": am[k], "shisper": sm[k], "ratio": ratios[k]} for k in tracks},
            "median_ratio": median_ratio, "attabad_status": status,
            "attabad_cloud_window_looks": cw, "pass": ok}


def build_lakes(lakes: list[Lake], cache_dir: Path, out_dir: Path, built: str, checks: list[dict] | None = None,
                collections: dict[str, str] | None = None) -> dict:
    """`checks` are the Sentinel-2 cross-check rows from `lakes-check`, merged in as the `checks` block.
    `collections` maps CRID -> CMR short name (default: read from `cache_dir`/passes.json). Only the passes that
    `cache_dir`/passes.json lists are built; without that file every cached window is read."""
    if collections is None:
        collections = read_collections(Path(cache_dir) / PASSES_JSON)
    listed = read_listed(Path(cache_dir) / PASSES_JSON)
    built_lakes = [build_lake(lake, Path(cache_dir), Path(out_dir), collections,
                              None if listed is None else listed.get(lake.id, set())) for lake in lakes]
    crids = sorted({p["crid"] for lk in built_lakes for p in lk["series"]})
    return {
        "version": 1, "built": built, "notes": NOTES,
        "crid": ", ".join(crids),  # every processing version used, e.g. "P05023, P05036"
        "collections": sorted({collections[c] for c in crids if c in collections}),
        "cloud_window": list(config.CLOUD_WINDOW),
        "constants": {"drop_db": config.DROP_DB, "min_looks": config.MIN_LOOKS,
                      "min_observable": config.MIN_OBSERVABLE, "noise_floor_km2": config.NOISE_FLOOR_KM2,
                      "change_factor": config.CHANGE_FACTOR, "speckle_box": config.SPECKLE_BOX,
                      "bright_pass_db": config.BRIGHT_PASS_DB, "outlier_z": config.OUTLIER_Z,
                      "outlier_share_floor": config.OUTLIER_SHARE_FLOOR,
                      "outlier_hv_floor_db": config.OUTLIER_HV_FLOOR_DB},
        "lakes": built_lakes,
        "checks": list(checks or []),
    }


def radar_water_masks(lake: Lake, cache_dir: Path, pass_id: str) -> dict:
    """Radar water of one cached pass, by the same rule `build_lake` counts area with.

    `pass_id` is `<date>_<key>`. Returns {"window": dark, valid, non-shadow mask over the whole window,
    "zone_mask": the same limited to the lake zone, "zone": the zone itself (outline if the lake has a
    readable one, else the 1 km circle), "x", "y", "epsg"}. KeyError if the pass is not usable,
    ValueError if the screen excluded it.
    """
    limits: list[str] = []
    outline = _load_outline(lake)
    lake_dir = Path(cache_dir) / lake.id
    listed = read_listed(Path(cache_dir) / PASSES_JSON)
    mine = None if listed is None else listed.get(lake.id, set())
    raw = _read_cache(lake_dir, limits, mine) if lake_dir.is_dir() else []
    passes, xs, ys = _align(raw, limits, lake) if raw else ([], None, None)
    if pass_id not in {p["id"] for p in passes}:
        raise KeyError(f"{lake.id}: no usable cached pass {pass_id}")
    epsg, px, _, excluded, _, shadow = _analyse(passes, xs, ys, limits)
    if pass_id in excluded:
        raise ValueError(f"{lake.id} {pass_id} was excluded: {excluded[pass_id]}")
    p = next(q for q in passes if q["id"] == pass_id)
    dark, valid = dark_mask(p["hh_db"], p["hv_db"])
    window = dark & valid & (np.ones(dark.shape, bool) if shadow is None else ~shadow)
    zone = lake_zone((len(ys), len(xs)), xs, ys, epsg, lake, outline_polygon=outline)
    return {"window": window, "zone_mask": window & zone, "zone": zone, "x": xs, "y": ys, "epsg": epsg}


def radar_water_mask(lake: Lake, cache_dir: Path, pass_id: str, zone_only: bool = True):
    """(mask, x, y, epsg) of `radar_water_masks`: the zone mask if `zone_only`, else the window mask."""
    r = radar_water_masks(lake, cache_dir, pass_id)
    return (r["zone_mask"] if zone_only else r["window"]), r["x"], r["y"], r["epsg"]
