"""Tests for the helper scripts the GitHub workflows run (.github/scripts). No network, no real GitHub."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / ".github" / "scripts"


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode, before = True, sys.dont_write_bytecode  # no __pycache__ under .github
    sys.path.insert(0, str(SCRIPTS))  # as when run as a script: approver imports fetch_issues
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = before
        sys.path.remove(str(SCRIPTS))
    return module


fetch_issues = load_script("fetch_issues")
json_changed = load_script("json_changed")
approver = load_script("approver")


def issue(number, state="open", labels=("lake-request",), **extra):
    return {"number": number, "title": f"Add a lake: {number}", "body": "b", "state": state,
            "labels": [{"name": n} for n in labels], "created_at": "2026-11-03T10:00:00Z",
            "user": {"login": "visitor"}, "author_association": "NONE", **extra}


def comment(body, assoc, kind="User"):
    return {"body": body, "author_association": assoc, "user": {"login": "x", "type": kind}}


class FakeGh:
    """Answers `gh api ...` calls from a table of paths; records every call."""

    def __init__(self, pages, comments=None, single=None, events=None, permissions=None):
        self.pages, self.comments, self.calls = pages, comments or {}, []
        self.single, self.events = single, events or []
        self.permissions = permissions or {}  # login -> permission; anyone else is "admin"

    def __call__(self, args):
        assert isinstance(args, list) and all(isinstance(a, str) for a in args)
        self.calls.append(args)
        assert args[0] == "api"
        path = next(a for a in args[1:] if not a.startswith("-"))
        if "/comments" in path:
            number = int(path.split("/issues/")[1].split("/")[0])
            return json.dumps(self.comments.get(number, []))
        if "/collaborators/" in path:
            login = path.split("/collaborators/")[1].split("/")[0]
            return json.dumps({"permission": self.permissions.get(login, "admin")})
        if "/events" in path:
            half = len(self.events) // 2  # two pages, as --paginate prints them
            return json.dumps(self.events[:half]) + json.dumps(self.events[half:])
        if "?" not in path:
            return json.dumps(self.single)
        return self.pages


def test_fetch_lists_lake_request_issues_with_pagination():
    pages = json.dumps([issue(1), issue(2)]) + "\n" + json.dumps([issue(3)])  # gh --paginate output
    gh = FakeGh(pages)
    got = fetch_issues.fetch("owner/repo", runner=gh)
    assert [i["number"] for i in got] == [1, 2, 3]
    first = gh.calls[0]
    assert "--paginate" in first
    assert "repos/owner/repo/issues?labels=lake-request&state=all&per_page=100" in first
    assert all(i["close_reason"] is None for i in got)
    assert len(gh.calls) == 1, "open issues need no comment lookups"


def test_fetch_drops_pull_requests():
    gh = FakeGh(json.dumps([issue(1), issue(2, pull_request={"url": "x"})]))
    assert [i["number"] for i in fetch_issues.fetch("o/r", runner=gh)] == [1]


def test_close_reason_is_last_team_comment():
    comments = {4: [comment("team first", "OWNER"), comment("visitor says", "NONE"),
                    comment("team last", "MEMBER"), comment("visitor again", "CONTRIBUTOR")],
                6: [comment("only visitor", "NONE")],
                7: [comment("collab", "COLLABORATOR")]}
    pages = json.dumps([issue(4, "closed"), issue(6, "closed"), issue(7, "closed"),
                        issue(8, "closed", ("lake-request", "accepted")),
                        issue(9, "closed", ("lake-request", "invalid"))])
    gh = FakeGh(pages, comments)
    got = {i["number"]: i["close_reason"] for i in fetch_issues.fetch("o/r", runner=gh)}
    assert got == {4: "team last", 6: None, 7: "collab", 8: None, 9: None}
    looked_up = [c for c in gh.calls if any("/comments" in a for a in c)]
    assert len(looked_up) == 3, "accepted and invalid issues need no reason"
    assert all("--paginate" in c for c in looked_up)


def test_bot_comments_are_never_a_reason():
    comments = {4: [comment("team reason", "OWNER"), comment("The check failed; see x.", "MEMBER", "Bot")]}
    gh = FakeGh(json.dumps([issue(4, "closed")]), comments)
    (got,) = fetch_issues.fetch("o/r", runner=gh)
    assert got["close_reason"] == "team reason"


def test_labels_are_passed_as_they_are():
    pages = json.dumps([issue(2, labels=("lake-request", "accepted"))])
    (got,) = fetch_issues.fetch("o/r", runner=FakeGh(pages), confirmed_from={"requests": []})
    assert [lb["name"] for lb in got["labels"]] == ["lake-request", "accepted"]


def test_unconfirmed_accept_on_closed_issue_gets_a_reason():
    feed = {"requests": [{"issue": 1, "state": "accepted"}]}
    pages = json.dumps([issue(1, "closed", ("lake-request", "accepted")),
                        issue(2, "closed", ("lake-request", "accepted"))])
    gh = FakeGh(pages, {1: [comment("yes", "OWNER")], 2: [comment("no", "OWNER")]})
    got = {i["number"]: i["close_reason"] for i in fetch_issues.fetch("o/r", runner=gh, confirmed_from=feed)}
    assert got == {1: None, 2: "no"}


def test_fetch_main_writes_file(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    feed = tmp_path / "requests.json"
    feed.write_text(json.dumps({"requests": []}), encoding="utf-8")
    out = tmp_path / "issues.json"
    gh = FakeGh(json.dumps([issue(1)]))
    fetch_issues.main(["--out", str(out), "--confirmed-from", str(feed)], runner=gh)
    assert json.loads(out.read_text(encoding="utf-8"))[0]["number"] == 1


def test_run_gh_uses_argument_list(monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"], seen["kw"] = cmd, kw
        return subprocess.CompletedProcess(cmd, 0, stdout="[]", stderr="")

    monkeypatch.setattr(fetch_issues.subprocess, "run", fake_run)
    assert fetch_issues.run_gh(["api", "x"]) == "[]"
    assert seen["cmd"] == ["gh", "api", "x"]
    assert not seen["kw"].get("shell") and seen["kw"].get("check") is True


def labeled(name, login, when="2026-11-05T10:00:00Z"):
    return {"event": "labeled", "label": {"name": name}, "actor": {"login": login}, "created_at": when}


def test_approval_is_the_last_to_add_accepted_with_its_time():
    events = [labeled("accepted", "early", "2026-11-01T00:00:00Z"), labeled("lake-request", "visitor"),
              {"event": "unlabeled", "label": {"name": "accepted"}, "actor": {"login": "bot"}},
              labeled("accepted", "owner-1", "2026-11-05T11:00:00Z"), labeled("searched", "github-actions[bot]")]
    gh = FakeGh("", single=issue(7, labels=("lake-request", "searched", "accepted")), events=events)
    assert approver.approval("o/r", 7, runner=gh) == ("owner-1", "2026-11-05T11:00:00Z")
    paths = [next(a for a in c[1:] if not a.startswith("-")) for c in gh.calls]
    assert paths == ["repos/o/r/issues/7", "repos/o/r/issues/7/events?per_page=100"]
    assert "--paginate" in gh.calls[1]


@pytest.mark.parametrize("single", [
    issue(7, labels=("lake-request", "searched")),                  # label removed since
    issue(7, "closed", labels=("lake-request", "accepted")),        # closed since
    issue(7, labels=("accepted",)),                                 # not a request
])
def test_not_waiting_when_the_issue_moved_on(single):
    gh = FakeGh("", single=single, events=[labeled("accepted", "owner")])
    with pytest.raises(approver.NotWaiting):
        approver.approval("o/r", 7, runner=gh)
    assert approver.approver("o/r", 7, runner=gh) is None


@pytest.mark.parametrize("events", [
    [],                                                             # no labeled event at all
    [labeled("accepted", "a/../b")],                                # not a login
    [labeled("accepted", "github-actions[bot]")],                   # a bot
    [labeled("accepted", "owner", "yesterday")],                    # no usable time
])
def test_no_valid_approver(events):
    single = issue(7, labels=("lake-request", "accepted"))
    assert approver.approval("o/r", 7, runner=FakeGh("", single=single, events=events)) is None


def test_approver_main_exit_codes(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    waiting = issue(7, labels=("lake-request", "accepted"))
    approver.main(["--issue", "7"], runner=FakeGh("", single=waiting, events=[labeled("accepted", "boss")]))
    assert capsys.readouterr().out == "boss\n2026-11-05T10:00:00Z\n"
    with pytest.raises(SystemExit) as e:
        approver.main(["--issue", "7"], runner=FakeGh("", single=issue(7), events=[]))
    assert e.value.code == 3, "moot: skip quietly"
    with pytest.raises(SystemExit) as e:
        approver.main(["--issue", "7"], runner=FakeGh("", single=waiting, events=[]))
    assert e.value.code == 4, "unverifiable: refuse"


feed_state = load_script("feed_state")


def test_feed_state(tmp_path, capsys):
    feed = {"requests": [{"issue": 3, "state": "accepted"}, {"issue": 4, "state": "searched"}]}
    assert feed_state.state(feed, 3) == "accepted" and feed_state.state(feed, 4) == "searched"
    assert feed_state.state(feed, 5) == "none"
    path = tmp_path / "requests.json"
    path.write_text(json.dumps(feed), encoding="utf-8")
    feed_state.main([str(path), "3"])
    feed_state.main([str(tmp_path / "missing.json"), "3"])
    assert capsys.readouterr().out == "accepted\nnone\n"
    with pytest.raises(ValueError):
        feed_state.main([str(path), "3; rm -rf /"])


@pytest.mark.parametrize("old,new,changed", [
    ({"built": "a", "lakes": [1]}, {"built": "b", "lakes": [1]}, False),
    ({"built": "a", "lakes": [1]}, {"built": "a", "lakes": [2]}, True),
    (None, {"built": "a"}, True),
])
def test_json_changed_ignores_one_key(old, new, changed):
    old_text = None if old is None else json.dumps(old)
    assert json_changed.changed(old_text, json.dumps(new), "built") is changed


data_artifact = load_script("data_artifact")
ACCEPTED_FEED = {"updated": "x", "requests": [
    {"issue": 9, "name": "Other", "state": "searched", "values_sha256": "b" * 64},
    {"issue": 7, "name": "Lake", "state": "searched", "values_sha256": "a" * 64, "lake_id": None}]}


@pytest.mark.parametrize("path,ok", [
    ("processing/lakes_in.json", True),
    ("app/public/data/lakes.json", True),
    ("app/public/data/requests.json", True),
    ("app/public/data/lakes/attabad/2026-10-01.webp", True),
    ("app/public/data/lakes/a_b-c.1/x.webp", True),
    ("app/public/data/lakes", False),
    ("app/public/data/lakes/", False),
    ("app/public/data/lakes/../../../.github/workflows/x.yml", False),
    ("app/public/data/lakes/./x.webp", False),
    ("app/public/data/lakes/.hidden", False),
    ("app/public/data/lakes/a\\b.webp", False),
    ("app/public/data/lakes//x.webp", False),
    ("app/public/data/other.json", False),
    ("/app/public/data/lakes.json", False),
    ("processing/sartale/run_pipeline.py", False),
    (".github/scripts/commit-data.sh", False),
])
def test_artifact_path_filter(path, ok):
    assert data_artifact.allowed(path) is ok


def make_repo(tmp_path, name="repo"):
    repo = tmp_path / name
    for rel, text in {"processing/lakes_in.json": "[]\n", "app/public/data/lakes.json": '{"built": "a"}\n',
                      "app/public/data/requests.json": json.dumps(ACCEPTED_FEED) + "\n",
                      "app/public/data/lakes/attabad/old.webp": "old", "app/public/data/lakes/attabad/keep.webp": "k",
                      "processing/sartale/config.py": "DROP_DB = 3.0\n",
                      "processing/outlines/a.geojson": "{}\n", "environment.yml": "name: sartale\n",
                      "README.md": "hi\n"}.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    git("init", "-q", "-b", "main", str(repo), cwd=tmp_path)
    git("config", "user.name", "t", cwd=repo)
    git("config", "user.email", "t@example.com", cwd=repo)
    git("config", "core.autocrlf", "false", cwd=repo)
    git("add", ".", cwd=repo)
    git("commit", "-q", "-m", "start", cwd=repo)
    return repo


def rebuilt(tmp_path):
    """A rebuild in its own clone: new lake, new pictures, one picture pruned, issue 7 accepted."""
    repo = make_repo(tmp_path)
    work = tmp_path / "rebuild"
    git("clone", "-q", str(repo), str(work), cwd=tmp_path)
    (work / "processing/lakes_in.json").write_text('[{"id": "lake"}]\n', encoding="utf-8")
    (work / "app/public/data/lakes.json").write_text('{"built": "b", "lakes": ["lake"]}\n', encoding="utf-8")
    (work / "app/public/data/lakes/attabad/old.webp").unlink()
    (work / "app/public/data/lakes/lake").mkdir()
    (work / "app/public/data/lakes/lake/new.webp").write_bytes(b"\x00new")
    feed = json.loads(json.dumps(ACCEPTED_FEED))
    feed["requests"][1].update(state="accepted", lake_id="lake")
    (work / "app/public/data/requests.json").write_text(json.dumps(feed), encoding="utf-8")
    out = tmp_path / "artifact"
    manifest = data_artifact.pack(work, out)
    return repo, out, manifest


def test_pack_lists_every_allowed_output_and_the_base(tmp_path):
    repo, out, manifest = rebuilt(tmp_path)
    assert sorted(manifest["files"]) == ["app/public/data/lakes.json", "app/public/data/lakes/attabad/keep.webp",
                                         "app/public/data/lakes/lake/new.webp", "app/public/data/requests.json",
                                         "processing/lakes_in.json"]
    assert set(manifest["base"]) == {"processing/lakes_in.json", "app/public/data/lakes.json",
                                     "app/public/data/lakes"}
    assert all(len(v) == 40 for v in manifest["base"].values())
    assert set(manifest["science"]) == set(data_artifact.SCIENCE)
    assert len(manifest["science"]["processing/sartale"]) == 40
    assert not (out / "README.md").exists()


def test_unpack_installs_data_but_never_requests_json(tmp_path):
    repo, out, _ = rebuilt(tmp_path)
    before = (repo / "app/public/data/requests.json").read_text(encoding="utf-8")
    data_artifact.unpack(repo, out)
    assert (repo / "processing/lakes_in.json").read_text(encoding="utf-8") == '[{"id": "lake"}]\n'
    assert (repo / "app/public/data/lakes/lake/new.webp").read_bytes() == b"\x00new"
    assert not (repo / "app/public/data/lakes/attabad/old.webp").exists(), "pruned pictures go"
    assert (repo / "app/public/data/lakes/attabad/keep.webp").exists()
    assert (repo / "app/public/data/requests.json").read_text(encoding="utf-8") == before


def test_accept_marks_only_the_issue_and_writes_the_comment(tmp_path):
    repo, out, _ = rebuilt(tmp_path)
    data_artifact.unpack(repo, out)
    (act,) = data_artifact.accept(repo, out, 7)
    assert act == {"issue": 7, "comment": "Accepted. The lake is now watched: "
                                          "https://saeedahmad.me/SARtale/#lakes/lake",
                   "add": [], "remove": ["searched", "too few passes", "rebuild failed"], "close": True,
                   "dispatch": False}
    feed = json.loads((repo / "app/public/data/requests.json").read_text(encoding="utf-8"))
    assert [(r["issue"], r["state"], r.get("lake_id")) for r in feed["requests"]] == [
        (9, "searched", None), (7, "accepted", "lake")]


def test_accept_refuses_when_the_request_changed_meanwhile(tmp_path):
    repo, out, _ = rebuilt(tmp_path)
    feed = json.loads((repo / "app/public/data/requests.json").read_text(encoding="utf-8"))
    feed["requests"][1]["values_sha256"] = "c" * 64  # a check recorded edited values during the rebuild
    (repo / "app/public/data/requests.json").write_text(json.dumps(feed), encoding="utf-8")
    with pytest.raises(data_artifact.Refused) as e:
        data_artifact.accept(repo, out, 7)
    assert e.value.code == 5


def test_accept_refuses_a_bad_lake_id(tmp_path):
    repo, out, _ = rebuilt(tmp_path)
    feed = json.loads((out / "app/public/data/requests.json").read_text(encoding="utf-8"))
    feed["requests"][1]["lake_id"] = "../x"
    (out / "app/public/data/requests.json").write_text(json.dumps(feed), encoding="utf-8")
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    manifest["files"]["app/public/data/requests.json"] = data_artifact.sha256(out / "app/public/data/requests.json")
    (out / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(data_artifact.Refused):
        data_artifact.accept(repo, out, 7)


def test_unpack_refuses_data_built_on_an_older_main(tmp_path):
    repo, out, _ = rebuilt(tmp_path)
    (repo / "processing/lakes_in.json").write_text('[{"id": "someone_else"}]\n', encoding="utf-8")
    git("commit", "-q", "-am", "another accept", cwd=repo)
    with pytest.raises(data_artifact.Refused) as e:
        data_artifact.unpack(repo, out)
    assert e.value.code == 6
    assert "someone_else" in (repo / "processing/lakes_in.json").read_text(encoding="utf-8")


def _rewrite_manifest(out, change):
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    change(manifest)
    (out / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


@pytest.mark.parametrize("tamper", ["extra_file", "outside_path", "bad_checksum", "missing_lakes_in"])
def test_unpack_refuses_a_tampered_artifact(tmp_path, tamper):
    repo, out, _ = rebuilt(tmp_path)
    if tamper == "extra_file":
        (out / ".github").mkdir()
        (out / ".github/evil.yml").write_text("x", encoding="utf-8")
    elif tamper == "outside_path":
        (out / ".github").mkdir()
        (out / ".github/evil.yml").write_text("x", encoding="utf-8")
        _rewrite_manifest(out, lambda m: m["files"].update({".github/evil.yml": data_artifact.sha256(
            out / ".github/evil.yml")}))
    elif tamper == "bad_checksum":
        (out / "app/public/data/lakes.json").write_text("{}", encoding="utf-8")
    else:
        (out / "processing/lakes_in.json").unlink()
        _rewrite_manifest(out, lambda m: m["files"].pop("processing/lakes_in.json"))
    snapshot = git("status", "--porcelain", cwd=repo)
    with pytest.raises(data_artifact.Refused) as e:
        data_artifact.unpack(repo, out)
    assert e.value.code == 2
    assert git("status", "--porcelain", cwd=repo) == snapshot, "nothing was written"
    assert not (repo / ".github").exists()


def test_unpack_refuses_symlinks(tmp_path):
    repo, out, _ = rebuilt(tmp_path)
    link = out / "app/public/data/lakes/lake/link.webp"
    try:
        link.symlink_to(out / "manifest.json")
    except OSError:
        pytest.skip("this system cannot make symlinks")
    with pytest.raises(data_artifact.Refused):
        data_artifact.unpack(repo, out)


def test_artifact_main_exit_codes(tmp_path):
    repo, out, _ = rebuilt(tmp_path)
    (out / "app/public/data/lakes.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        data_artifact.main(["unpack", "--repo", str(repo), "--from", str(out)])
    assert e.value.code == 2


waiting = load_script("waiting")


@pytest.mark.parametrize("found,expected", [
    (issue(7, labels=("lake-request", "searched", "accepted")), "yes"),
    (issue(7, labels=("lake-request", "searched")), "no"),
    (issue(7, "closed", labels=("lake-request", "accepted")), "no"),
    (issue(7, labels=("accepted",)), "no"),
    (issue(8, labels=("lake-request", "accepted")), "no"),
])
def test_waiting(tmp_path, capsys, found, expected):
    path = tmp_path / "issues.json"
    path.write_text(json.dumps([found]), encoding="utf-8")
    waiting.main([str(path), "7"])
    assert capsys.readouterr().out == expected + "\n"


next_accept = load_script("next_accept")


def feed_of(**states):
    return {"requests": [{"issue": int(n[1:]), "state": st} for n, st in states.items()]}


def test_next_accept_lists_open_accepted_requests_only():
    gh = FakeGh(json.dumps([issue(3, labels=("lake-request", "accepted"))]) + json.dumps([{"pull_request": {},
                **issue(4, labels=("lake-request", "accepted"))}, dict(issue(5), number="5")]))
    assert [i["number"] for i in next_accept.waiting_issues("o/r", runner=gh)] == [3]
    (call,) = gh.calls
    assert call == ["api", "--paginate", "repos/o/r/issues?labels=lake-request,accepted&state=open&per_page=100"]


@pytest.mark.parametrize("issues,feed,exclude,expected", [
    ([issue(9, labels=("lake-request", "searched", "accepted")),
      issue(4, labels=("lake-request", "too few passes", "accepted"))],
     feed_of(n9="searched", n4="too_few_passes"), None, "4"),                  # the lowest number
    ([issue(4, labels=("lake-request", "searched", "accepted")),
      issue(9, labels=("lake-request", "searched", "accepted"))],
     feed_of(n4="searched", n9="searched"), 4, "9"),                            # not the one just handled
    ([issue(4, labels=("lake-request", "searched", "accepted", "rebuild failed"))],
     feed_of(n4="searched"), None, "none"),                                     # failed: the team re-adds it
    ([issue(4, labels=("lake-request", "accepted"))], feed_of(n4="accepted"), None, "none"),   # done already
    ([issue(4, labels=("lake-request", "accepted"))], feed_of(n4="invalid"), None, "none"),    # not checked
    ([issue(4, labels=("lake-request", "accepted"))], feed_of(), None, "none"),                # never checked
    ([issue(4, "closed", labels=("lake-request", "accepted"))], feed_of(n4="searched"), None, "none"),
])
def test_next_accept_main(tmp_path, monkeypatch, capsys, issues, feed, exclude, expected):
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    path = tmp_path / "requests.json"
    path.write_text(json.dumps(feed), encoding="utf-8")
    argv = ["--feed", str(path)] + (["--exclude", str(exclude)] if exclude else [])
    next_accept.main(argv, runner=FakeGh(json.dumps(issues)))
    assert capsys.readouterr().out == expected + "\n"


def test_next_accept_without_a_feed_starts_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    waiting_one = [issue(4, labels=("lake-request", "searched", "accepted"))]
    next_accept.main(["--feed", str(tmp_path / "missing.json")], runner=FakeGh(json.dumps(waiting_one)))
    assert capsys.readouterr().out == "none\n"


def test_next_accept_refuses_a_non_numeric_exclude(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    with pytest.raises(SystemExit):
        next_accept.main(["--feed", str(tmp_path / "f.json"), "--exclude", "4; rm"], runner=FakeGh("[]"))


busy = load_script("busy")


def run_entry(number, status):
    return {"databaseId": number, "status": status}


@pytest.mark.parametrize("accept,refresh,expected", [
    ([], [], "idle"),
    ([run_entry(1, "completed")], [run_entry(2, "completed")], "idle"),
    ([run_entry(500, "in_progress")], [], "idle"),                               # this run itself
    ([run_entry(500, "in_progress"), run_entry(7, "queued")], [], "busy"),
    ([], [run_entry(8, "in_progress")], "busy"),
    ([], [run_entry(8, "waiting")], "busy"),
    ([], [run_entry(8, "requested")], "busy"),
    ([run_entry(8, "pending")], [], "busy"),
    ("not json", [], "busy"),                                                    # unreadable: fail safe
    ({"databaseId": 1}, [], "busy"),                                             # not a list
    ([{"databaseId": "8", "status": "completed"}], [], "busy"),                 # no integer id
])
def test_busy(tmp_path, monkeypatch, capsys, accept, refresh, expected):
    monkeypatch.setenv("GITHUB_RUN_ID", "500")
    paths = []
    for name, value in (("a.json", accept), ("r.json", refresh)):
        (tmp_path / name).write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")
        paths.append(str(tmp_path / name))
    busy.main(paths)
    assert capsys.readouterr().out == expected + "\n"


def test_busy_without_lists_or_files_is_busy(tmp_path, capsys):
    busy.main([])
    busy.main([str(tmp_path / "missing.json")])
    assert capsys.readouterr().out == "busy\nbusy\n"


# ---- shell scripts, run with a fake `gh` on PATH ---------------------------------------------

def find_bash():
    if sys.platform != "win32":
        return shutil.which("bash")
    git_bash = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe"
    return str(git_bash) if git_bash.is_file() else None  # never WSL's System32 bash


BASH = find_bash()
needs_bash = pytest.mark.skipif(BASH is None, reason="no bash")

FAKE_GH = """#!/usr/bin/env bash
# records each call (one argument per line, calls separated by ---) and copies --body-file contents
{ for a in "$@"; do printf '%s\\n' "$a"; done; echo ---; } >> "$GH_LOG"
prev=""
for a in "$@"; do
  if [ "$prev" = "--body-file" ]; then cat "$a" >> "$GH_BODIES"; echo "===" >> "$GH_BODIES"; fi
  prev="$a"
