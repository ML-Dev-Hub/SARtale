"""Read small lake windows from remote NISAR GCOV files with HTTP range requests, cached as .npz."""
import io
import time
from pathlib import Path

import numpy as np
import requests
from pyproj import Transformer

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


def cached_window_fits(path: Path, lake: Lake) -> bool:
    """True when the cached window at `path` was read for the lake's current search box.

    A window saved with its `bbox` must match the current box. An older window without one must lie inside the
    box's UTM extent, with one pixel of slack: the read keeps only pixels inside it, so a window read around an
    earlier point of a lake that has since moved sticks out and is fetched again. An unreadable file does not fit.
    """
    bbox = lake_bbox(lake)
    try:
        with np.load(path) as z:
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
    cached for an earlier position of the lake is fetched again (`cached_window_fits`). A pass whose window lies
    outside the grid is skipped with a note. Each file is written as .npz.part and renamed when complete, with the
    search box it was read for. `stats` (if given) accumulates 'fetched' bytes and 'requests'."""
    session = session or requests.Session()
    bbox = lake_bbox(lake)
    out = []
    for p in passes:
        path = cache_path(cache_dir, lake.id, p)
        if path.exists() and cached_window_fits(path, lake):
            out.append(path)
            continue
        if path.exists():
            print(f"refetch {lake.id} {p.date} {p.key}: the cached window was read for an earlier lake position",
                  flush=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_name(path.name + ".part")
        holder: list = []
        try:
            win = read_window(session, p.url, bbox, holder)
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
