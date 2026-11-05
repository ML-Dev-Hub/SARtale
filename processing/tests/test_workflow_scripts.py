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

    def __init__(self, pages, comments=None, single=None, events=None):
        self.pages, self.comments, self.calls = pages, comments or {}, []
        self.single, self.events = single, events or []

    def __call__(self, args):
        assert isinstance(args, list) and all(isinstance(a, str) for a in args)
        self.calls.append(args)
        assert args[0] == "api"
        path = next(a for a in args[1:] if not a.startswith("-"))
        if "/comments" in path:
            number = int(path.split("/issues/")[1].split("/")[0])
            return json.dumps(self.comments.get(number, []))
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


def labeled(name, login):
    return {"event": "labeled", "label": {"name": name}, "actor": {"login": login}}


def test_approver_is_last_to_add_accepted():
    events = [labeled("accepted", "early"), labeled("lake-request", "visitor"),
              {"event": "unlabeled", "label": {"name": "accepted"}, "actor": {"login": "bot"}},
              labeled("accepted", "owner-1"), labeled("searched", "github-actions[bot]")]
    gh = FakeGh("", single=issue(7, labels=("lake-request", "searched", "accepted")), events=events)
    assert approver.approver("o/r", 7, runner=gh) == "owner-1"
    paths = [next(a for a in c[1:] if not a.startswith("-")) for c in gh.calls]
    assert paths == ["repos/o/r/issues/7", "repos/o/r/issues/7/events?per_page=100"]
    assert "--paginate" in gh.calls[1]


@pytest.mark.parametrize("single", [
    issue(7, labels=("lake-request", "searched")),                  # label removed since
    issue(7, "closed", labels=("lake-request", "accepted")),        # closed since
    issue(7, labels=("accepted",)),                                 # not a request
])
def test_no_approver_when_the_issue_is_no_longer_waiting(single):
    gh = FakeGh("", single=single, events=[labeled("accepted", "owner")])
    assert approver.approver("o/r", 7, runner=gh) is None


def test_no_approver_without_event_or_with_odd_login():
    single = issue(7, labels=("lake-request", "accepted"))
    assert approver.approver("o/r", 7, runner=FakeGh("", single=single, events=[])) is None
    odd = [labeled("accepted", "a/../b")]
    assert approver.approver("o/r", 7, runner=FakeGh("", single=single, events=odd)) is None


def test_approver_main_exit_codes(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    good = FakeGh("", single=issue(7, labels=("lake-request", "accepted")), events=[labeled("accepted", "boss")])
    approver.main(["--issue", "7"], runner=good)
    assert capsys.readouterr().out == "boss\n"
    with pytest.raises(SystemExit) as e:
        approver.main(["--issue", "7"], runner=FakeGh("", single=issue(7), events=[]))
    assert e.value.code == 3


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
