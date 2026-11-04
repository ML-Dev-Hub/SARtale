"""Real imagery for the story video: a cloudy Sentinel-2 true-colour view and a NISAR HH view of the same
6 km Attabad window, plus the Shisper window. Run in the `sartale` env from the repo root:

    python video/story/fetch_imagery.py

Writes out/img/<lake>_s2_<date>.png (cloudiest usable scene in the cloud window) and
out/img/<lake>_nisar_<date>.png (the NISAR pass nearest that date), and prints the pair it chose.
"""
import json
import sys
from datetime import date as Date
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.warp import reproject, transform_bounds

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "processing"))
from sartale.lakecheck import _window, search_scenes  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "img"
OUT.mkdir(parents=True, exist_ok=True)
WINDOW = ("2026-06-17", "2026-08-04")
ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
           GDAL_HTTP_MAX_RETRY="3", GDAL_HTTP_RETRY_DELAY="2")


def grid(npz):
    d = np.load(npz)
    x, y, epsg = d["x"].astype(float), d["y"].astype(float), int(d["epsg"])
    dx, dy = x[1] - x[0], y[1] - y[0]
    tf = Affine(dx, 0, x[0] - dx / 2, 0, dy, y[0] - dy / 2)
    b = (x.min() - abs(dx) / 2, y.min() - abs(dy) / 2, x.max() + abs(dx) / 2, y.max() + abs(dy) / 2)
    return d, tf, (len(y), len(x)), epsg, b


def read_on_grid(href, tf, shape, epsg, bounds, bands, resampling=Resampling.bilinear):
    """Read `bands` of a COG window covering `bounds` and reproject onto the NISAR grid."""
    with rasterio.open(href) as s:
        sb = transform_bounds(CRS.from_epsg(epsg), s.crs, *bounds, densify_pts=21)
        win = _window(*sb, s.transform).round_offsets().round_lengths()
        a = s.read(bands, window=win, boundless=True, fill_value=0)
        stf, scrs = s.window_transform(win), s.crs
    dst = np.zeros((len(bands), *shape), np.float32)
    for i in range(len(bands)):
        reproject(a[i].astype(np.float32), dst[i], src_transform=stf, src_crs=scrs, dst_transform=tf,
                  dst_crs=CRS.from_epsg(epsg), resampling=resampling)
    return dst


def nisar_png(d, out):
    hh = 10 * np.log10(np.where(d["hh"] > 0, d["hh"], np.nan))
    lo, hi = np.nanpercentile(hh, [2, 98])
    v = np.clip((hh - lo) / (hi - lo), 0, 1) ** 0.9
    Image.fromarray((np.nan_to_num(v) * 255).astype(np.uint8)).save(out)


def main(lake):
    lon, lat = {l["id"]: (l["lon"], l["lat"]) for l in json.load(open(ROOT / "processing" / "lakes_in.json", encoding="utf8"))}[lake]
    passes = sorted((ROOT / "data" / "lakes" / lake).glob("*.npz"))
    _, tf, shape, epsg, bounds = grid(passes[0])
    bbox = (lon - 0.03, lat - 0.03, lon + 0.03, lat + 0.03)
    best = None
    with rasterio.Env(**ENV):
        for f in search_scenes(bbox, *WINDOW):
            a = f["assets"]
            scl = read_on_grid(a["scl"]["href"], tf, shape, epsg, bounds, [1], Resampling.nearest)[0]
            present = (scl > 0).mean()
            cloud = np.isin(scl, (8, 9, 10)).mean()
            day = f["properties"]["datetime"][:10]
            print(f"{day} {f['id']}: present {present:.2f}, cloud {cloud:.2f}")
            # most cloud over the window while the scene still covers it, and not the whole window white
            if present > 0.98 and 0.45 < cloud < 0.97 and (best is None or cloud > best[0]):
                best = (cloud, day, f)
        if best is None:
            sys.exit("no cloudy scene found")
        cloud, day, f = best
        rgb = read_on_grid(f["assets"]["visual"]["href"], tf, shape, epsg, bounds, [1, 2, 3])
    Image.fromarray(np.clip(np.moveaxis(rgb, 0, -1), 0, 255).astype(np.uint8)).save(OUT / f"{lake}_s2_{day}.png")
    target = Date.fromisoformat(day)
    near = min(passes, key=lambda p: abs((Date.fromisoformat(p.name[:10]) - target).days))
    nisar_png(np.load(near), OUT / f"{lake}_nisar_{near.name[:10]}.png")
    print(f"CHOSEN {lake}: Sentinel-2 {day} ({f['id']}, window cloud {cloud:.0%}) vs NISAR {near.name}")


if __name__ == "__main__":
    for lake in sys.argv[1:] or ["attabad", "shisper"]:
        main(lake)
