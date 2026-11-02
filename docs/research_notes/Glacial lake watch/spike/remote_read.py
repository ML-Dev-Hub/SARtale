"""Spike: read a small lake window from remote NISAR GCOV files with HTTP range requests.

Auth: requests picks up Earthdata credentials from the user's netrc on its own; this script never reads it.
Usage: python remote_read.py granules.json lon0 lat0 lon1 lat1 outdir [max_files]
"""
import io
import json
import sys
import time
from pathlib import Path

import numpy as np
import requests

sys.path.insert(0, r"I:/SARtale/processing")
from sartale.gcov import read_layer  # noqa: E402

BLOCK = 1 << 20  # 1 MiB cache blocks


class RangeFile(io.RawIOBase):
    def __init__(self, session, url):
        r = session.get(url, headers={"Range": "bytes=0-0"}, stream=True, timeout=120)
        r.raise_for_status()
        self.url = r.url  # final, signed URL after the Earthdata redirect
        self.size = int(r.headers["Content-Range"].split("/")[-1])
        r.close()
        self.s, self.pos, self.cache, self.fetched, self.requests = session, 0, {}, 0, 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def _block(self, i):
        if i not in self.cache:
            a = i * BLOCK
            b = min(a + BLOCK, self.size) - 1
            r = self.s.get(self.url, headers={"Range": f"bytes={a}-{b}"}, timeout=120)
            r.raise_for_status()
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
            blk = self._block(p // BLOCK)
            off = p % BLOCK
            take = blk[off: off + n - len(out)]
            out += take
            p += len(take)
        buf[:n] = out
        self.pos += n
        return n


def main():
    gran = json.load(open(sys.argv[1]))
    bbox = tuple(float(v) for v in sys.argv[2:6])
    outdir = Path(sys.argv[6])
    outdir.mkdir(exist_ok=True)
    limit = int(sys.argv[7]) if len(sys.argv) > 7 else len(gran)
    gran = [g for g in gran if "_4005_" in g["id"]][:limit]  # 40+5 MHz mode, same as the Peshawar stack
    s = requests.Session()
    for g in gran:
        t = time.time()
        f = RangeFile(s, g["urls"][0])
        hh = read_layer(f, "HHHH", bbox)
        hv = read_layer(f, "HVHV", bbox)
        key = g["id"].split("_")
        name = f"{g['start'][:10]}_{key[5]}{key[6]}"
        np.savez_compressed(outdir / f"{name}.npz", hh=hh.power, hv=hv.power, looks=hh.looks, mask=hh.mask,
                            x=hh.x, y=hh.y, epsg=hh.epsg)
        print(name, hh.power.shape, f"file {f.size / 1e9:.1f} GB, fetched {f.fetched / 1e6:.1f} MB in {f.requests} requests,"
              f" {time.time() - t:.0f} s", flush=True)


main()
