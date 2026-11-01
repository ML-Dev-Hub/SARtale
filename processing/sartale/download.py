"""Download GCOV files named in a search manifest, safely.

Uses a `requests` session, which reads Earthdata credentials from ~/.netrc. This module never reads,
prints or logs credentials, headers or tokens. Each file is written to `<name>.h5.part`, resumed with a
Range request after an interruption, and renamed to `<name>.h5` only when its size and MD5 both match
the values CMR published (stored in the manifest by `search`).
"""
import hashlib
import json
import time
from pathlib import Path

import requests

from sartale.catalog import granule_for_date

BASE_URL = "https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GCOV_PROVISIONAL_V1"
CHUNK = 1 << 22
HASH_CHUNK = 1 << 24
CONNECT_TIMEOUT = 60
READ_TIMEOUT = 180


def granule_url(name: str) -> str:
    return f"{BASE_URL}/{name}/{name}.h5"


def md5_of(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(HASH_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def _fetch(session, url: str, part: Path, size: int) -> None:
    """One attempt: append to `part` from where it stopped. Raises requests exceptions on network errors."""
    have = part.stat().st_size if part.exists() else 0
    if have > size:
        part.unlink()
        have = 0
    if have == size:
        return
    headers = {"Range": f"bytes={have}-"} if have else {}
    with session.get(url, headers=headers, stream=True, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)) as r:
        if r.status_code == 416:  # the part is not a prefix we can resume
            part.unlink(missing_ok=True)
            return
        if r.status_code == 200 and have:  # server ignored the Range header: start over
            part.unlink()
            have = 0
        elif r.status_code in (401, 403):
            raise ValueError(f"HTTP {r.status_code}: Earthdata login was refused. Check ~/.netrc and the data terms")
        elif 400 <= r.status_code < 500:
            raise ValueError(f"HTTP {r.status_code} for {Path(url).name}")
        elif r.status_code not in (200, 206):
            raise requests.HTTPError(f"HTTP {r.status_code} for {Path(url).name}")
        with open(part, "ab" if have else "wb") as f:
            for chunk in r.iter_content(CHUNK):
                f.write(chunk)


def download_file(session, name: str, size: int, md5: str, out_dir: Path,
                  retries: int = 8, sleep=time.sleep, log=print) -> Path:
    """Download one granule to out_dir/<name>.h5. Returns the path. Raises ValueError on a size or MD5 mismatch."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    final = out_dir / f"{name}.h5"
    part = out_dir / f"{name}.h5.part"
    if final.exists():
        if final.stat().st_size == size and md5_of(final) == md5:
            log(f"{name}: already present and verified")
            return final
        raise ValueError(f"{final} exists but does not match CMR's size and MD5; move it away and run again")
    url = granule_url(name)
    for attempt in range(retries):
        try:
            _fetch(session, url, part, size)
        except (requests.RequestException, OSError) as err:
            log(f"{name}: retry {attempt + 1} after {type(err).__name__}")
            sleep(10)
            continue
        if part.exists() and part.stat().st_size >= size:
            break
        sleep(1)
    if not part.exists() or part.stat().st_size != size:
        got = part.stat().st_size if part.exists() else 0
        raise ValueError(f"{name}: got {got} of {size} bytes; run the command again to resume")
    if md5_of(part) != md5:
        part.unlink()
        raise ValueError(f"{name}: MD5 does not match CMR, the partial file was deleted; run again")
    part.replace(final)
    log(f"{name}: downloaded and verified ({size} bytes)")
    return final


def download(manifest_path: Path, dates: list[str], out_dir: Path, session=None,
             sleep=time.sleep, log=print) -> list[Path]:
    """Download the granule for each date in the search manifest. Needs size and md5 in the manifest."""
    search = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    jobs = []
    for d in sorted(dates):
        g = granule_for_date(search["granules"], d)
        if not g.get("size") or not g.get("md5"):
            raise ValueError(f"The manifest has no size or md5 for {d}; run `search` again to refresh it")
        jobs.append((g["name"], int(g["size"]), g["md5"]))
    session = session if session is not None else requests.Session()
    return [download_file(session, n, s, m, out_dir, sleep=sleep, log=log) for n, s, m in jobs]
