"""Site time series and stable-control checks.

Order of operations: mask, average linear power inside the radius, convert to dB.
"""
import json
from pathlib import Path

import numpy as np
from pyproj import Transformer

from sartale import config
from sartale.gcov import Layer, check_identity, read_layer
from sartale.products import POL_TERMS, assert_same_grid, multilook_layer
from sartale.radiometry import to_db

RADIUS_M = 150.0
SITE_KEYS = ("id", "name", "lon", "lat", "role")
STAMP_KEYS = ("stack", "crid")  # which manifest these curves belong to


def _step(coords: np.ndarray) -> float:
    return float(np.median(np.abs(np.diff(coords)))) if coords.size > 1 else 0.0


def _footprint(layer: Layer, lon: float, lat: float, radius_m: float) -> np.ndarray:
    """Boolean (y, x) mask of pixels whose centres lie within radius_m of the site.

    Falls back to the pixel under the site if the radius holds no pixel centre.
    Raises ValueError if the site is outside the grid.
    """
    sx, sy = Transformer.from_crs(4326, layer.epsg, always_xy=True).transform(lon, lat)
    x, y = np.asarray(layer.x, dtype=np.float64), np.asarray(layer.y, dtype=np.float64)
    hx, hy = _step(x) / 2, _step(y) / 2
    if not (x.min() - hx <= sx <= x.max() + hx and y.min() - hy <= sy <= y.max() + hy):
        raise ValueError(f"Site ({lon}, {lat}) is outside the grid")
    dist2 = (x[None, :] - sx) ** 2 + (y[:, None] - sy) ** 2
    inside = dist2 <= radius_m ** 2
    if not inside.any():
        inside[np.unravel_index(np.argmin(dist2), dist2.shape)] = True
    return inside


def sample_site_stats(power_stack: np.ndarray, layer: Layer, lon: float, lat: float,
                      radius_m: float = RADIUS_M) -> tuple[list[float | None], list[float]]:
    """Per-date dB and valid fraction for pixels within radius_m of (lon, lat).

    power_stack is (dates, y, x) linear power. dB is None where no pixel in the
    radius is valid. The valid fraction is valid pixels over in-radius pixels.
    """
    stack = np.asarray(power_stack, dtype=np.float64)
    if stack.ndim != 3 or stack.shape[1:] != layer.power.shape:
        raise ValueError(f"Stack shape {stack.shape} does not match layer grid {layer.power.shape}")
    inside = _footprint(layer, lon, lat, radius_m)
    values = stack[:, inside]  # (dates, n_inside)
    valid = np.isfinite(values) & (values > 0)
    n_valid = valid.sum(axis=1)
    sums = np.where(valid, values, 0.0).sum(axis=1)
    db: list[float | None] = []
    for s, n in zip(sums, n_valid):
        db.append(float(to_db(s / n)) if n else None)
    return db, [float(n) / values.shape[1] for n in n_valid]


def sample_site(power_stack: np.ndarray, layer: Layer, lon: float, lat: float,
                radius_m: float = RADIUS_M) -> list[float | None]:
    """One dB value per date: the linear-power mean within radius_m, or None if nothing is valid."""
    return sample_site_stats(power_stack, layer, lon, lat, radius_m)[0]


def stability_report(series_db: list[float | None]) -> dict:
    """Spread (max minus min) and count of the non-None values."""
    vals = [v for v in series_db if v is not None]
    spread = round(max(vals) - min(vals), 2) if vals else None
    return {"spread_db": spread, "n_valid": len(vals)}


def write_sites(sites: list[dict], path: Path) -> Path:
    """Write sites.json; NaN is rejected rather than written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sites, indent=2, allow_nan=False), encoding="utf-8")
    return path


def _round(v: float | None) -> float | None:
    return None if v is None else round(v, 2)


def build_sites(gcov_dir: Path, manifest_path: Path, sites_in: list[dict],
                radius_m: float = RADIUS_M) -> list[dict]:
    """Sample every site on every manifest date, HH and HV, on the multilooked build grid.

    Each site is stamped with the manifest's `stack` and `crid`, so the app can refuse curves that
    belong to another build.
    """
    for i, s in enumerate(sites_in):
        missing = [k for k in SITE_KEYS if k not in s]
        if missing:
            raise ValueError(f"Site #{i} is missing {', '.join(missing)}")
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    missing = [k for k in STAMP_KEYS if not manifest.get(k)]
    if missing:
        raise ValueError(f"The manifest has no {', '.join(missing)}, so the sites cannot be stamped")
    stamp = {k: manifest[k] for k in STAMP_KEYS}
    entries = manifest["dates"]
    dates = [e["date"] for e in entries]
    files = [Path(gcov_dir) / f"{e['granule']}.h5" for e in entries]
    for d, f in zip(dates, files):
        if not f.is_file():
            raise FileNotFoundError(f"No GCOV file for {d}: expected {f}")
    for e, f in zip(entries, files):
        check_identity(f, e["granule"], config.CRID)

    stacks: dict[str, np.ndarray] = {}
    grid: Layer | None = None
    for pol, term in POL_TERMS.items():
        raw = [read_layer(f, term, config.BBOX) for f in files]
        assert_same_grid(raw)
        looked = [multilook_layer(layer) for layer in raw]
        grid = looked[0]
        stacks[pol] = np.stack([layer.power for layer in looked])

    sites = []
    for s in sites_in:
        hh, hh_frac = sample_site_stats(stacks["HH"], grid, s["lon"], s["lat"], radius_m)
        hv, hv_frac = sample_site_stats(stacks["HV"], grid, s["lon"], s["lat"], radius_m)
        series = [{"date": d, "hh_db": _round(a), "hv_db": _round(b),
                   "valid_fraction": round(min(fa, fb), 3)}
                  for d, a, b, fa, fb in zip(dates, hh, hv, hh_frac, hv_frac)]
        sites.append({**{k: s[k] for k in SITE_KEYS}, **stamp, "series": series})
    return sites
