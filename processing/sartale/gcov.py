"""Read clipped layers from NISAR GCOV HDF5 files."""
from dataclasses import dataclass
from pathlib import Path

import h5py
import numpy as np
from pyproj import Transformer

from sartale.radiometry import mask_power

# NOTE: this layout follows the public NISAR GCOV docs and the NISAR/ISCE3
# convention. The reader was run on two public single-pol NISAR sample GCOV files
# dated 2008 (older product versions over a different area), which confirmed the
# coordinate, projection and looks layout. Those samples have no HV term, and their
# mask holds only 0 and 255, so they cannot confirm what the mask values mean on a
# real file. The HV term and the P05023 files are still unread until the first real
# run (the Earthdata login now works). If a real file differs, fix it here only.
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

    A renamed file must never be labelled with another granule's name or as Provisional P05023.
    The granule ID is required. The release ID is compared only where the file has the field.
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


def apply_mask(power: np.ndarray, mask: np.ndarray | None) -> np.ndarray:
    """Set invalid GCOV samples to NaN, using the mask clipped to the same window as `power`.

    Fill (255) is always NaN. Zero (partially focused or invalid) is NaN only when the clip also holds
    real subswath numbers (1 to 254); a product whose mask holds only 0 and 255, like the 2008 samples,
    keeps its zeros.
    """
    if mask is None:
        return power
    mask = np.asarray(mask)
    if mask.shape != power.shape:
        raise ValueError(f"mask shape {mask.shape} does not match power shape {power.shape}")
    out = np.array(power, dtype=np.float64, copy=True)
    bad = mask == MASK_FILL
    if ((mask >= 1) & (mask < MASK_FILL)).any():
        bad |= mask == MASK_INVALID
    out[bad] = np.nan
    return out


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
        power = apply_mask(mask_power(g[term][sl]), mask)
        return Layer(power, x_all[xs_sl], y_all[ys_sl], epsg, looks, mask)
