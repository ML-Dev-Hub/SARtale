"""Statistical change layers: where radar brightness stepped, and how unusual each date is.

The step layer is the main one. At each pixel it looks for the split of the season into a before and an after that
differ most, so a pixel that stays dark for most of the season can still show when it went dark. Unusual dates, the
second layer, judges each date against the rest of the season, so it cannot place a lasting change.

Order of operations: linear averaging happens once, at multilooking (mask, average linear power, convert to dB, in
products.py). Every statistic here is in dB, on those 30 m values, read back from the COGs.

A step is judged on 90 m pixels, averaged once more in linear power, because 30 m pixels are too noisy for a split chosen
from several. Choosing the best split inflates the step, so a step counts only if HH and HV moved the same way at the
same split, by a mean size and a stability that shuffled dates rarely reach together. Stability is the step over its
standard error from the scatter inside the two segments: a two-sample t statistic with a floor on the scatter, combined
over the polarizations as a root mean square.

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
from PIL import Image
from pyproj import Transformer
from rasterio.warp import Resampling, reproject

from sartale import config
from sartale.gcov import Layer
from sartale.products import (
    DISPLAY_LOOKS,
    DISPLAY_MAX_WIDTH,
    INTERFERENCE_DATE,
    POL_TERMS,
    _north_up,
    _window_grid,
    bounds_3857_to_lonlat,
    multilook_layer,
    write_cog,
    write_webp_3857,
)
from sartale.radiometry import multilook_linear, to_db
from sartale.sites import RADIUS_M, _footprint

STEP_METHOD = ("Largest before-and-after step in HH and HV at one split per pixel, kept where both polarizations moved "
               "the same way and the size and stability together are rarely reached by shuffled dates")
STEP_REFERENCE = "Single change point by a two-sample t statistic, with a permutation check of the choice of split"
STEP_LOOKS = 3  # 30 m -> 90 m, in linear power
MIN_SEGMENT = 2  # dates on each side of a step, so one date alone cannot make one
STEP_SCATTER_FLOOR_DB = 0.5  # about the scatter of the stable controls at 90 m (0.4 to 0.45 dB)
STEP_CONTROL_RADIUS_M = 500.0  # at 90 m a 150 m radius holds about 9 pixels
STEP_MIN_DB = 3.0  # mean of |HH step| and |HV step|; below about 3 dB one site needs other support (docs/DATA_SOURCES.md)
STEP_PERCENTILE = 99  # at most 1% of control pixels and of shuffled noisy ground may pass both limits
STEP_RULE_STEP = 0.5  # the stability limit is rounded up to this
STEP_SHUFFLES = 5
STEP_SEED = 20261102
STEP_DISPLAY_LOOKS = 3  # the frame only: 90 m -> 270 m, about one map pixel at the default zoom, so patterns survive
STEP_DISPLAY_MIN_PIXELS = 2  # the frame only: of the 9 pixels in a cell, this many must be flagged to draw it
STEP_DISPLAY_WIDTH = 1522  # pixels: two per cell, so nearest-neighbour warping keeps cells even
# One hue per date. Stepped up is the light tint, stepped down the deep shade, so direction reads without a second map.
STEP_COLOURS = {  # split position in the date order: (up, down)
    2: ((255, 196, 120), (214, 96, 16)),
    3: ((255, 240, 130), (181, 150, 0)),
    4: ((150, 240, 160), (20, 130, 60)),
    5: ((140, 215, 255), (20, 100, 190)),
    6: ((240, 170, 240), (160, 40, 160)),
}
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


def _split_terms(stack_db: np.ndarray, min_segment: int) -> tuple[np.ndarray, np.ndarray]:
    """Step and stability of every allowed split: each (splits, ...) for a (dates, ...) stack. NaN where not allowed.

    Split k puts dates before k in the first segment. Each segment needs min_segment valid dates, so NaN dates count
    against it. Stability is |step| / (scatter x sqrt(1/n1 + 1/n2)), scatter being the pooled within-segment standard
    deviation with a floor.
    """
    valid = np.isfinite(stack_db)
    values = np.where(valid, stack_db, 0.0).astype(np.float64)
    counts, sums, squares = np.cumsum(valid, axis=0), np.cumsum(values, axis=0), np.cumsum(values ** 2, axis=0)
    n_all, sum_all, square_all = counts[-1], sums[-1], squares[-1]
    steps, stabilities = [], []
    for k in range(min_segment, stack_db.shape[0] - min_segment + 1):
        n1, sum1, square1 = counts[k - 1], sums[k - 1], squares[k - 1]
        n2, sum2, square2 = n_all - n1, sum_all - sum1, square_all - square1
        allowed = (n1 >= min_segment) & (n2 >= min_segment)
        with np.errstate(divide="ignore", invalid="ignore"):
            step = sum2 / n2 - sum1 / n1
            scatter2 = ((square1 - sum1 ** 2 / n1) + (square2 - sum2 ** 2 / n2)) / (n_all - 2)
            error = np.sqrt(np.maximum(scatter2, STEP_SCATTER_FLOOR_DB ** 2) * (1 / n1 + 1 / n2))
            stability = np.abs(step) / error
        steps.append(np.where(allowed, step, np.nan))
        stabilities.append(np.where(allowed, stability, np.nan))
    return np.stack(steps), np.stack(stabilities)


def best_split(stack_db: np.ndarray, min_segment: int = MIN_SEGMENT) -> tuple[np.ndarray, np.ndarray]:
    """One split per pixel of a (dates, pols, ...) stack: the one with the largest joint stability of the polarizations.

    Returns (step_db, split_index). step_db is (pols, ...): mean dB after minus mean dB before. split_index is the first
    date after the step, -1 where no split is allowed. Any polarization that lacks a split leaves the pixel without one.
    """
    if stack_db.shape[0] < 2 * min_segment:
        return np.full(stack_db.shape[1:], np.nan, np.float32), np.full(stack_db.shape[2:], -1, np.int16)
    steps, stabilities = _split_terms(stack_db, min_segment)
    joint = (stabilities ** 2).sum(axis=1)  # NaN if a polarization has no such split
    allowed = np.isfinite(joint).any(axis=0)
    best = np.argmax(np.nan_to_num(joint, nan=-1.0), axis=0)
    step_db = np.take_along_axis(steps, best[None, None], axis=0)[0]
    step_db = np.where(allowed, step_db, np.nan)
    return step_db.astype(np.float32), np.where(allowed, best + min_segment, -1).astype(np.int16)


def step_stability(stack_db: np.ndarray, split_index: np.ndarray, min_segment: int = MIN_SEGMENT) -> np.ndarray:
    """(pols, ...) stability of the given split at each pixel; NaN where split_index is -1."""
    if stack_db.shape[0] < 2 * min_segment:
        return np.full(stack_db.shape[1:], np.nan, np.float32)
    _, stabilities = _split_terms(stack_db, min_segment)
    at = np.maximum(split_index - min_segment, 0).astype(np.intp)
    out = np.take_along_axis(stabilities, at[None, None], axis=0)[0]
    return np.where(split_index >= 0, out, np.nan).astype(np.float32)


def step_strength(step_db: np.ndarray, stability: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """What HH and HV say together: mean |step| and root mean square stability, or 0 where they moved in opposite directions.

    A change is often weaker in HV, so requiring each polarization to pass alone misses real steps; the average lets the
    stronger one carry the weaker, and the same direction is what they must agree on.
    """
    same = np.all(np.sign(step_db) == np.sign(step_db[0]), axis=0)
    size = np.where(same, np.abs(step_db).mean(axis=0), 0.0)
    t = np.where(same, np.sqrt((stability ** 2).mean(axis=0)), 0.0)
    missing = ~np.isfinite(step_db).all(axis=0)
    return np.where(missing, np.nan, size), np.where(missing, np.nan, t)


def step_flags(size_db: np.ndarray, stability: np.ndarray, min_step_db: float, min_stability: float) -> np.ndarray:
    """True where a step passes both limits. NaN never passes."""
    return (np.nan_to_num(size_db) >= min_step_db) & (np.nan_to_num(stability) >= min_stability)


def shuffle_dates(values: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """A (dates, pols, pixels) array with the dates in a new random order at each pixel, the same for both polarizations."""
    order = np.argsort(rng.random((values.shape[0], values.shape[2])), axis=0)
    return np.take_along_axis(values, order[:, None], axis=0)


def _round_up(value: float) -> float:
    return math.ceil(value / STEP_RULE_STEP) * STEP_RULE_STEP


def _strength_of(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Step size and stability of a (dates, pols, pixels) array, keeping pixels with a score."""
    step, split = best_split(values)
    size, t = step_strength(step, step_stability(values, split))
    keep = np.isfinite(size)
    return size[keep], t[keep]


