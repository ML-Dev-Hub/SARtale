"""NASA's public browse previews of NISAR GCOV scenes, turned into web map frames.

These PNGs are display-scaled pictures. Their pixel values are NOT calibrated
backscatter and are never converted to dB, averaged into statistics or charted.
Everything here only reorders, warps and crops pixels for display.

Layout verified on the real files (see the Task P report): the *_LATLON.png images are
RGB with red = blue = HH and green = HV, on a plain lon/lat grid, with all-zero fill.
"""
import hashlib
import json
from datetime import timezone
from pathlib import Path

import numpy as np
from PIL import Image

from sartale import config
from sartale.catalog import parse_granule
from sartale.gcov import Layer
from sartale.products import bounds_3857_to_lonlat, write_webp_3857

PREVIEW_MATURITY = "Provisional preview"
# west, south, east, north in degrees: the part of the scene the app shows.
DISPLAY_WINDOW = (70.9, 33.6, 72.8, 34.8)
# HH of these three dates become red, green and blue. 2 July is never used.
COMPOSITE_DATES = ("2026-07-26", "2026-09-12", "2026-10-18")
INTERFERENCE_DATE = "2026-07-02"
INTERFERENCE_FLAG = ("Possible radio interference over the western area (unconfirmed). "
                     "Do not read this as surface change.")
FORECAST_FLAG = "Forecast-orbit product; positions may be less precise."
# The nine images sit on one pixel grid (zero shift between dates on the real files), so their
# footprint-fitted extents should agree. If they differ by more than this, something is wrong.
MAX_EXTENT_SPREAD_DEG = 0.02
POL_FILES = ("HH", "HV")
M_PER_DEG_LAT = 110_950.0
M_PER_DEG_LON_EQUATOR = 111_320.0


# --- channels -------------------------------------------------------------------

