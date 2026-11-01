"""The numbers behind the change layer's verdict, from the score COGs, the 30 m COGs and the OPERA tiles.

Prints: flagged share per date for controls, known changes, the plain box and the whole window, at the manifest's
threshold and two others; the shore split by what its pixels did; OPERA DSWx-S1 inside two boxes; and the 2 July and
6 October checks. Run from the repository root, after `run_pipeline change` and opera_fetch.py:
    conda run -n sartale python processing/checks/change_evidence.py
"""
import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "processing"))
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.warp import Resampling, reproject

from sartale import config
from sartale.change import _read_cog
from sartale.products import INTERFERENCE_DATE
from sartale.sites import RADIUS_M, _footprint

warnings.simplefilter("ignore", RuntimeWarning)  # nanmedian over the masked pixels
COG = ROOT / "data" / "cog"
OPERA = ROOT / "data" / "opera"
HH_LOW, HV_LOW = -12.1, -18.8  # the radar water-like mask of opera_compare.py
FARM_BOX = (72.10, 34.10, 72.25, 34.28)  # the plain box of july2.py; land cover not checked
TARBELA_BOX = (72.60, 34.00, 72.90, 34.30)  # opera_compare.py's box, widened to hold the shore site
ATTOCK_BOX = (72.15, 33.87, 72.32, 33.96)
OCT6_PATCH = (71.82, 34.29, 72.15, 34.46)  # the largest patch on 6 October, found from 10 km cells
OCT6_CLUSTER = (72.0175, 34.1902)  # the cluster rejected as a control in DATA_SOURCES.md
PAIRS = {"2026-09-12": "2026-09-15", "2026-09-24": "2026-09-23", "2026-10-06": "2026-10-05", "2026-10-18": "2026-10-17"}
DAYS_APART = {"2026-09-12": 3, "2026-09-24": 1, "2026-10-06": 1, "2026-10-18": 1}

manifest = json.loads((ROOT / "app" / "public" / "data" / "manifest.json").read_text(encoding="utf-8"))
change = manifest["change"]
threshold = change["threshold"]
dates = list(change["frames"])
sites = {s["id"]: s for s in json.loads((ROOT / "processing" / "sites_in.json").read_text(encoding="utf-8"))}
curves = {s["id"]: s for s in json.loads((ROOT / "app" / "public" / "data" / "sites.json").read_text(encoding="utf-8"))}

score, grid = None, None
scores = []
for d in dates:
    score, grid = _read_cog(COG / f"change_{d}.tif")
    scores.append(score)
scores = np.stack(scores)
hh = np.stack([_read_cog(COG / f"{d}_HH.tif")[0] for d in dates])
hv = np.stack([_read_cog(COG / f"{d}_HV.tif")[0] for d in dates])
to_utm = Transformer.from_crs(4326, grid.epsg, always_xy=True)


def box(bounds: tuple[float, float, float, float]) -> np.ndarray:
    x0, y0 = to_utm.transform(bounds[0], bounds[1])
    x1, y1 = to_utm.transform(bounds[2], bounds[3])
    return np.outer((grid.y >= min(y0, y1)) & (grid.y <= max(y0, y1)), (grid.x >= min(x0, x1)) & (grid.x <= max(x0, x1)))


def disc(site: str, radius: float = RADIUS_M) -> np.ndarray:
    return _footprint(grid, sites[site]["lon"], sites[site]["lat"], radius)


def shares(mask: np.ndarray, level: float) -> list[float]:
    """Percent of the scored pixels in the mask above the level, per date."""
    v = scores[:, mask]
    return [100 * float((row[np.isfinite(row)] > level).mean()) for row in v]


def row(name: str, values: list[float], fmt: str = "5.1f") -> None:
    print(f"  {name:34s} " + " ".join(f"{v:{fmt}}" for v in values))


