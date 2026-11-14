"""Build lakes.json and the per-lake images from the cached windows."""
import hashlib
import json
import warnings
from dataclasses import replace
from pathlib import Path

import numpy as np
from PIL import Image
from pyproj import Transformer

from sartale import config
from sartale.catalog import PROVISIONAL, STANDARD
from sartale.gcov import apply_mask
from sartale.lakecheck import ABSENCE_RULE, in_season
from sartale.lakes import Lake, exclude_geometry
from sartale.lakes import DEFAULT_ZONE_KM
from sartale import demmask
from sartale.lakestatus import (
    NOT_ENOUGH,
    SeriesPoint,
    _result,
    assess,
    cloud_window_looks,
    forming_status,
    is_valid,
    lake_status,
    no_lake_status,
)
from sartale.lakewater import (
    dark_mask,
    dark_medians,
    despeckle,
    lake_zone,
    lee_filter,
    outline_mask,
    outline_window_share,
    pass_water,
    screen_medians,
    screen_outliers,
    shadow_prone,
    water_mask,
    water_reference,
    window_stats,
)
from sartale.render import render_frame, shared_stretch
from sartale.radiometry import to_db

POINT_LABEL = "water area in the search window"
OUTLINE_LABEL = "water area in the lake outline (buffered 200 m)"
NO_LAKE_LABEL = "dark radar area in the search circle. There is no lake here now, so it is not lake area"
FORMING_LABEL = ("dark radar area in the search circle. Sentinel-2 shows water where there was no lake, so a lake may "
                 "be forming. This dark area is not treated as lake area until the SARtale team reviews the site and "
                 "adds it as a measured lake")
FORMING_STATE = "lake_forming_check"  # lakes.json lake_state of a no-lake site where the absence check found water
WATER_RGBA = (0x2b, 0x8c, 0xff, 200)
NOTES = ("Areas are water within a lake's outline (buffered 200 m) or, without one, a search circle (1 km unless "
         "the lake sets a smaller one), by method D17 (Lee-filtered HH at least 3 dB below the window median); wet "
         "shore and sediment flats read as water, so a lake drawing down onto them barely changes its radar area; "
         "images are crops on the UTM grid, north up; they are pictures, not map overlays.")
# Method D17, recorded in lakes.json `method` so a published number can be traced to the rule that made it.
METHOD = {
    "id": config.METHOD_ID,
    "water": (f"valid and HH at least {config.DROP_DB:g} dB below the window-median HH, after a {config.LEE_BOX}x"
              f"{config.LEE_BOX} Lee filter (ENL {config.LEE_ENL:g}) on linear HH power; HV is not used for water"),
    "lee_box": config.LEE_BOX, "lee_enl": config.LEE_ENL, "drop_db": config.DROP_DB, "polarisation": "HH",
    "zone": "the mapped outline buffered 200 m, or a circle around the lake point; no shadow rule inside it",
    "window": (f"the cache keeps each pass cropped to the zone plus {config.WINDOW_MARGIN_M:g} m on every side, with "
               "the window statistics (medians, dark share) of its full 6 km search window, measured before the crop; "
               "areas and screens use those"),
    "window_margin_m": config.WINDOW_MARGIN_M,
    "window_statistics": ("the window-median HH leaves out radar layover and shadow from the Copernicus GLO-30 DEM "
                          f"(look azimuth {config.DEM_LOOK_AZIMUTH_DEG['A']:g} degrees ascending, "
                          f"{config.DEM_LOOK_AZIMUTH_DEG['D']:g} descending, incidence {config.DEM_INCIDENCE_DEG:g} "
                          "degrees)"),
    "dem": demmask.SOURCE, "dem_look_azimuth_deg": dict(config.DEM_LOOK_AZIMUTH_DEG),
    "dem_incidence_deg": config.DEM_INCIDENCE_DEG,
    "screens": (f"as before: window-median HH within {config.BRIGHT_PASS_DB:g} dB of its track, robust outliers "
                f"(|z| > {config.OUTLIER_Z:g}) in the window dark share (HH and HV, {config.SPECKLE_BOX}x"
                f"{config.SPECKLE_BOX} boxcar) and median HV, and the hand list"),
    "noise": (f"per track: 1.4826 x the median pass-to-pass difference of up to {config.NOISE_PASSES} earlier valid "
              f"passes, at least max({config.NOISE_FLOOR_KM2:g} km2, {config.NOISE_REL_FLOOR:.0%} of the baseline)"),
    "baseline": f"median of up to {config.BASELINE_PASSES} earlier valid passes on the same track",
    "levels": {
        "Alert: growing": (f"two valid passes in a row, on any tracks, with z >= +{config.CHANGE_FACTOR:g}; neither a "
                           "track's first pass on a processing version its baseline lacks, nor flagged frozen, nor one "
                           f"of the first {config.AFTER_OPEN_PASSES} passes per track after the lake opened"),
        "Watch": (f"one valid pass with |z| >= {config.CHANGE_FACTOR:g}, or a CUSUM over the z values (k = "
                  f"{config.CUSUM_K:g}) reaching {config.CUSUM_H:g}"),
        "Decrease noted": f"the two-pass rule with z <= -{config.CHANGE_FACTOR:g}; information only, never an Alert",
        "No change": "none of the above",
    },
    "not_measurable": (f"no level when under {config.MIN_OBSERVABLE:.0%} of the zone is observable or the lake's "
                       f"Sentinel-2 check (lakes-check) has IoU under {config.MIN_VALIDATION_IOU:g}"),
    "study": "method study of 11 Nov 2026 (38 radar-optical pairs at Attabad, Passu, Karambar and Shazore)",
}
NO_LOOKS_REASON = "No valid NISAR pass yet."
OUTLINE_ROOT = Path(__file__).resolve().parents[1]  # processing/


def _nanmedian0(stack: np.ndarray) -> np.ndarray:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN pixels are legitimately NaN
        return np.nanmedian(stack, axis=0)


