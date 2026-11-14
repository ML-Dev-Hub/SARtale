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
   "coord_source": "x {y}", "outline": null, "downstream": null, "downstream_source": null, "district": "Chitral", "province": "KP", "district_source": "test districts"},
  {"id": "b", "name": "B", "lon": 72.1, "lat": 35.1, "role": "watch",
   "coord_source": "x", "outline": null, "downstream": null, "downstream_source": null, "district": "Chitral", "province": "KP", "district_source": "test districts",
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


def test_the_register_heights_are_valid_and_a_missing_one_says_why():
    """Runs in the rebuild after lakes-elevation, the build and lakes-freeze: every height present is plausible and
    sourced; a lake without one (the DEM could not be read: lakes-elevation fails soft) is allowed as long as the built
    lakes.json says "Freeze not assessed" for it with that reason. So a missing height never fails the rebuild."""
    from pathlib import Path

    from sartale.elevation import height_problems
    import os
    root = Path(__file__).resolve().parents[2]
    lakes = load_lakes(root / "processing" / "lakes_in.json")
    shipped = os.environ.get("SARTALE_LAKES_JSON") or root / "app" / "public" / "data" / "lakes.json"
    doc = json.loads(Path(shipped).read_text(encoding="utf-8"))
    assert height_problems(lakes, doc) == []


def test_a_missing_height_passes_only_with_its_reason_in_the_build():
    from dataclasses import replace

    from sartale.elevation import height_problems
    from sartale.freeze import freeze_lake
    from sartale.lakes import Lake
    new = Lake(id="new", name="New", lon=72.0, lat=35.0, coord_source="x", outline=None, role="watch",
               downstream=None, downstream_source=None)
    status = {"status": "Not enough NISAR looks yet", "track": None, "latest_date": None, "looks": 0,
              "change_km2": None, "noise_km2": None, "reason": "No valid NISAR pass yet.", "new_crid": None}
    # what the rebuild publishes for a lake whose DEM could not be read: lakes-freeze says why
    built = freeze_lake(new, {"id": "new", "lake_state": "lake", "series": [], "summer_ref": {}, "status": status},
                        "2026-11-12", log=lambda m: None)
    assert height_problems([new], {"lakes": [built]}) == []
    # a silent missing height (no build, or a build without the freeze check) is a problem
    assert height_problems([new], {"lakes": [{"id": "new", "status": status}]}) != []
    assert height_problems([new], None) != []
    # a height present must be plausible and sourced; a site with no lake now needs none
    assert height_problems([replace(new, elevation_m=4188.0, elevation_source="Copernicus DEM GLO-30")], None) == []
    assert height_problems([replace(new, elevation_m=9500.0, elevation_source="x")], None) != []
    assert height_problems([replace(new, elevation_m=4188.0, elevation_source=" ")], None) != []
    assert height_problems([replace(new, lake_state="no_lake", lake_state_source="dry")], None) == []


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
