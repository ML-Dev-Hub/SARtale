"""Radiometry helpers. Order of operations: mask, average in linear power, convert to dB."""

import numpy as np


def mask_power(power: np.ndarray, fill: float | None = None) -> np.ndarray:
    """Return float copy with non-finite, non-positive and fill-valued samples set to NaN."""
    out = np.array(power, dtype=np.float64, copy=True)
    bad = ~np.isfinite(out) | (out <= 0)
    if fill is not None:
        bad |= out == fill
    out[bad] = np.nan
    return out


def to_db(power: np.ndarray) -> np.ndarray:
    """Convert linear power to dB; non-positive values become NaN."""
    p = np.asarray(power, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(p > 0, 10.0 * np.log10(np.where(p > 0, p, 1.0)), np.nan)