def step_rule(stack_db: np.ndarray, control_mask: np.ndarray, noisy_mask: np.ndarray, seed: int = STEP_SEED) -> dict:
    """The limits for a step, from control pixels and from shuffled dates on noisy ground, never from known changes.

    The size limit is fixed. The stability limit is the smallest multiple of 0.5 that leaves at most 1% of control pixels
    and of shuffled pixels passing both limits. A shuffle keeps a pixel's values and destroys their order, so what it
    scores is what choosing the best split gives with no step there. It is seeded, so a rebuild gets the same limits.
    Limits taken separately would compound: 1% on each came to about 0.1% together.
    """
    size, t = _strength_of(stack_db[..., control_mask])
    if size.size == 0:
        raise ValueError("No control pixel has a step, so there is nothing to set the limits from")
    rng = np.random.default_rng(seed)
    noisy = stack_db[..., noisy_mask]
    shuffled = [_strength_of(shuffle_dates(noisy, rng)) for _ in range(STEP_SHUFFLES)]
    null_size, null_t = (np.concatenate(v) for v in zip(*shuffled))
    pct = lambda v: float(np.percentile(v, STEP_PERCENTILE))
    passing = lambda sizes, stabilities: pct(np.where(sizes >= STEP_MIN_DB, stabilities, 0.0))
    control, null = passing(size, t), passing(null_size, null_t)
    return {"min_step_db": STEP_MIN_DB, "min_stability": max(_round_up(max(control, null)), STEP_RULE_STEP),
            "control_p99_db": round(pct(size), 2), "control_p99_stability": round(control, 2),
            "shuffled_p99_db": round(pct(null_size), 2), "shuffled_p99_stability": round(null, 2)}


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