print("dates: " + " ".join(d[5:] for d in dates))
print(f"threshold {threshold}; baseline {', '.join(change['baseline_dates'])}")
print("removed offsets dB: " + json.dumps(change["removed_offsets_db"]))

controls = ["peshawar-city", "hazro-built-up", "tarbela-pool"]
pooled = scores[:, np.any([disc(c) for c in controls], axis=0)]
pooled = pooled[np.isfinite(pooled)]
print(f"pooled control pixels {pooled.size}: percentiles 50, 90, 95, 99, 99.5, max "
      + " ".join(f"{v:.2f}" for v in np.percentile(pooled, [50, 90, 95, 99, 99.5, 100])))

areas = {
    "Peshawar 150 m": disc("peshawar-city"),
    "Peshawar 500 m": disc("peshawar-city", 500),
    "Hazro 150 m": disc("hazro-built-up"),
    "Hazro 500 m": disc("hazro-built-up", 500),
    "Tarbela pool 150 m": disc("tarbela-pool"),
    "Tarbela pool 1 km": disc("tarbela-pool", 1000),
    "Tarbela shore 150 m": disc("tarbela-shore"),
    "Indus at Attock 150 m": disc("indus-attock"),
    "Plain east of Mardan 150 m": disc("mardan-plain"),
    "Plain near Swabi 150 m": disc("swabi-plain"),
    "Plain box (72.10-72.25E)": box(FARM_BOX),
    "Tarbela box": box(TARBELA_BOX),
    "Attock box": box(ATTOCK_BOX),
    "Whole window": np.isfinite(scores[0]),
}
for level in (threshold - 0.5, threshold, threshold + 0.5):
    print(f"percent of pixels above {level}")
    for name, mask in areas.items():
        row(name, shares(mask, level))

print("site change_score (median pixel score), then HH and HV of the curve")
for sid, s in curves.items():
    row(sid, [p["change_score"] if p["change_score"] is not None else float("nan") for p in s["series"]], "6.2f")

print("Tarbela box: pixels bright on 26 Jul (HH > -10) and dark on 19 and 31 Aug (HH < -13), by late dates still dark")
print("  (selected on those dates, so high scores on them are partly built in; a description, not a test)")
tb = box(TARBELA_BOX)
i26, i19, i31 = dates.index("2026-07-26"), dates.index("2026-08-19"), dates.index("2026-08-31")
went_dark = tb & (hh[i26] > -10) & (hh[i19] < -13) & (hh[i31] < -13)
late = [dates.index(d) for d in ("2026-09-24", "2026-10-06", "2026-10-18")]
still_dark = (hh[late] < -12).sum(axis=0)
for k in range(4):
    m = went_dark & (still_dark == k)
    if m.any():
        row(f"dark on {k} of 3 late dates, n={int(m.sum())}", shares(m, threshold))
        row("  median score", [float(np.nanmedian(scores[i][m])) for i in range(len(dates))], "5.2f")

print("OPERA DSWx-S1 inside the boxes. DSWx change: the tile's water state differs from the other three tiles' majority.")
print("Flagged water-like change: above threshold, and water-like by the radar mask on the date xor in the other dates' median.")
index = json.loads((OPERA / "opera_index.json").read_text(encoding="utf-8"))
water, invalid = list(config.DSWX_WTR_WATER_VALUES), list(config.DSWX_WTR_INVALID_VALUES)
with rasterio.open(COG / f"{dates[0]}_HH.tif") as src:
    transform, crs, shape = src.transform, src.crs, src.shape


