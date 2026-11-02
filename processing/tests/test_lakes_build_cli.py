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
