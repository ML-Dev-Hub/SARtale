import json
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


def _status_once(fixture_h5, status):
    """A RangeFile whose first block read answers `status`; returns (file, call counter)."""
    s = FakeSession(fixture_h5)
    f = remote.RangeFile(s, URL, block=4096)
    orig, seen = s.get, {"bad": 0}

    def get(url, headers=None, **kw):
        if headers["Range"] != "bytes=0-0" and seen["bad"] == 0:
            seen["bad"] = 1
            return FakeResponse(url, status, {}, b"")
        return orig(url, headers=headers, **kw)

    s.get = get
    return f, seen


@pytest.mark.parametrize("status", [401, 404])
def test_rangefile_does_not_retry_client_errors(fixture_h5, status):
    f, _ = _status_once(fixture_h5, status)
    with pytest.raises(requests.HTTPError):
        f.read(100)


@pytest.mark.parametrize("status", [429, 500, 503])
def test_rangefile_retries_rate_limit_and_server_errors(fixture_h5, status):
    f, seen = _status_once(fixture_h5, status)
    assert f.read(100) == fixture_h5.read_bytes()[:100]
    assert seen["bad"] == 1


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


def test_fetch_saves_the_search_box_and_refetches_when_the_lake_moves(tmp_path, fixture_h5, capsys):
    from dataclasses import replace

    from sartale.lakes import lake_bbox

    cache = tmp_path / "cache"
    lake = _mk_lake()
    (path,) = remote.fetch_lake_passes(lake, [_pass()], cache, FakeSession(fixture_h5))
    with np.load(path) as z:
        assert np.allclose(z["bbox"], lake_bbox(lake))
    assert remote.cached_window_fits(path, lake)
    moved = replace(lake, lon=lake.lon + 0.01)  # about 0.9 km east
    assert not remote.cached_window_fits(path, moved)
    s = FakeSession(fixture_h5)
    assert remote.fetch_lake_passes(moved, [_pass()], cache, s) == [path]
    assert s.calls > 0 and "refetch lk" in capsys.readouterr().out
    with np.load(path) as z:
        assert np.allclose(z["bbox"], lake_bbox(moved))


def test_an_older_window_without_a_box_fits_only_inside_the_current_box(tmp_path, fixture_h5):
    from dataclasses import replace

    cache = tmp_path / "cache"
    lake = _mk_lake()
    (path,) = remote.fetch_lake_passes(lake, [_pass()], cache, FakeSession(fixture_h5))
    with np.load(path) as z:
        arrays = {k: z[k] for k in z.files if k != "bbox"}
    np.savez_compressed(path, **arrays)  # as lakes-fetch wrote windows before the box was saved
    assert remote.cached_window_fits(path, lake)
    assert not remote.cached_window_fits(path, replace(lake, lat=lake.lat + 0.01))
    path.write_bytes(b"not a zip")
    assert not remote.cached_window_fits(path, lake)


# --- cropped float16 windows (lake watch overview, task 4) ---

from sartale import config  # noqa: E402
from sartale.lakewater import lee_filter, water_mask  # noqa: E402
from sartale.radiometry import to_db  # noqa: E402

W_EPSG = 32643
PX = 10.0
W_N = 600


def synthetic_window_db(seed: int) -> np.ndarray:
    """A 200x200 dB field: speckle around -12 dB (kept within -45..+5 dB) with a disc at -40 dB."""
    rng = np.random.default_rng(seed)
    db = np.clip(rng.normal(-12.0, 4.0, (200, 200)), -45.0, 5.0)
    yy, xx = np.mgrid[:200, :200]
    disc = (yy - 100) ** 2 + (xx - 100) ** 2 < 40 ** 2
    db[disc] = np.clip(rng.normal(-40.0, 2.0, int(disc.sum())), -45.0, 5.0)
    return db


def d17_water(power: np.ndarray) -> np.ndarray:
    """Water by method D17 as `pass_water` gets it: a Lee filter on linear HH power, dB, then `water_mask`."""
    hh_w = to_db(lee_filter(power))
    return water_mask(hh_w, np.isfinite(hh_w))


