import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import numpy as np
import pytest
import requests

from gcov_fixture import write_gcov
from sartale import remote
from sartale.gcov import read_layer
from sartale.lake_catalog import Pass
from sartale.lakes import Lake

BBOX = (71.74, 34.14, 71.76, 34.16)
URL = "https://example.test/file.h5"


class FakeResponse:
    def __init__(self, url, status, headers, content):
        self.url, self.status_code, self.headers, self.content = url, status, headers, content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}", response=self)

    def close(self):
        pass


class FakeSession:
    """Serves byte ranges of a local file; `fail_first` raises that many ConnectionErrors, `always_fail` never works."""

    def __init__(self, path, fail_first=0, always_fail=False):
        self.data = Path(path).read_bytes()
        self.fail_first, self.always_fail = fail_first, always_fail
        self.calls = 0
        self.range_calls = 0

    def get(self, url, headers=None, **kw):
        self.calls += 1
        if self.always_fail or self.fail_first > 0:
            self.fail_first -= 1
            raise requests.ConnectionError("dropped")
        a, b = headers["Range"].removeprefix("bytes=").split("-")
        a, b = int(a), int(b)
        if b > 0:
            self.range_calls += 1
        chunk = self.data[a: b + 1]
        return FakeResponse("https://signed.test/x", 206, {"Content-Range": f"bytes {a}-{a + len(chunk) - 1}/{len(self.data)}"}, chunk)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(remote, "_sleep", lambda s: None)


@pytest.fixture
def fixture_h5(tmp_path):
    return write_gcov(tmp_path / "g.h5")


def _pass():
    return Pass(granule="G", url=URL, date="2026-07-01", start="2026-07-01T00:00:00+00:00", track="156",
                direction="A", frame="020", mode="4005", crid="P05023")


def test_rangefile_reads_same_bytes_as_local(fixture_h5):
    f = remote.RangeFile(FakeSession(fixture_h5), URL, block=4096)
    assert f.size == fixture_h5.stat().st_size
    assert f.read() == fixture_h5.read_bytes()
    assert f.fetched >= f.size


def test_read_window_matches_local_read_layer(fixture_h5):
    got = remote.read_window(FakeSession(fixture_h5), URL, BBOX)
    for term, key in (("HHHH", "hh"), ("HVHV", "hv")):
        local = read_layer(fixture_h5, term, BBOX)
        np.testing.assert_array_equal(got[key], local.power)
    local = read_layer(fixture_h5, "HHHH", BBOX)
    np.testing.assert_array_equal(got["looks"], local.looks)
    np.testing.assert_array_equal(got["mask"], local.mask)
    np.testing.assert_array_equal(got["x"], local.x)
    np.testing.assert_array_equal(got["y"], local.y)
    assert got["epsg"] == local.epsg


def test_rangefile_retries_after_disconnect(fixture_h5):
    s = FakeSession(fixture_h5)
    f = remote.RangeFile(s, URL, block=4096)  # constructed fine; now drop the next block read
    s.fail_first, before = 1, s.calls
    assert f.read() == fixture_h5.read_bytes()
    assert s.calls - before == f.requests + 1  # one failed attempt, retried
    assert f.requests >= 1


def test_rangefile_reresolves_after_403(fixture_h5):
    s = FakeSession(fixture_h5)
    f = remote.RangeFile(s, URL, block=4096)
    orig, seen = s.get, {"n": 0, "resolves": 0}

    def get(url, headers=None, **kw):
        if headers["Range"] == "bytes=0-0":
            seen["resolves"] += 1
        elif seen["n"] == 0:
            seen["n"] = 1
            return FakeResponse(url, 403, {}, b"")
        r = orig(url, headers=headers, **kw)
        if headers["Range"] == "bytes=0-0":
            r.url = "https://signed.test/renewed"
        return r

    s.get = get
    assert f.read(100) == fixture_h5.read_bytes()[:100]
    assert seen["resolves"] == 1 and f.url == "https://signed.test/renewed"


def test_fetch_leaves_no_partial_cache_when_connection_never_works(tmp_path, fixture_h5):
    cache = tmp_path / "cache"
    with pytest.raises(requests.ConnectionError):
        remote.fetch_lake_passes(_mk_lake(), [_pass()], cache, FakeSession(fixture_h5, always_fail=True))
    assert not list(cache.rglob("*.npz")) and not list(cache.rglob("*.npz.part"))


def test_fetch_leaves_no_partial_cache(tmp_path, fixture_h5, monkeypatch):
    cache = tmp_path / "cache"
    seen = {}

    def boom(fh, **arrays):
        fh.write(b"half")  # the .part is open and non-empty when the write fails
        seen["part"] = Path(fh.name)
        raise OSError("disk dropped")

    monkeypatch.setattr(remote.np, "savez_compressed", boom)
    with pytest.raises(OSError):
        remote.fetch_lake_passes(_mk_lake(), [_pass()], cache, FakeSession(fixture_h5))
    assert seen["part"].name.endswith(".npz.part")
    assert not list(cache.rglob("*.npz")) and not list(cache.rglob("*.npz.part"))


def test_fetch_skips_cached(tmp_path, fixture_h5):
    cache = tmp_path / "cache"
    s = FakeSession(fixture_h5)
    paths = remote.fetch_lake_passes(_mk_lake(), [_pass()], cache, s)
    assert paths == [remote.cache_path(cache, "lk", _pass())] and paths[0].exists()
    assert paths[0].name == "2026-07-01_156A_P05023.npz"
    s2 = FakeSession(fixture_h5)
    assert remote.fetch_lake_passes(_mk_lake(), [_pass()], cache, s2) == paths
    assert s2.calls == 0


def test_fetch_skips_pass_outside_grid(tmp_path, fixture_h5, capsys):
    lake = _mk_lake(lon=10.0, lat=10.0)
    assert remote.fetch_lake_passes(lake, [_pass()], tmp_path / "c", FakeSession(fixture_h5)) == []
    assert "skip" in capsys.readouterr().out.lower()
    assert not list((tmp_path / "c").rglob("*.part"))


def _mk_lake(lon=71.75, lat=34.15):
    return Lake(id="lk", name="Lk", lon=lon, lat=lat, coord_source="test", outline=None, role="watch",
                downstream=None, downstream_source=None)