done
if [ "$1 $2" = "issue view" ] && [ -f "${GH_LABELS:-}" ]; then cat "$GH_LABELS"; fi
if [ "$1 $2" = "workflow run" ] && [ -n "${GH_FAIL_WORKFLOW:-}" ]; then exit 1; fi
if [ "$1 $2" = "run list" ] && [ -n "${GH_FAIL_RUNS:-}" ]; then exit 1; fi
if [ "$1 $2" = "run list" ]; then
  if [ -n "${GH_RUNS:-}" ]; then cat "$GH_RUNS"; else echo "[]"; fi
fi
exit 0
"""


def fake_env(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_bytes(FAKE_GH.encode())
    gh.chmod(0o755)
    if sys.platform == "win32":  # runners have python3; Windows has only a Store alias by that name
        exe = Path(sys.executable).as_posix()
        (bin_dir / "python3").write_bytes(f'#!/usr/bin/env bash\nexec "{exe}" "$@"\n'.encode())
    env = dict(os.environ)
    env.pop("GH_TOKEN", None)
    env["GH_LOG"], env["GH_BODIES"] = str(tmp_path / "gh.log"), str(tmp_path / "bodies.txt")
    env["FAKE_BIN"] = str(bin_dir)
    env["GITHUB_REPOSITORY"] = "o/r"
    env.pop("GITHUB_STEP_SUMMARY", None)
    return env


def bash(script, args, env, cwd):
    # prepend the fake gh inside bash so Windows path conversion does not get in the way
    cmd = 'export PATH="$(cd "$FAKE_BIN" && pwd):$PATH"; exec bash "$0" "$@"'
    return subprocess.run([BASH, "-c", cmd, str(script), *args], env=env, cwd=cwd,
                          capture_output=True, text=True, encoding="utf-8")


def gh_calls(env):
    log = Path(env["GH_LOG"])
    if not log.exists():
        return []
    return [c.strip("\n").split("\n") for c in log.read_text(encoding="utf-8").split("---\n") if c.strip()]


def act(number, comment=None, add=(), remove=(), close=False, dispatch=False):
    return {"issue": number, "comment": comment, "add": list(add), "remove": list(remove), "close": close,
            "dispatch": dispatch}


def write_actions(tmp_path, actions):
    path = tmp_path / "actions.json"
    path.write_text(json.dumps(actions), encoding="utf-8")
    return path


@needs_bash
def test_apply_actions_posts_comment_from_file_and_sets_labels(tmp_path):
    env = fake_env(tmp_path)
    (tmp_path / "labels.txt").write_bytes(b"lake-request\ntoo few passes\n")
    env["GH_LABELS"] = str(tmp_path / "labels.txt")
    nasty = "Checked $(touch pwned) `touch pwned2` \"quote\" ; rm -rf / 'x'"
    actions = write_actions(tmp_path, [act(12, nasty, ["searched"], ["too few passes", "invalid"])])
    r = bash(SCRIPTS / "apply-actions.sh", [str(actions)], env, tmp_path)
    assert r.returncode == 0, r.stderr
    assert not (tmp_path / "pwned").exists() and not (tmp_path / "pwned2").exists()
    assert Path(env["GH_BODIES"]).read_text(encoding="utf-8") == nasty + "===\n"  # the exact text, nothing run
    calls = gh_calls(env)
    assert ["issue", "comment", "12", "--body-file"] == calls[0][:4]
    assert ["issue", "edit", "12", "--add-label", "searched"] in calls
    assert ["issue", "edit", "12", "--remove-label", "too few passes"] in calls
    assert not any("invalid" in c for c in calls), "labels not on the issue are not removed"
    assert not any(c[:2] == ["issue", "close"] for c in calls)
    assert not any(c[:2] == ["workflow", "run"] for c in calls)


@needs_bash
def test_apply_actions_loops_over_every_issue(tmp_path):
    env = fake_env(tmp_path)
    actions = write_actions(tmp_path, [act(3, None, ["invalid"], close=True), act(4, "Two"), act(9, dispatch=True),
                                       act(10, "Accepted.", close=True)])
    r = bash(SCRIPTS / "apply-actions.sh", [str(actions)], env, tmp_path)
    assert r.returncode == 0, r.stderr
    calls = gh_calls(env)
    assert ["issue", "close", "3", "--reason", "not planned"] in calls
    assert [c[2] for c in calls if c[:2] == ["issue", "comment"]] == ["4", "10"]
    assert ["workflow", "run", "lake-accept.yml", "--ref", "main", "-f", "issue=9"] in calls
    assert ["issue", "close", "10"] in calls
    assert Path(env["GH_BODIES"]).read_text(encoding="utf-8") == "Two===\nAccepted.===\n"
    assert ["run", "list", "--repo", "o/r", "--workflow", "lake-accept.yml", "--json", "databaseId,status",
            "--limit", "100"] in calls, "it asked for active runs first"


@needs_bash
@pytest.mark.parametrize("runs,fail,expected", [
    ("[]", False, "idle"),
    ('[{"databaseId": 41, "status": "completed"}]', False, "idle"),
    ('[{"databaseId": 42, "status": "queued"}]', False, "busy"),
    ('[{"databaseId": 41, "status": "in_progress"}]', False, "idle"),   # GITHUB_RUN_ID: this run
    ("$(touch pwned)", False, "busy"),                                   # not JSON, and never run
    ("[]", True, "busy"),                                                # lookup failed: fail safe
])
def test_busy_sh(tmp_path, runs, fail, expected):
    env = fake_env(tmp_path)
    (tmp_path / "runs.json").write_text(runs, encoding="utf-8")
    env["GH_RUNS"], env["GITHUB_RUN_ID"] = str(tmp_path / "runs.json"), "41"
    if fail:
        env["GH_FAIL_RUNS"] = "1"
    r = bash(SCRIPTS / "busy.sh", [], env, tmp_path)
    assert r.returncode == 0, r.stderr
    assert r.stdout == expected + "\n"
    assert not (tmp_path / "pwned").exists()
    calls = gh_calls(env)
    asked = [c[c.index("--workflow") + 1] for c in calls]
    assert asked == (["lake-accept.yml"] if fail else ["lake-accept.yml", "refresh.yml"])
    assert all(c[:4] == ["run", "list", "--repo", "o/r"] for c in calls)


@needs_bash
@pytest.mark.parametrize("runs", ['[{"databaseId": 7, "status": "in_progress"}]', "gh: not json"])
def test_apply_actions_starts_no_accept_while_another_is_active(tmp_path, runs):
    env = fake_env(tmp_path)
    (tmp_path / "runs.json").write_text(runs, encoding="utf-8")
    env["GH_RUNS"], env["GITHUB_STEP_SUMMARY"] = str(tmp_path / "runs.json"), str(tmp_path / "summary.md")
    actions = write_actions(tmp_path, [act(9, "Checked.", dispatch=True)])
    r = bash(SCRIPTS / "apply-actions.sh", [str(actions)], env, tmp_path)
    assert r.returncode == 0, r.stderr
    calls = gh_calls(env)
    assert not any(c[:2] == ["workflow", "run"] for c in calls)
    assert [c[2] for c in calls if c[:2] == ["issue", "comment"]] == ["9"], "the rest is still applied"
    assert "the accept for issue #9 was not started" in (tmp_path / "summary.md").read_text(encoding="utf-8")


@needs_bash
def test_apply_actions_empty_list_does_nothing(tmp_path):
    env = fake_env(tmp_path)
    r = bash(SCRIPTS / "apply-actions.sh", [str(write_actions(tmp_path, []))], env, tmp_path)
    assert r.returncode == 0, r.stderr
    assert gh_calls(env) == []


@pytest.mark.parametrize("bad", [
    [act(3, add=["x; rm -rf /"])],
    [act(3, remove=["nope"])],
    [dict(act(3), issue="3; rm -rf /")],
    [dict(act(3), issue=-1)],
    [dict(act(3), issue=True)],
    {"comment": "old shape", "add": [], "remove": [], "close": False},
])
@needs_bash
def test_apply_actions_refuses_bad_input_before_any_call(tmp_path, bad):
    env = fake_env(tmp_path)
    r = bash(SCRIPTS / "apply-actions.sh", [str(write_actions(tmp_path, [act(2, "first")] + bad
                                                              if isinstance(bad, list) else bad))],
             env, tmp_path)
    assert r.returncode != 0
    assert gh_calls(env) == [], "nothing is applied when any entry is bad"


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def make_clone(tmp_path):
    origin = tmp_path / "origin.git"
    git("init", "--bare", "-b", "main", str(origin), cwd=tmp_path)
    work = tmp_path / "work"
    git("clone", str(origin), str(work), cwd=tmp_path)
    git("config", "user.name", "someone", cwd=work)
    git("config", "user.email", "someone@example.com", cwd=work)
    git("config", "core.autocrlf", "false", cwd=work)
    (work / "data").mkdir()
    (work / "data" / "a.json").write_text("1\n", encoding="utf-8")
    git("add", ".", cwd=work)
    git("commit", "-m", "start", cwd=work)
    git("push", "origin", "HEAD:main", cwd=work)
    return origin, work


@needs_bash
def test_commit_data_commits_pushes_and_starts_deploy(tmp_path):
    env = fake_env(tmp_path)
    env["GITHUB_OUTPUT"] = str(tmp_path / "out.txt")
    env["GH_TOKEN"] = "not-a-real-token"
    origin, work = make_clone(tmp_path)
    (work / "data" / "a.json").write_text("2\n", encoding="utf-8")
    (work / "other.txt").write_text("not mine\n", encoding="utf-8")
    r = bash(SCRIPTS / "commit-data.sh", ["Update lake requests", "data"], env, work)
    assert r.returncode == 0, r.stderr + r.stdout
    log = git("log", "-1", "--format=%an <%ae>%n%B", "main", cwd=origin)
    assert log.startswith("github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>")
    assert "Update lake requests" in log and "Co-Authored-By" not in log
    assert git("show", "main:data/a.json", cwd=origin) == "2\n"
    assert "other.txt" not in git("ls-tree", "-r", "--name-only", "main", cwd=origin)
    assert ["workflow", "run", "deploy.yml", "--ref", "main"] in gh_calls(env)
    assert Path(env["GITHUB_OUTPUT"]).read_text(encoding="utf-8") == "pushed=true\n"
    config = git("config", "--list", "--show-origin", cwd=work)
    assert "not-a-real-token" not in config and "extraheader" not in config, "the credential is never stored"
    assert "not-a-real-token" not in r.stdout + r.stderr


@needs_bash
def test_commit_data_reports_a_deploy_that_did_not_start(tmp_path):
    env = fake_env(tmp_path)
    env["GITHUB_OUTPUT"] = str(tmp_path / "out.txt")
    env["GH_FAIL_WORKFLOW"] = "1"
    origin, work = make_clone(tmp_path)
    (work / "data" / "a.json").write_text("5\n", encoding="utf-8")
    r = bash(SCRIPTS / "commit-data.sh", ["Update lake requests", "data"], env, work)
    assert r.returncode == 1
    assert git("show", "main:data/a.json", cwd=origin) == "5\n"
    assert Path(env["GITHUB_OUTPUT"]).read_text(encoding="utf-8") == "pushed=true\ndeploy_failed=true\n"


@needs_bash
def test_commit_data_rebases_on_newer_main(tmp_path):
    env = fake_env(tmp_path)
    origin, work = make_clone(tmp_path)
    other = tmp_path / "other"
    git("clone", str(origin), str(other), cwd=tmp_path)
    git("config", "user.name", "x", cwd=other)
    git("config", "user.email", "x@example.com", cwd=other)
    (other / "README").write_text("hi\n", encoding="utf-8")
    git("add", ".", cwd=other)
    git("commit", "-m", "someone else", cwd=other)
    git("push", "origin", "HEAD:main", cwd=other)
    (work / "data" / "a.json").write_text("3\n", encoding="utf-8")
    r = bash(SCRIPTS / "commit-data.sh", ["Weekly data refresh", "data"], env, work)
    assert r.returncode == 0, r.stderr + r.stdout
    subjects = git("log", "--format=%s", "main", cwd=origin).splitlines()
    assert subjects == ["Weekly data refresh", "someone else", "start"]


@needs_bash
def test_commit_data_without_changes_does_nothing(tmp_path):
    env = fake_env(tmp_path)
    origin, work = make_clone(tmp_path)
    before = git("rev-parse", "main", cwd=origin)
    r = bash(SCRIPTS / "commit-data.sh", ["Update lake requests", "data"], env, work)
    assert r.returncode == 0, r.stderr
    assert git("rev-parse", "main", cwd=origin) == before
    assert gh_calls(env) == []


@needs_bash
def test_commit_data_fails_after_three_push_attempts(tmp_path):
    env = fake_env(tmp_path)
    env["COMMIT_DATA_WAIT"] = "0"
    origin, work = make_clone(tmp_path)
    git("remote", "set-url", "origin", str(tmp_path / "missing.git"), cwd=work)
    (work / "data" / "a.json").write_text("4\n", encoding="utf-8")
    r = bash(SCRIPTS / "commit-data.sh", ["Update lake requests", "data"], env, work)
    assert r.returncode == 1
    assert r.stderr.count("push attempt") == 3
    assert gh_calls(env) == []


def artifact_for(work: Path, art: Path) -> Path:
    """A rebuild artifact whose manifest records the inputs of `work`'s HEAD, as pack would."""
    for rel in (data_artifact.LAKES_IN, data_artifact.LAKES_JSON):
        (art / rel).parent.mkdir(parents=True, exist_ok=True)
        (art / rel).write_text("{}\n", encoding="utf-8")
    manifest = {"version": 1,
                "base": {p: data_artifact.git_object(work, p) for p in data_artifact.BASE},
                "science": {p: data_artifact.git_object(work, p) for p in data_artifact.SCIENCE},
                "files": {rel: data_artifact.sha256(art / rel)
                          for rel in (data_artifact.LAKES_IN, data_artifact.LAKES_JSON)}}
    (art / data_artifact.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    return art


def push_from_other(tmp_path, origin, rel, text):
    other = tmp_path / "other"
    git("clone", str(origin), str(other), cwd=tmp_path)
    git("config", "user.name", "x", cwd=other)
    git("config", "user.email", "x@example.com", cwd=other)
    (other / rel).parent.mkdir(parents=True, exist_ok=True)
    (other / rel).write_text(text, encoding="utf-8")
    git("add", ".", cwd=other)
    git("commit", "-m", f"change {rel}", cwd=other)
    git("push", "origin", "HEAD:main", cwd=other)


@needs_bash
@pytest.mark.parametrize("rel", ["processing/sartale/config.py", "processing/lakes_in.json",
                                 ".github/actions/rebuild/action.yml"])
def test_commit_data_refuses_when_main_changed_the_inputs_before_the_push(tmp_path, rel):
    """M4: unpack checked the inputs against the publish checkout; a push of method code or data before our push
    is caught after the rebase, and nothing is pushed (exit 6, stale)."""
    env = fake_env(tmp_path)
    origin, work = make_clone(tmp_path)
    env["DATA_ARTIFACT"] = str(artifact_for(work, tmp_path / "lake-data"))
    push_from_other(tmp_path, origin, rel, "changed\n")
    before = git("rev-parse", "main", cwd=origin)
    (work / "data" / "a.json").write_text("6\n", encoding="utf-8")
    r = bash(SCRIPTS / "commit-data.sh", ["Weekly data refresh", "data"], env, work)
    assert r.returncode == 6, r.stderr + r.stdout
    assert "nothing was pushed" in r.stderr
    assert git("rev-parse", "main", cwd=origin) == before
    assert gh_calls(env) == [], "no deploy"


@needs_bash
def test_commit_data_pushes_when_main_changed_only_other_files(tmp_path):
    env = fake_env(tmp_path)
    origin, work = make_clone(tmp_path)
    env["DATA_ARTIFACT"] = str(artifact_for(work, tmp_path / "lake-data"))
    push_from_other(tmp_path, origin, "docs/guide/pages/faq.html", "<p>new</p>\n")
    (work / "data" / "a.json").write_text("7\n", encoding="utf-8")
    r = bash(SCRIPTS / "commit-data.sh", ["Weekly data refresh", "data"], env, work)
    assert r.returncode == 0, r.stderr + r.stdout
    assert git("show", "main:data/a.json", cwd=origin) == "7\n"


def test_verify_compares_the_inputs_at_the_given_commit(tmp_path):
    origin, work = make_clone(tmp_path)
    art = artifact_for(work, tmp_path / "lake-data")
    data_artifact.verify(work, art, "HEAD")
    (work / "environment.yml").write_text("name: x\n", encoding="utf-8")
    git("add", ".", cwd=work)
    git("commit", "-m", "env", cwd=work)
    with pytest.raises(data_artifact.Refused) as e:
        data_artifact.verify(work, art, "HEAD")
    assert e.value.code == 6 and "environment.yml" in str(e.value)
    data_artifact.verify(work, art, "HEAD~1")


@needs_bash
def test_every_run_block_is_valid_bash():
    import re

    import yaml

    files = sorted((ROOT / ".github" / "workflows").glob("*.yml")) + [ROOT / ".github/actions/rebuild/action.yml"]
    for f in files:
        doc = yaml.safe_load(f.read_text(encoding="utf-8"))
        jobs = doc.get("jobs") or {"composite": {"steps": doc["runs"]["steps"]}}
        for job_name, job in jobs.items():
            for s in job.get("steps", []):
                if s.get("run"):
                    script = re.sub(r"\$\{\{.*?\}\}", "X", s["run"])
                    r = subprocess.run([BASH, "-n"], input=script, capture_output=True, text=True)
                    assert r.returncode == 0, f"{f.name}:{job_name}:{s.get('name')}: {r.stderr}"


def test_the_accept_comment_has_one_wording():
    from sartale import lake_issues

    assert data_artifact.ACCEPTED_COMMENT == lake_issues.ACCEPTED_COMMENT
    assert data_artifact.SITE == lake_issues.SITE_LAKE


# --- W01: the live re-check just before an accepted lake is published --------------------------------------------

live_approval = load_script("live_approval")
BODY = ("### Lake name\n\nNew pond\n\n### Latitude (°N)\n\n36.2\n\n### Longitude (°E)\n\n74.1 °E\n\n"
        "### Where the coordinates come from\n\nA survey, 2026\n")
APPROVED_AT = "2026-11-05T11:00:00Z"


def live_gh(body=BODY, state="open", labels=("lake-request", "searched", "accepted"),
            events=(labeled("accepted", "owner-1", APPROVED_AT),), permissions=None):
    return FakeGh("", single=issue(7, state=state, labels=labels, body=body), events=list(events),
                  permissions=permissions)


def built_hash(body=BODY):
    from sartale.lake_issues import issue_values_sha256
    return issue_values_sha256({"body": body})


def test_live_hash_rule_matches_the_pipeline():
    from sartale.lake_issues import issue_values_sha256
    bodies = [BODY, BODY.replace("36.2", "36.20"), BODY.replace("74.1 °E", "74.1"), BODY.replace("New pond", "  New pond  "),
              BODY.replace("36.2", "3.6e1"), BODY.replace("New pond", "N"), BODY.replace("New pond", "New​pond"),
              BODY.replace("### Lake name", "### Name"), BODY.replace("A survey, 2026", "_No response_"), "", "\r\n".join(BODY.split("\n"))]
    for b in bodies:
        assert live_approval.issue_values_sha256({"body": b}) == issue_values_sha256({"body": b}), b


def test_live_recheck_passes_when_nothing_changed():
    assert live_approval.recheck("o/r", 7, "owner-1", APPROVED_AT, built_hash(), runner=live_gh()) is None
    # a label event's recorded time may be the issue's update time a few seconds off the event itself
    assert live_approval.recheck("o/r", 7, "owner-1", "2026-11-05T11:00:03Z", built_hash(), runner=live_gh()) is None


def test_live_recheck_refuses_a_revoked_approval():
    gh = live_gh(labels=("lake-request", "searched"))
    assert live_approval.recheck("o/r", 7, "owner-1", APPROVED_AT, built_hash(), runner=gh) == live_approval.NOT_OPEN


def test_live_recheck_refuses_a_closed_issue():
    gh = live_gh(state="closed")
    assert live_approval.recheck("o/r", 7, "owner-1", APPROVED_AT, built_hash(), runner=gh) == live_approval.NOT_OPEN


def test_live_recheck_refuses_edited_values():
    gh = live_gh(body=BODY.replace("74.1 °E", "74.2 °E"))
    assert live_approval.recheck("o/r", 7, "owner-1", APPROVED_AT, built_hash(), runner=gh) == live_approval.EDITED


@pytest.mark.parametrize("events", [
    [labeled("accepted", "owner-1", APPROVED_AT), labeled("accepted", "owner-2", "2026-11-05T12:00:00Z")],  # someone else
    [labeled("accepted", "owner-1", "2026-11-05T13:00:00Z")],   # removed and added again later
    [],                                                         # no approval event
])
def test_live_recheck_refuses_an_approver_or_time_change(events):
    gh = live_gh(events=events)
    assert live_approval.recheck("o/r", 7, "owner-1", APPROVED_AT, built_hash(), runner=gh) == live_approval.OTHER_APPROVAL


@pytest.mark.parametrize("perm", ["read", "triage", "none"])
def test_live_recheck_refuses_an_approver_who_lost_write_access(perm):
    """M2: the approver was a team member at the gate but was demoted during the rebuild."""
    gh = live_gh(permissions={"owner-1": perm})
    assert live_approval.recheck("o/r", 7, "owner-1", APPROVED_AT, built_hash(), runner=gh) == live_approval.NOT_TEAM
    assert ["api", "repos/o/r/collaborators/owner-1/permission"] in gh.calls


@pytest.mark.parametrize("perm", ["admin", "maintain", "write"])
def test_live_recheck_keeps_an_approver_with_write_access(perm):
    gh = live_gh(permissions={"owner-1": perm})
    assert live_approval.recheck("o/r", 7, "owner-1", APPROVED_AT, built_hash(), runner=gh) is None


def test_live_recheck_fails_closed_when_the_permission_lookup_fails():
    gh = live_gh()

    def broken(args):
        if "/collaborators/" in args[1]:
            raise RuntimeError("gh api failed")
        return gh(args)

    with pytest.raises(RuntimeError):
        live_approval.recheck("o/r", 7, "owner-1", APPROVED_AT, built_hash(), runner=broken)


def test_live_main_writes_the_reason_and_exits_7(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    art = tmp_path / "lake-data" / "app" / "public" / "data"
    art.mkdir(parents=True)
    (art / "requests.json").write_text(json.dumps({"requests": [{"issue": 7, "values_sha256": built_hash()}]}), "utf-8")
    why = tmp_path / "why.md"
    args = ["--issue", "7", "--approver", "owner-1", "--approved-at", APPROVED_AT, "--from", str(tmp_path / "lake-data"),
            "--why", str(why)]
    live_approval.main(args, runner=live_gh())
    assert not why.exists()
    with pytest.raises(SystemExit) as e:
        live_approval.main(args, runner=live_gh(body=BODY.replace("New pond", "Other pond")))
    assert e.value.code == 8 and why.read_text("utf-8").strip() == live_approval.EDITED  # void: drop accepted
    assert "Other pond" not in why.read_text("utf-8")
    with pytest.raises(SystemExit) as e:
        live_approval.main(args, runner=live_gh(permissions={"owner-1": "read"}))
    assert e.value.code == 8 and why.read_text("utf-8").strip() == live_approval.NOT_TEAM
    with pytest.raises(SystemExit) as e:
        live_approval.main(args, runner=live_gh(state="closed"))
    assert e.value.code == 7 and why.read_text("utf-8").strip() == live_approval.NOT_OPEN  # nothing to remove


def test_accept_workflow_rechecks_live_before_it_commits():
    import yaml
    wf = yaml.safe_load((SCRIPTS.parents[0] / "workflows" / "lake-accept.yml").read_text(encoding="utf-8"))
    steps = wf["jobs"]["publish"]["steps"]
    names = [s.get("name", "") for s in steps]
    live = names.index("Re-read the issue live just before publishing")
    commit = names.index("Commit the new lake and start the deploy")
    assert live < commit
    assert "steps.live.outputs.result == 'ok'" in steps[commit]["if"]
    assert "steps.live.outputs.result == 'ok'" in steps[names.index("Comment and close the issue")]["if"]
    assert "live_approval.py" in steps[live]["run"]
    # M3: a void approval (exit 8: edited, or the approver lost access) also loses `accepted`, as the changed path does
    run = steps[live]["run"]
    eight = run.index("8) ")
    assert "--remove-label accepted" in run[eight:] and "--remove-label accepted" not in run[:eight]
    assert "result=withdrawn" in run[eight:]
    assert wf["jobs"]["gate"]["outputs"]["approver"]



@pytest.mark.parametrize("path, text", [
    ("processing/sartale/config.py", "DROP_DB = 2.5\n"),          # a method constant changed
    ("processing/sartale/lakewater.py", "# new rule\n"),           # method code added
    ("processing/outlines/a.geojson", '{"type": "Polygon"}\n'),    # an outline changed
    ("environment.yml", "name: sartale\ndependencies: [numpy]\n"),
    ("processing/lake_checks.json", "[]\n"),                       # check rows the build merges in
])
def test_w02_unpack_refuses_data_built_with_other_method_inputs(tmp_path, path, text):
    repo, out, _ = rebuilt(tmp_path)
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text(text, encoding="utf-8")
    git("add", ".", cwd=repo)
    git("commit", "-q", "-m", "method fix", cwd=repo)
    with pytest.raises(data_artifact.Refused) as e:
        data_artifact.unpack(repo, out)
    assert e.value.code == 6 and "another" in str(e.value)


def test_w02_unpack_refuses_a_manifest_without_the_method_identity(tmp_path):
    repo, out, _ = rebuilt(tmp_path)
    _rewrite_manifest(out, lambda m: m.pop("science"))
    with pytest.raises(data_artifact.Refused) as e:
        data_artifact.unpack(repo, out)
    assert e.value.code == 2


def test_w02_a_change_outside_the_science_still_publishes(tmp_path):
    repo, out, _ = rebuilt(tmp_path)
    (repo / "README.md").write_text("changed\n", encoding="utf-8")
    git("commit", "-q", "-am", "docs", cwd=repo)
    data_artifact.unpack(repo, out)
