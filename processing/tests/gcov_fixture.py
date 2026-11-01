"""Shared synthetic GCOV HDF5 builder for tests (not real NISAR data)."""
import h5py
import numpy as np
from pyproj import Transformer

from sartale import gcov

EPSG = 32642
N = 100
STEP = 100.0  # metres
CENTER_LONLAT = (71.75, 34.15)


def write_gcov(path, descending_y=False, seed=0, scale=1.0, dx=0.0, mask=None,
               granule_id=None, release_id=None):
    """Write a small GCOV-like file. `dx` shifts the x grid (metres); `scale` multiplies power.

    `mask` is a (N, N) uint8 array (default all ones: subswath 1 everywhere). With `granule_id`
    the file gets /science/LSAR/identification/granuleId, and with `release_id` compositeReleaseId.
    """
    cx, cy = Transformer.from_crs(4326, EPSG, always_xy=True).transform(*CENTER_LONLAT)
    x = cx + (np.arange(N) - N / 2) * STEP + dx
    y = cy + (np.arange(N) - N / 2) * STEP
    if descending_y:
        y = y[::-1]
    rng = np.random.default_rng(seed)
    with h5py.File(path, "w") as f:
        g = f.create_group(gcov.GRID_GROUP)
        for term in ("HHHH", "HVHV"):
            d = (rng.uniform(0.01, 1.0, (N, N)) * scale).astype("f4")
            d[0, 0] = 0.0  # invalid sample
            g.create_dataset(term, data=d)
        g.create_dataset(gcov.LOOKS, data=np.full((N, N), 5.0, "f4"))
        g.create_dataset(gcov.MASK, data=np.ones((N, N), "u1") if mask is None else np.asarray(mask, "u1"))
        g.create_dataset(gcov.X_COORDS, data=x)
        g.create_dataset(gcov.Y_COORDS, data=y)
        p = g.create_dataset(gcov.PROJECTION, data=np.uint32(EPSG))
        p.attrs[gcov.EPSG_ATTR] = EPSG
        if granule_id is not None or release_id is not None:
            ident = f.create_group(gcov.IDENTIFICATION_GROUP)
            if granule_id is not None:
                ident.create_dataset(gcov.GRANULE_ID, data=np.bytes_(granule_id))
            if release_id is not None:
                ident.create_dataset(gcov.RELEASE_ID, data=np.bytes_(release_id))
    return path
