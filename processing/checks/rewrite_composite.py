"""Rewrite only the seasonal composite and the manifest's composite_dates, from the 30 m COGs.

For a change of composite dates that should not re-encode the other web frames. It follows `build`:
linear power, one more multilook, the manifest's shared HH stretch, the same window and width cap.
Run from the repository root: conda run -n sartale python processing/checks/rewrite_composite.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "processing"))
import numpy as np
import rasterio

from sartale import config
from sartale.gcov import Layer
from sartale.products import (
    DISPLAY_LOOKS,
    DISPLAY_MAX_WIDTH,
    composite_choice,
    multilook_layer,
    seasonal_composite,
    write_webp_3857,
)
from sartale.radiometry import to_db

OUT = ROOT / "app" / "public" / "data"
COG = ROOT / "data" / "cog"
manifest_path = OUT / "manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
dates = [e["date"] for e in manifest["dates"]]
flagged = {e["date"] for e in manifest["dates"] if e.get("flag")}
chosen = [dates[i] for i in composite_choice(dates, flagged)]


def coarse(date: str) -> Layer:
    with rasterio.open(COG / f"{date}_HH.tif") as src:
        db, t = src.read(1), src.transform
        epsg = src.crs.to_epsg()
    x = t.c + (np.arange(db.shape[1]) + 0.5) * t.a
    y = t.f + (np.arange(db.shape[0]) + 0.5) * t.e
    return multilook_layer(Layer(10 ** (db / 10), x, y, epsg, None, None), DISPLAY_LOOKS)


layers = [coarse(d) for d in chosen]
rgba = seasonal_composite(*[to_db(layer.power) for layer in layers], tuple(manifest["stretch_db"]["HH"]))
bounds = write_webp_3857(rgba, layers[0], OUT / manifest["composite"], window=config.WINDOW, max_width=DISPLAY_MAX_WIDTH)
manifest["composite_dates"] = chosen
manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(chosen, (OUT / manifest["composite"]).stat().st_size, bounds)
