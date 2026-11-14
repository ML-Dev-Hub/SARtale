"""Radar layover and shadow from the Copernicus GLO-30 DEM, for the window statistics of lake water (method D17).

Water is HH at least DROP_DB below the window-median HH. Steep valley walls in layover (bright) or shadow (dark) pull
that median about, so they are left out of it. Inside the lake zone nothing is masked: a flat lake surface is almost
never in layover or shadow (.superpowers/sdd/post-merge/method-study.md, "DEM layover+shadow mask").

The viewing geometry is not read from the product: the look azimuth was fitted to GCOV's own numberOfLooks layer (looks
grow with the sine of the local incidence angle). Ascending tracks fit best at 250-265 degrees and descending ones at
100-105 degrees (NISAR looks left); config.DEM_LOOK_AZIMUTH_DEG holds 255 and 105. The incidence angle cannot be fitted
that way; config.DEM_INCIDENCE_DEG is 40 (33 and 47 gave the same water).

The DEM is read once per lake grid from Earth Search's Copernicus DEM collection (open, no login) and kept next to the
lake's NISAR windows (`<cache>/<lake>/dem/`), with the masks it gives. Without it (no network, or SARTALE_DEM_OFFLINE set),
`stat_masks` returns None and the median uses every valid pixel; the lake then carries a limit that says so.
"""
from __future__ import annotations

import hashlib
import os
import threading
import zlib
from pathlib import Path

import numpy as np

from sartale import config

STAC_URL = "https://earth-search.aws.element84.com/v1/search"
DEM_COLLECTION = "cop-dem-glo-30"
SOURCE = "Copernicus DEM GLO-30 (Earth Search)"
OFFLINE_ENV = "SARTALE_DEM_OFFLINE"
NO_DEM_LIMIT = ("no Copernicus DEM for this build: the window median that water is measured against uses every valid "
                "pixel, terrain in radar layover or shadow included")

# Every pass of a lake on one grid shares one DEM file, which `stat_masks` reads, adds its look direction's mask to and
# writes back. Workers that measure passes at the same time (lakes-fetch processes, lakes-check threads) take the lock of
# the file first, so no mask is lost and the file is downloaded once. Locks are striped by a stable hash of the path (not
# `hash()`, which differs per process). In one process these are thread locks; lakes-fetch hands its worker processes
# locks shared between them (`set_locks`).
_LOCKS: list = [threading.Lock() for _ in range(16)]


def set_locks(locks) -> None:
    """Use `locks` (a non-empty list of lock objects, e.g. multiprocessing locks shared by worker processes)."""
    global _LOCKS
    _LOCKS = list(locks)


def _lock_for(path: Path):
    key = os.path.normcase(os.path.abspath(path)).encode("utf-8", "surrogatepass")
    return _LOCKS[zlib.crc32(key) % len(_LOCKS)]


def local_incidence(dem: np.ndarray, px: float, look_az_deg: float, inc_deg: float) -> np.ndarray:
    """Local incidence angle (degrees) in the plane of the look, for a look of ground azimuth `look_az_deg` (from the
    radar toward the ground; from north, clockwise) and incidence `inc_deg`, on a north-up grid of `px` metres. A slope
    rising away from the radar faces it and lowers the angle; at 0 or below the pixel is in layover."""
    gy, gx = np.gradient(np.asarray(dem, np.float64), px)  # rows run south, so gy is the southward slope
    a = np.radians(look_az_deg)
    rise = gx * np.sin(a) - gy * np.cos(a)  # slope along the look direction
    return inc_deg - np.degrees(np.arctan(rise))


def cast_shadow(dem: np.ndarray, px: float, look_az_deg: float, inc_deg: float, max_m: float) -> np.ndarray:
    """Pixels hidden from the radar by terrain between them and it: marching toward the radar in nearest-pixel steps
    up to `max_m`, any point above the ray at `inc_deg` from the vertical shadows the pixel (0.5 m tolerance)."""
    d = np.nan_to_num(np.asarray(dem, np.float64), nan=float(np.nanmin(dem)))
    h, w = d.shape
    a = np.radians(look_az_deg)
    de, dn = -np.sin(a), -np.cos(a)  # toward the radar: east = +column, north = -row
    cot = 1.0 / np.tan(np.radians(inc_deg))
    shadow = np.zeros((h, w), bool)
    for k in range(1, int(max_m / px) + 1):
        dc, dr = int(round(k * de)), int(round(-k * dn))
        r0, r1 = max(0, -dr), min(h, h - dr)
        c0, c1 = max(0, -dc), min(w, w - dc)
        if r0 >= r1 or c0 >= c1:
            break
        src = d[r0 + dr:r1 + dr, c0 + dc:c1 + dc]
        shadow[r0:r1, c0:c1] |= src - k * px * cot > d[r0:r1, c0:c1] + 0.5
    return shadow


def layover_shadow(dem_big: np.ndarray, px: float, margin: int, look_az_deg: float,
                   inc_deg: float = config.DEM_INCIDENCE_DEG) -> np.ndarray:
    """Layover or shadow on the window (the DEM `dem_big` carries `margin` extra pixels on every side)."""
    li = local_incidence(dem_big, px, look_az_deg, inc_deg)
    unseen = (li <= 0) | (li >= 90) | cast_shadow(dem_big, px, look_az_deg, inc_deg, margin * px)
    return unseen[margin:dem_big.shape[0] - margin, margin:dem_big.shape[1] - margin]


