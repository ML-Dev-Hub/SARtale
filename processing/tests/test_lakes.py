import json
import shutil
from pathlib import Path

import pytest

from sartale.lake_requests import BOUNDS
from sartale.lakes import Lake, lake_bbox, load_lakes
from sartale.run_pipeline import append_lake_entry, lake_slug

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


def test_load_lakes_zone_radius_defaults_to_1_km_and_is_validated(tmp_path):
    (lake,) = load_lakes(write(tmp_path, [ROW]))
    assert lake.zone_radius_km == 1.0
    (small,) = load_lakes(write(tmp_path, [{**ROW, "zone_radius_km": 0.3}]))
    assert small.zone_radius_km == 0.3
    for bad in (0, -1, 2.6, "0.3", True, None):
        with pytest.raises(ValueError, match="zone_radius_km"):
            load_lakes(write(tmp_path, [{**ROW, "zone_radius_km": bad}]))


def test_load_lakes_lake_state_defaults_to_lake_and_needs_a_source_otherwise(tmp_path):
    (lake,) = load_lakes(write(tmp_path, [ROW]))
    assert (lake.lake_state, lake.lake_state_source) == ("lake", None)
    for state in ("no_lake", "unconfirmed"):
        with pytest.raises(ValueError, match="lake_state_source"):
            load_lakes(write(tmp_path, [{**ROW, "lake_state": state}]))
        (x,) = load_lakes(write(tmp_path, [{**ROW, "lake_state": state, "lake_state_source": "Sentinel-2, 2026"}]))
        assert (x.lake_state, x.lake_state_source) == (state, "Sentinel-2, 2026")
    with pytest.raises(ValueError, match="lake_state"):
        load_lakes(write(tmp_path, [{**ROW, "lake_state": "maybe", "lake_state_source": "s"}]))


def test_forming_share_is_a_sourced_share_on_a_no_lake_site_only(tmp_path):
    gone = {**ROW, "lake_state": "no_lake", "lake_state_source": "dry"}
    (x,) = load_lakes(write(tmp_path, [gone]))
    assert x.forming_share is None
    (y,) = load_lakes(write(tmp_path, [{**gone, "forming_share": 0.16, "forming_share_source": "river in zone"}]))
    assert (y.forming_share, y.forming_share_source) == (0.16, "river in zone")
    for bad in (0, 1, -0.1, "0.1", True):
        with pytest.raises(ValueError, match="forming_share"):
            load_lakes(write(tmp_path, [{**gone, "forming_share": bad, "forming_share_source": "s"}]))
    with pytest.raises(ValueError, match="forming_share_source"):
        load_lakes(write(tmp_path, [{**gone, "forming_share": 0.1}]))
    with pytest.raises(ValueError, match="no_lake"):
        load_lakes(write(tmp_path, [{**ROW, "forming_share": 0.1, "forming_share_source": "s"}]))


def test_site_limits_are_a_list_of_text(tmp_path):
    (x,) = load_lakes(write(tmp_path, [{**ROW, "limits": ["partly drained on 30 Aug 2024"]}]))
    assert x.limits == ("partly drained on 30 Aug 2024",)
    assert load_lakes(write(tmp_path, [ROW]))[0].limits == ()
    for bad in ("text", [""], [1]):
        with pytest.raises(ValueError, match="limits"):
            load_lakes(write(tmp_path, [{**ROW, "limits": bad}]))


def test_lake_bbox_is_centred_and_sized():
    lake = Lake(id="a", name="A", lon=74.86, lat=36.33, coord_source="s", outline=None, role="watch",
                downstream=None, downstream_source=None)
    lon0, lat0, lon1, lat1 = lake_bbox(lake, half_km=3.0)
    assert lon0 < 74.86 < lon1 and lat0 < 36.33 < lat1
    assert (lat1 - lat0) * 111.32 == pytest.approx(6.0, rel=0.02)
    assert (lon1 - lon0) * 111.32 * 0.8066 == pytest.approx(6.0, rel=0.02)  # cos(36.33 deg)


SHIPPED_REGISTER = Path(__file__).resolve().parents[1] / "lakes_in.json"


def check_register(path):
    """What every register must hold, whatever lakes it has: a request adds a lake, so no count is pinned."""
    lakes = load_lakes(path)
    assert lakes
    assert {"attabad", "shisper", "passu"} <= {l.id for l in lakes}
    lat_min, lat_max, lon_min, lon_max = BOUNDS  # the same box a lake request must fall in
    assert all(lon_min <= l.lon <= lon_max and lat_min <= l.lat <= lat_max for l in lakes)
    shisper = next(l for l in lakes if l.id == "shisper")
    assert shisper.downstream_source == "Radio Pakistan, 7 May 2022"
    assert all(l.downstream_source for l in lakes if l.downstream)
    return lakes


def test_shipped_register_loads_with_sources_and_inside_the_study_area():
    check_register(SHIPPED_REGISTER)


def test_register_checks_still_pass_after_an_accepted_request(tmp_path):
    """Guard: an accept appends a lake and the rebuild runs these tests on the new register."""
    copy = tmp_path / "lakes_in.json"
    shutil.copyfile(SHIPPED_REGISTER, copy)
    shipped = load_lakes(copy)
    lake_id = lake_slug("Requested lake", {l.id for l in shipped})  # as accept_entry picks it
    # in the request box but outside the older, narrower study box (34.5-37.1 N, 71-77.8 E)
    append_lake_entry(copy, {"id": lake_id, "name": "Requested lake", "lon": 70.9, "lat": 37.5,
                             "role": "watch", "coord_source": "Requested 2026-11-06 (issue #7): a survey",
                             "outline": None, "downstream": None, "downstream_source": None})
    lakes = check_register(copy)
    assert len(lakes) == len(shipped) + 1 and lakes[-1].id == lake_id
