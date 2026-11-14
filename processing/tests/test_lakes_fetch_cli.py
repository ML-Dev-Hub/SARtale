import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from sartale import run_pipeline
from sartale.lakes import Lake


def _lake(i):
    return Lake(id=i, name=i, lon=1.0, lat=1.0, coord_source="t", outline=None, role="watch",
                downstream=None, downstream_source=None)


def _row(date):
    return {"granule": "G", "url": "https://signed.test/secret", "date": date, "start": date + "T00:00:00+00:00",
            "track": "156", "direction": "A", "frame": "020", "mode": "4005", "crid": "P05023"}


def test_fetch_all_continues_past_a_failing_pass(tmp_path, capsys):
    doc = {"a": {"156A": [_row("2026-07-01"), _row("2026-07-02")]}, "b": {"156A": [_row("2026-07-03")]}}

    def fake(lake, passes, out, session, stats):
        if lake.id == "a" and passes[0].date == "2026-07-01":
            raise ConnectionError("https://signed.test/secret dropped")
        stats["fetched"] = stats.get("fetched", 0) + 1_000_000
        return [tmp_path / "x.npz"]

    failures = run_pipeline.fetch_all([_lake("a"), _lake("b")], doc, tmp_path, None, fetch=fake)
    out = capsys.readouterr().out
    assert failures == ["a 2026-07-01 156A: ConnectionError"]
    assert "b: 1/1 passes cached" in out and "a: 1/2 passes cached" in out
    assert "secret" not in out and "1 passes failed" in out


def test_fetch_takes_at_most_n_new_lakes_per_run(tmp_path, capsys):
    """A new lake (no cached window yet) waits when the run already took `max_new_lakes`; a lake with windows is
    always fetched (its new passes)."""
    from sartale.remote import cache_path

    old = _lake("old")
    (tmp_path / "old").mkdir()
    (tmp_path / "old" / "2026-06-30_156A_P05023.npz").write_bytes(b"x")
    lakes_15_new = [_lake(f"n{i:02d}") for i in range(15)]
    doc = {lk.id: {"156A": [_row("2026-07-01")]} for lk in [old, *lakes_15_new]}
    written = []

    def fake_fetch(lake, passes, out, session, stats):
        paths = [cache_path(out, lake.id, p) for p in passes]
        written.extend(paths)
        return paths

    run_pipeline.fetch_all([old, *lakes_15_new], doc, tmp_path, session=None, fetch=fake_fetch, max_new_lakes=12)
    assert {p.parent.name for p in written} == {"old", *(f"n{i:02d}" for i in range(12))}
    assert "3 new lakes wait for the next run" in capsys.readouterr().out
    written.clear()
    run_pipeline.fetch_all(lakes_15_new, doc, tmp_path, session=None, fetch=fake_fetch, max_new_lakes=None)
    assert len({p.parent.name for p in written}) == 15


def test_lakes_fetch_cli_passes_max_new_lakes(tmp_path, monkeypatch):
    import json
    seen = {}
    monkeypatch.setattr(run_pipeline, "fetch_all", lambda lakes, doc, out, session, **kw: seen.update(kw) or [])
    monkeypatch.setattr(run_pipeline, "load_lakes", lambda p: [])
    passes = tmp_path / "passes.json"
    passes.write_text(json.dumps({"lakes": {}}), encoding="utf-8")
    run_pipeline.main(["lakes-fetch", "--passes", str(passes), "--out", str(tmp_path), "--max-new-lakes", "12"])
    assert seen["max_new_lakes"] == 12
    run_pipeline.main(["lakes-fetch", "--passes", str(passes), "--out", str(tmp_path)])
    assert seen["max_new_lakes"] is None