def step_frame(split: np.ndarray, step_hh: np.ndarray, flags: np.ndarray) -> np.ndarray:
    """The classes behind the step frame, in cells of STEP_DISPLAY_LOOKS input pixels a side: 0 nothing, else 1 + 2 x
    position for a step up and 2 + 2 x position for a step down, position being the split.

    The image source has no mipmaps, so a fine frame loses small patches at the default zoom, and averaging would fade
    them. Instead a cell is drawn in its commonest class if enough of its pixels are flagged: lone pixels drop out, and
    a patch that fills only part of a cell is drawn whole, so the frame shows where steps gather, slightly too wide.
    """
    classes = np.where(flags & (split >= 0), 1 + 2 * split.clip(0) + (step_hh < 0), 0).astype(np.uint8)
    n = STEP_DISPLAY_LOOKS
    rows, cols = (classes.shape[0] // n) * n, (classes.shape[1] // n) * n
    blocks = classes[:rows, :cols].reshape(rows // n, n, cols // n, n)
    best, best_count = np.zeros((rows // n, cols // n), np.uint8), np.zeros((rows // n, cols // n), np.uint8)
    for c in np.unique(classes[classes > 0]):
        count = (blocks == c).sum(axis=(1, 3)).astype(np.uint8)
        take = count > best_count
        best[take], best_count[take] = c, count[take]
    best[(blocks > 0).sum(axis=(1, 3)) < STEP_DISPLAY_MIN_PIXELS] = 0
    return best


def _class_colour(c: int) -> tuple[int, int, int]:
    position, down = (c - 1) // 2, (c - 1) % 2
    return STEP_COLOURS[position][down]


def write_step_frame(classes: np.ndarray, layer: Layer, path: Path) -> None:
    """Classes to a lossless WebP over config.WINDOW in EPSG:3857, by nearest neighbour, so no colour is mixed or smeared.

    Lossy WebP would blur the hue of small patches, and bilinear warping would invent colours between dates.
    """
    data, transform = _north_up(classes, layer)
    dst_tf, dw, dh = _window_grid(config.WINDOW, 1.0, STEP_DISPLAY_WIDTH)
    out = np.zeros((dh, dw), np.uint8)
    reproject(np.ascontiguousarray(data), out, src_transform=transform, src_crs=f"EPSG:{layer.epsg}", dst_transform=dst_tf,
              dst_crs="EPSG:3857", resampling=Resampling.nearest, src_nodata=0, dst_nodata=0)
    rgba = np.zeros((dh, dw, 4), np.uint8)
    for c in np.unique(out[out > 0]):
        rgba[out == c] = (*_class_colour(int(c)), 255)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, "RGBA").save(path, "WEBP", lossless=True, method=6)


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


def looked_stack(stack: np.ndarray, grid: Layer) -> tuple[np.ndarray, Layer]:
    """A (dates, pols, rows, cols) dB stack averaged in linear power to the step layer's pixel, and its grid."""
    out = np.stack([np.stack([to_db(multilook_linear(10 ** (db / 10), STEP_LOOKS)).astype(np.float32) for db in pols])
                    for pols in stack])
    return out, multilook_layer(Layer(stack[0, 0], grid.x, grid.y, grid.epsg, None, None), STEP_LOOKS)


def _box_mask(layer: Layer, box: tuple[float, float, float, float]) -> np.ndarray:
    xs, ys = Transformer.from_crs(4326, layer.epsg, always_xy=True).transform([box[0], box[2]], [box[1], box[3]])
    return np.outer((layer.y >= min(ys)) & (layer.y <= max(ys)), (layer.x >= min(xs)) & (layer.x <= max(xs)))


def build_step(stack: np.ndarray, grid: Layer, dates: list[str], controls: list[dict], cog_dir: Path, out_dir: Path) -> dict:
    """Step COGs, the step frame and the record of the step layer. `stack` is at 30 m with scene offsets removed."""
    looked, layer = looked_stack(stack, grid)
    step, split = best_split(looked)
    stability = step_stability(looked, split)
    size, t = step_strength(step, stability)

    control_mask = np.any([_footprint(layer, s["lon"], s["lat"], STEP_CONTROL_RADIUS_M) for s in controls], axis=0)
    has_data = np.isfinite(looked).all(axis=(0, 1))
    noisy = _box_mask(layer, config.PLAIN_BOX) & has_data
    if not noisy.any():
        print("step rule: the plain box has no data here, so the shuffle uses every pixel")
        noisy = has_data
    rule = step_rule(looked, control_mask, noisy)
    flags = step_flags(size, t, rule["min_step_db"], rule["min_stability"])

    for pol_i, pol in enumerate(POL_TERMS):
        write_cog(step[pol_i], layer, cog_dir / f"change_step_{pol}.tif")
    write_cog(t, layer, cog_dir / "change_step_stability.tif")  # 0 where HH and HV moved in opposite directions
    write_cog(np.where(split >= 0, split, np.nan), layer, cog_dir / "change_step_split.tif")

    classes = step_frame(split, step[0], flags)
    coarse = Layer(classes, layer.x[:classes.shape[1] * STEP_DISPLAY_LOOKS].reshape(-1, STEP_DISPLAY_LOOKS).mean(axis=1),
                   layer.y[:classes.shape[0] * STEP_DISPLAY_LOOKS].reshape(-1, STEP_DISPLAY_LOOKS).mean(axis=1),
                   layer.epsg, None, None)
    frame = "frames/step_date.webp"
    write_step_frame(classes, coarse, out_dir / frame)

    scored = np.isfinite(size)
    split_positions = range(MIN_SEGMENT, len(dates) - MIN_SEGMENT + 1)
    return {
        "method": STEP_METHOD,
        "reference": STEP_REFERENCE,
        "pixel_m": round(float(np.abs(layer.x[1] - layer.x[0]))),
        "dates": dates,
        "split_dates": [dates[k] for k in split_positions],
        "min_segment": MIN_SEGMENT,
        **rule,
        "scatter_floor_db": STEP_SCATTER_FLOOR_DB,
        "flagged_share": round(float(flags[scored].mean()), 4),
        "frame": frame,
        "classes": [{"date": dates[k], "up": list(STEP_COLOURS[k][0]), "down": list(STEP_COLOURS[k][1])}
                    for k in split_positions if k in STEP_COLOURS],
    }


def build_change(cog_dir: Path, out_dir: Path, sites_in: list[dict], radius_m: float = RADIUS_M) -> dict | None:
    """Step and score COGs, display frames and the manifest's `change` record, from the 30 m COGs.

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
    stack -= offsets[:, :, None, None].astype(stack.dtype)
    controls = [s for s in sites_in if "control" in s["role"].lower()]
    if not controls:
        raise ValueError("No site has a role naming a control, so there is nothing to set the threshold from")
    step = build_step(stack, grid, dates, controls, cog_dir, out_dir)
    scores = season_scores(stack, use)
    del stack

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
        "step": step,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest["change"]


def _site_step(site: dict, change: Mapping, step_maps: tuple[np.ndarray, Layer] | None, radius_m: float) -> dict | None:
    """The step test on the site's own curve, with the scene offsets removed, plus the share of map pixels flagged here.

    Using the curve means a card's step can be read off the chart beside it.
    """
    rule = change.get("step")
    if not rule or step_maps is None:
        return None
    dates = rule["dates"]
    by_date = {p["date"]: p for p in site["series"]}
    removed = change["removed_offsets_db"]
    curve = [[(by_date[d].get(key) if d in by_date else None) for key in ("hh_db", "hv_db")] for d in dates]
    values = np.array([[np.nan if v is None else v - removed[d][pol] for v, pol in zip(row, POL_TERMS)]
                       for d, row in zip(dates, curve)], dtype=np.float64)[:, :, None]
    step, split = best_split(values)
    if split[0] < 0:
        return None
    size, t = step_strength(step, step_stability(values, split))
    flagged_map, layer = step_maps
    return {"date": dates[int(split[0])], "previous_date": dates[int(split[0]) - 1],
            "hh_db": round(float(step[0, 0]), 2), "hv_db": round(float(step[1, 0]), 2),
            "stability": round(float(t[0]), 2),
            "flagged": bool(step_flags(size, t, rule["min_step_db"], rule["min_stability"])[0]),
            "map_share": round(float(flagged_map[_footprint(layer, site["lon"], site["lat"], radius_m)].mean()), 3)}


def _step_maps(change: Mapping, cog_dir: Path) -> tuple[np.ndarray, Layer] | None:
    """Flagged pixels of the step layer from its COGs, or None for a build without it."""
    rule = change.get("step")
    if not rule:
        return None
    hh, layer = _read_cog(Path(cog_dir) / "change_step_HH.tif")
    hv = _read_cog(Path(cog_dir) / "change_step_HV.tif")[0]
    t = _read_cog(Path(cog_dir) / "change_step_stability.tif")[0]
    size = np.where(np.sign(hh) == np.sign(hv), (np.abs(hh) + np.abs(hv)) / 2, 0.0)
    return step_flags(size, t, rule["min_step_db"], rule["min_stability"]), layer


def add_change_scores(sites: list[dict], manifest: Mapping, cog_dir: Path, radius_m: float = RADIUS_M) -> list[dict]:
    """Set `change_score` on every series entry and `step` on every site.

    A change_score is the median pixel score inside the site's radius, or None where the date is not scored, the build
    has no change layer, or no pixel in the radius has a score. `step` is None for a build without the step layer.
    """
    change = manifest.get("change")
    step_maps = _step_maps(change, cog_dir) if change else None
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
        s["step"] = _site_step(s, change, step_maps, radius_m) if change else None
    return sites
