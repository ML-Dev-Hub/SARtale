import json

import pytest

from sartale import run_pipeline
from sartale.lake_requests import RequestStore

NOW = 1793750400.0  # 2026-11-04

OLD = ('[\r\n'
       '  {"id": "yaz_sam", "name": "Old", "lon": 74.0, "lat": 36.0, "role": "watch",\r\n'
       '   "coord_source": "x é", "outline": null, "downstream": null, "downstream_source": null}\r\n'
       ']\r\n')


def setup(tmp_path, names=("Yaz Sam",)):
    lakes = tmp_path / "lakes_in.json"
    lakes.write_bytes(OLD.encode("utf-8"))
    db = tmp_path / "data" / "r.sqlite"
    db.parent.mkdir()
    store = RequestStore(db)
    ids = [store.add({"name": n, "lat": 36.5, "lon": 74.5, "source": "Glacier survey"}, "1.2.3.4", NOW)["id"]
           for n in names]
    return lakes, db, store, ids


def run(lakes, db, *args):
    run_pipeline.main([*args, "--db", str(db)] + (["--lakes-in", str(lakes)] if args[0].endswith("accept") else []))


def test_accept_appends_one_entry_and_keeps_the_rest_of_the_file_byte_identical(tmp_path):
    lakes, db, store, (rid,) = setup(tmp_path, ("Zebra Lake é",))
    run(lakes, db, "lake-requests-accept", str(rid))
    new = lakes.read_bytes().decode("utf-8")
    old_with_comma = OLD.replace("null}\r\n]\r\n", "null},\r\n")
    assert new.startswith(old_with_comma)
    assert new.endswith("}\r\n]\r\n")
    entry = json.loads(new)[-1]
    assert entry == {"id": "zebra_lake", "name": "Zebra Lake é", "lon": 74.5, "lat": 36.5, "role": "watch",
                     "coord_source": "Requested 2026-11-04: Glacier survey", "outline": None,
                     "downstream": None, "downstream_source": None}
    assert json.loads(new)[:-1] == json.loads(OLD)
    assert "é" in new
    assert store.get(rid)["state"] == "accepted"


def test_accept_makes_a_unique_id_from_the_name(tmp_path):
    lakes, db, store, (rid,) = setup(tmp_path)
    run(lakes, db, "lake-requests-accept", str(rid))
    assert [e["id"] for e in json.loads(lakes.read_text(encoding="utf-8"))] == ["yaz_sam", "yaz_sam_2"]


def test_accept_refuses_a_rejected_request(tmp_path, capsys):
    lakes, db, store, (rid,) = setup(tmp_path)
    store.set_state(rid, "rejected", "no")
    with pytest.raises(SystemExit) as e:
        run(lakes, db, "lake-requests-accept", str(rid))
    assert e.value.code == 1
    assert lakes.read_bytes().decode("utf-8") == OLD


def test_accept_refuses_an_unknown_id(tmp_path):
    lakes, db, store, _ = setup(tmp_path)
    with pytest.raises(SystemExit) as e:
        run(lakes, db, "lake-requests-accept", "99")
    assert e.value.code == 1
    assert lakes.read_bytes().decode("utf-8") == OLD


def test_reject_records_the_reason(tmp_path):
    lakes, db, store, (rid,) = setup(tmp_path)
    run(lakes, db, "lake-requests-reject", str(rid), "--reason", "not a glacial lake")
    row = store.get(rid)
    assert (row["state"], row["reason"]) == ("rejected", "not a glacial lake")


def test_list_prints_open_requests_with_source(tmp_path, capsys):
    lakes, db, store, (rid,) = setup(tmp_path)
    run(lakes, db, "lake-requests-list")
    out = capsys.readouterr().out
    assert "Yaz Sam" in out and "Glacier survey" in out


def test_serve_arguments_parse_with_defaults():
    ns = run_pipeline.build_parser().parse_args(["lake-requests-serve"])
    assert (ns.host, ns.port, ns.origin) == ("127.0.0.1", 8787, "http://localhost:5173")
