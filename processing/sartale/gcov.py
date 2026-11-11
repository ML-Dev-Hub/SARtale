"""Read clipped layers from NISAR GCOV HDF5 files."""
from dataclasses import dataclass
from pathlib import Path

import h5py
import numpy as np
from pyproj import Transformer

from sartale.radiometry import mask_power

# This layout was confirmed on the real P05023 (provisional) files: HH and HV terms, 10 m pixels, EPSG:32643, mask
# values 0, 1 and 255 (one subswath), and granuleId and compositeReleaseId. The standard P05036 windows read with the
# same paths. If a later release differs, fix it here only.
GRID_GROUP = "/science/LSAR/GCOV/grids/frequencyA"
LOOKS = "numberOfLooks"
MASK = "mask"
X_COORDS = "xCoordinates"
Y_COORDS = "yCoordinates"
PROJECTION = "projection"
EPSG_ATTR = "epsg_code"
IDENTIFICATION_GROUP = "/science/LSAR/identification"
GRANULE_ID = "granuleId"
RELEASE_ID = "compositeReleaseId"  # the CRID, e.g. P05023 (D00404 in the 2008 samples)

# The mask dataset's own description: the value is the subswath number of valid
# samples; 0 means partially focused or invalid; 255 is fill.
MASK_FILL = 255
MASK_INVALID = 0
# The pre-launch simulated samples (CRID D00404, 2008) carry a mask of only 0 and 255 across the whole file, with 0
# on every real sample. Only products whose CRID starts with this letter keep their zeros. Every other product (the
# P05023 and P05036 releases, or a file without a CRID) follows the mask's own description: 0 is invalid.
LEGACY_ZERO_VALID_CRID_PREFIX = "D"


def zero_is_valid(crid: str | None) -> bool:
    """True only for the pre-launch sample convention (CRID D...), where mask 0 marks the real samples."""
    return bool(crid) and str(crid).startswith(LEGACY_ZERO_VALID_CRID_PREFIX)


def invalid_samples(mask: np.ndarray, crid: str | None = None) -> np.ndarray:
    """Boolean grid of the samples that are not valid: fill (255) always, and 0 (partially focused or invalid)
    unless the product is a pre-launch sample (`zero_is_valid`). The rule is per sample and never depends on what
    else the clip holds, so a pixel is valid or invalid whatever window it is read in."""
    mask = np.asarray(mask)
    bad = mask == MASK_FILL
    if not zero_is_valid(crid):
        bad |= mask == MASK_INVALID
    return bad


@dataclass
class Layer:
    power: np.ndarray
    x: np.ndarray
    y: np.ndarray
    epsg: int
    looks: np.ndarray | None
    mask: np.ndarray | None


def _text(value) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def check_identity(path: Path, expected_granule: str, expected_crid: str | None = None) -> None:
    """Raise ValueError if the file's own granule ID or release ID differs from what the manifest says.

    A renamed file must never be labelled with another granule's name or release. Pass the CRID of the pass's own
    granule name (each pass keeps its own; none is pinned). The granule ID is required. The release ID is compared
    only where the file has the field.
    """
    with h5py.File(path, "r") as f:
        ident = f[IDENTIFICATION_GROUP] if IDENTIFICATION_GROUP in f else None
        if ident is None or GRANULE_ID not in ident:
            raise ValueError(f"{path}: no {IDENTIFICATION_GROUP}/{GRANULE_ID}, cannot confirm which granule this is")
        granule = _text(ident[GRANULE_ID][()])
        release = _text(ident[RELEASE_ID][()]) if RELEASE_ID in ident else None
    if granule != expected_granule:
        raise ValueError(f"{path}: the file says it is granule {granule}, but the manifest expects {expected_granule}")
    if expected_crid is not None and release is not None and release != expected_crid:
        raise ValueError(f"{path}: the file has release ID {release}, expected {expected_crid}")


def mask_histogram(mask: np.ndarray | None) -> dict[int, int]:
    """Count of each mask value, e.g. {0: 120, 1: 90000, 255: 40}. Empty when there is no mask."""
    if mask is None:
        return {}
    values, counts = np.unique(np.asarray(mask), return_counts=True)
    return {int(v): int(c) for v, c in zip(values, counts)}


def apply_mask(power: np.ndarray, mask: np.ndarray | None, crid: str | None = None) -> np.ndarray:
    """Set invalid GCOV samples (`invalid_samples`) to NaN, using the mask clipped to the same window as `power`.

    `crid` is the file's composite release ID; only a pre-launch sample (D...) keeps its mask-0 samples.
    """
    if mask is None:
        return power
    mask = np.asarray(mask)
    if mask.shape != power.shape:
        raise ValueError(f"mask shape {mask.shape} does not match power shape {power.shape}")
    out = np.array(power, dtype=np.float64, copy=True)
    out[invalid_samples(mask, crid)] = np.nan
    return out


def read_release(f) -> str | None:
    """The open file's compositeReleaseId, or None when the file has no such field."""
    ident = f[IDENTIFICATION_GROUP] if IDENTIFICATION_GROUP in f else None
    if ident is None or RELEASE_ID not in ident:
        return None
    return _text(ident[RELEASE_ID][()])


def _span(coords: np.ndarray, lo: float, hi: float) -> slice | None:
    idx = np.flatnonzero((coords >= lo) & (coords <= hi))
    if idx.size == 0:
        return None
    return slice(int(idx.min()), int(idx.max()) + 1)


def read_layer(path: Path, term: str, bbox_lonlat: tuple[float, float, float, float]) -> Layer:
    """Read one covariance term clipped to a lon/lat bbox (lon_min, lat_min, lon_max, lat_max)."""
    with h5py.File(path, "r") as f:
        g = f[GRID_GROUP]
        if term not in g:
            raise KeyError(f"term {term!r} not found in {path}")
        epsg = int(g[PROJECTION].attrs[EPSG_ATTR])
        lon0, lat0, lon1, lat1 = bbox_lonlat
        tr = Transformer.from_crs(4326, epsg, always_xy=True)
        xs, ys = tr.transform([lon0, lon0, lon1, lon1], [lat0, lat1, lat0, lat1])
        x_all, y_all = g[X_COORDS][:], g[Y_COORDS][:]
        xs_sl = _span(x_all, min(xs), max(xs))
        ys_sl = _span(y_all, min(ys), max(ys))
        if xs_sl is None or ys_sl is None:
            raise ValueError(f"bbox {bbox_lonlat} is outside the grid of {path}")
        sl = (ys_sl, xs_sl)
        looks = g[LOOKS][sl] if LOOKS in g else None
        mask = g[MASK][sl] if MASK in g else None
        power = apply_mask(mask_power(g[term][sl]), mask, read_release(f))
        return Layer(power, x_all[xs_sl], y_all[ys_sl], epsg, looks, mask)
