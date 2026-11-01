"""Same-season reference checks: pick the nearest reference date and compare
a radar low-backscatter mask with a DSWx water classification."""
from datetime import date

import numpy as np


def nearest_date(target: date, candidates: list[date]) -> tuple[date, int]:
    """Return the candidate closest to target and the absolute gap in days.

    On a tie the earlier date wins. Raises ValueError for an empty list.
    """
    if not candidates:
        raise ValueError("candidates must not be empty")
    best = min(candidates, key=lambda d: (abs((d - target).days), d))
    return best, abs((best - target).days)


def water_agreement(
    radar_low: np.ndarray,
    dswx: np.ndarray,
    water_values: set[int],
    invalid_values: set[int],
) -> dict:
    """Fraction of comparable pixels where the radar mask and DSWx agree.

    A pixel is comparable when its DSWx value is not NaN and not in
    invalid_values, and (for float radar input) the radar value is not NaN.
    Radar True agrees with a DSWx water class; radar False agrees with any
    other valid class. Returns {"agreement": float | None, "n_compared": int};
    agreement is None when nothing is comparable.
    """
    radar_low = np.asarray(radar_low)
    dswx = np.asarray(dswx)
    if radar_low.shape != dswx.shape:
        raise ValueError(f"shape mismatch: {radar_low.shape} vs {dswx.shape}")

    comparable = ~np.isin(dswx, list(invalid_values))
    if np.issubdtype(dswx.dtype, np.floating):
        comparable &= ~np.isnan(dswx)
    if np.issubdtype(radar_low.dtype, np.floating):
        comparable &= ~np.isnan(radar_low)

    n = int(comparable.sum())
    if n == 0:
        return {"agreement": None, "n_compared": 0}

    radar_water = radar_low.astype(bool)
    dswx_water = np.isin(dswx, list(water_values))
    agree = int((radar_water == dswx_water)[comparable].sum())
    return {"agreement": agree / n, "n_compared": n}
