"""lakes-fetch with bounded concurrency gives the same files (and the same log) as the sequential run.

The fetch runs the real `fetch_lake_passes` (HTTP range reads through h5py, crop, full-window statistics, DEM masks)
in worker processes against a fake remote (`fake_remote`): several lakes and passes, one URL that always fails, one
whose first range read is refused with a 429, two passes that share one cache file, and lakes seen from both look
directions (so two passes add masks to the same DEM file)."""
import contextlib
import io
import json
import re
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import numpy as np
import pytest

from fake_remote import FakeRemote
from gcov_fixture import write_gcov
from sartale import config, demmask, run_pipeline
from sartale.gcov import read_layer
from sartale.lake_catalog import Pass
from sartale.lakes import Lake, lake_bbox

POINTS = {"a": (71.750, 34.150), "b": (71.760, 34.150), "c": (71.745, 34.155), "d": (71.755, 34.145),
          "e": (71.748, 34.152), "f": (71.752, 34.148), "g": (71.746, 34.149)}


def _lake(lid):
    lon, lat = POINTS[lid]
    return Lake(id=lid, name=lid, lon=lon, lat=lat, coord_source="t", outline=None, role="watch",
                downstream=None, downstream_source=None)


def _pass(lid, day, track="156", direction="A", granule="G", url=None):
    date = f"2026-07-{day:02d}"
    url = url or f"https://remote.test/{lid}/{date}/{track}{direction}/{granule}.h5"
    return Pass(granule=granule, url=url, date=date, start=date + "T00:00:00+00:00", track=track, direction=direction,
                frame="020", mode="4005", crid="P05023")


def _seed_dem(out: Path, lake: Lake, h5: Path):
    """A flat DEM (no mask) on the lake's full-window grid, as a kept dem/glo30_<grid>.npz holding only the DEM: every
    pass then adds its look direction's mask to the same file (tests run with SARTALE_DEM_OFFLINE set)."""
    lay = read_layer(h5, "HHHH", lake_bbox(lake))
    xs, ys = np.round(np.asarray(lay.x, float), 2), np.round(np.asarray(lay.y, float), 2)
    margin = int(round(config.DEM_MARGIN_M / abs(float(xs[1] - xs[0]))))
    path = out / lake.id / "dem" / f"glo30_{demmask.grid_key(xs, ys, lay.epsg)}.npz"
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, dem=np.zeros((len(ys) + 2 * margin, len(xs) + 2 * margin), np.float32))


def _scenario(tmp_path, ids=("a", "b", "c")):
    h5 = write_gcov(tmp_path / "g.h5")
    passes = {
        "a": [_pass("a", d) for d in (1, 13, 25)] + [_pass("a", d, "157", "D") for d in (5, 17)],
        "b": [_pass("b", d) for d in (2, 14, 26)] + [_pass("b", 14, granule="G2")],  # two passes, one cache file
        "c": [_pass("c", d) for d in (3, 15, 27)],
    }
    for lid in ids:
        passes.setdefault(lid, [_pass(lid, d) for d in (4, 16)])
    fail = passes["b"][1].url  # the first of the two passes sharing a file: the second then fetches it
    flaky = passes["c"][1].url
    files = {p.url: h5 for ps in passes.values() for p in ps}
    doc = {lid: {} for lid in ids}
    for lid in ids:
        for p in passes[lid]:
            doc[lid].setdefault(p.key, []).append(asdict(p))
    return h5, doc, files, fail, flaky


def _run(tmp_path, name, ids, workers, latency=0.0, max_new_lakes=None, prepare=None):
    h5, doc, files, fail, flaky = _scenario(tmp_path, ids)
    out = tmp_path / name
    out.mkdir()
    lakes = [_lake(i) for i in ids]
    for lake in lakes:
        _seed_dem(out, lake, h5)
    if prepare:
        prepare(out)
    flags = tmp_path / f"{name}-429"
    flags.mkdir()
    remote = FakeRemote(files, latency=latency, fail_urls={fail}, flaky_urls={flaky}, flaky_dir=flags)
    buf = io.StringIO()
    t = time.perf_counter()
    with contextlib.redirect_stdout(buf):
        failures = run_pipeline.fetch_all(lakes, doc, out, remote(), max_new_lakes=max_new_lakes, workers=workers,
                                          session_factory=remote)
    took = time.perf_counter() - t
    return out, failures, buf.getvalue(), took


