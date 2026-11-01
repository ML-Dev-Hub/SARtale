"""Statistical change layer: how unusual each date is against the season's own behaviour.

Order of operations: linear averaging happens once, at multilooking (mask, average linear power, convert to dB, in
products.py). Every statistic here is in dB, on those 30 m values, read back from the COGs.

The score of a date at a pixel is the larger, over HH and HV, of |value - median| / scale. Median and scale come from
the other baseline dates, so a date is never in its own baseline. The scale is 1.4826 x the median absolute deviation,
the factor that makes it match a standard deviation for normal noise, with a floor of 1 dB, because six dates give a
noisy spread. This is the modified z-score of Iglewicz and Hoaglin, "How to Detect and Handle Outliers" (1993), taken
per pixel and using both polarizations.

distmetrics 1.0.8 (Apache-2.0, https://github.com/opera-adt/distmetrics) was read and not used. Importing any part of
it imports PyTorch and asf_search, its Mahalanobis metric uses a mean and a covariance rather than robust statistics,
and on this stack a robust Mahalanobis form separated no better than the larger z-score, which is simpler to explain.
Details are in docs/DATA_SOURCES.md.
"""
import json
import math
from collections.abc import Mapping
from pathlib import Path

import numpy as np
import rasterio

from sartale import config
from sartale.gcov import Layer
from sartale.products import (
    DISPLAY_LOOKS,
    DISPLAY_MAX_WIDTH,
    INTERFERENCE_DATE,
    POL_TERMS,
    bounds_3857_to_lonlat,
    multilook_layer,
    write_cog,
    write_webp_3857,
)
from sartale.sites import RADIUS_M, _footprint

METHOD = "Largest robust z-score of HH and HV, each date against the season's other dates"
REFERENCE = "Modified z-score: Iglewicz and Hoaglin (1993), per pixel and per polarization"
MIN_VALID_DATES = 4  # a pixel with fewer valid baseline dates has no score
SCALE_FLOOR_DB = 1.0  # about the noise of one 30 m pixel; about 1 dB is meaningless at a site
MAD_TO_SIGMA = 1.4826
STABLE_QUANTILE = 0.25  # lowest quarter of temporal spread, in both polarizations
THRESHOLD_PERCENTILE = 99  # of the pooled control pixels on every scored date
THRESHOLD_STEP = 0.5  # the threshold is rounded up to this, so a reprocessing wobble does not move it
EXCLUDED_REASON = "Likely radio interference in HV on this date."
FRAME_LOW, FRAME_HIGH = (255, 214, 64), (214, 32, 39)  # yellow at the threshold, red at the top of the scale
FRAME_ALPHA = 235
# Evidence in docs/DATA_SOURCES.md: the rise is in HH and HV and at both NISAR frequencies.
DATE_NOTES = {"2026-10-06": ("Patches of the northern plain read about 1.5 dB brighter on this date, in HH and HV. "
                             "The cause is unexplained, and no rain record was compared.")}


# --- statistics -------------------------------------------------------------------

