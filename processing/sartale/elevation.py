"""The height of each lake's surface, from the Copernicus DEM, measured once and stored in lakes_in.json.

The freeze check moves NASA POWER air temperature from its grid cell's height to the lake's (config.LAPSE_C_PER_KM).
The lake surface is taken as the 10th percentile of the DEM within 1 km of the lake point: the lake is the low, flat
part of the circle (frozen-spike.md: where the DEM has a flat water surface this agrees with it within about 10 m).
"""
import json
import math
import os
from pathlib import Path

import numpy as np
import requests

STAC_URL = "https://earth-search.aws.element84.com/v1/search"
DEM_COLLECTION = "cop-dem-glo-30"
RADIUS_M = 1000.0
PERCENTILE = 10
SOURCE = "Copernicus DEM GLO-30 ({item}, Earth Search), 10th percentile within 1 km of the lake point"


def circle_percentile(dem: np.ndarray, row: float, col: float, dy_m: float, dx_m: float,
                      radius_m: float = RADIUS_M, q: float = PERCENTILE) -> float | None:
    """The `q`th percentile of the finite DEM values whose pixel centres lie within `radius_m` of (row, col), with
    pixels `dy_m` by `dx_m` metres. None when no such value exists."""
    rows, cols = np.indices(dem.shape)
    near = ((rows + 0.5 - row) * dy_m) ** 2 + ((cols + 0.5 - col) * dx_m) ** 2 <= radius_m ** 2
    vals = np.asarray(dem, float)[near]
    vals = vals[np.isfinite(vals) & (vals > -1000)]
    return float(np.percentile(vals, q)) if vals.size else None


def dem_item(lon: float, lat: float) -> dict | None:
    """The Copernicus DEM GLO-30 tile (STAC item) holding the point, or None."""
    body = {"collections": [DEM_COLLECTION], "intersects": {"type": "Point", "coordinates": [lon, lat]}, "limit": 5}
    r = requests.post(STAC_URL, json=body, timeout=60)
    r.raise_for_status()
    items = r.json().get("features") or []
    return items[0] if items else None


def _https(href: str) -> str:
    return href.replace("s3://copernicus-dem-30m/", "https://copernicus-dem-30m.s3.amazonaws.com/")


def lake_elevation(lake) -> tuple[float, str] | None:
    """(height in metres, source) of the lake's surface, or None when the DEM has no tile or no value there."""
    import rasterio
    from rasterio.windows import Window

    item = dem_item(lake.lon, lake.lat)
    if item is None:
        return None
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
                      GDAL_HTTP_MAX_RETRY="3", GDAL_HTTP_RETRY_DELAY="2"):
        with rasterio.open(_https(item["assets"]["data"]["href"])) as ds:
            t = ds.transform  # geographic: degrees per pixel
            dy_m = abs(t.e) * 111_320.0
            dx_m = abs(t.a) * 111_320.0 * math.cos(math.radians(lake.lat))
            half_r, half_c = int(math.ceil(RADIUS_M / dy_m)) + 2, int(math.ceil(RADIUS_M / dx_m)) + 2
            col, row = (lake.lon - t.c) / t.a, (lake.lat - t.f) / t.e
            win = Window(int(col) - half_c, int(row) - half_r, 2 * half_c + 1, 2 * half_r + 1)
            dem = ds.read(1, window=win, boundless=True, fill_value=-32767).astype(float)
            value = circle_percentile(dem, row - win.row_off, col - win.col_off, dy_m, dx_m)
    if value is None:
        return None
    return round(value), SOURCE.format(item=item["id"])


PLAUSIBLE_M = (0.0, 8900.0)  # a lake surface on Earth


def height_problems(lakes, doc: dict | None) -> list[str]:
    """What is wrong with the register's lake heights, given the built lakes.json `doc`: a height outside
    PLAUSIBLE_M or without a source; or a lake (lake_state "lake") without a height whose built entry does not say why,
    as "Freeze not assessed" with the missing height as the reason. A missing height is allowed (lakes-elevation fails
    soft and tries again at the next refresh); a silent one is not."""
    built = {lk.get("id"): lk for lk in (doc or {}).get("lakes", [])}
    out = []
    for lake in lakes:
        if lake.elevation_m is not None:
            lo, hi = PLAUSIBLE_M
            if not lo < lake.elevation_m < hi:
                out.append(f"{lake.id}: height {lake.elevation_m} m is not a lake surface height")
            if not str(lake.elevation_source or "").strip():
                out.append(f"{lake.id}: height without a source")
            continue
        if lake.lake_state != "lake":
            continue  # only lakes get a freeze check
        f = (built.get(lake.id) or {}).get("freeze") or {}
        if f.get("state") != "not_assessed" or "lake height" not in str(f.get("reason", "")):
            out.append(f"{lake.id}: no height, and the built lakes.json does not say \"Freeze not assessed\" for it")
    return out


def _object_span(text: str, start: int) -> int:
    """Index of the `}` that closes the JSON object opening at `text[start]` (strings and nesting respected)."""
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError("unclosed JSON object")


def set_elevation(path: Path, lake_id: str, elevation_m: float, source: str) -> None:
    """Add `elevation_m` and `elevation_source` to one entry of lakes_in.json, on a new line before the entry's closing
    brace, touching nothing else. An entry that already has an elevation is an error (it is measured once)."""
    text = Path(path).read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in text else "\n"
    key = f'"id": {json.dumps(lake_id)}'
    at = text.find(key)
    if at < 0:
        raise KeyError(f"{lake_id} is not in {path}")
    start = text.rindex("{", 0, at)
    end = _object_span(text, start)
    if '"elevation_m"' in text[start:end]:
        raise ValueError(f"{lake_id} already has an elevation in {path}")
    d = lambda v: json.dumps(v, ensure_ascii=False)  # noqa: E731
    value = int(elevation_m) if float(elevation_m).is_integer() else elevation_m
    new = text[:end] + "," + nl + f'   "elevation_m": {d(value)}, "elevation_source": {d(source)}' + text[end:]
    json.loads(new)  # still valid JSON
    tmp = Path(path).with_name(Path(path).name + ".tmp")
    tmp.write_bytes(new.encode("utf-8"))
    os.replace(tmp, path)