def _outline_path(lake: Lake) -> Path | None:
    """The outline file of `lake` (a relative path is read from the processing folder, where lakes_in.json lives,
    wherever the command runs), or None without an outline."""
    if not lake.outline:
        return None
    p = Path(lake.outline)
    return p if p.is_absolute() else OUTLINE_ROOT / p


def _outline_feature(lake: Lake) -> dict | None:
    """The outline as a GeoJSON Feature if `lake.outline` is a readable local GeoJSON file, else None."""
    p = _outline_path(lake)
    if p is None or not p.is_file():
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
    a newer release), the latest CRID is used and the others are noted. HH and HV are read as float64 whatever the
    window stores (float16 since the crop, `remote.crop_window`). A cropped window carries the statistics of its full
    6 km window (`window_reference`) as `ref`; an uncropped one has `ref` None and the build measures them."""
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
            hh, hv = remask(z, crid)
            passes.append({"date": date, "key": key, "id": f"{date}_{key}", "crid": crid,
                           "hh": hh, "hv": hv, "x": np.asarray(z["x"], float),
                           "y": np.asarray(z["y"], float), "epsg": int(z["epsg"]), "ref": stored_reference(z),
                           "full_x": np.asarray(z["full_x"] if "full_x" in z.files else z["x"], float),
                           "full_y": np.asarray(z["full_y"] if "full_y" in z.files else z["y"], float)})
    return passes


# The statistics of a pass's full 6 km window that the build compares pixels with, stored as scalars in a cropped
# cache window (`remote.crop_window`), so the crop changes no number: the despeckled window-median HH of the bright/dark
# screen; the window medians of HH and HV the dark rule (dark share, summer core, core contrast) compares with; the
# dark share; and the Lee-filtered window-median HH D17 measures water against, with the DEM layover/shadow mask
# (`water`) and without it (`water_all`, used when the mask could not be had: `water_dem` 0).
REF_KEYS = {"screen_hh": "ref_screen_hh_db", "dark_hh": "ref_dark_hh_db", "dark_hv": "ref_dark_hv_db",
            "dark_share": "ref_dark_share", "water": "ref_water_db", "water_all": "ref_water_all_db",
            "water_dem": "ref_water_dem"}


def window_reference(hh: np.ndarray, hv: np.ndarray, xs, ys, epsg: int, direction: str, lake_dir: Path) -> dict:
    """The full-window statistics (`REF_KEYS`, as npz entries) of one pass's masked linear HH and HV on its window grid
    (`xs`, `ys` in `epsg`), measured exactly as `_analyse`, `screen_all`, `summer_cores`, `core_metrics` and
    `pass_water` measure them on an uncropped window. The DEM layover/shadow mask of the look `direction` ("A"/"D") is
    read through `demmask.stat_masks` (kept in `lake_dir`/dem/ for the full window's grid). NaN for a statistic with
    no valid pixel."""
    xs, ys = np.round(np.asarray(xs, float), 2), np.round(np.asarray(ys, float), 2)
    hh_db, hv_db = to_db(despeckle(hh)), to_db(despeckle(hv))
    hh_w = to_db(lee_filter(hh))
    w_valid = np.isfinite(hh_w) & np.isfinite(lee_filter(hv))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        screen = float(np.nanmedian(hh_db))
    dm = dark_medians(hh_db, hv_db)
    share, _ = window_stats(hh_db, hv_db)
    masks = demmask.stat_masks(lake_dir, xs, ys, epsg, {direction})
    sm = (masks or {}).get(direction)
    water, water_all = water_reference(hh_w, w_valid, sm), water_reference(hh_w, w_valid, None)
    nan = float("nan")
    vals = {"screen_hh": screen, "dark_hh": dm[0] if dm else nan, "dark_hv": dm[1] if dm else nan,
            "dark_share": share, "water": nan if water is None else water,
            "water_all": nan if water_all is None else water_all, "water_dem": 1.0 if sm is not None else 0.0}
    return {REF_KEYS[k]: np.float64(v) for k, v in vals.items()}


def stored_reference(z) -> dict | None:
    """The full-window statistics a cropped cache window stores (`window_reference`), by `REF_KEYS` name; None when the
    window has none (an uncropped window: the build measures them on its pixels)."""
    if not all(v in z.files for v in REF_KEYS.values()):
        return None
    return {k: float(z[v]) for k, v in REF_KEYS.items()}


def _dark_ref(p: dict) -> tuple[float, float] | None:
    r = p.get("ref")
    return (r["dark_hh"], r["dark_hv"]) if r else None


def water_ref_of(p: dict) -> float | None:
    """The stored full-window D17 reference of pass `p` (with the DEM mask when it was had), or None to measure it."""
    r = p.get("ref")
    if not r:
        return None
    return r["water"] if r["water_dem"] and np.isfinite(r["water"]) else r["water_all"]


def lake_stat_masks(passes: list[dict], lake_dir: Path, xs, ys, epsg: int, directions, limits: list[str] | None):
    """`demmask.stat_masks` for the passes that measure their own window statistics (no stored `ref`); None, and no
    DEM read, when every pass stores them. Notes `demmask.NO_DEM_LIMIT` in `limits` (if given) when some pass's water
    reference goes without the DEM mask."""
    masks = None
    if any(p.get("ref") is None for p in passes):
        masks = demmask.stat_masks(lake_dir, xs, ys, epsg, set(directions))
        if masks is None and limits is not None:
            limits.append(demmask.NO_DEM_LIMIT)
    if limits is not None and demmask.NO_DEM_LIMIT not in limits and any(
            p.get("ref") and not p["ref"]["water_dem"] for p in passes):
        limits.append(demmask.NO_DEM_LIMIT)
    return masks


def remask(z, crid: str) -> tuple[np.ndarray, np.ndarray]:
    """HH and HV of a cached window with the GCOV validity rule applied again from the raw mask it stores.

    Windows cached before the rule was fixed kept mask-0 samples when the clip held no subswath number; applying
    `gcov.apply_mask` again (by the pass's own CRID) makes them invalid, so the build never depends on the rule
    in force when a window was fetched."""
    hh, hv = np.asarray(z["hh"], float), np.asarray(z["hv"], float)
    if "mask" not in z.files or z["mask"].shape != hh.shape:
        return hh, hv
    mask = np.asarray(z["mask"])
    return apply_mask(hh, mask, crid), apply_mask(hv, mask, crid)


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
    return (f"Track {track} mixes NISAR processing versions {listed}. A calibration change between them can shift areas.")


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


def _write_images(lake_out: Path, good: list[dict], latest: dict, zone, ys, prefix: str = "",
                  stat_mask: np.ndarray | None = None) -> dict:
    stretch = shared_stretch(np.stack([p["hh_db"] for p in good]))
    grey = render_frame(latest["hh_db"], stretch)
    rgba = np.dstack([grey, grey, grey, np.where(grey > 0, 255, 0).astype(np.uint8)])
    _save_webp(_north_up(rgba, ys), lake_out / f"{prefix}latest_hh.webp")

    # The water the area counts (D17): no shadow rule inside the zone, so no hatching.
    water = np.zeros(zone.shape + (4,), np.uint8)
    water[water_mask(latest["hh_w"], latest["w_valid"], stat_mask, ref_db=water_ref_of(latest)) & zone] = WATER_RGBA
    _save_webp(_north_up(water, ys), lake_out / f"{prefix}water.webp")
    rel = f"lakes/{lake_out.name}"
    return {"latest_hh": f"{rel}/{prefix}latest_hh.webp", "water": f"{rel}/{prefix}water.webp"}


OPEN_PREFIX = "open_"  # the pictures of a frozen lake's last open-water pass (lakes-freeze, `pass_images`)


def pass_images(lake: Lake, cache_dir: Path, out_dir: Path, pass_id: str, prefix: str = OPEN_PREFIX) -> dict | None:
    """Write the radar picture and water layer of one pass (`<date>_<key>`), the way the build draws the pictured
    pass (same stretch over the non-excluded passes, same water rule), as `<prefix>latest_hh.webp` and
    `<prefix>water.webp` in the lake's folder. Returns their paths, or None when the pass is not cached and usable."""
    limits: list[str] = []
    lake_dir = Path(cache_dir) / lake.id
    listed = read_listed(Path(cache_dir) / PASSES_JSON)
    mine = None if listed is None else listed.get(lake.id, set())
    raw = _read_cache(lake_dir, limits, mine) if lake_dir.is_dir() else []
    passes, xs, ys = _align(raw, limits, lake) if raw else ([], None, None)
    if not passes:
        return None
    epsg, px, _, excluded, directions, _ = _analyse(passes, xs, ys, limits)
    good = [p for p in passes if p["id"] not in excluded]
    chosen = next((p for p in good if p["id"] == pass_id), None)
    if chosen is None:
        return None
    zone = lake_zone((len(ys), len(xs)), xs, ys, epsg, lake, outline_polygon=_load_outline(lake))
    masks = lake_stat_masks(passes, lake_dir, xs, ys, epsg, directions.values(), None)
    return _write_images(Path(out_dir) / "lakes" / lake.id, good, chosen, zone, ys, prefix,
                         stat_mask_of(masks, chosen["key"]))


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
        excluded.update(screen_medians({p["id"]: _screen_median(p) for p in ps}))
    for ps in by_track.values():
        stats = {p["id"]: _window_stats_of(p) for p in ps if p["id"] not in excluded}
        excluded.update(screen_outliers({k: v[0] for k, v in stats.items()}, {k: v[1] for k, v in stats.items()}))
    for ps in by_track.values():
        for p in ps:
            if p["id"] in manual and p["id"] not in excluded:
                excluded[p["id"]] = manual[p["id"]]
    return excluded


def _screen_median(p: dict) -> float:
    """The despeckled window-median HH of the bright/dark screen: stored for a cropped window, else measured."""
    if p.get("ref"):
        return p["ref"]["screen_hh"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # a window with no valid pixel has a NaN median
        return float(np.nanmedian(p["hh_db"]))


def _window_stats_of(p: dict) -> tuple[float, float]:
    """`window_stats` (dark share, window-median HV): stored for a cropped window, else measured."""
    if p.get("ref"):
        return p["ref"]["dark_share"], p["ref"]["dark_hv"]
    return window_stats(p["hh_db"], p["hv_db"])


def season_dark(by_track: dict[str, list[dict]], excluded: dict[str, str]) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """(dark, valid) masks of each track's season-median image (two-view rule, R2), from non-excluded passes only.
    `valid` is kept so that a pixel a track never measured is not read as "not dark" there."""
    out = {}
    for k, ps in by_track.items():
        ok = [p for p in ps if p["id"] not in excluded]
        if ok:
            med_hh = _nanmedian0(np.stack([p["hh_db"] for p in ok]))
            med_hv = _nanmedian0(np.stack([p["hv_db"] for p in ok]))
            out[k] = dark_mask(med_hh, med_hv, ref=_season_ref(ok))
    return out


def _season_ref(ok: list[dict]) -> tuple[float, float] | None:
    """The window medians the season-median image of a track is compared with when its windows are cropped: the median,
    over the track's passes, of each pass's stored full-window medians (the full-window median of the median image
    itself cannot be had from cropped windows). None, to measure them on the image, while any pass is uncropped."""
    refs = [_dark_ref(p) for p in ok]
    if any(r is None for r in refs):
        return None
    hh = [r[0] for r in refs if np.isfinite(r[0])]
    hv = [r[1] for r in refs if np.isfinite(r[1])]
    if not hh or not hv:
        return None
    return float(np.median(hh)), float(np.median(hv))


def stat_mask_of(masks: dict[str, np.ndarray] | None, key: str) -> np.ndarray | None:
    """The layover/shadow mask (`demmask.stat_masks`) of a pass on track `key` ("156A": the ascending one), or None."""
    return (masks or {}).get(key[-1])


def _analyse(passes: list[dict], xs, ys, limits: list[str]):
    """Despeckle, screen, and apply the two-view rule. Adds to each pass in place: hh_db/hv_db (3x3 boxcar, for the
    screens, the pictures and the freeze check's core), and hh_w/w_valid (D17: Lee-filtered HH in dB, and the pixels
    valid after the Lee filter in both HH and HV), from which water is measured.

    Returns (epsg, px, by_track, excluded, directions, shadow).
    """
    epsg = passes[0]["epsg"]
    px = float(abs(xs[1] - xs[0])) if len(xs) > 1 else 1.0
    for p in passes:
        p["hh_db"], p["hv_db"] = to_db(despeckle(p["hh"])), to_db(despeckle(p["hv"]))
        p["hh_w"] = to_db(lee_filter(p["hh"]))
        p["w_valid"] = np.isfinite(p["hh_w"]) & np.isfinite(lee_filter(p["hv"]))
    by_track: dict[str, list[dict]] = {}
    for p in passes:
        by_track.setdefault(p["key"], []).append(p)

    excluded = screen_all(by_track)
    medians_dark = season_dark(by_track, excluded)
    directions = {k: k[-1] for k in by_track}
    shadow = (shadow_prone({k: v[0] for k, v in medians_dark.items()}, directions,
                           {k: v[1] for k, v in medians_dark.items()}) if medians_dark else None)
    if shadow is None:
        limits.append("single viewing direction")
    return epsg, px, by_track, excluded, directions, shadow


def summer_cores(by_track: dict[str, list[dict]], excluded: dict[str, str], zone: np.ndarray,
                 shadow: np.ndarray | None, frozen: set[str] | frozenset = frozenset()) -> dict[str, tuple[np.ndarray, int]]:
    """Per track: (the lake core, the number of open-water-season passes it comes from). The core is the zone pixels,
    not shadow-prone, that were dark in at least half of the track's non-excluded passes in the open-water season
    (config.OPEN_WATER_SEASON), leaving out the passes in `frozen` (ids of passes the last freeze check flagged: a
    late ice-out pass is not open water). A track without such a pass has no core."""
    not_shadow = np.ones(zone.shape, bool) if shadow is None else ~shadow
    out = {}
    for k, ps in by_track.items():
        summer = [p for p in ps if p["id"] not in excluded and p["id"] not in frozen and in_season(p["date"])]
        if summer:
            frac = np.mean([dark_mask(p["hh_db"], p["hv_db"], ref=_dark_ref(p))[0] for p in summer], axis=0)
            out[k] = (zone & not_shadow & (frac >= 0.5), len(summer))
    return out


def core_metrics(hh_db: np.ndarray, hv_db: np.ndarray, core: np.ndarray,
                 ref: tuple[float, float] | None = None) -> dict | None:
    """The lake core of one pass against its window: core median minus window median of the valid pixels, in dB, for
    HH and HV (a calibration change moves both, so it cancels), and the share of the core's valid pixels that are
    dark. `ref`: the full-window medians a cropped window stores. None when the core has no valid pixel."""
    dark, valid = dark_mask(hh_db, hv_db, ref=ref)
    c = core & valid
    if not c.any():
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        win_hh, win_hv = ref if ref is not None else (np.median(hh_db[valid]), np.median(hv_db[valid]))
        hh = float(np.median(hh_db[c]) - win_hh)
        hv = float(np.median(hv_db[c]) - win_hv)
    return {"core_contrast_hh_db": round(hh, 3), "core_contrast_hv_db": round(hv, 3),
            "core_dark_share": round(float((dark & c).sum() / c.sum()), 3)}


def summer_reference(series: list[dict], core_px: dict[str, int]) -> dict[str, dict]:
    """Per track (`core_px`: the track's core size in pixels), the summer level the radar break-up test compares a pass
    with: the medians, over the track's non-excluded open-water-season passes not flagged `frozen`, of the core
    contrast (HH, HV) and dark share; `assessed` is False with fewer than config.SUMMER_MIN_PASSES such passes or an
    empty core (the radar test is then not run there). lakes-freeze computes it again once it has flagged the passes."""
    out = {}
    for k, px in sorted(core_px.items()):
        rows = [p for p in series if p["track"] == k and p["excluded"] is None and in_season(p["date"])
                and not p.get("frozen") and "core_dark_share" in p]
        n = len(rows)
        ref = {"passes": n, "core_px": int(px), "assessed": n >= config.SUMMER_MIN_PASSES and int(px) > 0}
        if rows:
            ref.update({key: round(float(np.median([p[key] for p in rows])), 3)
                        for key in ("core_contrast_hh_db", "core_contrast_hv_db", "core_dark_share")})
        out[k] = ref
    return out


def pictured_pass(series: list[SeriesPoint], track: str | None) -> str | None:
    """Pass id of the picture a lake shows: the status track's latest valid pass (same rule as the status:
    not excluded, has an area, observable share >= MIN_OBSERVABLE). Without a status track, the latest
    valid pass on any track; None if there is no valid pass."""
    # A pass flagged frozen is still the newest look at the lake: the picture shows it (its water layer is hidden).
    valid = [p for p in series if is_valid({**p, "frozen": False})]
    on_track = [p for p in valid if p["track"] == track] if track else []
    pool = on_track or valid
    if not pool:
        return None
    p = max(pool, key=lambda q: (q["date"], q["track"]))
    return f"{p['date']}_{p['track']}"


def forming_share(lake: Lake) -> float | None:
    """The water share of the zone above which a no-lake site may be forming a lake; None for other sites."""
    if lake.lake_state != "no_lake":
        return None
    return lake.forming_share if lake.forming_share is not None else config.FORMING_WATER_SHARE


def forming_threshold(lake: Lake, iso_date: str) -> float | None:
    """The water share above which a scene of `iso_date` counts as forming at a no-lake site: the share of the season
    the date falls in (None: that season is not assessed), else the site's `forming_share`."""
    md = iso_date[5:10]
    for s in lake.forming_seasons:
        inside = s.start <= md <= s.end if s.start <= s.end else md >= s.start or md <= s.end
        if inside:
            return s.share
    return forming_share(lake)


def forming_rule(lake: Lake) -> dict:
    """What decides a site's forming state besides the scenes: the default share, the seasons, and the digest of the
    outline left out of the zone. The evidence stores it and is carried only while it is the same."""
    return {"share": forming_share(lake),
            "seasons": [{"start": s.start, "end": s.end, "share": s.share} for s in lake.forming_seasons],
            "exclude": outline_digest(exclude_geometry(lake.id, lake.forming_exclude)) if lake.forming_exclude else None}


def exclude_mask(lake: Lake, x, y, epsg) -> np.ndarray | None:
    """The `forming_exclude` outline on the grid (True inside it), or None when the site has none. A file that is
    missing, unreadable or not a polygon raises (`lakes.exclude_geometry`)."""
    if not lake.forming_exclude:
        return None
    geometry = exclude_geometry(lake.id, lake.forming_exclude)
    polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    mask = np.zeros((len(y), len(x)), bool)
    for coords in polygons:
        mask |= outline_mask((len(y), len(x)), x, y, epsg, {"type": "Polygon", "coordinates": coords})
    return mask


def is_forming(absence: dict | None) -> bool:
    """True when the absence check says a lake may be forming: its `forming` state, which two qualifying scenes above
    the site's threshold set (`lakecheck.step`). Evidence without a state (older builds, hand-made rows) falls back
    to its one scene: water on more than config.FORMING_WATER_SHARE of the lake zone."""
    if not absence:
        return False
    if "forming" in absence:
        return bool(absence["forming"])
    return float(absence.get("water_share") or 0.0) > config.FORMING_WATER_SHARE


def apply_absence(entry: dict, absence: dict | None) -> dict:
    """A built lakes.json entry of a site the register holds as "no lake now", with its absence evidence applied:
    `absence_checked` set, and the state, status and area label of "no lake now" or, when Sentinel-2 found water,
    "lake may be forming" (FORMING_STATE). Other entries are returned unchanged. The radar water layer is not
    restored here; the next lakes-build draws it."""
    if entry.get("lake_state") not in ("no_lake", FORMING_STATE):
        return entry
    st = entry["status"]
    if is_forming(absence):
        return {**entry, "lake_state": FORMING_STATE, "absence_checked": absence, "area_label": FORMING_LABEL,
                "status": forming_status(st, absence)}
    return {**entry, "lake_state": "no_lake", "absence_checked": absence, "area_label": NO_LAKE_LABEL,
            "status": no_lake_status(st, entry.get("lake_state_source"), absence)}


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
    return _result(NOT_ENOUGH, reason=NO_LOOKS_REASON)


def _empty(entry: dict, limits: list[str], lake: Lake, absence: dict | None = None) -> dict:
    out = {**entry, "status": _no_looks(), "validation": entry.get("validation"), "cloud_window_looks": 0,
           "directions": [], "limits": limits,
           "series": [], "excluded": [], "images": {"latest_hh": None, "water": None, "date": None, "track": None},
           "bounds": None, "summer_ref": {}}
    return apply_absence(out, absence)


def validation_of(check: dict | None) -> dict | None:
    """The part of a lakes-check row the level needs (`lakestatus.assess`): its IoU and which pair it came from. None
    for a row without an IoU (a note: no clear scene, no open-water-season pair)."""
    if not check or not isinstance(check.get("iou"), (int, float)):
        return None
    return {"iou": round(float(check["iou"]), 4), "nisar_date": check.get("nisar_date"),
            "nisar_track": check.get("nisar_track"), "s2_date": check.get("s2_date"), "s2_id": check.get("s2_id")}


def check_key(lake: Lake) -> dict:
    """What a Sentinel-2 check of a lake was made for, stored with it as `key`: the water method (config.METHOD_ID), the
    zone (`absence_zone`: the register point, and the circle's radius or the outline file's SHA-256) and the margin the
    cached windows are cropped with (config.WINDOW_MARGIN_M: the radar water a check compares is read from the cropped
    float16 windows). A check made for another method, zone, point or margin is stale."""
    return {"method": config.METHOD_ID, "zone": absence_zone(lake), "window_margin_m": config.WINDOW_MARGIN_M}


def is_current(row: dict | None, lake: Lake) -> bool:
    """True for a check row of `lake` made for its current key with an IoU (a usable check)."""
    return (bool(row) and row.get("lake") == lake.id and row.get("key") == check_key(lake)
            and isinstance(row.get("iou"), (int, float)))


def pick_check(lake: Lake, *sources: list[dict] | None) -> dict | None:
    """The lake's check row: the first current one (`is_current`) in `sources` (lake_checks.json, then the published
    lakes.json `checks`), else the first row of the lake at all (a note, a failure or a stale check, which says why
    the lake is not validated), else None."""
    rows = [r for src in sources for r in (src or []) if isinstance(r, dict) and r.get("lake") == lake.id]
    return next((r for r in rows if is_current(r, lake)), rows[0] if rows else None)


def validation_for(lake: Lake, row: dict | None) -> dict | None:
    """The `validation` of a lake (`lakestatus.assess`): the current check's IoU, or `iou` None with why there is none
    (no check yet, a check for an older method, zone or point, a note, a failure). None for a site with no lake now."""
    if lake.lake_state == "no_lake":
        return None
    if is_current(row, lake):
        return validation_of(row)
    if not row:
        why = "it has no Sentinel-2 check yet"
    elif row.get("key") != check_key(lake):
        why = "its Sentinel-2 check was made for an older water method, zone or lake point"
    elif row.get("failed"):
        why = f"its last Sentinel-2 check could not be made ({row.get('note', 'failed')})"
    else:
        why = f"its last Sentinel-2 check found no usable pair ({row.get('note', 'no measurement')})"
    return {"iou": None, "why": why}


def build_lake(lake: Lake, cache_dir: Path, out_dir: Path, collections: dict[str, str] | None = None,
               listed: set[tuple[str, str, str]] | None = None, absence: dict | None = None,
               prior: dict | None = None, check: dict | None = None) -> dict:
    """`listed`: the (date, key, CRID) of the passes lakes-search listed for this lake; None reads every window.
    `check`: the lake's `validation` (`validation_for`): without a current Sentinel-2 check, or with one under IoU 0.4,
    the lake gets no level. None leaves the check out (no level depends on it).
    `absence`: the last Sentinel-2 absence check of a site with no lake now (`lakecheck.absence_check`).
    `prior`: the lake's last freeze check ({"freeze": the freeze object, "flags": {(date, track): frozen}}, from
    `carried_freeze`): the passes it flagged keep their flag and stay out of the summer core and level, and the freeze
    object is carried for lakes-freeze, which keeps it when NASA POWER cannot be read this time."""
    limits: list[str] = state_limits(lake) + list(lake.limits)
    feature = _outline_feature(lake)
    outline = feature["geometry"] if feature else None
    if lake.outline and outline is None:
        limits.append("outline could not be read. The point circle is used")
    entry = {
        "id": lake.id, "name": lake.name, "lon": lake.lon, "lat": lake.lat, "role": lake.role,
        "coord_source": lake.coord_source,
        "outline_source": (feature["properties"].get("source") or lake.outline) if feature else None,
        "area_label": area_label(lake, outline is not None),
        "zone_radius_km": None if outline is not None else lake.zone_radius_km,
        "forming_share": forming_share(lake), "forming_share_source": lake.forming_share_source,
        "lake_state": lake.lake_state, "lake_state_source": lake.lake_state_source,
        "downstream": lake.downstream, "downstream_source": lake.downstream_source,
        "elevation_m": lake.elevation_m, "elevation_source": lake.elevation_source,
        "validation": check if lake.lake_state != "no_lake" else None,
    }
    lake_dir = Path(cache_dir) / lake.id
    if not lake_dir.is_dir():
        return _empty(entry, limits + ["no NISAR windows fetched yet"], lake, absence)
    raw = _read_cache(lake_dir, limits, listed)
    passes, xs, ys = _align(raw, limits, lake) if raw else ([], None, None)
    if not passes:
        return _empty(entry, limits + ["no usable NISAR window"], lake, absence)

    epsg, px, by_track, excluded, directions, shadow = _analyse(passes, xs, ys, limits)
    zone = lake_zone((len(ys), len(xs)), xs, ys, epsg, lake, outline_polygon=outline)
    if outline is not None:
        share = outline_window_share(xs, ys, epsg, outline)
        if share < 0.99:
            limits.append(f"the outline runs past the 6 km radar window, and {round(share * 100)}% of it is inside, "
                          "so only that part is counted")
    flags = (prior or {}).get("flags") or {}
    frozen_ids = {f"{d}_{k}" for (d, k), v in flags.items() if v}
    cores = summer_cores(by_track, excluded, zone, shadow, frozen_ids)
    masks = lake_stat_masks(passes, lake_dir, xs, ys, epsg, directions.values(), limits)
    series: list[SeriesPoint] = []
    for p in sorted(passes, key=lambda q: (q["date"], q["key"])):
        w = pass_water(p["hh_w"], p["w_valid"], zone, px, stat_mask_of(masks, p["key"]), ref_db=water_ref_of(p))
        reason = excluded.get(p["id"])
        point = {"date": p["date"], "track": p["key"], "area_km2": None if reason else w["area_km2"],
                 "observable_share": w["observable_share"], "excluded": reason, "crid": p["crid"]}
        if reason:
            # What the left-out pass read, so the chart can mark it; never used by the status (area_km2 is null).
            point["diagnostic_km2"] = w["area_km2"] if w["valid"] else None
        if p["key"] in cores:
            # The lake core against its window, for the freeze check's radar break-up test (lakes-freeze).
            point.update(core_metrics(p["hh_db"], p["hv_db"], cores[p["key"]][0], ref=_dark_ref(p)) or {})
        if p["id"] in frozen_ids and lake.lake_state == "lake":
            point["frozen"] = True  # the last freeze check's flag; lakes-freeze sets it again
        series.append(point)

    latest_expected: dict[str, str] = {}  # R-P2: newest cached pass per track, excluded or not (frozen ones aside)
    for p in passes:
        if p["id"] not in frozen_ids or lake.lake_state != "lake":
            latest_expected[p["key"]] = max(latest_expected.get(p["key"], ""), p["date"])

    good = [p for p in passes if p["id"] not in excluded]
    if lake.lake_state == "no_lake":
        status = lake_status(series, latest_expected)  # only its track, date and looks are kept (apply_absence)
    else:
        status, series = assess(series, latest_expected, entry["validation"], lake.name)
    if status["track"]:
        track_crids = sorted({p["crid"] for p in series if p["track"] == status["track"]})
        if len(track_crids) > 1:
            limits.append(mixed_crid_limit(status["track"], track_crids, collections or {}))
    images = {"latest_hh": None, "water": None, "date": None, "track": None}
    pictured = pictured_pass(series, status["track"])
    if good and pictured:
        latest = next(p for p in good if p["id"] == pictured)
        images = {**_write_images(Path(out_dir) / "lakes" / lake.id, good, latest, zone, ys,
                                  stat_mask=stat_mask_of(masks, latest["key"])),
                  "date": latest["date"], "track": latest["key"]}
    if lake.lake_state == "no_lake":
        # No verdict, and no blue "water" layer: the dark pixels at an empty basin are not a lake. Where Sentinel-2
        # has since found water (a lake may be forming), the layer stays once the pictured pass is no older than
        # that scene.
        keep = is_forming(absence) and images["date"] is not None and images["date"] >= absence["date"]
        if images["water"] and not keep:
            (Path(out_dir) / images["water"]).unlink(missing_ok=True)
            images = {**images, "water": None}
    out = {**entry, "status": status,
           "cloud_window_looks": cloud_window_looks(series),
           "directions": sorted(set(directions.values())), "limits": limits, "series": series,
           "excluded": [{"pass": k, "reason": v} for k, v in sorted(excluded.items())],
           "images": images, "bounds": _bounds(xs, ys, epsg, px),
           "summer_ref": summer_reference(series, {k: int(c.sum()) for k, (c, _) in cores.items()})}
    if lake.lake_state == "lake" and (prior or {}).get("freeze"):
        out["freeze"] = prior["freeze"]
    return apply_absence(out, absence)


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


def _canonical(v):
    """Coordinates rounded to 9 decimals (well under a millimetre), so the same outline always serialises the same."""
    if isinstance(v, float):
        return round(v, 9)
    if isinstance(v, list):
        return [_canonical(x) for x in v]
    if isinstance(v, dict):
        return {k: _canonical(x) for k, x in v.items()}
    return v


def outline_digest(geometry: dict) -> str:
    """SHA-256 of an outline's geometry in a canonical form (parsed GeoJSON, keys sorted, no spaces, coordinates
    rounded to 9 decimals): the same outline gives the same key whatever the file's line endings, spacing or property
    order, on a Windows or a Linux checkout."""
    text = json.dumps(_canonical(geometry), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def absence_zone(lake: Lake) -> dict:
    """The key of the zone an absence check measures: the lake point with the circle's radius, or with the outline
    (its path in the register and `outline_digest` of its geometry) when the lake has a readable outline, as `build_lake`
    uses it. The evidence stores it, and is carried only while the lake's key is the same."""
    key = {"lon": lake.lon, "lat": lake.lat}
    feature = _outline_feature(lake)
    if feature is not None:
        return {**key, "outline": lake.outline, "outline_sha256": outline_digest(feature["geometry"])}
    return {**key, "radius_km": lake.zone_radius_km}


def carried_absence(previous: dict | None, lake: Lake) -> dict | None:
    """The last absence check of `lake` in a previously published lakes.json, if it was made for the same zone
    (`absence_zone`: point, and radius or outline file) under the current rule. A moved site, a new radius or a
    changed outline starts again with no evidence, and so does evidence made under another rule (`rule`, e.g. from
    before snow, ice and cloud edges stopped counting as a clear view) or for another forming rule (share, seasons, excluded outline), since its
    forming state was worked out with them."""
    if lake.lake_state != "no_lake" or not previous:
        return None
    old = next((lk for lk in previous.get("lakes", []) if lk.get("id") == lake.id), None)
    ev = old.get("absence_checked") if old else None
    if not isinstance(ev, dict) or ev.get("rule") != ABSENCE_RULE:
        return None
    if ev.get("zone") != absence_zone(lake) or ev.get("forming_rule") != forming_rule(lake):
        return None
    return ev


def carried_freeze(previous: dict | None, lake: Lake) -> dict | None:
    """The lake's last freeze check from a previously published lakes.json: {"freeze": its freeze object, "flags":
    {(date, track): frozen}}, or None (no previous file, no entry, or a site that is not a lake)."""
    if lake.lake_state != "lake" or not previous:
        return None
    old = next((lk for lk in previous.get("lakes", []) if lk.get("id") == lake.id), None)
    if not old or not isinstance(old.get("freeze"), dict):
        return None
    flags = {(p["date"], p["track"]): bool(p.get("frozen")) for p in old.get("series", []) if "frozen" in p}
    return {"freeze": old["freeze"], "flags": flags}


def build_lakes(lakes: list[Lake], cache_dir: Path, out_dir: Path, built: str, checks: list[dict] | None = None,
                collections: dict[str, str] | None = None, previous: dict | None = None) -> dict:
    """`checks` are the Sentinel-2 cross-check rows from `lakes-check`, merged in as the `checks` block.
    `collections` maps CRID -> CMR short name (default: read from `cache_dir`/passes.json). With `checks` (a list, maybe
    empty) each lake needs a current check (`check_key`) for a level; `checks` None leaves the check out. Only the passes that
    `cache_dir`/passes.json lists are built; without that file every cached window is read. `previous` is the
    lakes.json this build replaces: each no-lake site keeps its last Sentinel-2 absence check from it."""
    if collections is None:
        collections = read_collections(Path(cache_dir) / PASSES_JSON)
    listed = read_listed(Path(cache_dir) / PASSES_JSON)
    # With `checks` given (the CLI always gives a list), a lake gets a level only with a current Sentinel-2 check, from
    # lake_checks.json or carried from the published lakes.json (a refresh's lakes-check writes only the latter).
    # Without, no level depends on a check.
    picked = {lake.id: pick_check(lake, checks, (previous or {}).get("checks")) for lake in lakes} \
        if checks is not None else {}
    built_lakes = [build_lake(lake, Path(cache_dir), Path(out_dir), collections,
                              None if listed is None else listed.get(lake.id, set()),
                              carried_absence(previous, lake), carried_freeze(previous, lake),
                              validation_for(lake, picked[lake.id]) if checks is not None else None)
                   for lake in lakes]
    out_checks = [r for lake in lakes for r in [picked.get(lake.id)] if r and (is_current(r, lake) or (
        r.get("key") == check_key(lake)))] if checks is not None else []
    crids = sorted({p["crid"] for lk in built_lakes for p in lk["series"]})
    return {
        "version": 1, "built": built, "notes": NOTES, "method": METHOD,
        "crid": ", ".join(crids),  # every processing version used, e.g. "P05023, P05036"
        "collections": sorted({collections[c] for c in crids if c in collections}),
        "cloud_window": list(config.CLOUD_WINDOW),
        "constants": {"drop_db": config.DROP_DB, "min_looks": config.MIN_LOOKS,
                      "min_observable": config.MIN_OBSERVABLE, "noise_floor_km2": config.NOISE_FLOOR_KM2,
                      "change_factor": config.CHANGE_FACTOR, "speckle_box": config.SPECKLE_BOX,
                      "lee_box": config.LEE_BOX, "lee_enl": config.LEE_ENL,
                      "baseline_passes": config.BASELINE_PASSES, "noise_passes": config.NOISE_PASSES,
                      "noise_rel_floor": config.NOISE_REL_FLOOR, "cusum_k": config.CUSUM_K,
                      "cusum_h": config.CUSUM_H, "after_open_passes": config.AFTER_OPEN_PASSES,
                      "min_validation_iou": config.MIN_VALIDATION_IOU,
                      "bright_pass_db": config.BRIGHT_PASS_DB, "outlier_z": config.OUTLIER_Z,
                      "outlier_share_floor": config.OUTLIER_SHARE_FLOOR,
                      "outlier_hv_floor_db": config.OUTLIER_HV_FLOOR_DB,
                      "lapse_c_per_km": config.LAPSE_C_PER_KM, "freeze_cold_run_days": config.FREEZE_COLD_RUN_DAYS,
                      "freeze_fdd": config.FREEZE_FDD, "breakup_warm_run_days": config.BREAKUP_WARM_RUN_DAYS,
                      "thaw_warm_run_days": config.THAW_WARM_RUN_DAYS,
                      "breakup_contrast_db": config.BREAKUP_CONTRAST_DB,
                      "breakup_dark_drop": config.BREAKUP_DARK_DROP,
                      "s2_frozen_snow_share": config.S2_FROZEN_SNOW_SHARE,
                      "s2_open_water_share": config.S2_OPEN_WATER_SHARE,
                      "s2_freeze_days": config.S2_FREEZE_DAYS, "s2_freeze_clear": config.S2_FREEZE_CLEAR,
                      "s2_target_clear": config.S2_TARGET_CLEAR,
                      "power_stale_days": config.POWER_STALE_DAYS},
        "lakes": built_lakes,
        "checks": out_checks,
    }


def radar_water_context(lake: Lake, cache_dir: Path):
    """A function pass_id -> `radar_water_masks` of that pass, which reads, aligns and analyses the lake's cached
    windows once (lakes-check asks for several passes of one lake: doing that per pass made it take minutes)."""
    limits: list[str] = []
    outline = _load_outline(lake)
    lake_dir = Path(cache_dir) / lake.id
    listed = read_listed(Path(cache_dir) / PASSES_JSON)
    mine = None if listed is None else listed.get(lake.id, set())
    raw = _read_cache(lake_dir, limits, mine) if lake_dir.is_dir() else []
    passes, xs, ys = _align(raw, limits, lake) if raw else ([], None, None)
    state: dict = {}

    def masks_for(pass_id: str) -> dict:
        if pass_id not in {p["id"] for p in passes}:
            raise KeyError(f"{lake.id}: no usable cached pass {pass_id}")
        if not state:
            epsg, _, _, excluded, directions, _ = _analyse(passes, xs, ys, limits)
            state.update(epsg=epsg, excluded=excluded,
                         masks=lake_stat_masks(passes, lake_dir, xs, ys, epsg, directions.values(), None),
                         zone=lake_zone((len(ys), len(xs)), xs, ys, epsg, lake, outline_polygon=outline))
        if pass_id in state["excluded"]:
            raise ValueError(f"{lake.id} {pass_id} was excluded: {state['excluded'][pass_id]}")
        p = next(q for q in passes if q["id"] == pass_id)
        window = water_mask(p["hh_w"], p["w_valid"], stat_mask_of(state["masks"], p["key"]), ref_db=water_ref_of(p))
        zone = state["zone"]
        return {"window": window, "zone_mask": window & zone, "zone": zone, "x": xs, "y": ys, "epsg": state["epsg"],
                "full_x": _common_axis([q["full_x"] for q in passes]),
                "full_y": _common_axis([q["full_y"] for q in passes])}

    return masks_for


def radar_water_masks(lake: Lake, cache_dir: Path, pass_id: str) -> dict:
    """Radar water of one cached pass, by the same rule `build_lake` counts area with.

    `pass_id` is `<date>_<key>`. Returns {"window": D17 water over the whole (cached) window, "zone_mask": the same
    limited to the lake zone, "zone": the zone itself (outline if the lake has a readable one, else the 1 km circle),
    "x", "y", "epsg", and "full_x", "full_y": the axes of the full 6 km window the cached one was cropped from}. KeyError if the pass is not usable, ValueError if the screen excluded it.
    """
    return radar_water_context(lake, cache_dir)(pass_id)


def freeze_masks(lake: Lake, cache_dir: Path, frozen: set[str] | frozenset = frozenset()) -> dict | None:
    """The masks the freeze check's Sentinel-2 look uses, on the lake's radar window grid: the lake zone (outline
    buffered 200 m, or the circle; the clear gate and the snow/ice share are measured over it) and where open water is
    looked for: the outline itself, unbuffered, for a lake with an outline, else the summer radar core (zone pixels,
    not shadow-prone, dark in at least half of a track's open-water-season passes, all tracks together). When that is
    empty, the zone. Returns {"zone", "target", "target_kind", "x", "y", "epsg"}, or None without a usable cached
    window."""
    limits: list[str] = []
    lake_dir = Path(cache_dir) / lake.id
    listed = read_listed(Path(cache_dir) / PASSES_JSON)
    mine = None if listed is None else listed.get(lake.id, set())
    raw = _read_cache(lake_dir, limits, mine) if lake_dir.is_dir() else []
    passes, xs, ys = _align(raw, limits, lake) if raw else ([], None, None)
    if not passes:
        return None
    epsg, px, by_track, excluded, _, shadow = _analyse(passes, xs, ys, limits)
    outline = _load_outline(lake)
    shape = (len(ys), len(xs))
    zone = lake_zone(shape, xs, ys, epsg, lake, outline_polygon=outline)
    if outline is not None:
        target, kind = outline_mask(shape, xs, ys, epsg, outline) & zone, "lake outline"
    else:
        target = np.zeros(shape, bool)
        for core, _ in summer_cores(by_track, excluded, zone, shadow, frozen).values():
            target |= core
        kind = "summer radar water core"
    if not target.any():
        target, kind = zone, "lake zone"
    return {"zone": zone, "target": target, "target_kind": kind, "x": xs, "y": ys, "epsg": epsg}


def radar_water_mask(lake: Lake, cache_dir: Path, pass_id: str, zone_only: bool = True):
    """(mask, x, y, epsg) of `radar_water_masks`: the zone mask if `zone_only`, else the window mask."""
    r = radar_water_masks(lake, cache_dir, pass_id)
    return (r["zone_mask"] if zone_only else r["window"]), r["x"], r["y"], r["epsg"]
