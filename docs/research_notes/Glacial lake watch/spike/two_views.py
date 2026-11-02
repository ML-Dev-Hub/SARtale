"""Spike: water = dark in BOTH an ascending and a descending view (shadow is dark in only one).

Per geometry: per-pixel median over passes (robust to a bad pass), then dark if HH and HV are both
`drop` dB below that view's scene median. Usage: python two_views.py indir out.png asc_key desc_key [drop]
"""
import glob
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

indir, out, asc, desc = sys.argv[1:5]
drop = float(sys.argv[5]) if len(sys.argv) > 5 else 4.0


def stack(key):
    fs = sorted(glob.glob(str(Path(indir) / f"*_{key}.npz")))
    ds = [np.load(f) for f in fs]
    x, y = ds[0]["x"], ds[0]["y"]
    for d in ds:
        assert np.array_equal(d["x"], x) and np.array_equal(d["y"], y), "grids differ"
    db = {k: np.nanmedian([10 * np.log10(np.where(d[k] > 0, d[k], np.nan)) for d in ds], axis=0) for k in ("hh", "hv")}
    dark = (db["hh"] < np.nanmedian(db["hh"]) - drop) & (db["hv"] < np.nanmedian(db["hv"]) - drop)
    return db, dark, x, y, len(fs)


a_db, a_dark, x, y, na = stack(asc)
d_db, d_dark, x2, y2, nd = stack(desc)
assert np.array_equal(x, x2) and np.array_equal(y, y2), "asc/desc grids differ"
both = a_dark & d_dark
print(f"{asc}: {na} passes, dark {a_dark.mean():.2%} | {desc}: {nd} passes, dark {d_dark.mean():.2%} | both {both.mean():.2%}"
      f" = {both.sum() * 100 / 1e6:.2f} km2")
ext = [x[0] / 1e3, x[-1] / 1e3, y[-1] / 1e3, y[0] / 1e3]
fig, ax = plt.subplots(1, 3, figsize=(15, 5))
for a, img, t in [(ax[0], a_dark, f"dark in {asc}"), (ax[1], d_dark, f"dark in {desc}"), (ax[2], both, "dark in BOTH = water")]:
    a.imshow(img, extent=ext, cmap="Blues")
    a.set_title(t)
    a.tick_params(labelsize=6)
fig.tight_layout()
fig.savefig(out, dpi=75)
