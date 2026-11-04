"""Wide, clear Sentinel-2 true-colour view of the Hunza valley for the opening shot (sartale env):

    python video/story/fetch_wide.py 2026-07-20

Writes out/img/hunza_wide_<date>.png (UTM 43N, 25 m) and out/img/hunza_wide.json with the image bounds,
so lake pins can be placed from lakes_in.json coordinates.
"""
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import reproject, transform_bounds

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "processing"))
from sartale.lakecheck import _window, search_scenes  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "img"
BBOX = (74.45, 36.24, 75.00, 36.54)  # lon/lat: Hassanabad and Shisper to Passu and Attabad
UTM = 32643
RES = 25.0


def main(day):
    feats = [f for f in search_scenes(BBOX, day, day) if "_43SDA_" in f["id"]]
    f = feats[0]
    west, south, east, north = transform_bounds(CRS.from_epsg(4326), CRS.from_epsg(UTM), *BBOX)
    w, h = int((east - west) / RES), int((north - south) / RES)
    dst_tf = from_bounds(west, south, east, north, w, h)
    dst = np.zeros((3, h, w), np.float32)
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif"):
        with rasterio.open(f["assets"]["visual"]["href"]) as s:
            sb = transform_bounds(CRS.from_epsg(UTM), s.crs, west, south, east, north, densify_pts=21)
            win = _window(*sb, s.transform).round_offsets().round_lengths()
            shape = (3, int(win.height * 10 / RES), int(win.width * 10 / RES))
            a = s.read([1, 2, 3], window=win, out_shape=shape, boundless=True, fill_value=0,
                       resampling=Resampling.average)
            stf = rasterio.windows.transform(win, s.transform) * rasterio.Affine.scale(win.width / shape[2], win.height / shape[1])
            for i in range(3):
                reproject(a[i].astype(np.float32), dst[i], src_transform=stf, src_crs=s.crs, dst_transform=dst_tf,
                          dst_crs=CRS.from_epsg(UTM), resampling=Resampling.bilinear)
    Image.fromarray(np.clip(np.moveaxis(dst, 0, -1), 0, 255).astype(np.uint8)).save(OUT / f"hunza_wide_{day}.png")
    json.dump({"scene": f["id"], "date": day, "epsg": UTM, "bounds": [west, south, east, north], "size": [w, h]},
              open(OUT / "hunza_wide.json", "w"), indent=1)
    print(f["id"], w, h, "present", float((dst[0] > 0).mean()))


if __name__ == "__main__":
    main(sys.argv[1])
