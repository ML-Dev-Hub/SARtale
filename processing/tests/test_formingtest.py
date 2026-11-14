"""The forming back-test (formingtest): every scene of a period through the absence check's rule, read once."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import numpy as np
import pytest

from sartale import lakecheck
from sartale.formingtest import backtest, persistent_water
from test_lakecheck import _khurdopin, _scenes

# The Round-2 Khurdopin sequence (8 Oct 2025 to 12 Nov 2026): the spring false alarm 26 Apr-8 Jun 2026 and the
# below-threshold scenes around it. (date, zone seen clear, water share of the clear zone)
KHURDOPIN = [
    ("2025-10-20", 1.0, 0.10), ("2026-01-15", 0.95, 0.08), ("2026-04-26", 1.0, 0.997), ("2026-05-09", 1.0, 0.186),
    ("2026-06-03", 1.0, 0.150), ("2026-06-08", 1.0, 0.151), ("2026-07-20", 1.0, 0.12),
    ("2026-08-16", 0.5, 0.90),  # clouded zone: does not qualify, whatever it reads
    ("2026-09-16", 1.0, 0.076), ("2026-11-10", 0.99, 0.1177),
]


@pytest.fixture
def lake():
    return _khurdopin()


@pytest.fixture
def reads(monkeypatch, lake):
    """Scene search and reads faked: each read appends the scene id; the gridded scene has water on the given share of
    the lake zone's clear pixels."""
    from sartale.lakewater import lake_zone
    by_id = {f"S2_{d}": (clear, water) for d, clear, water in KHURDOPIN}
    seen = []
    monkeypatch.setattr(lakecheck, "search_scenes", lambda *a, **k: _scenes(*[(f"S2_{d}", d, 5.0) for d, *_ in KHURDOPIN]))
    monkeypatch.setattr(lakecheck, "read_scene", lambda scene, x, y, epsg: seen.append(scene["id"]) or {"id": scene["id"]})

    def grid(scene, raw, x, y, epsg, buffer_m=None):
        clear, water = by_id[raw["id"]]
        shape = (len(y), len(x))
        zone = lake_zone(shape, x, y, epsg, lake)
        rank = np.full(shape, -1.0)
        rank[zone] = np.arange(zone.sum()) / zone.sum()
        valid = ~zone | (rank < clear)
        wet = zone & valid & (rank < clear * water)
        return {"water": wet, "valid": valid, "snow": np.zeros(shape, bool), "terrain_shadow": np.zeros(shape, bool),
                "clear": valid, "window_cloud_share": 0.0, "invalid_share": 0.0}
    monkeypatch.setattr(lakecheck, "grid_scene", grid)
    return seen


def test_backtest_reports_each_flip_once_and_reads_each_scene_once(lake, reads):
    out = backtest(lake, "2025-10-08", "2026-11-12", log=lambda *_: None)
    assert out["flips"] == [{"date": "2026-05-09", "forming": True}, {"date": "2026-06-08", "forming": False}]
    assert len(reads) == len(set(reads)) == len(KHURDOPIN)
    assert out["qualifying"] == len(KHURDOPIN) - 1  # 16 Aug: zone half clouded
    assert [r["date"] for r in out["pending"]] == ["2026-04-26", "2026-06-03"]


def test_backtest_with_a_not_assessed_season_has_no_spring_flip(lake, reads):
    rule = {"share": 0.16, "seasons": [{"start": "03-15", "end": "06-15", "share": None, "source": "t"}], "exclude": None}
    out = backtest(lake, "2025-10-08", "2026-11-12", rule=rule, log=lambda *_: None)
    assert out["flips"] == []
    spring = [r for r in out["scenes"] if "2026-03-15" <= r["date"] <= "2026-06-15"]
    assert spring and all(r["threshold"] is None for r in spring)


def test_backtest_applies_an_exclusion_mask(lake, reads):
    x, y, _ = lakecheck.absence_grid(lake)
    grid_shape = (len(y), len(x))
    out = backtest(lake, "2025-10-08", "2026-11-12", rule={"share": 0.16, "seasons": [], "exclude": np.ones(grid_shape, bool)},
                   log=lambda *_: None)
    assert out["flips"] == [] and all(r["water_share"] == 0.0 for r in out["scenes"])


def test_backtest_reads_an_exclusion_outline_from_a_path(lake, reads, tmp_path, monkeypatch):
    from sartale import lakes
    monkeypatch.setattr(lakes, "OUTLINES_DIR", tmp_path)
    ring = [[lake.lon + sx * 0.02, lake.lat + sy * 0.02] for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1))]
    path = tmp_path / "river.geojson"
    path.write_text(json.dumps({"type": "Polygon", "coordinates": [ring]}), encoding="utf-8")
    out = backtest(lake, "2025-10-08", "2026-11-12", rule={"share": 0.16, "seasons": [], "exclude": str(path)},
                   log=lambda *_: None)
    assert out["flips"] == [] and out["qualifying"] == 0  # the outline covers the whole zone: nothing left to see


def test_persistent_water_keeps_pixels_water_in_most_scenes():
    a = np.zeros((4, 4), bool)
    b = np.zeros((4, 4), bool)
    a[0:2, :] = True
    b[1:3, :] = True  # row 1 in both
    assert (persistent_water([a, a, b], 0.6) == a).all()  # a's pixels are water in 2 of 3 scenes, b-only pixels in 1


def test_the_cli_writes_the_back_test_and_prints_each_flip(lake, reads, tmp_path, monkeypatch, capsys):
    from sartale import run_pipeline
    monkeypatch.setattr(run_pipeline, "load_lakes", lambda path: [lake])
    out = tmp_path / "bt.json"
    run_pipeline.main(["lakes-absence-backtest", "--lake", "khurdopin", "--start", "2025-10-08", "--end", "2026-11-12",
                       "--out", str(out)])
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["flips"] == [{"date": "2026-05-09", "forming": True}, {"date": "2026-06-08", "forming": False}]
    printed = capsys.readouterr().out
    assert "2026-05-09" in printed and "qualifying" in printed
