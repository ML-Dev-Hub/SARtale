"""OPERA DSWx-S1 against NISAR, on the 30 m COG grid: a low-backscatter mask, and water counts inside each site.

The mask thresholds were set on the main Tarbela pool on 26 July, a date not compared. Run from the
repository root, after opera_fetch.py and `run_pipeline rebuild`:
    conda run -n sartale python processing/checks/opera_compare.py
"""
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "processing"))
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.warp import Resampling, reproject

from sartale import config
from sartale.gcov import Layer
from sartale.references import water_agreement
from sartale.sites import RADIUS_M, _footprint

COG = ROOT / "data" / "cog"
OPERA = ROOT / "data" / "opera"
HH_LOW, HV_LOW = -12.1, -18.8
PAIRS = [("2026-09-12", "2026-09-15"), ("2026-09-12", "2026-09-16"), ("2026-09-24", "2026-09-23"),
         ("2026-10-06", "2026-10-05"), ("2026-10-18", "2026-10-17")]
TARBELA = (72.60, 34.02, 72.85, 34.30)  # west, south, east, north
index = json.loads((OPERA / "opera_index.json").read_text(encoding="utf-8"))
WATER, INVALID = set(config.DSWX_WTR_WATER_VALUES), set(config.DSWX_WTR_INVALID_VALUES)


def read_cog(d: str, pol: str):
    with rasterio.open(COG / f"{d}_{pol}.tif") as src:
        return src.read(1), src.transform, src.crs


def mosaic(day: str, shape, transform, crs) -> np.ndarray:
    """DSWx tiles of one day warped by nearest neighbour to the NISAR grid. A valid class wins over fill or a mask."""
    out = np.full(shape, config.DSWX_WTR_FILL, np.uint8)
    for entry in index[day]:
        with rasterio.open(OPERA / day / entry["file"]) as src:
            dst = np.full(shape, config.DSWX_WTR_FILL, np.uint8)
            reproject(src.read(1), dst, src_transform=src.transform, src_crs=src.crs, dst_transform=transform,
                      dst_crs=crs, resampling=Resampling.nearest, src_nodata=config.DSWX_WTR_FILL,
                      dst_nodata=config.DSWX_WTR_FILL)
        take = np.isin(out, list(INVALID)) & ~np.isin(dst, [config.DSWX_WTR_FILL])
        out[take] = dst[take]
    return out


def scores(radar: np.ndarray, dswx: np.ndarray, valid: np.ndarray) -> dict:
    ok = valid & ~np.isin(dswx, list(INVALID))
    r = water_agreement(np.where(valid, radar.astype(float), np.nan), dswx, WATER, INVALID)
    water = np.isin(dswx, list(WATER)) & ok
    low = radar & ok
    both = (water & low).sum()
    return {"n": r["n_compared"], "agreement": round(r["agreement"], 3), "all_dry": round(float(1 - water.sum() / ok.sum()), 3),
            "recall": round(float(both / water.sum()), 2), "precision": round(float(both / low.sum()), 2),
            "iou": round(float(both / (water | low).sum()), 2)}


hh, transform, crs = read_cog(PAIRS[0][0], "HH")
to_utm = Transformer.from_crs(4326, crs, always_xy=True)
c0, r0 = ~transform * to_utm.transform(TARBELA[0], TARBELA[3])
c1, r1 = ~transform * to_utm.transform(TARBELA[2], TARBELA[1])
box = np.zeros(hh.shape, bool)
box[int(r0):int(r1), int(c0):int(c1)] = True

mosaics = {}
for build, near in PAIRS:
    hh, _, _ = read_cog(build, "HH")
    hv, _, _ = read_cog(build, "HV")
    dswx = mosaics.setdefault(near, mosaic(near, hh.shape, transform, crs))
    valid = np.isfinite(hh) & np.isfinite(hv)
    days = abs((date.fromisoformat(build) - date.fromisoformat(near)).days)
    low = (hh < HH_LOW) & (hv < HV_LOW)
    print(build, near, f"{days} d", "window", scores(low, dswx, valid), "Tarbela box", scores(low, dswx, valid & box))

for extra in sorted(set(index) - set(mosaics)):
    mosaics[extra] = mosaic(extra, hh.shape, transform, crs)
x = transform.c + (np.arange(hh.shape[1]) + 0.5) * transform.a
y = transform.f + (np.arange(hh.shape[0]) + 0.5) * transform.e
grid = Layer(hh, x, y, crs.to_epsg(), None, None)
sites = json.loads((ROOT / "processing" / "sites_in.json").read_text(encoding="utf-8"))
days = sorted(mosaics)
print("water pixels of valid pixels inside each site, on the NISAR grid:", ", ".join(days))
for s in sites:
    inside = _footprint(grid, s["lon"], s["lat"], RADIUS_M)
    cells = []
    for d in days:
        v = mosaics[d][inside]
        ok = ~np.isin(v, list(INVALID))
        cells.append(f"{int(np.isin(v, list(WATER)).sum())}/{int(ok.sum())}")
    print(f"  {s['id']:16s} {int(inside.sum()):3d} px  " + "  ".join(cells))
