"""Read clipped layers from NISAR GCOV HDF5 files."""
from dataclasses import dataclass
from pathlib import Path

import h5py
import numpy as np
from pyproj import Transformer

from sartale.radiometry import mask_power

# NOTE: this layout follows the public NISAR GCOV docs and the NISAR/ISCE3
# convention. It has been run on two public NISAR sample GCOV files dated 2008
# (older product versions over a different area), which confirmed the coordinate,
# projection, mask and looks layout. It has NOT been run on a real P05023 file
# (no Earthdata login). If a real file differs, fix it here only.
GRID_GROUP = "/science/LSAR/GCOV/grids/frequencyA"
LOOKS = "numberOfLooks"
MASK = "mask"
X_COORDS = "xCoordinates"
Y_COORDS = "yCoordinates"
PROJECTION = "projection"
EPSG_ATTR = "epsg_code"


@dataclass
class Layer:
    power: np.ndarray
    x: np.ndarray
    y: np.ndarray
    epsg: int
    looks: np.ndarray | None
    mask: np.ndarray | None


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
        power = mask_power(g[term][sl])
        looks = g[LOOKS][sl] if LOOKS in g else None
        mask = g[MASK][sl] if MASK in g else None
        return Layer(power, x_all[xs_sl], y_all[ys_sl], epsg, looks, mask)
