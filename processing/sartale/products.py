"""Stack products: multilooked dB layers, shared stretch, overlays, COGs and the web manifest.

Order of operations everywhere: mask, average in linear power, convert to dB.
"""
import json
from pathlib import Path

import numpy as np
import rasterio
import rasterio.shutil
from PIL import Image
from pyproj import Transformer
from rasterio.io import MemoryFile
from rasterio.transform import Affine, array_bounds
from rasterio.warp import Resampling, calculate_default_transform, reproject

from sartale import config
from sartale.catalog import granule_for_date, utc_date
from sartale.gcov import Layer, check_identity, mask_histogram, read_layer
from sartale.radiometry import multilook_linear, to_db

MULTILOOK = 3  # 10 m -> 30 m
MATURITY = "Provisional"
POL_TERMS = {"HH": "HHHH", "HV": "HVHV"}
WEBP_QUALITY = 80
INTERFERENCE_DATE = "2026-07-02"


# --- grids ----------------------------------------------------------------------

def assert_same_grid(layers: list[Layer]) -> None:
    """Raise ValueError unless all layers share EPSG, shape and coordinates."""
    first = layers[0]
    for i, other in enumerate(layers[1:], start=1):
        same = (
            other.epsg == first.epsg
            and other.power.shape == first.power.shape
            and np.allclose(other.x, first.x, rtol=0, atol=1e-6)
            and np.allclose(other.y, first.y, rtol=0, atol=1e-6)
        )
        if not same:
            raise ValueError(f"Layer {i} is not on the same grid as layer 0")


def multilook_layer(layer: Layer, factor: int = MULTILOOK) -> Layer:
    """Block-average linear power and recompute coordinates as block centres."""
    power = multilook_linear(layer.power, factor)
    rows, cols = power.shape[0] * factor, power.shape[1] * factor
    x = layer.x[:cols].reshape(-1, factor).mean(axis=1)
    y = layer.y[:rows].reshape(-1, factor).mean(axis=1)
    return Layer(power, x, y, layer.epsg, None, None)


# --- rendering ------------------------------------------------------------------

def shared_stretch(stack_db: np.ndarray, low: float = 2, high: float = 98) -> tuple[float, float]:
    """Percentile stretch over every finite value of a (dates, rows, cols) dB stack."""
    values = np.asarray(stack_db, dtype=np.float64)
    values = values[np.isfinite(values)]
    if values.size == 0:
        raise ValueError("Cannot compute a stretch: no finite values")
    lo, hi = np.percentile(values, [low, high])
    return float(lo), float(hi)


def render_frame(db: np.ndarray, stretch: tuple[float, float]) -> np.ndarray:
    """dB to uint8: 1..255 across the stretch, 0 reserved for NaN (nodata)."""
    lo, hi = stretch
    db = np.asarray(db, dtype=np.float64)
    scaled = np.clip((db - lo) / (hi - lo), 0.0, 1.0)
    out = 1 + np.rint(np.nan_to_num(scaled) * 254)
    out[~np.isfinite(db)] = 0
    return out.astype(np.uint8)


def seasonal_composite(early: np.ndarray, mid: np.ndarray, late: np.ndarray,
                       stretch: tuple[float, float]) -> np.ndarray:
    """RGBA uint8: red early, green middle, blue late. Transparent where any date is NaN."""
    rgb = np.stack([render_frame(a, stretch) for a in (early, mid, late)], axis=-1)
    valid = (rgb > 0).all(axis=-1)
    rgb[~valid] = 0
    alpha = np.where(valid, 255, 0).astype(np.uint8)
    return np.dstack([rgb, alpha])


def composite_indices(n: int) -> tuple[int, int, int]:
    """Indices of the early, middle and late dates; even counts take the later central date."""
    if n < 1:
        raise ValueError("Need at least one date for a composite")
    return 0, n // 2, n - 1


# --- georeferenced outputs ------------------------------------------------------

def _north_up(array: np.ndarray, layer: Layer) -> tuple[np.ndarray, Affine]:
    """Orient an array for a north-up raster and return its transform (pixel-centre coords in layer)."""
    xs, ys = np.asarray(layer.x, dtype=np.float64), np.asarray(layer.y, dtype=np.float64)
    if array.shape[:2] != (ys.size, xs.size):
        raise ValueError(f"Array shape {array.shape[:2]} does not match layer grid {(ys.size, xs.size)}")
    if xs.size < 2 or ys.size < 2:
        raise ValueError("Grid needs at least 2 samples per axis")
    if xs[0] > xs[-1]:
        array, xs = array[:, ::-1], xs[::-1]
    if ys[0] < ys[-1]:
        array, ys = array[::-1], ys[::-1]
    dx = (xs[-1] - xs[0]) / (xs.size - 1)
    dy = (ys[0] - ys[-1]) / (ys.size - 1)
    return array, Affine(dx, 0.0, xs[0] - dx / 2, 0.0, -dy, ys[0] + dy / 2)