def read_dem(xs: np.ndarray, ys: np.ndarray, epsg: int, margin: int) -> np.ndarray:
    """GLO-30 on the window grid (pixel centres `xs`, `ys` in `epsg`) grown by `margin` pixels on every side, bilinear.
    Raises when Earth Search or a tile cannot be read, or when the DEM leaves the grid without a value."""
    import rasterio
    import requests
    from pyproj import Transformer
    from rasterio.crs import CRS
    from rasterio.enums import Resampling
    from rasterio.transform import Affine
    from rasterio.warp import reproject

    dx, dy = float(xs[1] - xs[0]), float(ys[1] - ys[0])
    X = np.concatenate([xs[0] + dx * np.arange(-margin, 0), xs, xs[-1] + dx * np.arange(1, margin + 1)])
    Y = np.concatenate([ys[0] + dy * np.arange(-margin, 0), ys, ys[-1] + dy * np.arange(1, margin + 1)])
    to_ll = Transformer.from_crs(epsg, 4326, always_xy=True)
    corners = [to_ll.transform(a, b) for a in (X[0], X[-1]) for b in (Y[0], Y[-1])]
    lons, lats = [c[0] for c in corners], [c[1] for c in corners]
    body = {"collections": [DEM_COLLECTION], "bbox": [min(lons), min(lats), max(lons), max(lats)], "limit": 20}
    r = requests.post(STAC_URL, json=body, timeout=60)
    r.raise_for_status()
    items = r.json().get("features") or []
    if not items:
        raise RuntimeError("no Copernicus DEM tile over the window")
    transform = Affine(dx, 0, X[0] - dx / 2, 0, dy, Y[0] - dy / 2)
    out = np.full((len(Y), len(X)), np.nan, np.float32)
    env = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
               GDAL_HTTP_MAX_RETRY="3", GDAL_HTTP_RETRY_DELAY="2")
    for it in items:
        href = it["assets"]["data"]["href"].replace("s3://copernicus-dem-30m/",
                                                    "https://copernicus-dem-30m.s3.amazonaws.com/")
        with rasterio.Env(**env), rasterio.open(href) as ds:
            tile = np.full(out.shape, np.nan, np.float32)
            reproject(ds.read(1).astype(np.float32), tile, src_transform=ds.transform, src_crs=ds.crs,
                      dst_transform=transform, dst_crs=CRS.from_epsg(epsg), resampling=Resampling.bilinear,
                      dst_nodata=np.nan)
        out = np.where(np.isfinite(tile), tile, out)
    if not np.isfinite(out).all():
        raise RuntimeError("the Copernicus DEM leaves part of the window without a value")
    return out


def grid_key(xs, ys, epsg: int) -> str:
    """A short name for a window grid (CRS, origin, size, spacing): the DEM is kept per grid."""
    text = f"{epsg}|{float(xs[0]):.2f}|{float(ys[0]):.2f}|{len(xs)}|{len(ys)}|{float(xs[1] - xs[0]):.3f}"
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def stat_masks(lake_dir: Path, xs, ys, epsg: int, directions, log=print) -> dict[str, np.ndarray] | None:
    """Per viewing direction ("A", "D") in `directions`: True where the window is in radar layover or shadow, to leave
    out of the window median. Read from `<lake_dir>/dem/` when kept there, else built from GLO-30 and kept. None when
    the DEM cannot be had (no network, or SARTALE_DEM_OFFLINE set and nothing kept); never raises for that."""
    if len(xs) < 2 or len(ys) < 2:
        return None
    px = abs(float(xs[1] - xs[0]))
    margin = int(round(config.DEM_MARGIN_M / px))
    path = Path(lake_dir) / "dem" / f"glo30_{grid_key(xs, ys, epsg)}.npz"
    with _lock_for(path):
        return _stat_masks_locked(path, xs, ys, epsg, px, margin, directions, lake_dir, log)


def _stat_masks_locked(path: Path, xs, ys, epsg: int, px: float, margin: int, directions, lake_dir, log):
    """`stat_masks` once the DEM file's lock is held. The file is written with its entries in one order (the DEM,
    then the masks by name), so it is the same whichever direction's mask was added first."""
    kept: dict[str, np.ndarray] = {}
    if path.is_file():
        with np.load(path) as z:
            kept = {k: z[k] for k in z.files}
    if "dem" not in kept:
        if os.environ.get(OFFLINE_ENV):
            return None
        try:
            kept = {"dem": read_dem(np.asarray(xs, float), np.asarray(ys, float), epsg, margin)}
        except Exception as e:  # noqa: BLE001 - the build goes on without the mask, and the lake says so
            log(f"{Path(lake_dir).name}: Copernicus DEM not read ({type(e).__name__}: {e}); window statistics "
                "use every valid pixel")
            return None
    out: dict[str, np.ndarray] = {}
    changed = not path.is_file()
    for d in sorted(set(directions)):
        az = config.DEM_LOOK_AZIMUTH_DEG.get(d)
        if az is None:
            continue
        name = f"mask_{d}_{az:g}_{config.DEM_INCIDENCE_DEG:g}_{margin}"
        if name not in kept:
            kept[name] = layover_shadow(kept["dem"], px, margin, az)
            changed = True
        out[d] = np.asarray(kept[name], bool)
    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.stem + ".tmp.npz")
        np.savez_compressed(tmp, **{k: kept[k] for k in ["dem", *sorted(set(kept) - {"dem"})]})
        os.replace(tmp, path)
    return out