def mosaic(day: str) -> np.ndarray:
    """DSWx tiles of one day warped by nearest neighbour to the NISAR grid, as in opera_compare.py."""
    out = np.full(shape, config.DSWX_WTR_FILL, np.uint8)
    for entry in index[day]:
        with rasterio.open(OPERA / day / entry["file"]) as src:
            dst = np.full(shape, config.DSWX_WTR_FILL, np.uint8)
            reproject(src.read(1), dst, src_transform=src.transform, src_crs=src.crs, dst_transform=transform,
                      dst_crs=crs, resampling=Resampling.nearest, src_nodata=config.DSWX_WTR_FILL,
                      dst_nodata=config.DSWX_WTR_FILL)
        take = np.isin(out, invalid) & (dst != config.DSWX_WTR_FILL)
        out[take] = dst[take]
    return out


tiles = {d: mosaic(day) for d, day in PAIRS.items()}
is_water = {d: np.isin(t, water) for d, t in tiles.items()}
all_valid = np.all([~np.isin(t, invalid) for t in tiles.values()], axis=0)
base_idx = [dates.index(d) for d in change["baseline_dates"]]
for name, bounds in (("Tarbela", TARBELA_BOX), ("Attock", ATTOCK_BOX)):
    area = box(bounds) & all_valid & np.isfinite(scores[0])
    for d in PAIRS:
        i = dates.index(d)
        others = [x for x in PAIRS if x != d]
        usual = np.sum([is_water[x] for x in others], axis=0) >= 2
        dswx_change = is_water[d] ^ usual
        rest = [j for j in base_idx if j != i]
        low_now = (hh[i] < HH_LOW) & (hv[i] < HV_LOW)
        low_usual = (np.nanmedian(hh[rest], axis=0) < HH_LOW) & (np.nanmedian(hv[rest], axis=0) < HV_LOW)
        flagged = scores[i] > threshold
        water_flag = flagged & (low_now ^ low_usual)
        n, n_change = int(area.sum()), int((dswx_change & area).sum())
        for label, f in (("flagged", flagged), ("flagged water-like", water_flag)):
            nf, both = int((f & area).sum()), int((f & dswx_change & area).sum())
            print(f"  {name} {d[5:]} vs {PAIRS[d][5:]} ({DAYS_APART[d]} d) {label}: {n} px, DSWx change {n_change} "
                  f"({100 * n_change / n:.1f}%), flagged {nf}, both {both}, "
                  f"share of flagged that DSWx changed {100 * both / nf if nf else float('nan'):.1f}%, "
                  f"share of DSWx change flagged {100 * both / n_change if n_change else float('nan'):.1f}%")

print("2 July")
print(f"  in baseline: {INTERFERENCE_DATE in change['baseline_dates']}, in frames: {INTERFERENCE_DATE in change['frames']}, "
      f"score COG exists: {(COG / f'change_{INTERFERENCE_DATE}.tif').exists()}, excluded: {change['excluded']}")

print("6 October")
cluster = _footprint(grid, *OCT6_CLUSTER, RADIUS_M)
wide = _footprint(grid, *OCT6_CLUSTER, 1000)
patch = box(OCT6_PATCH)
row("rejected cluster 150 m, % flagged", shares(cluster, threshold))
row("rejected cluster 1 km, % flagged", shares(wide, threshold))
row("patch, % flagged", shares(patch, threshold))
for name, stack in (("HH", hh), ("HV", hv)):
    row(f"patch {name} minus other dates, dB", [float(np.nanmedian(stack[i][patch] - np.nanmedian(np.delete(stack[:, patch], i, 0), axis=0)))
                                               for i in range(len(dates))], "5.2f")
i = dates.index("2026-10-06")
cells = 330
flagged, valid = scores[i] > threshold, np.isfinite(scores[i])
cell_shares = [100 * flagged[r:r + cells, c:c + cells][valid[r:r + cells, c:c + cells]].mean()
               for r in range(0, flagged.shape[0] - cells, cells) for c in range(0, flagged.shape[1] - cells, cells)
               if valid[r:r + cells, c:c + cells].sum() > 1000]
print(f"  10 km cells on 6 Oct: {len(cell_shares)}, median {np.median(cell_shares):.1f}%, max {np.max(cell_shares):.1f}%")