def test_float16_round_trip_keeps_the_d17_water_mask():
    hh64 = 10 ** (synthetic_window_db(seed=1) / 10)  # linear power, -45..+5 dB, with a -40 dB lake
    hh16 = hh64.astype(np.float16).astype(np.float64)
    assert (d17_water(hh64) == d17_water(hh16)).mean() >= 0.999


def _lake_at(lid="lk", lon=74.86, lat=36.33, **kw):
    kw.setdefault("outline", None)
    return Lake(id=lid, name=lid, lon=lon, lat=lat, coord_source="test", role="watch",
                downstream=None, downstream_source=None, **kw)


def _grid(lake, n=W_N):
    """An n x n window grid (PX m pixels, y descending) centred on the lake point."""
    from pyproj import Transformer
    cx, cy = Transformer.from_crs(4326, W_EPSG, always_xy=True).transform(lake.lon, lake.lat)
    x = cx - (n // 2) * PX + np.arange(n) * PX
    y = cy + (n // 2) * PX - np.arange(n) * PX
    return x, y, W_EPSG


@pytest.fixture
def circle_lake_1km():
    return _lake_at()


def _outline_lake(tmp_path, lid, dlon, dlat):
    lon, lat = 74.86, 36.33
    ring = [[lon - dlon, lat - dlat], [lon + dlon, lat - dlat], [lon + dlon, lat + dlat], [lon - dlon, lat + dlat],
            [lon - dlon, lat - dlat]]
    f = tmp_path / f"{lid}.geojson"
    f.write_text(json.dumps({"type": "Feature", "properties": {},
                             "geometry": {"type": "Polygon", "coordinates": [ring]}}), encoding="utf-8")
    return _lake_at(lid, outline=str(f))


@pytest.fixture
def long_outline_lake(tmp_path):
    return _outline_lake(tmp_path, "long", 0.06, 0.05)  # about 10.8 x 11 km, wider than the 6 km window


def test_crop_box_is_the_zone_plus_margin_inside_the_window(circle_lake_1km):
    x, y, epsg = _grid(circle_lake_1km)
    rows, cols = remote.crop_box(circle_lake_1km, x, y, epsg)
    assert (cols.stop - cols.start) * PX == pytest.approx(2 * (1000 + 1500), abs=2 * PX)
    assert (rows.stop - rows.start) * PX == pytest.approx(2 * (1000 + 1500), abs=2 * PX)
    rows, cols = remote.crop_box(_lake_at(zone_radius_km=0.3), x, y, epsg)
    assert (cols.stop - cols.start) * PX == pytest.approx(2 * (300 + 1500), abs=2 * PX)


def test_crop_box_never_exceeds_the_window_for_a_large_outline(long_outline_lake):
    x, y, epsg = _grid(long_outline_lake)
    rows, cols = remote.crop_box(long_outline_lake, x, y, epsg)
    assert (rows, cols) == (slice(0, len(y)), slice(0, len(x)))


def test_crop_box_of_an_outline_covers_its_buffered_bounds_plus_the_margin(tmp_path):
    lake = _outline_lake(tmp_path, "small", 0.002, 0.002)  # about 360 x 445 m
    x, y, epsg = _grid(lake)
    rows, cols = remote.crop_box(lake, x, y, epsg)
    width = (cols.stop - cols.start) * PX  # buffer 200 m and margin 1500 m on each side of the outline
    assert width == pytest.approx(360 + 2 * (200 + 1500), abs=4 * PX)


def _window(lake, n=W_N):
    x, y, epsg = _grid(lake, n)
    rng = np.random.default_rng(0)
    return {"hh": rng.uniform(0.01, 1.0, (n, n)), "hv": rng.uniform(0.001, 0.1, (n, n)),
            "looks": np.full((n, n), 5.0, np.float32), "mask": np.ones((n, n), np.uint8), "x": x, "y": y,
            "epsg": np.int64(epsg)}


def test_crop_window_keeps_float16_power_and_records_the_margin(circle_lake_1km):
    win = _window(circle_lake_1km)
    rows, cols = remote.crop_box(circle_lake_1km, win["x"], win["y"], int(win["epsg"]))
    out = remote.crop_window(win, rows, cols)
    assert out["hh"].dtype == out["hv"].dtype == np.float16
    assert "looks" not in out  # read by nothing in the pipeline
    assert out["mask"].dtype == np.uint8
    assert out["hh"].shape == (rows.stop - rows.start, cols.stop - cols.start) == out["mask"].shape
    np.testing.assert_array_equal(out["x"], win["x"][cols])
    np.testing.assert_array_equal(out["y"], win["y"][rows])
    assert float(out["crop_m"]) == config.WINDOW_MARGIN_M and int(out["epsg"]) == int(win["epsg"])


def test_crop_window_keeps_bright_points_finite_and_dark_pixels_positive(circle_lake_1km):
    """Real windows hold point targets up to ~1e7 and noise down to ~1e-9 in linear power: float16 would make them inf
    and 0 (no dB); they are clipped into float16's finite positive range instead. NaN stays NaN."""
    import warnings

    win = _window(circle_lake_1km)
    win["hh"][300, 300], win["hh"][301, 301], win["hh"][302, 302] = 9.6e6, 1e-9, np.nan
    rows, cols = remote.crop_box(circle_lake_1km, win["x"], win["y"], int(win["epsg"]))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        out = remote.crop_window(win, rows, cols)
    hh = out["hh"].astype(np.float64)
    r0, c0 = rows.start, cols.start
    assert hh[300 - r0, 300 - c0] == float(np.finfo(np.float16).max)
    assert hh[301 - r0, 301 - c0] > 0
    assert np.isnan(hh[302 - r0, 302 - c0])
    assert np.isfinite(hh[~np.isnan(hh)]).all()


def _save_full(path, lake):
    """An uncropped float64 window with its search box, as lakes-fetch wrote them before the crop."""
    from sartale.lakes import lake_bbox
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **_window(lake), bbox=np.asarray(lake_bbox(lake), float))


def test_shrink_cache_drops_unlisted_windows_and_unregistered_lakes_and_keeps_dem(tmp_path, circle_lake_1km):
    lake = circle_lake_1km
    _save_full(tmp_path / lake.id / "2026-06-18_055A_P05023.npz", lake)
    _save_full(tmp_path / lake.id / "2026-06-30_055A_P05023.npz", lake)  # no longer in the catalogue
    from sartale.demmask import grid_key
    x, y, epsg = _grid(lake)
    full_dem = tmp_path / lake.id / "dem" / f"glo30_{grid_key(np.round(x, 2), np.round(y, 2), epsg)}.npz"
    full_dem.parent.mkdir()
    # the full window's grid: lakes-fetch measures new passes with it
    np.savez_compressed(full_dem, dem=np.zeros((W_N + 600, W_N + 600), np.float32))
    (tmp_path / lake.id / "dem" / "glo30_0123456789abcdef.npz").write_bytes(b"old")  # a grid no window has
    _save_full(tmp_path / "batura" / "2026-06-18_055A_P05023.npz", lake)  # not in the register
    (tmp_path / "passes.json").write_text("{}", encoding="utf-8")
    report = remote.shrink_cache(tmp_path, [lake], listed={lake.id: {("2026-06-18", "055A", "P05023")}})
    assert sorted(p.name for p in (tmp_path / lake.id).iterdir()) == ["2026-06-18_055A_P05023.npz", "dem"]
    assert not (tmp_path / "batura").exists()
    assert (tmp_path / "passes.json").exists() and full_dem.exists()
    assert [f.name for f in (tmp_path / lake.id / "dem").iterdir()] == [full_dem.name]
    with np.load(tmp_path / lake.id / "2026-06-18_055A_P05023.npz") as z:
        assert z["hh"].dtype == np.float16 and float(z["crop_m"]) == 1500.0
        assert "bbox" in z.files and "looks" not in z.files
        assert np.isfinite(float(z["ref_water_all_db"])) and str(z["dem_grid"]) == full_dem.stem[6:]
        assert len(z["full_x"]) == len(z["full_y"]) == W_N  # the full window grid, for lakes-check
    assert report[0]["id"] == lake.id
    assert report[0]["removed"] == ["2026-06-30_055A_P05023.npz", "dem/glo30_0123456789abcdef.npz"]
    assert report[0]["mb_after"] < report[0]["mb_before"]
    assert any(r["id"] == "batura" and r["mb_after"] == 0 for r in report)
    assert remote.cached_window_fits(tmp_path / lake.id / "2026-06-18_055A_P05023.npz", lake)


def test_shrink_cache_dry_run_changes_nothing(tmp_path, circle_lake_1km):
    lake = circle_lake_1km
    path = tmp_path / lake.id / "2026-06-18_055A_P05023.npz"
    _save_full(path, lake)
    _save_full(tmp_path / "batura" / "2026-06-18_055A_P05023.npz", lake)
    before = path.read_bytes()
    report = remote.shrink_cache(tmp_path, [lake], listed={lake.id: {("2026-06-18", "055A", "P05023")}},
                                 dry_run=True)
    assert path.read_bytes() == before and (tmp_path / "batura").exists()
    assert report[0]["mb_after"] < report[0]["mb_before"]


def test_shrink_cache_keeps_the_windows_of_a_lake_the_catalogue_listed_nothing_for(tmp_path, circle_lake_1km):
    """A lake with no listed pass (a catalogue hiccup) or no passes.json keeps its windows: they are only cropped."""
    lake = circle_lake_1km
    path = tmp_path / lake.id / "2026-06-18_055A_P05023.npz"
    for listed in ({lake.id: set()}, {}, None):
        _save_full(path, lake)
        remote.shrink_cache(tmp_path, [lake], listed=listed)
        with np.load(path) as z:
            assert z["hh"].dtype == np.float16


def test_a_window_cropped_with_another_margin_or_for_a_smaller_zone_does_not_fit(tmp_path, circle_lake_1km):
    from dataclasses import replace

    small = replace(circle_lake_1km, zone_radius_km=0.3)
    path = tmp_path / small.id / "2026-06-18_055A_P05023.npz"
    _save_full(path, small)
    assert remote.cached_window_fits(path, small)  # an uncropped window fits (the shrink crops it in place)
    remote.shrink_cache(tmp_path, [small], listed=None)
    assert remote.cached_window_fits(path, small)
    assert not remote.cached_window_fits(path, circle_lake_1km)  # the 1 km circle needs a wider crop
    with np.load(path) as z:
        arrays = {k: z[k] for k in z.files}
    np.savez_compressed(path, **{**arrays, "crop_m": np.float64(1000.0)})
    assert not remote.cached_window_fits(path, small)


def test_fetch_saves_a_cropped_float16_window(tmp_path, fixture_h5):
    (path,) = remote.fetch_lake_passes(_mk_lake(), [_pass()], tmp_path / "cache", FakeSession(fixture_h5))
    with np.load(path) as z:
        assert z["hh"].dtype == z["hv"].dtype == np.float16 and float(z["crop_m"]) == config.WINDOW_MARGIN_M
        assert np.isfinite(float(z["ref_water_all_db"])) and "looks" not in z.files
        assert z["hh"].shape[1] * 100.0 == pytest.approx(2 * (1000 + 1500), abs=200)  # the fixture's 100 m grid
    assert remote.cached_window_fits(path, _mk_lake())


def test_a_window_cropped_without_its_full_window_statistics_is_fetched_again(tmp_path, circle_lake_1km):
    """A window cropped before the statistics were kept (the first version of the crop) cannot give them back: it does
    not fit, so lakes-fetch reads the pass again."""
    from sartale.lakebuild import REF_KEYS
    lake = circle_lake_1km
    path = tmp_path / lake.id / "2026-06-18_055A_P05023.npz"
    _save_full(path, lake)
    remote.shrink_cache(tmp_path, [lake], listed=None)
    assert remote.cached_window_fits(path, lake)
    with np.load(path) as z:
        arrays = {k: z[k] for k in z.files if k not in REF_KEYS.values()}
    np.savez_compressed(path, **arrays)
    assert not remote.cached_window_fits(path, lake)
