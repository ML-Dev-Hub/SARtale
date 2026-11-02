import json
from pathlib import Path

import pytest

from sartale.lakes import Lake, lake_bbox, load_lakes

ROW = {"id": "x", "name": "X", "lon": 74.0, "lat": 36.0, "coord_source": "src", "role": "watch"}


def write(tmp_path, rows):
    p = tmp_path / "l.json"
    p.write_text(json.dumps(rows))
    return p


def test_load_lakes_requires_coord_source(tmp_path):
    with pytest.raises(ValueError, match="coord_source"):
        load_lakes(write(tmp_path, [{**ROW, "coord_source": ""}]))


def test_load_lakes_rejects_duplicate_ids_and_bad_role(tmp_path):
    with pytest.raises(ValueError, match="Duplicate"):
        load_lakes(write(tmp_path, [ROW, ROW]))
    with pytest.raises(ValueError, match="role"):
        load_lakes(write(tmp_path, [{**ROW, "role": "danger"}]))


def test_load_lakes_downstream_needs_source(tmp_path):
    with pytest.raises(ValueError, match="downstream_source"):
        load_lakes(write(tmp_path, [{**ROW, "downstream": "A village"}]))


def test_load_lakes_defaults_optional_fields_to_none(tmp_path):
    (lake,) = load_lakes(write(tmp_path, [ROW]))
    assert (lake.outline, lake.downstream, lake.downstream_source) == (None, None, None)


def test_lake_bbox_is_centred_and_sized():
    lake = Lake(id="a", name="A", lon=74.86, lat=36.33, coord_source="s", outline=None, role="watch",
                downstream=None, downstream_source=None)
    lon0, lat0, lon1, lat1 = lake_bbox(lake, half_km=3.0)
    assert lon0 < 74.86 < lon1 and lat0 < 36.33 < lat1
    assert (lat1 - lat0) * 111.32 == pytest.approx(6.0, rel=0.02)
    assert (lon1 - lon0) * 111.32 * 0.8066 == pytest.approx(6.0, rel=0.02)  # cos(36.33 deg)


def test_shipped_register_loads_with_sources_and_inside_the_study_area():
    lakes = load_lakes(Path(__file__).resolve().parents[1] / "lakes_in.json")
    assert len(lakes) >= 7
    assert {"attabad", "shisper", "passu"} <= {l.id for l in lakes}
    assert all(71 <= l.lon <= 77.8 and 34.5 <= l.lat <= 37.1 for l in lakes)
    shisper = next(l for l in lakes if l.id == "shisper")
    assert shisper.downstream_source == "Radio Pakistan, 7 May 2022"
    assert all(l.downstream_source for l in lakes if l.downstream)
