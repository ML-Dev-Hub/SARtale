"""Radiometry helpers. Order of operations: mask, average in linear power, convert to dB."""
import warnings

import numpy as np


def mask_power(power: np.ndarray, fill: float | None = None) -> np.ndarray:
    """Return float copy with non-finite, non-positive and fill-valued samples set to NaN."""
    out = np.array(power, dtype=np.float64, copy=True)
    bad = ~np.isfinite(out) | (out <= 0)
    if fill is not None:
        bad |= out == fill
    out[bad] = np.nan
    return out


def multilook_linear(power: np.ndarray, factor: int, min_valid: float = 0.5) -> np.ndarray:
    """Average linear power over non-overlapping factor x factor blocks.

    Edges that do not fill a block are trimmed. Cells whose valid fraction is
    below min_valid are NaN.
    """
    a = np.asarray(power, dtype=np.float64)
    rows, cols = (a.shape[0] // factor) * factor, (a.shape[1] // factor) * factor
    blocks = a[:rows, :cols].reshape(rows // factor, factor, cols // factor, factor)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        mean = np.nanmean(blocks, axis=(1, 3))
    valid_frac = np.isfinite(blocks).mean(axis=(1, 3))
    mean[valid_frac < min_valid] = np.nan
    return mean


def to_db(power: np.ndarray) -> np.ndarray:
    """Convert linear power to dB; non-positive values become NaN."""
    p = np.asarray(power, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(p > 0, 10.0 * np.log10(np.where(p > 0, p, 1.0)), np.nan)


def log_ratio_db(later: np.ndarray, earlier: np.ndarray) -> np.ndarray:
    """10*log10(later/earlier) in dB."""
    return to_db(later) - to_db(earlier)
