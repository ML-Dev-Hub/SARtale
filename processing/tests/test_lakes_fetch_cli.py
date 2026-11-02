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