def _median(values: np.ndarray) -> np.ndarray:
    """Median along axis 0, ignoring NaN; NaN where nothing is valid. Much faster here than np.nanmedian."""
    ordered = np.sort(values, axis=0)  # NaN sorts last
    n = np.isfinite(values).sum(axis=0)
    low = np.take_along_axis(ordered, np.maximum((n - 1) // 2, 0)[None], axis=0)[0]
    high = np.take_along_axis(ordered, np.maximum(n // 2, 0)[None], axis=0)[0]
    return (low + high) / 2


def _median_and_spread(stack_db: np.ndarray, use: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-pixel median, unfloored robust scale, and count of valid dates, from the dates in `use`."""
    use = np.asarray(use, dtype=bool)
    if use.shape != stack_db.shape[:1]:
        raise ValueError(f"use has shape {use.shape}, expected one value per date: {stack_db.shape[:1]}")
    chosen = stack_db[use]
    median = _median(chosen)
    return median, MAD_TO_SIGMA * _median(np.abs(chosen - median)), np.isfinite(chosen).sum(axis=0)


def robust_baseline(stack_db: np.ndarray, use: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per-pixel median and floored robust scale from the dates in `use`. stack_db is (dates, ...).

    Both are NaN where fewer than MIN_VALID_DATES dates are valid.
    """
    median, spread, n = _median_and_spread(stack_db, use)
    scale = np.maximum(spread, SCALE_FLOOR_DB)
    few = n < MIN_VALID_DATES
    return np.where(few, np.nan, median), np.where(few, np.nan, scale)


def change_score(stack_db: np.ndarray, baseline: tuple[np.ndarray, np.ndarray]) -> np.ndarray:
    """(dates, rows, cols) score of a (dates, pols, rows, cols) stack: the larger robust z-score of the polarizations.

    NaN in either polarization, or in the baseline, gives NaN.
    """
    median, scale = baseline
    return np.max(np.abs(stack_db - median) / scale, axis=1)


def season_scores(stack_db: np.ndarray, use: np.ndarray) -> np.ndarray:
    """Score every date of a (dates, pols, rows, cols) stack against the other dates in `use`.

    A date outside `use` is scored against all of `use`, and affects no other date's score.
    """
    use = np.asarray(use, dtype=bool)
    scores = np.empty((stack_db.shape[0], *stack_db.shape[2:]), dtype=np.float32)
    for t in range(stack_db.shape[0]):
        others = use.copy()
        others[t] = False
        scores[t] = change_score(stack_db[t:t + 1], robust_baseline(stack_db, others))[0]
    return scores


def stable_pixels(stack_db: np.ndarray, use: np.ndarray, quantile: float = STABLE_QUANTILE) -> np.ndarray:
    """(rows, cols) mask of pixels in the lowest `quantile` of temporal spread in every polarization."""
    _, spread, n = _median_and_spread(stack_db, use)
    mask = np.ones(stack_db.shape[-2:], dtype=bool)
    for pol_spread, pol_n in zip(spread, n):
        known = pol_spread[pol_n >= MIN_VALID_DATES]
        mask &= (pol_n >= MIN_VALID_DATES) & (pol_spread <= np.quantile(known, quantile))
    return mask


def scene_offsets(stack_db: np.ndarray, stable_mask: np.ndarray, use: np.ndarray) -> np.ndarray:
    """(dates, pols) scene-wide offset in dB: the median, over stable pixels, of a date minus the other `use` dates.

    Each date is compared with the other dates, not with a median it is part of: over many pixels such a median equals
    the date itself so often that the offset comes out near zero whatever the scene did.
    """
    values = stack_db[..., stable_mask]
    if values.shape[-1] == 0:
        raise ValueError("No stable pixels to measure the scene offset on")
    use = np.asarray(use, dtype=bool)
    offsets = np.empty(values.shape[:2], dtype=np.float64)
    for t in range(values.shape[0]):
        others = use.copy()
        others[t] = False
        offsets[t] = _median(np.moveaxis(values[t] - _median(values[others]), -1, 0))
    return offsets


def normalise_scene_drift(stack_db: np.ndarray, stable_mask: np.ndarray, use: np.ndarray | None = None) -> np.ndarray:
    """A copy of the stack with each date's scene-wide offset removed. NaN stays NaN. `use` defaults to every date."""
    use = np.ones(stack_db.shape[0], dtype=bool) if use is None else use
    offsets = scene_offsets(stack_db, stable_mask, use)
    return stack_db - offsets[:, :, None, None].astype(stack_db.dtype)


def control_threshold(control_scores: np.ndarray) -> float:
    """The 99th percentile of the control pixels' scores, rounded up to the next THRESHOLD_STEP."""
    values = np.asarray(control_scores, dtype=np.float64)
    values = values[np.isfinite(values)]
    if values.size == 0:
        raise ValueError("No control pixel has a score, so there is nothing to set the threshold from")
    return math.ceil(float(np.percentile(values, THRESHOLD_PERCENTILE)) / THRESHOLD_STEP) * THRESHOLD_STEP


def score_plan(entries: list[dict]) -> dict:
    """Which manifest dates are scored, which form the baseline and which are left out, and why.

    The interference date is left out entirely. Any other flagged date is scored but stays out of the baseline.
    """
    scored = [e for e in entries if e["date"] != INTERFERENCE_DATE]
    return {"scored": [e["date"] for e in scored],
            "baseline": [e["date"] for e in scored if not e.get("flag")],
            "excluded": [{"date": e["date"], "reason": EXCLUDED_REASON} for e in entries if e["date"] == INTERFERENCE_DATE]}


# --- outputs ----------------------------------------------------------------------

def render_change_frame(score: np.ndarray, threshold: float, top: float) -> np.ndarray:
    """RGBA uint8: yellow to red from `threshold` to `top`, transparent below the threshold and for NaN."""
    score = np.asarray(score, dtype=np.float64)
    shown = score >= threshold  # False for NaN
    t = np.clip((np.nan_to_num(score, nan=threshold) - threshold) / (top - threshold), 0.0, 1.0)[..., None]
    rgb = np.rint((1 - t) * np.array(FRAME_LOW) + t * np.array(FRAME_HIGH))
    rgba = np.dstack([rgb, np.full(score.shape, FRAME_ALPHA)]).astype(np.uint8)
    rgba[~shown] = 0
    return rgba


def _read_cog(path: Path) -> tuple[np.ndarray, Layer]:
    with rasterio.open(path) as src:
        data, t = src.read(1), src.transform
        epsg = src.crs.to_epsg()
    x = t.c + (np.arange(data.shape[1]) + 0.5) * t.a
    y = t.f + (np.arange(data.shape[0]) + 0.5) * t.e
    return data, Layer(data, x, y, epsg, None, None)


def _read_stack(cog_dir: Path, dates: list[str]) -> tuple[np.ndarray, Layer]:
    """(dates, pols, rows, cols) dB in single precision, from the 30 m COGs."""
    grid = None
    rows = []
    for d in dates:
        pols = []
        for pol in POL_TERMS:
            data, grid = _read_cog(cog_dir / f"{d}_{pol}.tif")
            pols.append(data)
        rows.append(np.stack(pols))
    return np.stack(rows), grid


def build_change(cog_dir: Path, out_dir: Path, sites_in: list[dict], radius_m: float = RADIUS_M) -> dict | None:
    """Score COGs, display frames and the manifest's `change` record, from the 30 m COGs.

    The threshold comes from the sites whose role names a control. With too few dates for a date-by-date baseline there
    is no layer: any old `change` record is dropped and None is returned. No other frame is touched.
    """
    cog_dir, out_dir = Path(cog_dir), Path(out_dir)
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    plan = score_plan(manifest["dates"])
    if len(plan["baseline"]) <= MIN_VALID_DATES:
        print(f"no change layer: not enough dates ({len(plan['baseline'])} usable in the baseline)")
        manifest.pop("change", None)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return None

    dates = plan["scored"]
    stack, grid = _read_stack(cog_dir, dates)
    use = np.array([d in plan["baseline"] for d in dates])
    stable = stable_pixels(stack, use)
    offsets = scene_offsets(stack, stable, use)
    scores = season_scores(stack - offsets[:, :, None, None].astype(stack.dtype), use)
    del stack

    controls = [s for s in sites_in if "control" in s["role"].lower()]
    if not controls:
        raise ValueError("No site has a role naming a control, so there is nothing to set the threshold from")
    pooled = np.concatenate([scores[:, _footprint(grid, s["lon"], s["lat"], radius_m)].ravel() for s in controls])
    threshold = control_threshold(pooled)
    top = 2 * threshold

    frames = {}
    for i, d in enumerate(dates):
        write_cog(scores[i], grid, cog_dir / f"change_{d}.tif")
        coarse = multilook_layer(Layer(scores[i], grid.x, grid.y, grid.epsg, None, None), DISPLAY_LOOKS)
        frames[d] = f"frames/change_{d}.webp"
        bounds = write_webp_3857(render_change_frame(coarse.power, threshold, top), coarse, out_dir / frames[d],
                                 window=config.WINDOW, max_width=DISPLAY_MAX_WIDTH)
        if not np.allclose(bounds_3857_to_lonlat(bounds), manifest["bounds"], rtol=0, atol=1e-5):
            raise RuntimeError(f"{frames[d]} does not cover the manifest bounds")

    manifest["change"] = {
        "method": METHOD,
        "reference": REFERENCE,
        "library": "numpy",
        "version": np.__version__,
        "threshold": threshold,
        "scale_max": top,
        "baseline_dates": plan["baseline"],
        "excluded": plan["excluded"],
        "removed_offsets_db": {d: {pol: round(float(offsets[i, j]), 3) for j, pol in enumerate(POL_TERMS)}
                               for i, d in enumerate(dates)},
        "date_notes": {d: note for d, note in DATE_NOTES.items() if d in dates},
        "frames": frames,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest["change"]


def add_change_scores(sites: list[dict], manifest: Mapping, cog_dir: Path, radius_m: float = RADIUS_M) -> list[dict]:
    """Set `change_score` on every series entry: the median pixel score inside the site's radius, or None.

    None means the date is not scored, the build has no change layer, or no pixel in the radius has a score.
    """
    change = manifest.get("change")
    scored = {}
    grid = None
    if change:
        for d in change["frames"]:
            scored[d], grid = _read_cog(Path(cog_dir) / f"change_{d}.tif")
    for s in sites:
        inside = _footprint(grid, s["lon"], s["lat"], radius_m) if grid is not None else None
        for point in s["series"]:
            score = scored.get(point["date"])
            values = score[inside] if score is not None else np.empty(0)
            values = values[np.isfinite(values)]
            point["change_score"] = round(float(np.median(values)), 2) if values.size else None
    return sites
