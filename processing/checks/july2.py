"""The 2 July evidence in docs/DATA_SOURCES.md, from the 30 m COGs and the GCOV files.

Run from the repository root after `run_pipeline rebuild`:
    conda run -n sartale python processing/checks/july2.py
"""
import glob
import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "processing"))
import h5py
import numpy as np
import rasterio
from pyproj import Transformer
from scipy import ndimage as ndi

warnings.simplefilter("ignore")
COG = ROOT / "data" / "cog"
GCOV = ROOT / "data" / "gcov"
J2 = "2026-07-02"
BLOCK = 5  # 30 m -> 150 m
PATCH_BOX = (71.30, 34.10, 71.45, 34.28)
FARM_BOX = (72.10, 34.10, 72.25, 34.28)  # away from the patch
to_utm = Transformer.from_crs(4326, 32643, always_xy=True)
to_ll = Transformer.from_crs(32643, 4326, always_xy=True)
dates = sorted(p.name[:10] for p in COG.glob("*_HH.tif"))
ij = dates.index(J2)
others = [i for i in range(len(dates)) if i != ij]


def linear(pol: str) -> tuple[np.ndarray, rasterio.Affine]:
    arrays = []
    for d in dates:
        with rasterio.open(COG / f"{d}_{pol}.tif") as src:
            a, t = src.read(1), src.transform
        rows, cols = a.shape[0] // BLOCK * BLOCK, a.shape[1] // BLOCK * BLOCK
        blocks = (10 ** (a[:rows, :cols] / 10)).reshape(rows // BLOCK, BLOCK, cols // BLOCK, BLOCK)
        arrays.append(np.nanmean(blocks, axis=(1, 3)))
    return np.stack(arrays), rasterio.Affine(t.a * BLOCK, 0, t.c, 0, t.e * BLOCK, t.f)


def db(a):
    return 10 * np.log10(a)


HH, tf = linear("HH")
HV, _ = linear("HV")
ref_hv, ref_hh = np.nanmedian(HV[others], axis=0), np.nanmedian(HH[others], axis=0)
d_hv = db(HV[ij]) - db(ref_hv)
d_hh = db(HH[ij]) - db(ref_hh)
kernel = 7  # about 1 km
smooth = ndi.uniform_filter(np.nan_to_num(d_hv), kernel)
cell_km2 = (abs(tf.a) / 1000) ** 2

corners = np.array(next(iter(json.loads((ROOT / "processing" / "reference" / "cmr_footprints.json")
                                        .read_text(encoding="utf-8"))["footprints"].values())))
south, west = corners[corners[:, 1].argmin()], corners[corners[:, 0].argmin()]
sx, sy = to_utm.transform(*south)
wx, wy = to_utm.transform(*west)
along = np.array([wx - sx, wy - sy]) / np.hypot(wx - sx, wy - sy)
across = np.array([along[1], -along[0]])

for thr in (6, 10):
    mask = smooth > thr
    lab, n = ndi.label(mask)
    sizes = ndi.sum(mask, lab, np.arange(1, n + 1)) * cell_km2
    rows, cols = np.nonzero(lab == (int(np.argmax(sizes)) + 1))
    xs, ys = tf * (cols + 0.5, rows + 0.5)
    lon, lat = to_ll.transform(np.asarray(xs), np.asarray(ys))
    a = np.asarray(xs) * along[0] + np.asarray(ys) * along[1]
    c = np.asarray(xs) * across[0] + np.asarray(ys) * across[1]
    print(f"excess > {thr} dB: {mask.sum() * cell_km2:.0f} km2 in {n} pieces, largest {sizes.max():.0f} km2 "
          f"({100 * sizes.max() / sizes.sum():.1f}%), lon {lon.min():.2f}-{lon.max():.2f}, lat {lat.min():.2f}-{lat.max():.2f}, "
          f"{(np.ptp(a)) / 1000:.0f} km along track, {(np.ptp(c)) / 1000:.0f} km across")
    print(f"  median excess HV {np.nanmedian(d_hv[mask]):.2f}, HH {np.nanmedian(d_hh[mask]):.2f} dB")

core = smooth > 10
print("core, linear means by date (HH, HV dB)")
for i, d in enumerate(dates):
    print(f"  {d} {db(np.nanmean(HH[i][core])):7.2f} {db(np.nanmean(HV[i][core])):7.2f}")
print("added power in the core, binned by reference HV")
x, y = ref_hv[core], HV[ij][core]
ok = np.isfinite(x) & np.isfinite(y)
x, y = x[ok], y[ok]
edges = np.quantile(x, np.linspace(0, 1, 9))
for lo, hi in zip(edges[:-1], edges[1:]):
    m = (x >= lo) & (x <= hi)
    print(f"  ref {db(np.median(x[m])):7.2f} dB, 2 Jul {db(np.median(y[m])):7.2f} dB, "
          f"added {np.median(y[m] - x[m]):.3f}, rise {db(np.median(y[m]) / np.median(x[m])):.2f} dB")


def box_mean(path: str, freq: str, term: str, box: tuple[float, float, float, float]) -> float:
    west_, south_, east_, north_ = box
    with h5py.File(path, "r") as f:
        g = f[f"/science/LSAR/GCOV/grids/{freq}"]
        xs, ys = to_utm.transform([west_, west_, east_, east_], [south_, north_, south_, north_])
        xc, yc = g["xCoordinates"][:], g["yCoordinates"][:]
        ix, iy = np.flatnonzero((xc >= min(xs)) & (xc <= max(xs))), np.flatnonzero((yc >= min(ys)) & (yc <= max(ys)))
        sl = (slice(iy[0], iy[-1] + 1), slice(ix[0], ix[-1] + 1))
        a = g[term][sl].astype("f8")
        a[(g["mask"][sl] == 255) | (a <= 0)] = np.nan
    return float(db(np.nanmean(a)))


for name, box in (("patch box", PATCH_BOX), ("farmland box", FARM_BOX)):
    print(f"{name} {box}: date, A HH, A HV, B HH, B HV (A 1239 MHz, B 1293.5 MHz), A HV minus A HH")
    rows = []
    for p in sorted(glob.glob(str(GCOV / "*.h5"))):
        v = [box_mean(p, fr, term, box) for fr in ("frequencyA", "frequencyB") for term in ("HHHH", "HVHV")]
        rows.append(v)
        print(f"  {Path(p).name.split('_')[11][:8]} " + " ".join(f"{u:7.2f}" for u in v) + f"  {v[1] - v[0]:6.2f}")
    r = np.array(rows)
    print(f"  A HH span {np.ptp(r[:, 0]):.2f} dB; largest |A-B| HH {np.abs(r[:, 0] - r[:, 2]).max():.2f}, HV {np.abs(r[:, 1] - r[:, 3]).max():.2f} dB")
