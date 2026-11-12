"""lakes-diff: added, dropped and reprocessed passes, backwards latest dates, the drop threshold, and the
lakes-search catalogue-outage stop."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import pytest

from sartale import run_pipeline
from sartale.lakes import Lake
from sartale.lakes_diff import diff_lakes, summary_markdown, warnings


def _lake(lid, passes, latest):
    """passes: list of (date, track) or (date, track, crid)."""
    series = [{"date": p[0], "track": p[1], "area_km2": 0.1, "observable_share": 1.0, "excluded": None,
               **({"crid": p[2]} if len(p) > 2 else {})} for p in passes]
    return {"id": lid, "series": series, "status": {"latest_date": latest}}


def _doc(*lakes):
    return {"lakes": list(lakes)}


OLD = _doc(
    _lake("attabad", [("2026-10-11", "156A"), ("2026-10-16", "055A"), ("2026-10-23", "156A", "P05023")], "2026-10-23"),
    _lake("passu", [("2026-10-11", "156A"), ("2026-10-23", "156A")], "2026-10-23"),
    _lake("shisper", [("2026-10-11", "156A"), ("2026-10-16", "055A"), ("2026-10-23", "156A")], "2026-10-23"),
)


def test_added_dropped_and_reprocessed_passes_per_lake():
    new = _doc(
        _lake("attabad", [("2026-10-11", "156A"), ("2026-10-16", "055A"), ("2026-10-23", "156A", "P05036"),
                          ("2026-11-04", "156A", "P05036")], "2026-11-04"),
        _lake("passu", [("2026-10-11", "156A"), ("2026-10-23", "156A")], "2026-10-23"),
        _lake("shisper", [("2026-10-11", "156A"), ("2026-10-16", "055A"), ("2026-10-23", "156A")], "2026-10-23"),
    )
    r = diff_lakes(OLD, new)
    a = next(x for x in r["lakes"] if x["id"] == "attabad")
    assert a["added"] == ["2026-11-04 156A"] and a["dropped"] == []
    assert a["reprocessed"] == ["2026-10-23 156A P05023 -> P05036"]
    assert (r["added"], r["dropped"], r["backwards"], r["fail"]) == (1, 0, [], None)
    assert warnings(r) == []


def test_a_dropped_pass_and_a_backwards_latest_date_warn():
    new = _doc(
        _lake("attabad", [("2026-10-11", "156A"), ("2026-10-16", "055A")], "2026-10-16"),
        _lake("passu", [("2026-10-11", "156A"), ("2026-10-23", "156A")], "2026-10-23"),
        _lake("shisper", [("2026-10-11", "156A"), ("2026-10-16", "055A"), ("2026-10-23", "156A")], "2026-10-23"),
    )
    r = diff_lakes(OLD, new)
    assert r["dropped"] == 1 and r["backwards"] == ["attabad"] and r["fail"] is None  # 1 of 8 is under a quarter
    w = warnings(r)
    assert "::warning::attabad: pass 2026-10-23 156A was published before and is gone from this build" in w
    assert "::warning::attabad: latest date moved backwards, 2026-10-23 -> 2026-10-16" in w
    md = summary_markdown(r)
    assert "| attabad | - | 2026-10-23 156A |" in md and "moved backwards: attabad" in md


def test_more_than_a_quarter_dropped_fails_and_a_quarter_does_not():
    two = _doc(_lake("attabad", [("2026-10-11", "156A")], "2026-10-11"),
               _lake("passu", [("2026-10-11", "156A")], "2026-10-11"),
               _lake("shisper", [("2026-10-11", "156A"), ("2026-10-16", "055A")], "2026-10-16"))
    r = diff_lakes(OLD, two)  # 4 of 8 dropped
    assert r["dropped"] == 4 and "4 of 8 previously published passes" in r["fail"]
    quarter = _doc(_lake("attabad", [("2026-10-11", "156A"), ("2026-10-16", "055A")], "2026-10-16"),
                   _lake("passu", [("2026-10-11", "156A")], "2026-10-11"),
                   OLD["lakes"][2])
    assert diff_lakes(OLD, quarter)["fail"] is None  # exactly 2 of 8


def test_freeze_state_changes_are_reported_but_never_count_as_dropped_passes():
    import copy
    new = copy.deepcopy(OLD)
    a = new["lakes"][0]
    a["freeze"] = {"state": "frozen_likely"}
    for p in a["series"][1:]:
        p["frozen"] = True  # two passes now flagged frozen: their area stays, they leave the baseline
    a["status"] = {"latest_date": "2026-10-23", "status": "Frozen (likely)"}
    r = diff_lakes(OLD, new)
    assert (r["dropped"], r["added"], r["backwards"], r["fail"]) == (0, 0, [], None)
    row = next(x for x in r["lakes"] if x["id"] == "attabad")
    assert (row["freeze_before"], row["freeze_after"]) == (None, "frozen_likely")
    assert warnings(r) == []
    assert "| - | frozen_likely |" in summary_markdown(r)
    from sartale.lakes_diff import text_report
    assert "attabad: latest 2026-10-23 -> 2026-10-23; added 0, dropped 0; freeze - -> frozen_likely" in text_report(r)
    # and back again: a thawed lake's passes are the same passes
    back = diff_lakes(new, OLD)
    assert (back["dropped"], back["added"]) == (0, 0)


def test_a_lake_gone_from_the_build_counts_as_dropped():
    r = diff_lakes(OLD, _doc(*OLD["lakes"][:2]))
    assert next(x for x in r["lakes"] if x["id"] == "shisper")["dropped"] == ["2026-10-11 156A", "2026-10-16 055A",
                                                                             "2026-10-23 156A"]
    assert "shisper" in r["backwards"] and r["fail"] is not None


def _diff_cli(tmp_path, old, new, monkeypatch):
    o, n, summ = tmp_path / "old.json", tmp_path / "new.json", tmp_path / "summary.md"
    if old is not None:
        o.write_text(json.dumps(old), encoding="utf-8")
    n.write_text(json.dumps(new), encoding="utf-8")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summ))
    run_pipeline.main(["lakes-diff", "--old", str(o), "--new", str(n)])
    return summ


def test_lakes_diff_cli_writes_the_summary_and_exits_zero(tmp_path, monkeypatch, capsys):
    summ = _diff_cli(tmp_path, OLD, OLD, monkeypatch)
    assert "8 passes before, 8 after" in summ.read_text(encoding="utf-8")
    assert "dropped 0" in capsys.readouterr().out


def test_lakes_diff_cli_fails_above_the_threshold(tmp_path, monkeypatch, capsys):
    with pytest.raises(SystemExit) as e:
        _diff_cli(tmp_path, OLD, _doc(OLD["lakes"][0]), monkeypatch)
    assert e.value.code == 1
    out = capsys.readouterr().out
    assert "::error::5 of 8 previously published passes would be dropped" in out
    assert out.count("::warning::") == 5 + 2  # five passes, two lakes backwards


def test_lakes_diff_cli_without_a_previous_file_compares_nothing(tmp_path, monkeypatch, capsys):
    _diff_cli(tmp_path, None, OLD, monkeypatch)
    assert "nothing to compare" in capsys.readouterr().out


def test_lakes_search_stops_when_no_lake_has_a_pass(tmp_path, monkeypatch):
    lakes_in = tmp_path / "lakes_in.json"
    lakes_in.write_text("[]", encoding="utf-8")
    lake = Lake(id="x", name="X", lon=74.0, lat=36.0, coord_source="s", outline=None, role="watch",
                downstream=None, downstream_source=None)
    monkeypatch.setattr(run_pipeline, "load_lakes", lambda p: [lake])
    monkeypatch.setattr(run_pipeline, "search_lake_passes", lambda lk: [])
    with pytest.raises(SystemExit) as e:
        run_pipeline.main(["lakes-search", "--lakes-in", str(lakes_in), "--out", str(tmp_path / "passes.json")])
    assert e.value.code == 1
