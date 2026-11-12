"""The lake surface height: the DEM percentile and the one-off write into lakes_in.json."""
import json

import numpy as np
import pytest

from sartale.elevation import circle_percentile, set_elevation
from sartale.lakes import load_lakes


def test_the_lake_surface_is_the_low_flat_part_of_the_circle():
    dem = np.full((81, 81), 4300.0)
    dem[30:51, 30:51] = 4181.0  # a flat lake surface in the middle, ~600 m across at 30 m pixels
    dem[0, 0] = 2000.0  # a low pixel outside the 1 km circle is not counted
    dem[40, 40] = np.nan
    v = circle_percentile(dem, 40.5, 40.5, 30.0, 30.0)
    assert v == 4181.0
    assert circle_percentile(np.full((5, 5), np.nan), 2.5, 2.5, 30.0, 30.0) is None
    # the DEM's no-data value never counts
    assert circle_percentile(np.full((5, 5), -32767.0), 2.5, 2.5, 30.0, 30.0) is None


REGISTER = """[
  {"id": "a", "name": "A", "lon": 72.0, "lat": 35.0, "role": "watch",
   "coord_source": "x {y}", "outline": null, "downstream": null, "downstream_source": null},
  {"id": "b", "name": "B", "lon": 72.1, "lat": 35.1, "role": "watch",
   "coord_source": "x", "outline": null, "downstream": null, "downstream_source": null,
   "limits": ["a limit with } and \\" in it"]}
]
"""


def test_set_elevation_adds_two_keys_to_one_entry_and_nothing_else(tmp_path):
    p = tmp_path / "lakes_in.json"
    p.write_text(REGISTER, encoding="utf-8")
    set_elevation(p, "b", 4181, "Copernicus DEM GLO-30 (tile), 10th percentile within 1 km of the lake point")
    text = p.read_text(encoding="utf-8")
    assert text.startswith(REGISTER[: REGISTER.index('{"id": "b"')])  # entry a untouched
    assert '\n   "elevation_m": 4181, "elevation_source": "Copernicus DEM GLO-30 (tile), 10th percentile within 1 km' in text
    rows = json.loads(text)
    assert "elevation_m" not in rows[0] and rows[1]["elevation_m"] == 4181
    assert rows[1]["limits"] == ['a limit with } and " in it']
    lakes = load_lakes(p)
    assert lakes[1].elevation_m == 4181.0 and lakes[1].elevation_source.startswith("Copernicus")
    with pytest.raises(ValueError, match="already has an elevation"):
        set_elevation(p, "b", 4000, "again")
    with pytest.raises(KeyError):
        set_elevation(p, "zz", 4000, "x")


def test_the_register_checks_the_elevation(tmp_path):
    rows = json.loads(REGISTER)
    p = tmp_path / "lakes_in.json"
    for bad, msg in (({"elevation_m": 4181}, "needs an elevation_source"),
                     ({"elevation_m": "high", "elevation_source": "x"}, "height in metres"),
                     ({"elevation_m": 99999, "elevation_source": "x"}, "height in metres")):
        p.write_text(json.dumps([{**rows[0], **bad}]), encoding="utf-8")
        with pytest.raises(ValueError, match=msg):
            load_lakes(p)


def test_every_lake_in_the_register_has_its_height():
    from pathlib import Path
    lakes = load_lakes(Path(__file__).resolve().parents[1] / "lakes_in.json")
    for lk in lakes:
        if lk.lake_state == "lake":
            assert lk.elevation_m is not None and "Copernicus DEM GLO-30" in lk.elevation_source, lk.id


def test_lakes_elevation_fills_missing_heights_and_fails_soft(tmp_path, monkeypatch, capsys):
    """The rebuild runs lakes-elevation before the build: a lake without a height gets one; a lake whose DEM read fails
    keeps none (its freeze stays "not assessed") and the run goes on; a lake with a height is not measured again."""
    from sartale import elevation, run_pipeline
    rows = json.loads(REGISTER)
    rows[0]["elevation_m"], rows[0]["elevation_source"] = 4000, "measured before"
    rows.append({**rows[1], "id": "c", "name": "C", "limits": []})
    p = tmp_path / "lakes_in.json"
    p.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    calls = []

    def fake(lake):
        calls.append(lake.id)
        if lake.id == "b":
            raise TimeoutError("DEM")
        return 3100, "Copernicus DEM GLO-30 (tile), 10th percentile within 1 km of the lake point"
    monkeypatch.setattr(elevation, "lake_elevation", fake)
    run_pipeline.main(["lakes-elevation", "--lakes-in", str(p)])
    out = capsys.readouterr().out
    assert calls == ["b", "c"]
    assert "b: the Copernicus DEM could not be read (TimeoutError); its freeze stays not assessed" in out
    got = {lk.id: lk.elevation_m for lk in load_lakes(p)}
    assert got == {"a": 4000.0, "b": None, "c": 3100.0}


def test_a_lake_without_a_height_is_freeze_not_assessed_with_the_reason():
    from sartale.freeze import freeze_lake
    from sartale.lakes import Lake
    lake = Lake(id="new", name="New", lon=72.0, lat=35.0, coord_source="x", outline=None, role="watch",
                downstream=None, downstream_source=None)
    entry = {"id": "new", "lake_state": "lake", "series": [], "summer_ref": {},
             "status": {"status": "Not enough NISAR looks yet", "track": None, "latest_date": None, "looks": 0,
                        "change_km2": None, "noise_km2": None, "reason": "No valid NISAR pass yet.", "new_crid": None}}
    out = freeze_lake(lake, entry, "2026-11-12", power=lambda *a: pytest.fail("no POWER call without a height"),
                      log=lambda m: None)
    assert out["freeze"]["state"] == "not_assessed"
    assert out["freeze"]["reason"].startswith("Freeze not assessed: no lake height in the register yet (the Copernicus "
                                              "DEM could not be read for it; lakes-elevation tries again at the next "
                                              "refresh).")
    assert out["elevation_m"] is None and out["status"]["status"] == "Not enough NISAR looks yet"