def _files(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def _log(text: str) -> list[str]:
    """The log without the run's duration."""
    return [re.sub(r" in \d+ s$", " in N s", ln) for ln in text.splitlines()]


@pytest.fixture(scope="module")
def sequential_and_parallel(tmp_path_factory):
    """One sequential (1 worker) and one parallel (4 worker processes) fetch of the same scenario."""
    tmp = tmp_path_factory.mktemp("pf")
    seq = _run(tmp, "seq", ("a", "b", "c"), 1)
    par = _run(tmp, "par", ("a", "b", "c"), 4)
    return seq, par


def test_parallel_fetch_writes_the_same_files_as_the_sequential_one(sequential_and_parallel):
    (seq_out, _, _, _), (par_out, _, _, _) = sequential_and_parallel
    seq, par = _files(seq_out), _files(par_out)
    assert sorted(seq) == sorted(par)
    assert not [n for n in seq if n.endswith((".part", ".tmp.npz"))], "no temporary file is left behind"
    assert sum(n.endswith(".npz") and "/dem/" not in n for n in seq) == 11, "12 passes, two of them share a file"
    differ = [n for n in seq if seq[n] != par[n]]
    assert not differ, f"files differ between the sequential and the parallel fetch: {differ}"


def test_parallel_fetch_reports_failures_and_logs_like_the_sequential_one(sequential_and_parallel):
    (_, seq_failures, seq_log, _), (_, par_failures, par_log, _) = sequential_and_parallel
    assert seq_failures == par_failures == ["b 2026-07-14 156A: HTTPError"]
    assert _log(seq_log) == _log(par_log)
    assert "FAILED b 2026-07-14 156A: HTTPError" in par_log and "remote.test" not in par_log
    assert "c: 3/3 passes cached" in par_log, "the pass refused once with a 429 is fetched on the retry"
    assert "b: 3/4 passes cached" in par_log


def test_both_look_directions_keep_their_mask_in_the_shared_dem_file(sequential_and_parallel):
    (_, _, _, _), (par_out, _, _, _) = sequential_and_parallel
    (dem,) = (par_out / "a" / "dem").glob("glo30_*.npz")
    with np.load(dem) as z:
        names = list(z.files)
    assert names[0] == "dem" and sorted(n[:6] for n in names[1:]) == ["mask_A", "mask_D"]
    assert names == ["dem", *sorted(names[1:])], "kept in one order, whichever pass added its mask first"


def test_max_new_lakes_holds_under_concurrency(tmp_path):
    def old_lake(out):
        (out / "a" / "2026-06-30_156A_P05023.npz").write_bytes(b"x")  # "a" already has a cached window

    out, failures, log, _ = _run(tmp_path, "lim", ("a", "d", "e", "f", "g"), 4, max_new_lakes=2,
                                 prepare=old_lake)
    fetched = {p.parent.name for p in out.glob("*/2026-07-*.npz")}
    assert fetched == {"a", "d", "e"}
    assert "2 new lakes wait for the next run (at most 2 new lakes per run): f, g" in log


def test_lakes_fetch_takes_a_worker_count(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(run_pipeline, "fetch_all", lambda lakes, doc, out, session, **kw: seen.update(kw) or [])
    monkeypatch.setattr(run_pipeline, "load_lakes", lambda p: [])
    passes = tmp_path / "passes.json"
    passes.write_text(json.dumps({"lakes": {}}), encoding="utf-8")
    run_pipeline.main(["lakes-fetch", "--passes", str(passes), "--out", str(tmp_path)])
    assert seen["workers"] == run_pipeline.FETCH_WORKERS == 6
    run_pipeline.main(["lakes-fetch", "--passes", str(passes), "--out", str(tmp_path), "--workers", "1"])
    assert seen["workers"] == 1
