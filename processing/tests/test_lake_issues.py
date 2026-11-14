import json
from pathlib import Path

import pytest

from sartale import lake_issues, run_pipeline
from sartale.lake_issues import (accept_entry, build_feed, issue_actions, issue_values_sha256, parse_issue_body,
                                 reconcile_actions, write_feed)
from sartale.lake_requests import RequestError
from sartale.lakes import load_lakes

NOW = "2026-11-05T09:00:00Z"
HERE = Path(__file__).parent
LAKES_IN = (
    '[\n'
    '  {"id": "attabad", "name": "Attabad Lake (landslide-dammed control)", "lon": 74.86, "lat": 36.33, "role": "control",\n'
    '   "coord_source": "spike", "outline": null, "downstream": null, "downstream_source": null,\n'
    '   "district": "Hunza", "province": "GB", "district_source": "test districts"}\n'
    ']\n')


def fake_search(lat, lon):
    return {"passes": 14, "tracks": ["055A", "156A"], "first": "2026-06-18", "last": "2026-10-23"}


def body(name="Moraine lake above Gulmit", lat="36.2", lon="74.0", source="Glacier survey"):
    return (f"### Lake name\n\n{name}\n\n### Latitude (°N)\n\n{lat}\n\n### Longitude (°E)\n\n{lon}\n\n"
            f"### Where the coordinates come from\n\n{source}")


def issue(number, state="open", labels=(), **fields):
    return {"number": number, "title": "Add a lake", "body": body(**fields), "state": state,
            "labels": [{"name": n} for n in ("lake-request", *labels)],
            "created_at": f"2026-11-0{min(number, 9)}T10:00:00Z", "user": {"login": "visitor"}}


@pytest.fixture
def watched(tmp_path):
    path = tmp_path / "lakes_in.json"
    path.write_text(LAKES_IN, encoding="utf-8")
    return load_lakes(path)


def one(feed, number):
    return next(r for r in feed["requests"] if r["issue"] == number)


def test_parse_valid_body():
    assert parse_issue_body(body()) == {
        "name": "Moraine lake above Gulmit", "lat": "36.2", "lon": "74.0", "source": "Glacier survey"}


def test_parse_no_response_is_empty():
    assert parse_issue_body(body(source="_No response_"))["source"] == ""


def test_parse_missing_heading_is_invalid():
    with pytest.raises(RequestError) as e:
        parse_issue_body("### Lake name\n\nOnly a name")
    assert e.value.status == 400
    assert str(e.value) == "The request form was changed; open a new request from the SARtale site."


def test_malformed_body_is_invalid_and_closed(watched):
    bad = issue(1)
    bad["body"] = "just some text"
    feed = build_feed([bad], watched, None, search=fake_search, now=NOW)
    assert one(feed, 1)["state"] == "invalid"
    assert one(feed, 1)["reason"] == "The request form was changed; open a new request from the SARtale site."
    assert one(feed, 1)["name"] == "Request #1"
    act = issue_actions(feed, 1, None)
    assert act["close"] is True and act["add"] == ["invalid"]


def test_coordinate_forms(watched):
    feed = build_feed([issue(1, lat="36.2°N", lon=" 74.0 °E"), issue(2, lat="36,2")], watched, None,
                      search=fake_search, now=NOW)
    assert one(feed, 1)["state"] == "searched" and one(feed, 1)["lat"] == 36.2 and one(feed, 1)["lon"] == 74.0
    assert one(feed, 2)["state"] == "invalid" and one(feed, 2)["reason"] == "lat must be a number."


def test_states_from_passes(watched):
    few = lambda lat, lon: {"passes": 2, "tracks": ["055A"], "first": "2026-10-01", "last": "2026-10-13"}  # noqa: E731
    assert one(build_feed([issue(1)], watched, None, search=fake_search, now=NOW), 1)["state"] == "searched"
    feed = build_feed([issue(1)], watched, None, search=few, now=NOW)
    assert one(feed, 1)["state"] == "too_few_passes" and one(feed, 1)["passes"] == 2


def test_outside_bounds_and_near_watched_are_invalid(watched):
    feed = build_feed([issue(1, lat="10"), issue(2, lat="36.33", lon="74.86")], watched, None,
                      search=fake_search, now=NOW)
    assert one(feed, 1)["state"] == "invalid" and "Gilgit-Baltistan" in one(feed, 1)["reason"]
    assert one(feed, 2)["reason"] == "Already watched: Attabad Lake (landslide-dammed control)."


