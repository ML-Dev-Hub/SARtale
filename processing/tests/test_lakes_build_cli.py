"""Attabad gate (R-T5e), the lakes-build exit code, atomic lakes.json and stale-image pruning."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import pytest

from sartale import run_pipeline
from sartale.lakebuild import attabad_gate
from sartale.run_pipeline import prune_lake_images, write_json_atomic


def _gate_doc(a_by_track, s_by_track, status="Stable", cw=5):
    def lk(lid, by):
        series = [{"date": f"2026-07-{i + 10}", "track": t, "area_km2": v, "observable_share": 1.0, "excluded": None}
                  for t, vals in by.items() for i, v in enumerate(vals)]
        return {"id": lid, "series": series, "status": {"status": status}, "cloud_window_looks": cw}
    return {"lakes": [lk("attabad", a_by_track), lk("shisper", s_by_track)]}


def test_attabad_gate_passes():
    g = attabad_gate(_gate_doc({"055A": [0.3, 0.3, 0.3], "156A": [0.2, 0.2, 0.2]},
                               {"055A": [0.1, 0.1, 0.1], "156A": [0.05, 0.05, 0.05]}))
    assert g["pass"] and g["median_ratio"] == pytest.approx(3.5)


def test_attabad_gate_fails_when_one_track_loses():
    g = attabad_gate(_gate_doc({"055A": [0.9], "063D": [0.9], "156A": [0.05]},
                               {"055A": [0.1], "063D": [0.1], "156A": [0.1]}))
    assert g["median_ratio"] >= 2 and not g["pass"]


def test_attabad_gate_fails_when_median_ratio_under_2():
    g = attabad_gate(_gate_doc({"055A": [0.15], "156A": [0.15]}, {"055A": [0.1], "156A": [0.1]}))
    assert g["median_ratio"] == pytest.approx(1.5) and not g["pass"]


def test_attabad_gate_fails_with_too_few_cloud_window_looks():
    g = attabad_gate(_gate_doc({"055A": [0.3]}, {"055A": [0.1]}, cw=2))
    assert not g["pass"]


DOC = {"lakes": [{"id": "attabad", "status": {"status": "Stable", "looks": 3, "track": "156A", "latest_date": "d"},
                  "cloud_window_looks": 3, "directions": ["A"], "excluded": [], "limits": [],
                  "images": {"latest_hh": "lakes/attabad/latest_hh.webp", "water": None}}], "checks": []}


def _cli(tmp_path, monkeypatch, gate_pass, extra=()):
    out = tmp_path / "out"
    stale = out / "lakes" / "old_lake"
    stale.mkdir(parents=True)
    (stale / "latest_hh.webp").write_bytes(b"x")
    keep = out / "lakes" / "attabad"
    keep.mkdir(parents=True)
    (keep / "latest_hh.webp").write_bytes(b"k")
    (tmp_path / "passes.json").write_text(json.dumps({"lakes": {}}), encoding="utf-8")
    monkeypatch.setattr(run_pipeline, "load_lakes", lambda p: [])
    monkeypatch.setattr(run_pipeline, "build_lakes", lambda *a, **k: DOC)
    monkeypatch.setattr(run_pipeline, "attabad_gate", lambda d: {
        "tracks": {}, "median_ratio": 1.0, "attabad_status": "Stable", "attabad_cloud_window_looks": 3, "pass": gate_pass})
    argv = ["lakes-build", "--out", str(out), "--cache", str(tmp_path), "--checks", str(tmp_path / "none.json"), *extra]
    return argv, out, stale, keep


def test_lakes_build_exits_1_when_the_gate_fails(tmp_path, monkeypatch):
    argv, out, _, _ = _cli(tmp_path, monkeypatch, gate_pass=False)
    with pytest.raises(SystemExit) as e:
        run_pipeline.main(argv)
    assert e.value.code == 1
    assert (out / "lakes.json").is_file() and not (out / "lakes.json.tmp").exists()


def test_lakes_build_allow_gate_fail_exits_0(tmp_path, monkeypatch):
    argv, _, _, _ = _cli(tmp_path, monkeypatch, gate_pass=False, extra=["--allow-gate-fail"])
    run_pipeline.main(argv)  # returns normally: exit code 0


def test_lakes_build_prunes_stale_images_only_under_lakes(tmp_path, monkeypatch):
    argv, out, stale, keep = _cli(tmp_path, monkeypatch, gate_pass=True)
    other = out / "keep.webp"
    other.write_bytes(b"y")
    run_pipeline.main(argv)
    assert not stale.exists()
    assert (keep / "latest_hh.webp").exists() and other.exists()
    assert json.loads((out / "lakes.json").read_text(encoding="utf-8"))["lakes"][0]["id"] == "attabad"


def test_lakes_build_needs_the_search_manifest(tmp_path, monkeypatch, capsys):
    argv, out, _, _ = _cli(tmp_path, monkeypatch, gate_pass=True)
    (tmp_path / "passes.json").unlink()
    with pytest.raises(SystemExit) as e:
        run_pipeline.main(argv)
    assert e.value.code == 1 and "run lakes-search first" in capsys.readouterr().err
    assert not (out / "lakes.json").exists()


def test_prune_keeps_referenced_images(tmp_path):
    d = tmp_path / "lakes" / "a"
    d.mkdir(parents=True)
    for n in ("latest_hh.webp", "water.webp", "old.webp"):
        (d / n).write_bytes(b"x")
    doc = {"lakes": [{"images": {"latest_hh": "lakes/a/latest_hh.webp", "water": "lakes/a/water.webp"}}]}
    removed = prune_lake_images(tmp_path, doc)
    assert [p.name for p in removed] == ["old.webp"]
    assert (d / "latest_hh.webp").exists() and (d / "water.webp").exists()


def test_write_json_atomic_replaces_and_leaves_no_tmp(tmp_path):
    p = tmp_path / "lakes.json"
    p.write_text("old", encoding="utf-8")
    write_json_atomic(p, {"a": 1})
    assert json.loads(p.read_text(encoding="utf-8")) == {"a": 1}
    assert not (tmp_path / "lakes.json.tmp").exists()
    with pytest.raises(ValueError):
        write_json_atomic(p, {"a": float("nan")})
    assert json.loads(p.read_text(encoding="utf-8")) == {"a": 1}


def test_lakes_check_writes_the_rows_and_merges_them_into_lakes_json(tmp_path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    (out / "lakes.json").write_text(json.dumps({"lakes": [{"id": "attabad", "series": []}], "checks": []}), encoding="utf-8")
    monkeypatch.setattr(run_pipeline, "load_lakes", lambda p: [type("L", (), {"id": "attabad"})()])
    monkeypatch.setattr(run_pipeline, "check_lake", lambda lake, cache, series: {"lake": lake.id, "note": "no clear scene"})
    checks = tmp_path / "checks.json"
    run_pipeline.main(["lakes-check", "--out", str(out), "--cache", str(tmp_path), "--checks", str(checks), "--lakes", "attabad"])
    rows = [{"lake": "attabad", "note": "no clear scene"}]
    assert json.loads(checks.read_text(encoding="utf-8")) == rows
    assert json.loads((out / "lakes.json").read_text(encoding="utf-8"))["checks"] == rows


def test_lakes_check_defaults_to_every_lake_that_holds_a_lake_now():
    from dataclasses import replace

    from sartale.lakes import Lake
    from sartale.run_pipeline import check_ids

    base = Lake(id="a", name="A", lon=74.0, lat=36.0, coord_source="s", outline=None, role="watch",
                downstream=None, downstream_source=None)
    lakes = [base, replace(base, id="gone", lake_state="no_lake", lake_state_source="s"),
             replace(base, id="maybe", lake_state="unconfirmed", lake_state_source="s")]
    assert check_ids(lakes, None) == ["a", "maybe"]
    assert check_ids(lakes, " gone , a ") == ["gone", "a"]


# --- M8: the absence check runs before the build -------------------------------------------------------------------

def _absence_site(tmp_path):
    from dataclasses import replace

    from test_lakebuild import make_lake, write_pass
    cache = tmp_path / "cache"
    base = make_lake("basin")
    for d in ["2026-06-18", "2026-06-30", "2026-07-12", "2026-07-24", "2026-09-04"]:
        write_pass(cache, base, d, "156A")
    return cache, replace(base, lake_state="no_lake", lake_state_source="a dry basin")


def _wet_evidence(lake, today):
    from sartale.lakebuild import absence_zone, forming_share
    from sartale.lakecheck import ABSENCE_RULE
    pair = [{"date": "2026-08-25", "s2_id": "S2_WET0", "water_share": 0.07},
            {"date": "2026-09-01", "s2_id": "S2_WET", "water_share": 0.08}]
    return {"date": "2026-09-01", "s2_id": "S2_WET", "water_share": 0.08, "water_km2": 0.25, "zone_valid_share": 1.0,
            "snow_share": 0.0, "forming": True, "pending_scene": None, "confirmed": pair,
            "threshold": forming_share(lake), "checked": today, "searched": today, "no_view_since": False,
            "rule": ABSENCE_RULE, "source": "S2", "zone": absence_zone(lake)}


def test_m8_absence_before_the_build_shows_the_forming_water_layer_in_the_same_refresh(tmp_path, monkeypatch):
    from sartale import lakecheck
    from sartale.lakebuild import build_lakes
    from sartale.lakestatus import LAKE_FORMING
    cache, gone = _absence_site(tmp_path)
    out = tmp_path / "out"
    write_json_atomic(out / "lakes.json", build_lakes([gone], cache, out, "published"))  # the published file
    calls = []
    monkeypatch.setattr(run_pipeline, "load_lakes", lambda p: [gone])
    monkeypatch.setattr(lakecheck, "absence_check", lambda lake, today, prior: calls.append(prior) or _wet_evidence(lake, today))
    run_pipeline.main(["lakes-absence", "--out", str(out), "--today", "2026-09-08"])
    assert calls == [None]
    # lakes-build then reads that lakes.json as `previous` (its default) and keeps the new evidence
    previous = json.loads((out / "lakes.json").read_text(encoding="utf-8"))
    lk = build_lakes([gone], cache, out, "new", previous=previous)["lakes"][0]
    assert lk["status"]["status"] == LAKE_FORMING and lk["absence_checked"]["s2_id"] == "S2_WET"
    assert lk["images"]["water"] and (out / lk["images"]["water"]).is_file()


def test_lakes_absence_only_missing_checks_just_the_sites_without_evidence(tmp_path, monkeypatch):
    from sartale import lakecheck
    from sartale.lakebuild import build_lakes
    cache, gone = _absence_site(tmp_path)
    out = tmp_path / "out"
    doc = build_lakes([gone], cache, out, "t")
    write_json_atomic(out / "lakes.json", doc)
    calls = []
    monkeypatch.setattr(run_pipeline, "load_lakes", lambda p: [gone])
    monkeypatch.setattr(lakecheck, "absence_check", lambda lake, today, prior: calls.append(prior) or _wet_evidence(lake, today))
    run_pipeline.main(["lakes-absence", "--out", str(out), "--today", "2026-09-08", "--only-missing"])
    assert calls == [None]  # no evidence yet: checked
    run_pipeline.main(["lakes-absence", "--out", str(out), "--today", "2026-09-15", "--only-missing"])
    assert len(calls) == 1  # evidence now: skipped
    run_pipeline.main(["lakes-absence", "--out", str(out), "--today", "2026-09-15"])
    assert len(calls) == 2 and calls[1]["s2_id"] == "S2_WET"  # a normal run re-checks from the evidence


def test_lakes_absence_without_lakes_json_does_nothing(tmp_path, monkeypatch, capsys):
    from sartale import lakecheck
    monkeypatch.setattr(run_pipeline, "load_lakes", lambda p: pytest.fail("no lakes.json: nothing to read"))
    monkeypatch.setattr(lakecheck, "absence_check", lambda *a: pytest.fail("no lakes.json: no check"))
    run_pipeline.main(["lakes-absence", "--out", str(tmp_path / "none")])
    assert "nothing to re-check yet" in capsys.readouterr().out


def test_lakes_check_sets_the_status_again_from_the_new_check(tmp_path, monkeypatch):
    """A new Sentinel-2 check can take a lake's level away (IoU under 0.4) or give it back."""
    out = tmp_path / "out"
    out.mkdir()
    series = [{"date": f"2026-09-{d:02d}", "track": "156A", "area_km2": a, "observable_share": 1.0, "excluded": None}
              for d, a in zip(range(1, 8), [1.0, 1.02, 0.99, 1.01, 1.0, 1.5, 1.5])]
    lk = {"id": "attabad", "name": "Attabad", "lake_state": "lake", "series": series, "validation": None,
          "status": {"status": "Alert: growing"}}
    (out / "lakes.json").write_text(json.dumps({"lakes": [lk], "checks": []}), encoding="utf-8")
    monkeypatch.setattr(run_pipeline, "load_lakes", lambda p: [type("L", (), {"id": "attabad"})()])
    row = {"lake": "attabad", "nisar_date": "2026-09-01", "nisar_track": "156A", "s2_date": "2026-09-01", "s2_id": "S",
           "iou": 0.2, "days_apart": 0, "radar_km2": 1.0, "optical_km2": 2.0, "area_error_pct": -50.0,
           "window_radar_km2": 1.0, "window_optical_km2": 2.0, "window_iou": 0.2}
    monkeypatch.setattr(run_pipeline, "check_lake", lambda lake, cache, series: row)
    args = ["lakes-check", "--out", str(out), "--cache", str(tmp_path), "--checks", str(tmp_path / "c.json"),
            "--lakes", "attabad"]
    run_pipeline.main(args)
    got = json.loads((out / "lakes.json").read_text(encoding="utf-8"))["lakes"][0]
    assert got["validation"]["iou"] == 0.2 and got["status"]["status"] == "Not measurable"
    monkeypatch.setattr(run_pipeline, "check_lake", lambda lake, cache, series: {**row, "iou": 0.7})
    run_pipeline.main(args)
    got = json.loads((out / "lakes.json").read_text(encoding="utf-8"))["lakes"][0]
    assert got["status"]["status"] == "Alert: growing" and got["status"]["message"]["level"] == "Alert: growing"
    assert got["series"][-1]["level_contrib"] == "Alert: growing"
