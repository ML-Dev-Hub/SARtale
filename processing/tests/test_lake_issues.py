import json
from pathlib import Path

import pytest

from sartale import lake_issues, run_pipeline
from sartale.lake_issues import accept_entry, build_feed, issue_actions, parse_issue_body, write_feed
from sartale.lake_requests import RequestError
from sartale.lakes import load_lakes

NOW = "2026-11-05T09:00:00Z"
HERE = Path(__file__).parent
LAKES_IN = (
    '[\n'
    '  {"id": "attabad", "name": "Attabad Lake (landslide-dammed control)", "lon": 74.86, "lat": 36.33, "role": "control",\n'
    '   "coord_source": "spike", "outline": null, "downstream": null, "downstream_source": null}\n'
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
    issues = [issue(n, lat=str(34.5 + (n - 1) // 100 * 0.05), lon=str(71.0 + (n - 1) % 100 * 0.05))
              for n in range(1, 202)]
    feed = build_feed(issues, watched, None, search=fake_search, now=NOW)
    assert one(feed, 200)["state"] == "searched"
    assert one(feed, 201)["state"] == "invalid"
    assert one(feed, 201)["reason"] == "The request list is full; try again later."


def test_labels_drive_state(watched):
    issues = [issue(1, labels=["accepted"], lat="36.2"),
              issue(2, "closed", labels=["invalid"], lat="36.5"),
              issue(3, "closed", labels=["searched"], lat="36.8"),
              issue(4, "open", labels=["invalid"], lat="37.1")]  # reopened
    feed = build_feed(issues, watched, None, search=fake_search, now=NOW)
    assert one(feed, 1)["state"] == "accepted"
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
    first["requests"][0]["lake_id"] = "moraine_lake"
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


def test_accept_uses_checked_values_not_edited_body(watched, tmp_path):
    lakes_in = tmp_path / "lakes_in.json"
    lakes_in.write_text(LAKES_IN, encoding="utf-8")
    feed = build_feed([issue(7)], watched, None, search=fake_search, now=NOW)
    accept_entry(feed, issue(7, lat="36.9", name="Renamed"), lakes_in, "2026-11-05")
    added = json.loads(lakes_in.read_text(encoding="utf-8"))[1]
    assert added["lat"] == 36.2 and added["name"] == "Moraine lake above Gulmit"


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
    act = json.loads(actions.read_text(encoding="utf-8"))
    assert act["add"] == ["searched"] and act["comment"] and act["close"] is False
    run_pipeline.main(args)
    assert json.loads(actions.read_text(encoding="utf-8"))["comment"] is None
    run_pipeline.main(["lake-issue-accept", "--issues", str(issues), "--feed", str(feed_path), "--issue", "3",
                       "--lakes-in", str(lakes_in), "--today", "2026-11-05", "--actions", str(actions)])
    assert one(json.loads(feed_path.read_text(encoding="utf-8")), 3)["lake_id"] == "moraine_lake_above_gulmit"
    act = json.loads(actions.read_text(encoding="utf-8"))
    assert act == {"comment": "Accepted. The lake is now watched: "
                              "https://saeedahmadicp.github.io/SARtale/#lakes/moraine_lake_above_gulmit",
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
    feed = build_feed([issue(3, name="First", lat="36.2"), issue(7, name="Second", lat="36.5")], watched, None,
                      search=fake_search, now=NOW)
    accept_entry(feed, issue(3, name="First", lat="36.2", source="see (issue #7): nothing"), lakes_in, "2026-11-05")
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