def test_earlier_issue_wins(watched):
    feed = build_feed([issue(8, name="Later"), issue(4, name="Earlier")], watched, None,
                      search=fake_search, now=NOW)
    assert one(feed, 4)["state"] == "searched"
    assert one(feed, 8)["state"] == "invalid"
    assert one(feed, 8)["reason"] == "Already requested: issue #4."


def test_cap_of_200_open(watched):
    issues = [issue(n, lat=str(35.5 + (n - 1) // 100 * 0.05), lon=str(72.0 + (n - 1) % 100 * 0.02))
              for n in range(1, 202)]
    feed = build_feed(issues, watched, None, search=fake_search, now=NOW)
    assert one(feed, 200)["state"] == "searched"
    assert one(feed, 201)["state"] == "invalid"
    assert one(feed, 201)["reason"] == "The request list is full; try again later."


def test_labels_drive_state(watched):
    issues = [issue(1, labels=["accepted"], lat="36.2"),
              issue(2, "closed", labels=["invalid"], lat="36.5"),
              issue(3, "closed", labels=["searched"], lat="36.8"),
              issue(4, "open", labels=["invalid"], lat="36.65")]  # reopened
    feed = build_feed(issues, watched, None, search=fake_search, now=NOW)
    assert one(feed, 1)["state"] == "searched", "only the accept job makes a request accepted, never the label"
    assert one(feed, 2)["state"] == "invalid"
    assert one(feed, 3)["state"] == "rejected"
    assert one(feed, 4)["state"] == "searched"


def test_catalogue_failure_is_retried_next_run(watched):
    def down(lat, lon):
        raise OSError("no route")
    first = build_feed([issue(1)], watched, None, search=down, now=NOW)
    assert one(first, 1)["state"] == "check_failed"
    assert one(first, 1)["reason"] == "NASA's catalogue did not answer; the team will retry."
    act = issue_actions(first, 1, None)
    assert act["add"] == ["rebuild failed"] and act["close"] is False
    second = build_feed([issue(1)], watched, first, search=fake_search, now=NOW)
    assert one(second, 1)["state"] == "searched" and one(second, 1)["passes"] == 14


def test_reuses_previous_search(watched):
    first = build_feed([issue(1)], watched, None, search=fake_search, now=NOW)

    def boom(lat, lon):
        raise AssertionError("search must not run")
    again = build_feed([issue(1)], watched, first, search=boom, now=NOW)
    assert one(again, 1)["passes"] == 14
    with pytest.raises(AssertionError):
        build_feed([issue(1, lat="36.25")], watched, first, search=boom, now=NOW)


def test_edits_after_accept_ignored(watched):
    first = build_feed([issue(1, labels=["accepted"])], watched, None, search=fake_search, now=NOW)
    first["requests"][0].update(state="accepted", lake_id="moraine_lake")  # as accept_entry leaves it
    edited = issue(1, "closed", labels=["accepted"], name="Changed", lat="36.9")
    again = build_feed([edited], watched, first, search=fake_search, now=NOW)
    assert one(again, 1) == first["requests"][0]


def test_comment_never_echoes_text(watched):
    evil = "<img src=x> @someone"
    issues = [issue(1, name=evil), issue(2, name=evil, lat="10"), issue(3, name=evil, lat="36.2", lon="74.0")]
    feed = build_feed(issues, watched, None, search=fake_search, now=NOW)
    for n in (1, 2, 3):
        comment = issue_actions(feed, n, None)["comment"]
        assert comment and "@someone" not in comment and "<img" not in comment


def test_actions_only_on_change(watched):
    feed = build_feed([issue(1), issue(2, lat="10")], watched, None, search=fake_search, now=NOW)
    new = issue_actions(feed, 1, None)
    assert new["comment"] and new["add"] == ["searched"] and not new["close"]
    assert issue_actions(feed, 1, "searched") == {"comment": None, "add": [], "remove": [], "close": False}
    bad = issue_actions(feed, 2, "searched")
    assert bad["close"] and bad["add"] == ["invalid"] and "searched" in bad["remove"]
    assert issue_actions(feed, 99, None) == {"comment": None, "add": [], "remove": [], "close": False}


def test_accept_entry_appends_once(watched, tmp_path):
    lakes_in = tmp_path / "lakes_in.json"
    lakes_in.write_text(LAKES_IN, encoding="utf-8")
    feed = build_feed([issue(7)], watched, None, search=fake_search, now=NOW)
    first = accept_entry(feed, issue(7), lakes_in, "2026-11-05")
    second = accept_entry(feed, issue(7), lakes_in, "2026-11-06")
    assert first == second == "moraine_lake_above_gulmit"
    rows = json.loads(lakes_in.read_text(encoding="utf-8"))
    assert len(rows) == 2 and rows[1]["role"] == "watch"
    assert rows[1]["coord_source"] == "Requested 2026-11-05 (issue #7): Glacier survey"
    assert one(feed, 7)["state"] == "accepted" and one(feed, 7)["lake_id"] == first


@pytest.mark.parametrize("edit", [{"lat": "36.9"}, {"name": "Renamed"}, {"source": "Another survey"}])
def test_accept_refuses_values_edited_after_the_check(watched, tmp_path, edit):
    lakes_in = tmp_path / "lakes_in.json"
    lakes_in.write_text(LAKES_IN, encoding="utf-8")
    feed = build_feed([issue(7)], watched, None, search=fake_search, now=NOW)
    with pytest.raises(RequestError) as e:
        accept_entry(feed, issue(7, **edit), lakes_in, "2026-11-05")
    assert str(e.value) == "This request changed after it was approved. A team member must accept it again."
    assert lakes_in.read_text(encoding="utf-8") == LAKES_IN
    assert one(feed, 7)["state"] == "searched"


def test_accept_refuses_invalid_entry(watched, tmp_path):
    lakes_in = tmp_path / "lakes_in.json"
    lakes_in.write_text(LAKES_IN, encoding="utf-8")
    feed = build_feed([issue(7, lat="10")], watched, None, search=fake_search, now=NOW)
    with pytest.raises(RequestError):
        accept_entry(feed, issue(7, lat="10"), lakes_in, "2026-11-05")
    with pytest.raises(RequestError):
        accept_entry(feed, issue(99), lakes_in, "2026-11-05")
    assert lakes_in.read_text(encoding="utf-8") == LAKES_IN


def test_feed_never_contains_source(watched, tmp_path):
    feed = build_feed([issue(1, source="Secret survey")], watched, None, search=fake_search, now=NOW)
    path = tmp_path / "requests.json"
    write_feed(feed, path)
    text = path.read_text(encoding="utf-8")
    assert "Secret survey" not in text and "source" not in text
    assert json.loads(text)["requests"][0].keys() >= {"issue", "name", "lat", "lon", "state", "created"}


def test_cli_lake_issues_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(lake_issues, "coverage", fake_search)
    lakes_in = tmp_path / "lakes_in.json"
    lakes_in.write_text(LAKES_IN, encoding="utf-8")
    issues = tmp_path / "issues.json"
    issues.write_bytes((HERE / "fixtures" / "issues_basic.json").read_bytes())
    feed_path, actions = tmp_path / "out" / "requests.json", tmp_path / "actions.json"
    args = ["lake-issues", "--issues", str(issues), "--feed", str(feed_path),
            "--lakes-in", str(lakes_in), "--event-issue", "3", "--actions", str(actions)]
    run_pipeline.main(args)
    feed = json.loads(feed_path.read_text(encoding="utf-8"))
    assert [r["issue"] for r in feed["requests"]] == [5, 3]
    assert one(feed, 3)["state"] == "searched" and one(feed, 5)["state"] == "invalid"
    acts = {a["issue"]: a for a in json.loads(actions.read_text(encoding="utf-8"))}
    assert acts[3]["add"] == ["searched"] and acts[3]["comment"] and acts[3]["close"] is False
    assert acts[5]["add"] == ["invalid"] and acts[5]["close"] is True
    run_pipeline.main(args)  # the labels were never applied, so the same actions come again
    assert {a["issue"] for a in json.loads(actions.read_text(encoding="utf-8"))} == {3, 5}
    labelled = json.loads(issues.read_text(encoding="utf-8"))
    labelled[0]["labels"].append({"name": "searched"})
    labelled[1].update(state="closed", labels=labelled[1]["labels"] + [{"name": "invalid"}])
    issues.write_text(json.dumps(labelled), encoding="utf-8")
    run_pipeline.main(["lake-issues", "--issues", str(issues), "--feed", str(feed_path),
                       "--lakes-in", str(lakes_in), "--actions", str(actions)])  # --event-issue is optional
    assert json.loads(actions.read_text(encoding="utf-8")) == []
    run_pipeline.main(["lake-issue-accept", "--issues", str(issues), "--feed", str(feed_path), "--issue", "3",
                       "--lakes-in", str(lakes_in), "--today", "2026-11-05", "--actions", str(actions)])
    assert one(json.loads(feed_path.read_text(encoding="utf-8")), 3)["lake_id"] == "moraine_lake_above_gulmit"
    (act,) = json.loads(actions.read_text(encoding="utf-8"))
    assert act == {"issue": 3, "comment": "Accepted. The lake is now watched: "
                              "https://saeedahmad.me/SARtale/#lakes/moraine_lake_above_gulmit",
                   "add": [], "remove": ["searched", "too few passes", "rebuild failed"], "close": True}


def test_rejected_reason_from_close_reason(watched):
    closed = issue(1, "closed")
    closed["close_reason"] = "Not a\u202e lake\x00, " + "x" * 300
    plain = issue(2, "closed", lat="36.5")
    feed = build_feed([closed, plain], watched, None, search=fake_search, now=NOW)
    reason = one(feed, 1)["reason"]
    assert one(feed, 1)["state"] == "rejected" and reason.startswith("Not a lake, x") and len(reason) == 200
    assert one(feed, 2)["state"] == "rejected" and one(feed, 2)["reason"] is None


def test_invalid_name_is_not_stored_raw(watched, tmp_path):
    feed = build_feed([issue(4, name="Bad\u202ename"), issue(5, name="Fine name", lat="10")], watched, None,
                      search=fake_search, now=NOW)
    assert one(feed, 4)["state"] == "invalid" and one(feed, 4)["name"] == "Request #4"
    assert one(feed, 5)["name"] == "Fine name"


def test_accept_marker_cannot_be_spoofed(watched, tmp_path):
    lakes_in = tmp_path / "lakes_in.json"
    lakes_in.write_text(LAKES_IN, encoding="utf-8")
    spoof = "see (issue #7): nothing"  # the source the check recorded, so the approval covers it
    feed = build_feed([issue(3, name="First", lat="36.2", source=spoof), issue(7, name="Second", lat="36.5")],
                      watched, None, search=fake_search, now=NOW)
    accept_entry(feed, issue(3, name="First", lat="36.2", source=spoof), lakes_in, "2026-11-05")
    second = accept_entry(feed, issue(7, name="Second", lat="36.5"), lakes_in, "2026-11-05")
    rows = json.loads(lakes_in.read_text(encoding="utf-8"))
    assert len(rows) == 3 and rows[2]["id"] == second == "second"


def test_cli_accept_error_exits_one_without_traceback(tmp_path, capsys):
    lakes_in = tmp_path / "lakes_in.json"
    lakes_in.write_text(LAKES_IN, encoding="utf-8")
    issues, feed_path = tmp_path / "issues.json", tmp_path / "requests.json"
    issues.write_text(json.dumps([issue(7, lat="10")]), encoding="utf-8")
    write_feed(build_feed([issue(7, lat="10")], [], None, search=fake_search, now=NOW), feed_path)
    with pytest.raises(SystemExit) as e:
        run_pipeline.main(["lake-issue-accept", "--issues", str(issues), "--feed", str(feed_path), "--issue", "7",
                           "--lakes-in", str(lakes_in), "--today", "2026-11-05", "--actions", str(tmp_path / "a.json")])
    assert e.value.code == 1
    err = capsys.readouterr().err
    assert "Issue #7" in err and "Traceback" not in err
    assert not (tmp_path / "a.json").exists()


OLD = ('[\r\n'
       '  {"id": "yaz_sam", "name": "Old", "lon": 74.0, "lat": 36.0, "role": "watch",\r\n'
       '   "coord_source": "x é", "outline": null, "downstream": null, "downstream_source": null}\r\n'
       ']\r\n')


def test_append_lake_entry_appends_one_entry_and_keeps_the_rest_of_the_file_byte_identical(tmp_path):
    lakes = tmp_path / "lakes_in.json"
    lakes.write_bytes(OLD.encode("utf-8"))
    entry = {"id": "zebra_lake", "name": "Zebra Lake é", "lon": 74.5, "lat": 36.5, "role": "watch",
             "coord_source": "Requested 2026-11-04: Glacier survey", "outline": None,
             "downstream": None, "downstream_source": None}
    run_pipeline.append_lake_entry(lakes, entry)
    new = lakes.read_bytes().decode("utf-8")
    assert new.startswith(OLD.replace("null}\r\n]\r\n", "null},\r\n"))
    assert new.endswith("}\r\n]\r\n")
    assert json.loads(new)[-1] == entry
    assert json.loads(new)[:-1] == json.loads(OLD)
    assert "é" in new


def test_lake_slug_makes_a_unique_id_from_the_name():
    assert run_pipeline.lake_slug("Yaz Sam", {"yaz_sam"}) == "yaz_sam_2"
    assert run_pipeline.lake_slug("Yaz Sam", {"yaz_sam", "yaz_sam_2"}) == "yaz_sam_3"
    assert run_pipeline.lake_slug("Zebra Lake é", set()) == "zebra_lake"
    assert run_pipeline.lake_slug("!!!", set()) == "lake"


def test_closed_with_unconfirmed_accepted_label_is_rejected(watched):
    feed = build_feed([issue(1, "closed", labels=["accepted"])], watched, None, search=fake_search, now=NOW)
    assert one(feed, 1)["state"] == "rejected"


def test_reconcile_adds_missing_state_label_with_comment_once(watched):
    issues = [issue(1), issue(2, lat="10")]
    feed = build_feed(issues, watched, None, search=fake_search, now=NOW)
    acts = {a["issue"]: a for a in reconcile_actions(feed, issues, None)}
    assert acts[1]["add"] == ["searched"] and acts[1]["comment"].startswith("Checked against NASA")
    assert acts[2]["add"] == ["invalid"] and acts[2]["close"] is True and acts[2]["comment"]
    told = [issue(1, labels=["searched"]), issue(2, "closed", labels=["invalid"], lat="10")]
    assert reconcile_actions(feed, told, feed) == []


def test_reconcile_removes_stale_labels_without_comment(watched):
    issues = [issue(1, labels=["searched", "too few passes", "invalid"])]
    feed = build_feed(issues, watched, None, search=fake_search, now=NOW)
    (act,) = reconcile_actions(feed, issues, feed)
    assert act["add"] == [] and act["comment"] is None and act["close"] is False
    assert sorted(act["remove"]) == ["invalid", "too few passes"]


def test_reconcile_closes_open_invalid(watched):
    issues = [issue(2, labels=["invalid"], lat="10")]  # reopened by the visitor, still invalid
    feed = build_feed(issues, watched, None, search=fake_search, now=NOW)
    (act,) = reconcile_actions(feed, issues, feed)
    assert act["close"] is True and act["comment"] is None and act["add"] == []


def test_reconcile_keeps_rebuild_failed_on_checked_request(watched):
    issues = [issue(1, labels=["searched", "rebuild failed"])]  # a failed accept
    feed = build_feed(issues, watched, None, search=fake_search, now=NOW)
    assert reconcile_actions(feed, issues, feed) == []
    down = dict(feed, requests=[dict(feed["requests"][0], state="check_failed")])
    (act,) = reconcile_actions(feed, issues, down)  # the catalogue answered this time
    assert act["remove"] == ["rebuild failed"]


def test_reconcile_catalogue_down_comments_once(watched):
    def down(lat, lon):
        raise OSError("no route")
    feed = build_feed([issue(1)], watched, None, search=down, now=NOW)
    (act,) = reconcile_actions(feed, [issue(1)], None)
    assert act["add"] == ["rebuild failed"]
    assert act["comment"] == "NASA's catalogue did not answer; the team will retry."
    assert reconcile_actions(feed, [issue(1, labels=["rebuild failed"])], feed) == []


def test_reconcile_accepted_only_tidies_labels(watched):
    issues = [issue(1, "closed", labels=["accepted", "searched"])]
    feed = build_feed([issue(1)], watched, None, search=fake_search, now=NOW)
    feed["requests"][0].update(state="accepted", lake_id="x")
    feed = build_feed(issues, watched, feed, search=fake_search, now=NOW)
    (act,) = reconcile_actions(feed, issues, feed)
    assert act == {"issue": 1, "comment": None, "add": [], "remove": ["searched"], "close": False,
                   "dispatch": False}
    assert reconcile_actions(feed, [issue(1, labels=["accepted"])], feed) == []


def test_reconcile_redispatches_unconfirmed_accept(watched):
    issues = [issue(1, labels=["searched", "accepted"]),
              issue(2, labels=["searched", "accepted", "rebuild failed"], lat="36.5"),
              issue(3, "closed", labels=["rejected", "accepted"], lat="36.8")]
    feed = build_feed(issues, watched, None, search=fake_search, now=NOW)
    acts = {a["issue"]: a for a in reconcile_actions(feed, issues, feed)}
    assert acts[1]["dispatch"] is True and acts[1]["comment"] is None
    assert 2 not in acts, "after a failed rebuild the team re-adds the label"
    assert 3 not in acts
    feed["requests"] = [dict(r, state="accepted") if r["issue"] == 1 else r for r in feed["requests"]]
    acts = {a["issue"]: a for a in reconcile_actions(feed, issues, feed)}
    assert acts[1]["dispatch"] is False and acts[1]["remove"] == ["searched"]


def test_reconcile_never_echoes_text(watched):
    evil = "<img src=x> @someone"
    issues = [issue(1, name=evil), issue(2, name=evil, lat="10")]
    feed = build_feed(issues, watched, None, search=fake_search, now=NOW)
    for act in reconcile_actions(feed, issues, None):
        assert "@someone" not in json.dumps(act) and "<img" not in json.dumps(act)


CHANGED = "This request changed after it was approved. A team member must accept it again."


def test_checked_entries_record_the_values_hash(watched):
    feed = build_feed([issue(1), issue(2, lat="10")], watched, None, search=fake_search, now=NOW)
    h = one(feed, 1)["values_sha256"]
    assert len(h) == 64 and one(feed, 1)["values_at"] == NOW
    assert one(feed, 2)["values_sha256"] is None, "an invalid request has no values to approve"
    same = build_feed([issue(1, lat="36.2 °N")], watched, feed, search=fake_search, now="2026-11-06T00:00:00Z")
    assert one(same, 1)["values_sha256"] == h and one(same, 1)["values_at"] == NOW, "same values, same hash"
    edited = build_feed([issue(1, source="Another survey")], watched, feed, search=fake_search,
                        now="2026-11-06T00:00:00Z")
    assert one(edited, 1)["values_sha256"] != h and one(edited, 1)["values_at"] == "2026-11-06T00:00:00Z"
    assert "Glacier survey" not in json.dumps(feed), "the hash, never the source, is in requests.json"


def test_accept_refuses_an_approval_older_than_the_checked_values(watched, tmp_path):
    lakes_in = tmp_path / "lakes_in.json"
    lakes_in.write_text(LAKES_IN, encoding="utf-8")
    feed = build_feed([issue(7)], watched, None, search=fake_search, now=NOW)
    with pytest.raises(RequestError) as e:
        accept_entry(feed, issue(7), lakes_in, "2026-11-05", approved_at="2026-11-05T08:59:59Z")
    assert str(e.value) == CHANGED
    assert accept_entry(feed, issue(7), lakes_in, "2026-11-05", approved_at="2026-11-05T09:00:00Z")


def test_accept_refuses_an_entry_without_a_hash(watched, tmp_path):
    lakes_in = tmp_path / "lakes_in.json"
    lakes_in.write_text(LAKES_IN, encoding="utf-8")
    feed = build_feed([issue(7)], watched, None, search=fake_search, now=NOW)
    del feed["requests"][0]["values_sha256"]  # written before hashes existed
    with pytest.raises(RequestError):
        accept_entry(feed, issue(7), lakes_in, "2026-11-05")


def test_reconcile_voids_an_approval_after_an_edit(watched):
    before = build_feed([issue(1, labels=["searched"])], watched, None, search=fake_search, now=NOW)
    edited = [issue(1, labels=["searched", "accepted"], name="Other name")]
    feed = build_feed(edited, watched, before, search=fake_search, now="2026-11-06T00:00:00Z")
    (act,) = reconcile_actions(feed, edited, before)
    assert act["comment"] == CHANGED and act["remove"] == ["accepted"] and act["dispatch"] is False
    assert act["add"] == [] and act["close"] is False


def test_reconcile_voids_an_approval_when_the_edit_makes_it_invalid(watched):
    before = build_feed([issue(1, labels=["searched"])], watched, None, search=fake_search, now=NOW)
    edited = [issue(1, labels=["searched", "accepted"], lat="10")]
    feed = build_feed(edited, watched, before, search=fake_search, now=NOW)
    (act,) = reconcile_actions(feed, edited, before)
    assert act["comment"].startswith(CHANGED) and "This request cannot be used." in act["comment"]
    assert sorted(act["remove"]) == ["accepted", "searched"] and act["add"] == ["invalid"] and act["close"]


def test_reconcile_unchanged_approval_still_dispatches(watched):
    before = build_feed([issue(1, labels=["searched"])], watched, None, search=fake_search, now=NOW)
    same = [issue(1, labels=["searched", "accepted"])]
    feed = build_feed(same, watched, before, search=fake_search, now=NOW)
    (act,) = reconcile_actions(feed, same, before)
    assert act["dispatch"] is True and act["comment"] is None and act["remove"] == []


def test_reconcile_dispatches_one_issue_per_run(watched):
    issues = [issue(5, labels=["searched", "accepted"], lat="36.65"), issue(3, labels=["searched", "accepted"]),
              issue(4, labels=["searched", "accepted"], lat="36.5")]
    feed = build_feed(issues, watched, None, search=fake_search, now=NOW)
    acts = reconcile_actions(feed, issues, feed)
    assert [a["issue"] for a in acts if a["dispatch"]] == [3]
    assert [a["issue"] for a in acts] == [3], "the others wait for a later run"


def test_reconcile_and_the_publish_drain_choose_the_same_issue(watched):
    from sartale.accept_queue import next_accept

    issues = [issue(5, labels=["searched", "accepted"], lat="36.65"),
              issue(3, labels=["searched", "accepted", "rebuild failed"]),
              issue(4, labels=["searched", "accepted"], lat="36.5")]
    feed = build_feed(issues, watched, None, search=fake_search, now=NOW)
    acts = reconcile_actions(feed, issues, feed)
    assert [a["issue"] for a in acts if a["dispatch"]] == [4] == [next_accept(feed, issues)]
    assert next_accept(feed, issues, exclude={4}) == 5


def test_reconcile_dispatches_the_next_one_when_the_lowest_is_voided(watched):
    before = build_feed([issue(1, labels=["searched"]), issue(2, labels=["searched"], lat="36.5")],
                        watched, None, search=fake_search, now=NOW)
    now = [issue(1, labels=["searched", "accepted"], name="Other name"),
           issue(2, labels=["searched", "accepted"], lat="36.5")]
    feed = build_feed(now, watched, before, search=fake_search, now="2026-11-06T00:00:00Z")
    acts = {a["issue"]: a for a in reconcile_actions(feed, now, before)}
    assert acts[1]["dispatch"] is False and "accepted" in acts[1]["remove"]
    assert acts[2]["dispatch"] is True


def test_cli_accept_passes_the_approval_time(tmp_path, monkeypatch):
    monkeypatch.setattr(lake_issues, "coverage", fake_search)
    lakes_in = tmp_path / "lakes_in.json"
    lakes_in.write_text(LAKES_IN, encoding="utf-8")
    issues, feed_path = tmp_path / "issues.json", tmp_path / "requests.json"
    issues.write_text(json.dumps([issue(7)]), encoding="utf-8")
    write_feed(build_feed([issue(7)], [], None, search=fake_search, now=NOW), feed_path)
    args = ["lake-issue-accept", "--issues", str(issues), "--feed", str(feed_path), "--issue", "7",
            "--lakes-in", str(lakes_in), "--today", "2026-11-05", "--actions", str(tmp_path / "a.json")]
    with pytest.raises(SystemExit) as e:
        run_pipeline.main(args + ["--approved-at", "2026-11-01T00:00:00Z"])
    assert e.value.code == 1
    run_pipeline.main(args + ["--approved-at", "2026-11-05T10:00:00Z"])
    assert one(json.loads(feed_path.read_text(encoding="utf-8")), 7)["state"] == "accepted"


MIGRATED = "This request was approved before the new check existed. A team member must accept it again."


def test_reconcile_never_voids_a_closed_issue(watched):
    before = build_feed([issue(1, labels=["searched"])], watched, None, search=fake_search, now=NOW)
    closed = [issue(1, "closed", labels=["rejected", "accepted"], name="Other name")]
    feed = build_feed(closed, watched, before, search=fake_search, now=NOW)
    for act in reconcile_actions(feed, closed, before):
        assert "accepted" not in act["remove"] and CHANGED not in (act["comment"] or "")


def test_reconcile_voids_an_approval_given_before_hashes_existed(watched):
    old = build_feed([issue(1, labels=["searched"])], watched, None, search=fake_search, now=NOW)
    for r in old["requests"]:
        r.pop("values_sha256"), r.pop("values_at")  # requests.json as the previous version wrote it
    labelled = [issue(1, labels=["searched", "accepted"])]
    feed = build_feed(labelled, watched, old, search=fake_search, now=NOW)
    (act,) = reconcile_actions(feed, labelled, old)
    assert act["comment"] == MIGRATED and act["remove"] == ["accepted"] and act["dispatch"] is False
    assert reconcile_actions(feed, [issue(1, labels=["searched"])], feed) == [], "once is enough"


def test_accept_refuses_an_entry_from_before_hashes_with_the_migration_message(watched, tmp_path):
    lakes_in = tmp_path / "lakes_in.json"
    lakes_in.write_text(LAKES_IN, encoding="utf-8")
    feed = build_feed([issue(7)], watched, None, search=fake_search, now=NOW)
    del feed["requests"][0]["values_sha256"]
    with pytest.raises(RequestError) as e:
        accept_entry(feed, issue(7), lakes_in, "2026-11-05")
    assert str(e.value) == MIGRATED


def test_a_name_with_a_banned_phrase_is_invalid_and_never_reaches_requests_json(watched):
    feed = build_feed([issue(1, name="Safe lake")], watched, None, search=fake_search, now=NOW)
    entry = one(feed, 1)
    assert entry["state"] == "invalid"
    assert entry["reason"] == ('The name uses a phrase SARtale does not use ("safe"); '
                               "please use the lake's usual name.")
    assert entry["name"] == "Request #1" and "Safe lake" not in json.dumps(feed)


# exponent, digit-group underscore, Arabic-Indic and full-width digits: float() takes them, the app does not
LOOSE_NUMBERS = ("3.62e1", "3_6.2", "٣٦.٢", "３６.２", "36.2e0°N", "36.2 °N")


@pytest.mark.parametrize("bad", LOOSE_NUMBERS)
def test_coordinates_only_in_plain_ascii_decimals(watched, bad):
    feed = build_feed([issue(1, lat=bad)], watched, None, search=fake_search, now=NOW)
    entry = one(feed, 1)
    assert entry["state"] == "invalid" and entry["reason"] == "lat must be a number." and entry["lat"] is None
    assert issue_values_sha256(issue(1, lat=bad)) is None


@pytest.mark.parametrize("passes, words", [(0, "0 NISAR passes"), (1, "1 NISAR pass over"), (2, "2 NISAR passes")])
def test_the_comment_counts_passes_in_good_english(watched, passes, words):
    found = lambda lat, lon: {"passes": passes, "tracks": ["055A"], "first": "2026-10-01", "last": "2026-10-01"}  # noqa: E731
    feed = build_feed([issue(1)], watched, None, search=found, now=NOW)
    comment = issue_actions(feed, 1, None)["comment"]
    assert words in comment and ("1 NISAR passes" not in comment)


def test_a_searched_comment_with_many_passes():
    from sartale.lake_issues import _comment
    entry = {"state": "searched", "passes": 14, "tracks": ["055A", "156A"], "first": "2026-06-18", "last": "2026-10-23"}
    assert _comment(entry) == ("Checked against NASA's catalogue: 14 NISAR passes over this point on 2 tracks, "
                               "2026-06-18 to 2026-10-23. The team decides whether this lake is watched.")


BANNED_SOURCE = ('The source uses a phrase SARtale does not use ("{}"); '
                 "please describe where the coordinates come from.")


def test_a_source_with_a_banned_phrase_is_invalid(watched):
    feed = build_feed([issue(1, source="Early warning survey")], watched, None, search=fake_search, now=NOW)
    entry = one(feed, 1)
    assert entry["state"] == "invalid" and entry["reason"] == BANNED_SOURCE.format("early warning")
    assert "Early warning survey" not in json.dumps(feed)


def test_accept_refuses_a_banned_source_checked_before_the_rule(watched, tmp_path):
    lakes_in = tmp_path / "lakes_in.json"
    lakes_in.write_text(LAKES_IN, encoding="utf-8")
    feed = build_feed([issue(7)], watched, None, search=fake_search, now=NOW)
    old = issue(7, source="A safe survey")
    one(feed, 7)["values_sha256"] = issue_values_sha256(old)  # as a check before the source rule recorded it
    with pytest.raises(RequestError) as e:
        accept_entry(feed, old, lakes_in, "2026-11-05")
    assert str(e.value) == BANNED_SOURCE.format("safe")
    assert lakes_in.read_text(encoding="utf-8") == LAKES_IN
