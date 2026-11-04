"""Radar pictures: one grey stretch shared by every pass, and dB to 8-bit."""
import numpy as np


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
