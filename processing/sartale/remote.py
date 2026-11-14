"""Read small lake windows from remote NISAR GCOV files with HTTP range requests, cached as .npz."""
import io
import os
import shutil
import time
from pathlib import Path

import numpy as np
import requests
from pyproj import Transformer

from sartale import config
from sartale.gcov import read_layer
from sartale.lake_catalog import Pass
from sartale.lakes import Lake, lake_bbox

TIMEOUT = 120
BACKOFF = (1, 2, 4)  # seconds before each retry


def _retryable(status: int | None) -> bool:
    """403 (expired signed URL), 429 and 5xx are worth retrying; 401, 404 and other 4xx will not fix themselves."""
    return status is not None and (status in (403, 429) or 500 <= status < 600)


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


class RangeFile(io.RawIOBase):
    """Seekable read-only view of a remote file, fetched in `block`-sized ranges and cached in memory."""

    def __init__(self, session, url: str, block: int = 1 << 20, retries: int = 3):
        self.s, self.src_url, self.block, self.retries = session, url, block, retries
        self.pos, self.cache, self.fetched, self.requests = 0, {}, 0, 0
        self.url = url
        self._resolve()

    def _resolve(self) -> None:
        """Follow the Earthdata redirect once and keep the final signed URL."""
        r = self._with_retries(lambda: self.s.get(self.src_url, headers={"Range": "bytes=0-0"}, stream=True, timeout=TIMEOUT),
                               resolve=False)
        self.url = r.url
        self.size = int(r.headers["Content-Range"].split("/")[-1])
        r.close()

    def _with_retries(self, request, resolve: bool = True):
        """Run request(); on a connection error, a timeout or a retryable HTTP status (403, 429, 5xx) wait 1, 2, 4 s
        and retry. After a 403, re-resolve the URL. Other HTTP errors (401, 404, ...) raise at once."""
        for attempt in range(self.retries + 1):
            try:
                r = request()
                r.raise_for_status()
                return r
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                if isinstance(e, requests.HTTPError) and not _retryable(status):
                    raise
                if attempt == self.retries:
                    raise
                _sleep(BACKOFF[min(attempt, len(BACKOFF) - 1)])
                if status == 403 and resolve:
                    self._resolve()

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def _block(self, i: int) -> bytes:
        if i not in self.cache:
            a = i * self.block
            b = min(a + self.block, self.size) - 1
            r = self._with_retries(lambda: self.s.get(self.url, headers={"Range": f"bytes={a}-{b}"}, timeout=TIMEOUT))
            self.cache[i] = r.content
            self.fetched += len(r.content)
            self.requests += 1
        return self.cache[i]

    def readinto(self, buf):
        n = min(len(buf), self.size - self.pos)
        if n <= 0:
            return 0
        out, p = bytearray(), self.pos
        while len(out) < n:
            blk = self._block(p // self.block)
            off = p % self.block
            take = blk[off: off + n - len(out)]
            out += take
            p += len(take)
        buf[:n] = out
        self.pos += n
        return n


def read_window(session, url: str, bbox, _file: list | None = None) -> dict:
    """HHHH and HVHV clipped to bbox, read over HTTP range requests. `_file` (if a list) receives the RangeFile."""
    f = RangeFile(session, url)
    if _file is not None:
        _file.append(f)
    hh = read_layer(f, "HHHH", bbox)
    hv = read_layer(f, "HVHV", bbox)
    return {"hh": hh.power, "hv": hv.power, "looks": hh.looks, "mask": hh.mask, "x": hh.x, "y": hh.y, "epsg": hh.epsg}


def cache_path(cache_dir: Path, lake_id: str, p: Pass) -> Path:
    return Path(cache_dir) / lake_id / f"{p.date}_{p.key}_{p.crid}.npz"


def crop_bounds(lake: Lake, epsg: int, margin_m: float = config.WINDOW_MARGIN_M) -> np.ndarray:
    """UTM [x_min, x_max, y_min, y_max] (metres, in `epsg`) of the lake zone plus `margin_m` on every side: the
    outline's bounds buffered by `lakewater.OUTLINE_BUFFER_M` when the lake has a readable outline (as the build
    uses it), else the circle of `zone_radius_km` around the point."""
    from sartale.lakebuild import _load_outline  # lakebuild is heavy; it never imports this module
    from sartale.lakewater import OUTLINE_BUFFER_M, _ring

    tr = Transformer.from_crs(4326, epsg, always_xy=True)
    outline = _load_outline(lake)
    if outline is not None:
        pts = [tr.transform(lon, lat) for lon, lat in _ring(outline)]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        pad = OUTLINE_BUFFER_M + margin_m
    else:
        cx, cy = tr.transform(lake.lon, lake.lat)
        x0, x1, y0, y1 = cx, cx, cy, cy
        pad = lake.zone_radius_km * 1000.0 + margin_m
    return np.array([x0 - pad, x1 + pad, y0 - pad, y1 + pad], float)


def _span_of(axis: np.ndarray, lo: float, hi: float) -> slice:
    """The index range of the pixel centres of a monotonic `axis` within [lo, hi]; the whole axis when none is."""
    idx = np.nonzero((axis >= lo) & (axis <= hi))[0]
    return slice(int(idx.min()), int(idx.max()) + 1) if len(idx) else slice(0, len(axis))


def crop_box(lake: Lake, x: np.ndarray, y: np.ndarray, epsg: int,
             margin_m: float = config.WINDOW_MARGIN_M) -> tuple[slice, slice]:
    """(rows, cols) of the window (pixel-centre axes `x`, `y` in `epsg`) that hold the lake zone plus `margin_m`
    (`crop_bounds`), intersected with the window: never more than the window, and the whole window along an axis
    the zone misses."""
    x0, x1, y0, y1 = crop_bounds(lake, epsg, margin_m)
    x, y = np.asarray(x, float), np.asarray(y, float)
    return _span_of(y, y0, y1), _span_of(x, x0, x1)


def to_cache_dtype(a: np.ndarray) -> np.ndarray:
    """`a` as `config.CACHE_DTYPE` (float16). A positive value stays positive and finite: it is clipped into
    [smallest subnormal, largest finite] (about 6e-8 to 65504, -72 to +48 dB in power), so a very dark pixel does not
    become 0 (no dB) and a bright point target does not become inf. NaN and 0 are kept; a negative value (invalid
    power) is only kept finite."""
    dt = np.dtype(config.CACHE_DTYPE)
    fi = np.finfo(dt)
    a = np.asarray(a, np.float64)
    with np.errstate(invalid="ignore"):
        a = np.where(a > 0, np.clip(a, fi.smallest_subnormal, fi.max), a)
        return np.where(a < 0, np.maximum(a, -fi.max), a).astype(dt)


DROPPED_LAYERS = ("looks",)  # read by nothing in the pipeline: not kept in a cropped window


def crop_window(win: dict, rows: slice, cols: slice, margin_m: float = config.WINDOW_MARGIN_M) -> dict:
    """The window cut to `rows`, `cols`: HH and HV as `config.CACHE_DTYPE` (float16, `to_cache_dtype`), the mask as
    uint8, x and y sliced (the full axes kept as `full_x`, `full_y`), `DROPPED_LAYERS` left out, every other entry
    (epsg, bbox, ...) kept, and the margin it was cut with as `crop_m`."""
    out = {k: v for k, v in win.items() if k not in DROPPED_LAYERS}
    hh = np.asarray(win["hh"])
    for k in ("hh", "hv", "mask"):
        a = win.get(k)
        if a is None or np.ndim(a) != 2 or np.shape(a) != hh.shape:
            continue
        a = np.asarray(a)[rows, cols]
        out[k] = a.astype(np.uint8) if k == "mask" else to_cache_dtype(a)
    out["x"], out["y"] = np.asarray(win["x"])[cols], np.asarray(win["y"])[rows]
    # the full window's axes: lakes-check measures a scene's cloud over the whole 6 km window, as before the crop
    out["full_x"], out["full_y"] = np.asarray(win.get("full_x", win["x"])), np.asarray(win.get("full_y", win["y"]))
    out["crop_m"] = np.float64(margin_m)
    return out


def full_window_reference(win: dict, crid: str, key: str, lake_dir: Path) -> dict:
    """The statistics of the full (uncropped) window `win` the build compares pixels with (`lakebuild.window_reference`),
    on HH and HV with the GCOV validity rule applied by the pass's CRID as the build applies it (`lakebuild.remask`),
    and `dem_grid`: the key of the full window's DEM in `lake_dir`/dem/ (`demmask.grid_key`)."""
    from sartale import demmask
    from sartale.lakebuild import remask, window_reference

    class _Z(dict):
        files = property(lambda self: list(self.keys()))

    hh, hv = remask(_Z(win), crid)
    epsg = int(win["epsg"])
    xs, ys = np.round(np.asarray(win["x"], float), 2), np.round(np.asarray(win["y"], float), 2)
    ref = window_reference(hh, hv, xs, ys, epsg, key[-1], lake_dir)
    return {**ref, "dem_grid": np.str_(demmask.grid_key(xs, ys, epsg))}


def _cropped(lake: Lake, win: dict, crid: str, key: str, lake_dir: Path) -> dict | None:
    """`win` cropped for `lake` (`crop_box`, `crop_window`), carrying its full-window statistics
    (`full_window_reference`, measured before the crop) and the zone-plus-margin bounds it was cut for as `crop_bounds`,
    so `cached_window_fits` can tell when the lake's zone outgrows the crop.

    None when the DEM layover/shadow mask of the full window could not be had (network, or offline with no DEM kept):
    the D17 reference would then be the unmasked median for good, since the crop throws away the pixels to measure it
    again. The caller keeps the window uncropped, and a later shrink crops it once the DEM can be read."""
    epsg = int(win["epsg"])
    ref = full_window_reference(win, crid, key, lake_dir)
    if not float(ref["ref_water_dem"]):
        return None
    rows, cols = crop_box(lake, win["x"], win["y"], epsg)
    return {**crop_window(win, rows, cols), **ref, "crop_bounds": crop_bounds(lake, epsg)}


def _crop_still_fits(z, lake: Lake) -> bool:
    """For a cropped window: cut with the current margin, for zone bounds that hold the lake's current ones (an outline
    or a radius that grew needs a wider window)."""
    from sartale.lakebuild import REF_KEYS

    if float(z["crop_m"]) != config.WINDOW_MARGIN_M or "crop_bounds" not in z.files:
        return False
    if not all(v in z.files for v in REF_KEYS.values()):
        return False  # cropped before the full-window statistics were kept: they cannot be had again
    if not float(z["ref_water_dem"]):
        return False  # its reference was measured without the DEM mask: read the pass again
    have = np.asarray(z["crop_bounds"], float)
    need = crop_bounds(lake, int(z["epsg"]))
    tol = 0.5  # metres
    return bool(have[0] <= need[0] + tol and have[1] >= need[1] - tol and have[2] <= need[2] + tol
                and have[3] >= need[3] - tol)


def cached_window_fits(path: Path, lake: Lake) -> bool:
    """True when the cached window at `path` was read for the lake's current search box and zone.

    A window saved with its `bbox` must match the current box. An older window without one must lie inside the
    box's UTM extent, with one pixel of slack: the read keeps only pixels inside it, so a window read around an
    earlier point of a lake that has since moved sticks out and is fetched again. A cropped window (`crop_m`) must
    also be cut with `config.WINDOW_MARGIN_M` for bounds that hold the lake's current zone plus that margin; an
    uncropped one fits (`shrink_cache` crops it in place). An unreadable file does not fit.
    """
    bbox = lake_bbox(lake)
    try:
        with np.load(path) as z:
            if "crop_m" in z.files and not _crop_still_fits(z, lake):
                return False
            if "bbox" in z.files:
                return bool(np.allclose(np.asarray(z["bbox"], float), bbox, rtol=0, atol=1e-9))
            x, y, epsg = np.asarray(z["x"], float), np.asarray(z["y"], float), int(z["epsg"])
    except (OSError, ValueError, KeyError):
        return False
    if not len(x) or not len(y):
        return False
    lon0, lat0, lon1, lat1 = bbox
    xs, ys = Transformer.from_crs(4326, epsg, always_xy=True).transform([lon0, lon0, lon1, lon1], [lat0, lat1, lat0, lat1])
    px = abs(float(x[1] - x[0])) if len(x) > 1 else 0.0
    py = abs(float(y[1] - y[0])) if len(y) > 1 else 0.0
    return bool(x.min() >= min(xs) - px and x.max() <= max(xs) + px and y.min() >= min(ys) - py
                and y.max() <= max(ys) + py)


def fetch_lake_passes(lake: Lake, passes: list[Pass], cache_dir: Path, session=None, stats: dict | None = None) -> list[Path]:
    """Cache one window per pass. Passes already cached for the lake's current search box are skipped; a window
    cached for an earlier position or a smaller zone of the lake is fetched again (`cached_window_fits`). A pass
    whose window lies outside the grid is skipped with a note. The 6 km search window is read, then cropped to the
    lake zone plus `config.WINDOW_MARGIN_M` in float16 (`crop_window`). Each file is written as .npz.part and renamed
    when complete, with the search box it was read for (`bbox`, not the crop). `stats` (if given) accumulates
    'fetched' bytes and 'requests'."""
    session = session or requests.Session()
    bbox = lake_bbox(lake)
    out = []
    for p in passes:
        path = cache_path(cache_dir, lake.id, p)
        if path.exists() and cached_window_fits(path, lake):
            out.append(path)
            continue
        if path.exists():
            print(f"refetch {lake.id} {p.date} {p.key}: the cached window was read for an earlier lake position or "
                  "zone", flush=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_name(path.name + ".part")
        holder: list = []
        try:
            full = read_window(session, p.url, bbox, holder)
            win = _cropped(lake, full, p.crid, p.key, path.parent)
            if win is None:
                print(f"kept {lake.id} {p.date} {p.key} uncropped: the DEM layover/shadow mask could not be read "
                      "(lakes-cache-shrink crops it once it can)", flush=True)
                win = full
            with open(part, "wb") as fh:
                np.savez_compressed(fh, **win, bbox=np.asarray(bbox, float))
            part.replace(path)
        except ValueError as e:
            part.unlink(missing_ok=True)
            print(f"skip {lake.id} {p.date} {p.key}: {e}", flush=True)
            continue
        except BaseException:
            part.unlink(missing_ok=True)
            raise
        finally:
            if stats is not None and holder:
                stats["fetched"] = stats.get("fetched", 0) + holder[0].fetched
                stats["requests"] = stats.get("requests", 0) + holder[0].requests
        out.append(path)
    return out


def _mb(path: Path) -> float:
    """Size of a file, or of every file under a folder, in MB."""
    p = Path(path)
    if p.is_file():
        return p.stat().st_size / 1e6
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1e6


def _is_window_cache(folder: Path) -> bool:
    """True for a folder that holds lake windows (.npz) or a lake's DEM: the only kind `shrink_cache` deletes."""
    return any(folder.glob("*.npz")) or any(folder.glob("*.npz.part")) or (folder / "dem").is_dir()


def shrink_cache(cache_dir: Path, lakes: list[Lake], listed: dict | None, dry_run: bool = False) -> list[dict]:
    """Shrink the window cache in place (lakes-cache-shrink).

    For each register lake: delete the windows the catalogue no longer lists (`listed`, from passes.json as
    `lakebuild.read_listed` reads it; a lake it lists nothing for, or no list at all, keeps every window) and any
    .npz.part left by a broken fetch, and crop every uncropped window that still fits the lake's search box to the
    zone plus `config.WINDOW_MARGIN_M` in float16 (`crop_window`), keeping its full-window statistics
    (`full_window_reference`, measured first), written as .part and renamed. In each lake's `dem/`, the DEM of every
    window's full grid is kept (lakes-fetch measures new passes with it) and a DEM of any other grid (the build of a
    cropped cache reads none) is deleted. Folders of lakes no longer in the register are deleted. Files at the top of
    the cache (passes.json, logs) are left alone. With `dry_run` nothing changes (no DEM is read either) and the sizes
    are what the shrink would leave, give or take the few bytes of the statistics.

    Returns per lake {"id", "mb_before", "mb_after", "removed": [names]}: the register lakes first, in register
    order, then each deleted folder (mb_after 0, removed ["<id>/"])."""
    import io as _io

    from sartale.demmask import grid_key

    cache_dir = Path(cache_dir)
    ids = {lake.id for lake in lakes}
    report = []
    for lake in lakes:
        d = cache_dir / lake.id
        if not d.is_dir():
            continue
        before = _mb(d)
        after, removed = before, []
        mine = (listed or {}).get(lake.id)
        for f in sorted(d.glob("*.npz.part")):
            removed.append(f.name)
            after -= _mb(f)
            if not dry_run:
                f.unlink()
        grids: set[str] = set()
        for f in sorted(d.glob("*.npz")):
            parts = tuple(f.stem.split("_"))
            if mine and len(parts) == 3 and all(parts) and parts not in mine:
                removed.append(f.name)
                after -= _mb(f)
                if not dry_run:
                    f.unlink()
                continue
            try:
                with np.load(f) as z:
                    arrays = {k: z[k] for k in z.files}
            except (OSError, ValueError):
                continue  # unreadable: lakes-fetch reads it again (cached_window_fits)
            if "dem_grid" in arrays:
                grids.add(str(arrays["dem_grid"]))
            elif "x" in arrays and "y" in arrays and "epsg" in arrays and len(arrays["x"]) > 1:
                grids.add(grid_key(np.round(arrays["x"], 2), np.round(arrays["y"], 2), int(arrays["epsg"])))
            if "crop_m" in arrays or len(parts) != 3 or not all(parts) or not cached_window_fits(f, lake):
                continue  # already cropped, not a pass window, or read for an earlier position: lakes-fetch reads it
            if dry_run:
                epsg = int(arrays["epsg"])
                cropped = crop_window(arrays, *crop_box(lake, arrays["x"], arrays["y"], epsg))
            else:
                cropped = _cropped(lake, arrays, parts[2], parts[1], d)
                if cropped is None:
                    print(f"{lake.id}: {f.name} left uncropped: the DEM layover/shadow mask could not be read "
                          "(the next shrink tries again)", flush=True)
                    continue
            buf = _io.BytesIO()
            np.savez_compressed(buf, **cropped)
            after += buf.getbuffer().nbytes / 1e6 - _mb(f)
            if not dry_run:
                part = f.with_name(f.name + ".part")
                part.write_bytes(buf.getvalue())
                os.replace(part, f)
        if grids and (d / "dem").is_dir():
            for f in sorted((d / "dem").glob("glo30_*.npz")):
                if f.stem.removeprefix("glo30_") not in grids:
                    removed.append(f"dem/{f.name}")
                    after -= _mb(f)
                    if not dry_run:
                        f.unlink()
        report.append({"id": lake.id, "mb_before": round(before, 2), "mb_after": round(after, 2),
                       "removed": removed})
    for d in sorted(p for p in cache_dir.iterdir() if p.is_dir()):
        if d.name in ids or not _is_window_cache(d):
            continue
        report.append({"id": d.name, "mb_before": round(_mb(d), 2), "mb_after": 0.0, "removed": [f"{d.name}/"]})
        if not dry_run:
            shutil.rmtree(d)
    return report
