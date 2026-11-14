"""Back-test of the forming check at a site with no lake now: every Sentinel-2 scene of a period, oldest first, through
the absence check's rule (`lakecheck.qualifies`, `lakecheck.step`) with the site's forming rule or a trial one. Each
scene is read once. Used to choose a site's forming settings (season, excluded river) before they go in the register.
"""
from dataclasses import replace
from datetime import date as Date
from pathlib import Path

import numpy as np
from rasterio.crs import CRS
from rasterio.transform import Affine

from sartale import lakecheck

PERSISTENT_SHARE = 0.6  # a pixel is lasting water when it is water in at least this share of the scenes


def trial_lake(lake, rule: dict | None):
    """The lake with the forming share and seasons of `rule` ({"share", "seasons": [{"start", "end", "share",
    "source"}], "exclude"}), checked as the register checks them; `lake` itself when `rule` is None. A path in
    `rule["exclude"]` becomes the trial lake's `forming_exclude`; a mask is applied by `backtest` instead."""
    from sartale.lakes import _forming_seasons
    if rule is None:
        return lake
    seasons = _forming_seasons(lake.id, [{"source": "back-test", **s} for s in rule.get("seasons") or []],
                               lake.lake_state)
    exclude = rule.get("exclude")
    path = str(exclude) if isinstance(exclude, (str, Path)) else None
    return replace(lake, forming_share=rule["share"], forming_share_source=lake.forming_share_source or "back-test",
                   forming_seasons=seasons, forming_exclude=path,
                   forming_exclude_source="back-test" if path else None)


def _exclusion(trial, rule: dict | None, x, y, epsg) -> np.ndarray | None:
    from sartale.lakebuild import exclude_mask
    exclude = None if rule is None else rule.get("exclude")
    if isinstance(exclude, np.ndarray):
        mask = np.asarray(exclude, bool)
        if mask.shape != (len(y), len(x)):
            raise ValueError(f"the exclusion mask is {mask.shape}, the absence grid {(len(y), len(x))}")
        return mask
    return exclude_mask(trial, x, y, epsg)


def _read(scene: dict, x, y, epsg, cache_dir: Path | None) -> dict:
    """`lakecheck.read_scene`, kept in `cache_dir` (one .npz per scene and grid) when given, so another trial rule
    over the same period reads nothing again."""
    if cache_dir is None:
        return lakecheck.read_scene(scene, x, y, epsg)
    path = Path(cache_dir) / f"{scene['id']}_{epsg}_{x[0]:.0f}_{y[0]:.0f}_{len(x)}x{len(y)}.npz"
    if path.is_file():
        z = np.load(path)
        return {"green": z["green"], "swir": z["swir"], "scl": z["scl"], "transform": Affine(*z["transform"]),
                "crs": CRS.from_wkt(str(z["crs"])), "px": float(z["px"])}
    raw = lakecheck.read_scene(scene, x, y, epsg)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, green=raw["green"], swir=raw["swir"], scl=raw["scl"],
                        transform=np.array(tuple(raw["transform"])[:6]), crs=raw["crs"].to_wkt(), px=raw["px"])
    return raw