def split_channels(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """RGB browse image -> (HH, HV) uint8 arrays. Red and blue are both HH, green is HV.

    Fill (all three channels 0) becomes 0, which the frame writer treats as transparent.
    A real pixel never comes out as 0: a real value of 0 is raised to 1.
    """
    rgb = np.asarray(rgb)
    if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.dtype != np.uint8:
        raise ValueError(f"Expected a uint8 RGB array of shape (rows, cols, 3), got {rgb.dtype} {rgb.shape}")
    valid = (rgb > 0).any(axis=2)
    if not np.array_equal(rgb[..., 0][valid], rgb[..., 2][valid]):
        raise ValueError("Layout check failed: red and blue differ, so red is not a copy of HH")
    hh = np.where(valid, np.maximum(rgb[..., 0], 1), 0).astype(np.uint8)
    hv = np.where(valid, np.maximum(rgb[..., 1], 1), 0).astype(np.uint8)
    return hh, hv


def valid_mask(rgb: np.ndarray) -> np.ndarray:
    """True where the browse image holds data (any channel above 0)."""
    return (np.asarray(rgb) > 0).any(axis=2)


# --- georeferencing -------------------------------------------------------------

def footprint_bbox(corners: list[list[float]] | list[tuple[float, float]]) -> tuple[float, float, float, float]:
    """(west, south, east, north) of a footprint given as (lon, lat) corners."""
    lons = [float(c[0]) for c in corners]
    lats = [float(c[1]) for c in corners]
    return min(lons), min(lats), max(lons), max(lats)


def geo_extent(valid_mask: np.ndarray, footprint: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """Lon/lat extent (west, south, east, north) of the WHOLE image, edge to edge.

    The footprint is the lon/lat bounding box of the scene's data. The valid pixels' bounding box
    is mapped onto it, then extended to the image edges at the same degrees per pixel.
    """
    valid_mask = np.asarray(valid_mask, dtype=bool)
    if not valid_mask.any():
        raise ValueError("geo_extent: the mask has no valid pixels")
    rows, cols = np.flatnonzero(valid_mask.any(axis=1)), np.flatnonzero(valid_mask.any(axis=0))
    r0, r1, c0, c1 = int(rows[0]), int(rows[-1]) + 1, int(cols[0]), int(cols[-1]) + 1  # pixel edges
    west_fp, south_fp, east_fp, north_fp = footprint
    dx = (east_fp - west_fp) / (c1 - c0)
    dy = (north_fp - south_fp) / (r1 - r0)
    height, width = valid_mask.shape
    west = west_fp - c0 * dx
    north = north_fp + r0 * dy
    return west, north - height * dy, west + width * dx, north


def shared_extent(extents: list[tuple[float, float, float, float]],
                  tolerance: float = MAX_EXTENT_SPREAD_DEG) -> tuple[float, float, float, float]:
    """Mean of per-date extents; raises if any edge strays more than `tolerance` degrees from the mean."""
    arr = np.asarray(extents, dtype=np.float64)
    mean = arr.mean(axis=0)
    if np.abs(arr - mean).max() > tolerance:
        raise ValueError(f"Per-date extents differ by more than {tolerance} degrees: {extents}")
    return tuple(float(v) for v in mean)


def pixel_size_m(extent: tuple[float, float, float, float], shape: tuple[int, int]) -> float:
    """Mean ground size of one pixel in metres (east-west and north-south averaged), at the extent's mid latitude."""
    west, south, east, north = extent
    height, width = shape
    dx, dy = (east - west) / width, (north - south) / height
    lat = np.radians((south + north) / 2)
    return float(np.mean([dx * M_PER_DEG_LON_EQUATOR * np.cos(lat), dy * M_PER_DEG_LAT]))


def _layer(channel: np.ndarray, extent: tuple[float, float, float, float]) -> Layer:
    """A lon/lat Layer whose x and y are pixel centres, so products.py can warp it."""
    west, south, east, north = extent
    height, width = channel.shape[:2]
    x = west + (np.arange(width) + 0.5) * (east - west) / width
    y = north - (np.arange(height) + 0.5) * (north - south) / height
    return Layer(channel, x, y, 4326, None, None)


# --- frames ---------------------------------------------------------------------

def _preview_composite(early: np.ndarray, mid: np.ndarray, late: np.ndarray) -> np.ndarray:
    """RGBA uint8 from three HH preview channels (red, green, blue). Transparent where any is fill."""
    rgb = np.stack([early, mid, late], axis=-1)
    alpha = np.where((rgb > 0).all(axis=-1), 255, 0).astype(np.uint8)
    rgb[alpha == 0] = 0
    return np.dstack([rgb, alpha])


def write_preview_frames(channels: dict[str, tuple[np.ndarray, np.ndarray]],
                         extent: tuple[float, float, float, float], out_dir: Path,
                         window: tuple[float, float, float, float] = DISPLAY_WINDOW,
                         composite_dates: tuple[str, str, str] = COMPOSITE_DATES) -> dict:
    """Warp every frame to EPSG:3857, crop to `window` and write lossy WebP with alpha.

    `channels` maps an ISO date to its (HH, HV) arrays. Writes frames/<date>_HH.webp, frames/<date>_HV.webp
    and frames/composite_HH.webp under `out_dir`. All files share identical bounds. Returns
    {"bounds": [west, south, east, north], "frames": {date: {"HH": rel, "HV": rel}}, "composite": rel,
    "composite_dates": [...]}.
    """
    out_dir = Path(out_dir)
    west, south, east, north = extent
    if not (west <= window[0] and south <= window[1] and east >= window[2] and north >= window[3]):
        raise ValueError(f"The display window {window} is not inside the image extent {extent}")
    missing = [d for d in composite_dates if d not in channels]
    if missing:
        raise ValueError(f"Cannot build the composite: no data for {missing}")

    bounds_seen = set()
    frames: dict[str, dict[str, str]] = {}
    for date in sorted(channels):
        frames[date] = {}
        for pol, channel in zip(POL_FILES, channels[date]):
            rel = f"frames/{date}_{pol}.webp"
            bounds_seen.add(write_webp_3857(channel, _layer(channel, extent), out_dir / rel, window=window))
            frames[date][pol] = rel
    early, mid, late = (channels[d][0] for d in composite_dates)
    comp_rel = "frames/composite_HH.webp"
    bounds_seen.add(write_webp_3857(_preview_composite(early, mid, late), _layer(early, extent),
                                    out_dir / comp_rel, window=window))
    if len(bounds_seen) != 1:
        raise RuntimeError(f"Frames have differing bounds: {sorted(bounds_seen)}")
    return {
        "bounds": bounds_3857_to_lonlat(bounds_seen.pop()),
        "frames": frames,
        "composite": comp_rel,
        "composite_dates": list(composite_dates),
    }


# --- manifest -------------------------------------------------------------------

def flag_for(date: str, granule: str) -> str | None:
    """The visible caution for a date, or None. 2 July: possible interference. Forecast orbit: less precise."""
    if date == INTERFERENCE_DATE:
        return INTERFERENCE_FLAG
    if parse_granule(granule).accuracy == "F":
        return FORECAST_FLAG
    return None


def build_preview_manifest(info: dict, granules: dict[str, str], pixel_m: float, out_dir: Path) -> dict:
    """Write manifest.json for the frames described by `info` (from write_preview_frames) and return it."""
    dates = sorted(info["frames"])
    entries = []
    for date in dates:
        granule = granules.get(date)
        if granule is None:
            raise ValueError(f"No granule name for {date}")
        parsed = parse_granule(granule)
        if parsed.start.astimezone(timezone.utc).date().isoformat() != date:
            raise ValueError(f"Granule for {date} starts on a different day: {granule}")
        if parsed.crid != config.CRID:
            raise ValueError(f"Granule for {date} has CRID {parsed.crid}, expected {config.CRID}")
        entry = {"date": date, "granule": granule, "frames": info["frames"][date]}
        flag = flag_for(date, granule)
        if flag:
            entry["flag"] = flag
        entries.append(entry)
    manifest = {
        "stack": config.STACK_ID,
        "crid": config.CRID,
        "maturity": PREVIEW_MATURITY,
        "bounds": info["bounds"],
        "dates": entries,
        "composite": info["composite"],
        "composite_dates": info["composite_dates"],
        "stretch_db": None,  # browse pixels are display-scaled: there is no dB stretch
        "gap": {"start": config.GAP_START, "end": config.GAP_END},
        "pixel_m": round(pixel_m),
    }
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


# --- reading the downloaded browse folder ---------------------------------------

def load_browse(browse_dir: Path) -> dict[str, dict]:
    """Read every *_LATLON.png listed in browse_manifest.json, checking each file's sha256.

    Returns {iso_date: {"rgb": uint8 array, "granule": name, "file": name}}.
    """
    browse_dir = Path(browse_dir)
    entries = json.loads((browse_dir / "browse_manifest.json").read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for entry in entries:
        name = entry["file"]
        if not name.endswith("_LATLON.png"):
            continue
        path = browse_dir / name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry["sha256"]:
            raise ValueError(f"{name}: sha256 {digest} does not match browse_manifest.json ({entry['sha256']})")
        stamp = name.split("_")[0]
        date = f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}"
        if parse_granule(entry["granule"]).start.date().isoformat() != date:
            raise ValueError(f"{name}: file date does not match its granule {entry['granule']}")
        if date in out:
            raise ValueError(f"Two LATLON images for {date}")
        with Image.open(path) as img:
            rgb = np.asarray(img.convert("RGB"), dtype=np.uint8)
        out[date] = {"rgb": rgb, "granule": entry["granule"], "file": name}
    if not out:
        raise ValueError(f"No *_LATLON.png entries in {browse_dir / 'browse_manifest.json'}")
    return out


def build_preview(browse_dir: Path, footprints_path: Path, out_dir: Path) -> dict:
    """Browse folder + CMR footprints -> frames and manifest.json in out_dir. Returns the manifest."""
    loaded = load_browse(browse_dir)
    fp_doc = json.loads(Path(footprints_path).read_text(encoding="utf-8"))["footprints"]
    shapes = {v["rgb"].shape for v in loaded.values()}
    if len(shapes) != 1:
        raise ValueError(f"Browse images differ in size: {sorted(shapes)}")
    shape = shapes.pop()[:2]
    extents = []
    for date, v in sorted(loaded.items()):
        if v["granule"] not in fp_doc:
            raise ValueError(f"No CMR footprint for {date} ({v['granule']})")
        extents.append(geo_extent(valid_mask(v["rgb"]), footprint_bbox(fp_doc[v["granule"]])))
    extent = shared_extent(extents)
    channels = {date: split_channels(v["rgb"]) for date, v in loaded.items()}
    info = write_preview_frames(channels, extent, out_dir)
    granules = {date: v["granule"] for date, v in loaded.items()}
    return build_preview_manifest(info, granules, pixel_size_m(extent, shape), out_dir)
