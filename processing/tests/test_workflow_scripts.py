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
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = before
    return module


fetch_issues = load_script("fetch_issues")
json_changed = load_script("json_changed")


def issue(number, state="open", labels=("lake-request",), **extra):
    return {"number": number, "title": f"Add a lake: {number}", "body": "b", "state": state,
            "labels": [{"name": n} for n in labels], "created_at": "2026-11-03T10:00:00Z",
            "user": {"login": "visitor"}, "author_association": "NONE", **extra}


class FakeGh:
    """Answers `gh api ...` calls from a table of paths; records every call."""

    def __init__(self, pages, comments=None):
        self.pages, self.comments, self.calls = pages, comments or {}, []

    def __call__(self, args):
        assert isinstance(args, list) and all(isinstance(a, str) for a in args)
        self.calls.append(args)
        assert args[0] == "api"
        path = next(a for a in args[1:] if not a.startswith("-"))
        if "/comments" in path:
            number = int(path.split("/issues/")[1].split("/")[0])
            return json.dumps(self.comments.get(number, []))
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
    comments = {4: [
        {"body": "team first", "author_association": "OWNER"},
        {"body": "visitor says", "author_association": "NONE"},
        {"body": "team last", "author_association": "MEMBER"},
        {"body": "visitor again", "author_association": "CONTRIBUTOR"},
    ], 6: [{"body": "only visitor", "author_association": "NONE"}],
        7: [{"body": "collab", "author_association": "COLLABORATOR"}]}
    pages = json.dumps([issue(4, "closed"), issue(6, "closed"), issue(7, "closed"),
                        issue(8, "closed", ("lake-request", "accepted")),
                        issue(9, "closed", ("lake-request", "invalid"))])
    gh = FakeGh(pages, comments)
    got = {i["number"]: i["close_reason"] for i in fetch_issues.fetch("o/r", runner=gh)}
    assert got == {4: "team last", 6: None, 7: "collab", 8: None, 9: None}
    looked_up = [c for c in gh.calls if any("/comments" in a for a in c)]
    assert len(looked_up) == 3, "accepted and invalid issues need no reason"
    assert all("--paginate" in c for c in looked_up)


def test_unconfirmed_accepted_label_is_dropped():
    feed = {"requests": [{"issue": 1, "state": "accepted"}, {"issue": 2, "state": "searched"}]}
    pages = json.dumps([issue(1, labels=("lake-request", "accepted")),
                        issue(2, labels=("lake-request", "accepted")),
                        issue(3, labels=("lake-request", "accepted", "searched"))])
    got = {i["number"]: [lb["name"] for lb in i["labels"]]
           for i in fetch_issues.fetch("o/r", runner=FakeGh(pages), confirmed_from=feed)}
    assert got == {1: ["lake-request", "accepted"], 2: ["lake-request"], 3: ["lake-request", "searched"]}


def test_dropped_accept_on_closed_issue_still_gets_a_reason():
    pages = json.dumps([issue(2, "closed", ("lake-request", "accepted"))])
    gh = FakeGh(pages, {2: [{"body": "no", "author_association": "OWNER"}]})
    (got,) = fetch_issues.fetch("o/r", runner=gh, confirmed_from={"requests": []})
    assert got["close_reason"] == "no"


def test_fetch_main_writes_file(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    feed = tmp_path / "requests.json"
    feed.write_text(json.dumps({"requests": []}), encoding="utf-8")
    out = tmp_path / "issues.json"
    gh = FakeGh(json.dumps([issue(1, labels=("lake-request", "accepted"))]))
    fetch_issues.main(["--out", str(out), "--confirmed-from", str(feed)], runner=gh)
    assert json.loads(out.read_text(encoding="utf-8"))[0]["labels"] == [{"name": "lake-request"}]


def test_run_gh_uses_argument_list(monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"], seen["kw"] = cmd, kw
        return subprocess.CompletedProcess(cmd, 0, stdout="[]", stderr="")

    monkeypatch.setattr(fetch_issues.subprocess, "run", fake_run)
    assert fetch_issues.run_gh(["api", "x"]) == "[]"
    assert seen["cmd"] == ["gh", "api", "x"]
    assert not seen["kw"].get("shell") and seen["kw"].get("check") is True


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
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}" if sys.platform != "win32" else env["PATH"]
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


@needs_bash
def test_apply_actions_posts_comment_from_file_and_sets_labels(tmp_path):
    env = fake_env(tmp_path)
    (tmp_path / "labels.txt").write_bytes(b"lake-request\ntoo few passes\n")
    env["GH_LABELS"] = str(tmp_path / "labels.txt")
    nasty = "Checked $(touch pwned) `touch pwned2` \"quote\" ; rm -rf / 'x'"
    actions = tmp_path / "actions.json"
    actions.write_text(json.dumps({"comment": nasty, "add": ["searched"],
                                   "remove": ["too few passes", "invalid"], "close": False}), encoding="utf-8")
    r = bash(SCRIPTS / "apply-actions.sh", ["12", str(actions)], env, tmp_path)
    assert r.returncode == 0, r.stderr
    assert not (tmp_path / "pwned").exists() and not (tmp_path / "pwned2").exists()
    assert Path(env["GH_BODIES"]).read_text(encoding="utf-8") == nasty + "===\n"  # the exact text, nothing run
    calls = gh_calls(env)
    assert ["issue", "comment", "12", "--body-file"] == calls[0][:4]
    assert ["issue", "edit", "12", "--add-label", "searched"] in calls
    assert ["issue", "edit", "12", "--remove-label", "too few passes"] in calls
    assert not any("invalid" in c for c in calls), "labels not on the issue are not removed"
    assert not any(c[:2] == ["issue", "close"] for c in calls)


@needs_bash
def test_apply_actions_closes_and_skips_empty_comment(tmp_path):
    env = fake_env(tmp_path)
    actions = tmp_path / "actions.json"
    actions.write_text(json.dumps({"comment": None, "add": ["invalid"], "remove": [], "close": True}),
                       encoding="utf-8")
    r = bash(SCRIPTS / "apply-actions.sh", ["3", str(actions)], env, tmp_path)
    assert r.returncode == 0, r.stderr
    calls = gh_calls(env)
    assert not any(c[:2] == ["issue", "comment"] for c in calls)
    assert ["issue", "close", "3", "--reason", "not planned"] in calls


@needs_bash
def test_apply_actions_refuses_unknown_labels(tmp_path):
    env = fake_env(tmp_path)
    actions = tmp_path / "actions.json"
    actions.write_text(json.dumps({"comment": None, "add": ["x; rm -rf /"], "remove": [], "close": False}),
                       encoding="utf-8")
    r = bash(SCRIPTS / "apply-actions.sh", ["3", str(actions)], env, tmp_path)
    assert r.returncode != 0
    assert not any(c[:2] == ["issue", "edit"] for c in gh_calls(env))


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
    assert "pushed=true" in Path(env["GITHUB_OUTPUT"]).read_text(encoding="utf-8")


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
