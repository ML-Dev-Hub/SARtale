"""Shift of each date against 26 July, by FFT cross-correlation of 30 m HH, with a sub-pixel peak.

Run from the repository root after `run_pipeline rebuild`:
    conda run -n sartale python processing/checks/shifts.py
"""
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[2]
COG = ROOT / "data" / "cog"
REFERENCE = "2026-07-26"
TILES = {"Peshawar plain": (2400, 1100), "Swabi": (2000, 3200), "Tarbela": (2000, 4700)}
N = 1024
dates = sorted(p.name[:10] for p in COG.glob("*_HH.tif"))


def tile(date: str, r0: int, c0: int) -> np.ndarray:
    with rasterio.open(COG / f"{date}_HH.tif") as src:
        a = src.read(1, window=((r0, r0 + N), (c0, c0 + N)))
    a = np.nan_to_num(a, nan=np.nanmedian(a))
    return (a - a.mean()) * np.outer(np.hanning(N), np.hanning(N))


for name, (r0, c0) in TILES.items():
    ref = np.fft.rfft2(tile(REFERENCE, r0, c0))
    for d in dates:
        cc = np.fft.fftshift(np.fft.irfft2(ref * np.conj(np.fft.rfft2(tile(d, r0, c0)))))
        r, c = np.unravel_index(np.argmax(cc), cc.shape)
        sub = [0.5 * (lo - hi) / (lo - 2 * cc[r, c] + hi)
               for lo, hi in ((cc[r - 1, c], cc[r + 1, c]), (cc[r, c - 1], cc[r, c + 1]))]
        dy, dx = r - N // 2 + sub[0], c - N // 2 + sub[1]
        print(f"{name:15s} {d} {np.hypot(dx, dy) * 30:5.1f} m")