def backtest(lake, start: str, end: str, rule: dict | None = None, log=print, cache_dir: Path | None = None,
             keep_masks: bool = False) -> dict:
    """Every scene from `start` to `end` (YYYY-MM-DD) with tile cloud at most ABSENCE_MAX_TILE_CLOUD, oldest first,
    through the absence check from "No lake now": which qualify, the threshold each is judged by, and when the state
    would have changed.

    `rule` ({"share", "seasons", "exclude"}) replaces the site's forming rule: `exclude` is a bool mask on the absence
    grid, a GeoJSON path (read as `forming_exclude` is) or None. Without `rule`, the register's rule is used.

    Returns {"scenes": [row...] (every scene, with "qualifying"), "qualifying": int, "flips": [{"date", "forming"}],
    "pending": [row...] (each scene that became a pending scene), "state": the state at the end, "rule"}; with
    `keep_masks`, also "water_masks": the water of each qualifying scene on the clear zone pixels of the whole grid,
    and "grid": (x, y, epsg)."""
    from sartale.lakebuild import forming_rule, forming_threshold
    from sartale.lakes import lake_bbox
    trial = trial_lake(lake, rule)
    x, y, epsg = lakecheck.absence_grid(lake)
    exclude = _exclusion(trial, rule, x, y, epsg)
    scenes = [lakecheck._scene(f, Date.fromisoformat(end)) for f in lakecheck.search_scenes(lake_bbox(lake), start, end)]
    scenes = [s for s in scenes if s["cloud"] <= lakecheck.ABSENCE_MAX_TILE_CLOUD and start <= s["date"] <= end
              and all(k in s["assets"] for k in ("green", "swir16", "scl"))]
    scenes.sort(key=lambda s: (s["date"], s["id"]))
    state, rows, flips, pending, masks = lakecheck.start_state(), [], [], [], []
    for scene in scenes:
        try:
            raw = _read(scene, x, y, epsg, cache_dir)
        except Exception as e:  # noqa: BLE001 - an unreadable scene is listed and skipped, as the absence check does
            log(f"{lake.id} {scene['id']}: unreadable ({type(e).__name__})")
            rows.append({"date": scene["date"], "s2_id": scene["id"], "tile_cloud": scene["cloud"],
                         "unreadable": True, "qualifying": False})
            continue
        opt = lakecheck.grid_scene(scene, raw, x, y, epsg)
        w = lakecheck.zone_water(trial, opt, x, y, epsg, exclude=exclude)
        ok = lakecheck.qualifies(w)
        row = {**lakecheck.scene_row(scene, w, forming_threshold(trial, scene["date"])), "tile_cloud": scene["cloud"],
               "qualifying": ok}
        rows.append(row)
        note = ""
        if ok and row["threshold"] is not None:
            before = state
            state = lakecheck.step(state, row, row["threshold"])
            if state["forming"] != before["forming"]:
                flips.append({"date": row["date"], "forming": state["forming"]})
                note = " -> Lake may be forming" if state["forming"] else " -> No lake now"
            elif state["pending_scene"] is not None and state["pending_scene"] != before["pending_scene"]:
                pending.append(row)
                note = " (pending)"
        if ok and keep_masks:
            clear = opt["valid"] & ~np.asarray(opt.get("terrain_shadow", False), bool)
            masks.append(np.asarray(opt["water"], bool) & clear)
        thr = "not assessed" if row["threshold"] is None else f"{100 * row['threshold']:.0f}%"
        log(f"{lake.id} {scene['date']} {scene['id']}: zone clear {100 * w['zone_valid_share']:.1f}%, snow "
            f"{100 * w['snow_share']:.2f}%, water {100 * w['water_share']:.2f}% (threshold {thr}): "
            f"{'qualifies' if ok else 'skipped'}{note}")
    if rule is None:
        used = forming_rule(lake)
    else:
        ex = rule.get("exclude")
        used = {"share": rule["share"], "seasons": list(rule.get("seasons") or []),
                "exclude": "mask" if isinstance(ex, np.ndarray) else (None if ex is None else str(ex))}
    out = {"lake": lake.id, "start": start, "end": end, "rule": used, "scenes": rows,
           "qualifying": sum(1 for r in rows if r["qualifying"]), "flips": flips, "pending": pending, "state": state}
    if keep_masks:
        out["water_masks"], out["grid"] = masks, (x, y, epsg)
    return out


def persistent_water(masks: list[np.ndarray], min_share: float = PERSISTENT_SHARE) -> np.ndarray:
    """Pixels that are water in at least `min_share` of the masks (water that is always there, such as a river)."""
    if not masks:
        raise ValueError("no water masks: no scene qualified")
    return np.stack([np.asarray(m, bool) for m in masks]).mean(axis=0) >= min_share


def mask_outline(mask: np.ndarray, x, y, epsg) -> dict:
    """A bool mask on a north-up UTM grid (pixel centres `x`, `y`) as a lon/lat MultiPolygon. Holes are filled, as
    `lakebuild.exclude_mask` reads only the outer ring of each polygon."""
    from pyproj import Transformer
    from rasterio.features import shapes
    x, y = np.asarray(x, float), np.asarray(y, float)
    dx, dy = float(x[1] - x[0]), float(y[1] - y[0])
    tf = Affine(dx, 0, x[0] - dx / 2, 0, dy, y[0] - dy / 2)
    to_ll = Transformer.from_crs(epsg, 4326, always_xy=True)
    polygons = []
    for geom, value in shapes(mask.astype(np.uint8), mask=mask, transform=tf):
        if value:
            ring = [[round(c, 7) for c in to_ll.transform(px, py)] for px, py in geom["coordinates"][0]]
            polygons.append([ring])
    if not polygons:
        raise ValueError("the mask is empty: no lasting water to outline")
    return {"type": "MultiPolygon", "coordinates": polygons}