def write_cog(array: np.ndarray, layer: Layer, path: Path) -> None:
    """Write a float32 dB array as a Cloud Optimized GeoTIFF in the layer's CRS."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data, transform = _north_up(np.asarray(array, dtype=np.float32), layer)
    profile = dict(driver="GTiff", count=1, dtype="float32", nodata=float("nan"),
                   height=data.shape[0], width=data.shape[1],
                   crs=f"EPSG:{layer.epsg}", transform=transform)
    with MemoryFile() as mem:
        with mem.open(**profile) as dst:
            dst.write(data, 1)
        with mem.open() as src:
            rasterio.shutil.copy(src, str(path), driver="COG", compress="DEFLATE")


def _to_premultiplied(array: np.ndarray) -> np.ndarray:
    """(rows, cols) uint8 grey (0 = nodata) or (rows, cols, 4) RGBA -> float32 (4, rows, cols) premultiplied."""
    a = np.asarray(array)
    if a.ndim == 2:
        alpha = (a > 0).astype(np.float32)
        rgb = np.repeat(a[..., None], 3, axis=-1).astype(np.float32)
    elif a.ndim == 3 and a.shape[2] == 4:
        alpha = a[..., 3].astype(np.float32) / 255.0
        rgb = a[..., :3].astype(np.float32)
    else:
        raise ValueError(f"Expected 2-D grey or RGBA array, got shape {a.shape}")
    return np.concatenate([np.moveaxis(rgb * alpha[..., None], -1, 0), alpha[None]], axis=0)


def _window_grid(window: tuple[float, float, float, float], res: float) -> tuple[Affine, int, int]:
    """Destination grid in EPSG:3857 that covers a lon/lat window (west, south, east, north) at about `res` metres."""
    tr = Transformer.from_crs(4326, 3857, always_xy=True)
    left, bottom = tr.transform(window[0], window[1])
    right, top = tr.transform(window[2], window[3])
    dw, dh = max(1, round((right - left) / res)), max(1, round((top - bottom) / res))
    return Affine((right - left) / dw, 0.0, left, 0.0, -(top - bottom) / dh, top), dw, dh


def write_webp_3857(array: np.ndarray, layer: Layer, path: Path,
                    window: tuple[float, float, float, float] | None = None) -> tuple[float, float, float, float]:
    """Warp an overlay to EPSG:3857 and save it as lossy WebP with alpha.

    MapLibre stretches image layers linearly in Web Mercator, so the picture must
    be Mercator-aligned. Returns the warped image bounds as (left, bottom, right,
    top) in Web Mercator metres. Nodata (0 in grey, alpha 0 in RGBA) stays transparent.
    With `window` (west, south, east, north in degrees) the output is cropped to that
    window, so every frame written with the same window has identical bounds.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    src_img = _to_premultiplied(array)
    transform = _north_up(src_img[0], layer)[1]
    src_img = np.stack([_north_up(band, layer)[0] for band in src_img])
    h, w = src_img.shape[1:]
    src_crs, dst_crs = f"EPSG:{layer.epsg}", "EPSG:3857"
    left, bottom, right, top = array_bounds(h, w, transform)
    dst_tf, dw, dh = calculate_default_transform(src_crs, dst_crs, w, h, left, bottom, right, top)
    if window is not None:
        dst_tf, dw, dh = _window_grid(window, dst_tf.a)
    dst = np.zeros((4, dh, dw), dtype=np.float32)
    for i in range(4):
        reproject(np.ascontiguousarray(src_img[i]), dst[i], src_transform=transform,
                  src_crs=src_crs, dst_transform=dst_tf, dst_crs=dst_crs,
                  resampling=Resampling.bilinear, dst_nodata=0)
    alpha = np.clip(dst[3], 0.0, 1.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        rgb = np.where(alpha > 0, dst[:3] / np.where(alpha > 0, alpha, 1.0), 0.0)
    rgba = np.dstack([np.moveaxis(np.clip(np.rint(rgb), 0, 255), 0, -1),
                      np.rint(alpha * 255)[..., None]]).astype(np.uint8)
    rgba[rgba[..., 3] == 0] = 0
    Image.fromarray(rgba, "RGBA").save(path, "WEBP", quality=WEBP_QUALITY, method=4)
    return tuple(float(v) for v in array_bounds(dh, dw, dst_tf))


def bounds_3857_to_lonlat(bounds: tuple[float, float, float, float]) -> list[float]:
    """(left, bottom, right, top) in EPSG:3857 -> [west, south, east, north] in degrees."""
    tr = Transformer.from_crs(3857, 4326, always_xy=True)
    west, south = tr.transform(bounds[0], bounds[1])
    east, north = tr.transform(bounds[2], bounds[3])
    return [round(v, 6) for v in (west, south, east, north)]


# --- build ----------------------------------------------------------------------

def _warn_about(date: str, g: dict) -> None:
    """Print a warning for dates that need a caution. Never blocks the build."""
    if g.get("accuracy") == "F":
        print(f"WARNING: {date} is a forecast-orbit product (accuracy F); positions may be less precise.")
    if date == INTERFERENCE_DATE:
        print(f"WARNING: {date} may show radio interference over the western area (unconfirmed); "
              "check it by eye and do not read it as surface change.")


def _print_mask_histogram(date: str, layer: Layer) -> None:
    hist = mask_histogram(layer.mask)
    shown = ", ".join(f"{v}: {n}" for v, n in hist.items()) if hist else "no mask in file"
    print(f"mask {date}: {shown}")


def _remove_unlisted_frames(frames_dir: Path, listed: set[str]) -> None:
    """Delete files in frames/ that the new manifest does not name (left by an earlier build or preview)."""
    if not frames_dir.is_dir():
        return
    for f in frames_dir.iterdir():
        if f.is_file() and f"frames/{f.name}" not in listed:
            f.unlink()


def build_products(gcov_dir: Path, dates: list[str], manifest_in: Path,
                   out_dir: Path, cog_dir: Path) -> dict:
    """Read one GCOV file per date, write overlays, COGs and manifest.json; return the manifest.

    Also removes any sites.json in out_dir (curves from another build must never sit beside this
    manifest) and any frame the new manifest does not list.
    """
    gcov_dir, out_dir, cog_dir = Path(gcov_dir), Path(out_dir), Path(cog_dir)
    dates = sorted(dates)
    if len(set(dates)) != len(dates):
        raise ValueError("Duplicate dates")
    search = json.loads(Path(manifest_in).read_text(encoding="utf-8"))
    granules = [granule_for_date(search["granules"], d) for d in dates]
    for d, g in zip(dates, granules):
        if g["crid"] != config.CRID:
            raise ValueError(f"Granule for {d} has CRID {g['crid']}, expected {config.CRID}")
    files = [gcov_dir / f"{g['name']}.h5" for g in granules]
    for d, f in zip(dates, files):
        if not f.is_file():
            raise FileNotFoundError(f"No GCOV file for {d}: expected {f}")
    for d, g, f in zip(dates, granules, files):
        check_identity(f, g["name"], config.CRID)
        _warn_about(d, g)
    acquisitions = sorted({utc_date(g) for g in search["granules"]})

    db: dict[str, list[np.ndarray]] = {}
    grid: Layer | None = None
    for pol, term in POL_TERMS.items():
        raw = [read_layer(f, term, config.BBOX) for f in files]
        assert_same_grid(raw)
        if pol == next(iter(POL_TERMS)):
            for d, layer in zip(dates, raw):
                _print_mask_histogram(d, layer)
        looked = [multilook_layer(layer) for layer in raw]
        grid = looked[0]
        db[pol] = [to_db(layer.power) for layer in looked]
    stretch = {pol: shared_stretch(np.stack(arrays)) for pol, arrays in db.items()}

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "sites.json").unlink(missing_ok=True)
    frames = out_dir / "frames"
    all_bounds = set()
    entries = []
    for i, (d, g) in enumerate(zip(dates, granules)):
        rel = {}
        for pol in POL_TERMS:
            write_cog(db[pol][i], grid, cog_dir / f"{d}_{pol}.tif")
            rel[pol] = f"frames/{d}_{pol}.webp"
            all_bounds.add(write_webp_3857(render_frame(db[pol][i], stretch[pol]), grid,
                                           out_dir / rel[pol]))
        entries.append({"date": d, "granule": g["name"], "frames": rel})

    e, m, l = composite_indices(len(dates))
    composite_dates = [dates[e], dates[m], dates[l]]
    rgba = seasonal_composite(db["HH"][e], db["HH"][m], db["HH"][l], stretch["HH"])
    all_bounds.add(write_webp_3857(rgba, grid, frames / "composite_HH.webp"))
    if len(all_bounds) != 1:
        raise RuntimeError(f"Overlays have differing bounds: {sorted(all_bounds)}")

    manifest = {
        "stack": config.STACK_ID,
        "crid": config.CRID,
        "maturity": MATURITY,
        "bounds": bounds_3857_to_lonlat(all_bounds.pop()),
        "dates": entries,
        "acquisitions": acquisitions,
        "composite": "frames/composite_HH.webp",
        "composite_dates": composite_dates,
        "stretch_db": {pol: [round(v, 3) for v in s] for pol, s in stretch.items()},
        "gap": {"start": config.GAP_START, "end": config.GAP_END},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _remove_unlisted_frames(frames, {*(p for e_ in entries for p in e_["frames"].values()), manifest["composite"]})
    return manifest
