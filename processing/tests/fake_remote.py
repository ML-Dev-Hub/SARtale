"""A fake Earthdata remote for the parallel-fetch tests: serves byte ranges of local GCOV fixtures per URL, with an
injected latency per request, URLs that always fail (404) and URLs whose first range read is refused with a 429.

Everything here is a module-level class, so the session factory can be pickled into the fetch worker processes (which
import this module from the parent's sys.path). The "first read refused" state lives on disk (a marker file created
with O_EXCL), so a URL is refused exactly once whichever process reads it first.
"""
import hashlib
import os
import time
from pathlib import Path

import requests


class FakeResponse:
    def __init__(self, url, status, headers, content):
        self.url, self.status_code, self.headers, self.content = url, status, headers, content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}", response=self)

    def close(self):
        pass


class FakeRemote:
    """Session factory: `files` maps URL -> local file; `latency` seconds per request; `fail_urls` answer 404 for
    good; the first range read (past byte 0) of each URL in `flaky_urls` answers 429 once, recorded in `flaky_dir`."""

    def __init__(self, files: dict, latency: float = 0.0, fail_urls=(), flaky_urls=(), flaky_dir=None):
        self.files = {u: str(p) for u, p in files.items()}
        self.latency, self.fail_urls, self.flaky_urls = latency, set(fail_urls), set(flaky_urls)
        self.flaky_dir = None if flaky_dir is None else str(flaky_dir)

    def __call__(self):
        return FakeSession(self)


class FakeSession:
    def __init__(self, remote: FakeRemote):
        self.remote = remote
        self.data: dict[str, bytes] = {}

    def _bytes(self, url):
        if url not in self.data:
            self.data[url] = Path(self.remote.files[url]).read_bytes()
        return self.data[url]

    def _first_refusal(self, url) -> bool:
        if url not in self.remote.flaky_urls:
            return False
        marker = Path(self.remote.flaky_dir) / hashlib.sha1(url.encode()).hexdigest()
        try:
            os.close(os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return True
        except FileExistsError:
            return False

    def get(self, url, headers=None, **kw):
        if self.remote.latency:
            time.sleep(self.remote.latency)
        if url in self.remote.fail_urls:
            return FakeResponse(url, 404, {}, b"")
        a, b = (int(v) for v in headers["Range"].removeprefix("bytes=").split("-"))
        if b > 0 and self._first_refusal(url):
            return FakeResponse(url, 429, {}, b"")
        data = self._bytes(url)
        chunk = data[a: b + 1]
        return FakeResponse(url, 206, {"Content-Range": f"bytes {a}-{a + len(chunk) - 1}/{len(data)}"}, chunk)
