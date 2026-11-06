"""Guards on the GitHub workflows and the lake request issue form."""

import re
from pathlib import Path

import pytest
import yaml

from sartale.lake_issues import FIELDS

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.y*ml"))
FORM = ROOT / ".github" / "ISSUE_TEMPLATE" / "add-lake.yml"

FORBIDDEN_IN_RUN = (
    "github.event.issue.title",
    "github.event.issue.body",
    "github.event.comment",
    "github.head_ref",
)


def load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def jobs_of(doc):
    return (doc.get("jobs") or {}).items()


def test_workflows_exist():
    assert WORKFLOWS, "no workflow files found"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_no_issue_text_in_run_scripts(path):
    for job_name, job in jobs_of(load(path)):
        for step in job.get("steps", []):
            bodies = [step.get("run")]
            if str(step.get("uses", "")).startswith("actions/github-script"):
                bodies.append((step.get("with") or {}).get("script"))
            for body in bodies:
                if body is None:
                    continue
                for bad in FORBIDDEN_IN_RUN:
                    assert bad not in body, f"{path.name}:{job_name} puts {bad} in a script"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_earthdata_secrets_only_in_earthdata_jobs(path):
    doc = load(path)
    for key, value in doc.items():
        if key != "jobs":
            assert "secrets.EARTHDATA_" not in yaml.safe_dump(value), (
                f"{path.name}: top-level {key!r} mentions the Earthdata secrets"
            )
    for job_name, job in jobs_of(doc):
        mentions = "secrets.EARTHDATA_" in yaml.safe_dump(job)
        env = job.get("environment")
        env_name = env.get("name") if isinstance(env, dict) else env
        if mentions:
            assert env_name == "earthdata", f"{path.name}:{job_name} needs environment earthdata"
        else:
            assert env_name != "earthdata", f"{path.name}:{job_name} has no need for earthdata"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_workflow_sets_permissions(path):  # write-all counts as setting them
    doc = load(path)
    if "permissions" in doc:
        return
    for job_name, job in jobs_of(doc):
        assert "permissions" in job, f"{path.name}:{job_name} has no permissions"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_data_jobs_share_concurrency(path):
    doc = load(path)
    top = doc.get("permissions") or {}
    for job_name, job in jobs_of(doc):
        perms = job.get("permissions", top)
        writes = perms == "write-all" or (
            isinstance(perms, dict) and perms.get("contents") == "write"
        )
        if not writes:
            continue
        conc = job.get("concurrency") or doc.get("concurrency")
        assert conc, f"{path.name}:{job_name} writes data without concurrency"
        assert conc.get("group") == "sartale-data", f"{path.name}:{job_name}"
        assert conc.get("cancel-in-progress") is False, f"{path.name}:{job_name}"


def test_issue_form_matches_parser():
    form = load(FORM)
    assert form["name"] == "Add a lake"
    assert form["title"] == "Add a lake: "
    assert form["labels"] == ["lake-request"]
    fields = [b for b in form["body"] if b["type"] != "markdown"]
    assert {b["attributes"]["label"]: b["id"] for b in fields} == FIELDS
    assert all(b["validations"]["required"] is True for b in fields)
    assert {b["id"]: b["type"] for b in fields} == {
        "name": "input", "lat": "input", "lon": "input", "source": "textarea",
    }
    assert load(FORM.parent / "config.yml")["blank_issues_enabled"] is True


def test_deploy_copies_guide_and_tests_first():
    doc = load(ROOT / ".github" / "workflows" / "deploy.yml")
    on = doc.get(True, doc.get("on"))  # PyYAML reads the key `on` as True
    assert on["push"]["branches"] == ["main"]
    assert "workflow_dispatch" in on
    steps = doc["jobs"]["build"]["steps"]
    runs = [s.get("run", "") for s in steps]
    uses = [s.get("uses", "") for s in steps]
    test_at = next(i for i, r in enumerate(runs) if "npm" in r and "test" in r)
    copy_at = next(i for i, r in enumerate(runs) if "docs/guide" in r and "app/dist/guide" in r)
    upload_at = next(i for i, u in enumerate(uses) if u.startswith("actions/upload-pages-artifact@"))
    assert test_at < upload_at and copy_at < upload_at
    assert doc["concurrency"]["group"] == "pages"
    assert "--run" in runs[test_at]
    assert steps[upload_at]["with"]["path"] == "app/dist"
    commands = [c.strip() for c in runs[copy_at].splitlines()]
    cp_at = next(i for i, c in enumerate(commands) if c.startswith("cp ") and "docs/guide" in c)
    for excluded in ("app/dist/guide/pages", "app/dist/guide/build.py"):
        assert any(
            c.startswith("rm ") and excluded in c for c in commands[cp_at + 1 :]
        ), f"{excluded} is not removed after the copy"
    assert doc["jobs"]["deploy"]["environment"]["name"] == "github-pages"
    assert any(s.get("uses", "").startswith("actions/deploy-pages@") for s in doc["jobs"]["deploy"]["steps"])


# ---- lake request, accept and refresh workflows -------------------------------------------------

GITHUB = ROOT / ".github"
SCRIPTS = GITHUB / "scripts"
REBUILD = GITHUB / "actions" / "rebuild" / "action.yml"
LAKE_REQUEST = GITHUB / "workflows" / "lake-request.yml"
LAKE_ACCEPT = GITHUB / "workflows" / "lake-accept.yml"
REFRESH = GITHUB / "workflows" / "refresh.yml"
DATA_WORKFLOWS = (LAKE_REQUEST, LAKE_ACCEPT, REFRESH)
LABELS = ("lake-request", "searched", "too few passes", "accepted", "rebuild failed", "invalid", "rejected")
PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
CHANGED = "This request changed after it was approved. A team member must accept it again."


def on_of(doc):
    return doc.get(True, doc.get("on"))  # PyYAML reads the key `on` as True


def runs_rebuild(step):
    return str(step.get("uses", "")).rstrip("/") == "./.github/actions/rebuild"


def checks_permission(step):
    run = step.get("run") or ""
    return "collaborators/" in run and "/permission" in run


def env_name(job):
    env = job.get("environment")
    return env.get("name") if isinstance(env, dict) else env


def writes(job, doc):
    perms = job.get("permissions", doc.get("permissions")) or {}
    return perms == "write-all" or (isinstance(perms, dict) and "write" in perms.values())


def accept_jobs():
    return load(LAKE_ACCEPT)["jobs"]


def test_accept_checks_permission_before_rebuild():
    jobs = accept_jobs()
    gate, rebuild, publish = jobs["gate"], jobs["rebuild"], jobs["publish"]
    perm = next(s for s in gate["steps"] if checks_permission(s))
    assert "github.event.sender.login" in str(perm["env"]["SENDER"])
    assert "github.event.sender" not in perm["run"]
    assert "approver.py" in perm["run"], "the approval time and a dispatched run's approver come from the events"
    assert "sleep 5" in perm["run"] and perm["run"].count("perm=\"$(lookup)\"") == 2, "one retry"
    assert "refuse-team" in perm["run"] and "4) decide refuse-team" in perm["run"], "no valid approver: refuse"
    assert "environment" not in gate and not writes(gate, {})
    assert "secrets." not in yaml.safe_dump(gate)
    assert rebuild["needs"] == "gate" and rebuild["if"] == "needs.gate.outputs.decision == 'allowed'"
    assert any(runs_rebuild(s) for s in rebuild["steps"])
    assert not any(runs_rebuild(s) for j in (gate, publish) for s in j["steps"])
    assert rebuild["environment"] == "earthdata" and rebuild["timeout-minutes"] == 360
    add = next(s for s in rebuild["steps"] if "lake-issue-accept" in (s.get("run") or ""))
    assert "--approved-at" in add["run"] and "needs.gate.outputs.approved_at" in str(add["env"]["APPROVED_AT"])
    assert CHANGED in add["run"]


def test_accept_workflow_triggers():
    doc = load(LAKE_ACCEPT)
    on = on_of(doc)
    assert on["issues"]["types"] == ["labeled"]
    assert on["workflow_dispatch"]["inputs"]["issue"]["required"] is True
    gate = accept_jobs()["gate"]
    assert "accepted" in gate["if"] and "lake-request" in gate["if"] and "workflow_dispatch" in gate["if"]
    assert "inputs.issue" in str(doc["env"]["ISSUE"]) and "github.event.issue.number" in str(doc["env"]["ISSUE"])
    perm = next(s for s in gate["steps"] if checks_permission(s))
    assert "*[!0-9]*" in perm["run"], "the dispatched issue number must be digits"
    text = LAKE_ACCEPT.read_text(encoding="utf-8")
    assert "Only the SARtale team can accept a request." in text
    assert 'commit-data.sh "Add requested lake from issue #' in text
    assert "Published, but the site deploy did not start; run the Deploy workflow." in text
    assert text.count(CHANGED) == 3, "refused before the rebuild, during it (publish), and matched in the log"


def test_rebuild_jobs_cannot_write_and_writers_have_no_earthdata():
    for path in DATA_WORKFLOWS:
        doc = load(path)
        for job_name, job in jobs_of(doc):
            if env_name(job) == "earthdata":
                assert not writes(job, doc), f"{path.name}:{job_name} holds Earthdata and a write token"
                assert job["concurrency"] == {"group": "sartale-rebuild", "cancel-in-progress": False}
            if writes(job, doc):
                assert "EARTHDATA" not in yaml.safe_dump(job), f"{path.name}:{job_name}"
                assert not any(runs_rebuild(s) for s in job["steps"]), f"{path.name}:{job_name} builds"
                assert job["concurrency"] == {"group": "sartale-data", "cancel-in-progress": False}


def test_rebuilt_data_travel_as_a_checked_artifact():
    for path, rebuild, publish in ((LAKE_ACCEPT, "rebuild", "publish"), (REFRESH, "rebuild", "publish")):
        jobs = load(path)["jobs"]
        up = [s for s in jobs[rebuild]["steps"] if str(s.get("uses", "")).startswith("actions/upload-artifact@")]
        pack = [s for s in jobs[rebuild]["steps"] if "data_artifact.py pack" in (s.get("run") or "")]
        assert up and pack and up[0]["with"]["name"] == "lake-data"
        steps = jobs[publish]["steps"]
        names = [s.get("uses") or s.get("run") or "" for s in steps]
        down = next(i for i, n in enumerate(names) if n.startswith("actions/download-artifact@"))
        unpack = next(i for i, n in enumerate(names) if "data_artifact.py unpack" in n)
        commit = next(i for i, n in enumerate(names) if "commit-data.sh" in n)
        assert down < unpack < commit, path.name
        assert publish in [k for k in jobs if rebuild in str(jobs[k].get("needs"))]
        assert jobs[publish]["if"].startswith("always()")


def test_check_job_only():
    doc = load(LAKE_REQUEST)
    assert sorted(on_of(doc)["issues"]["types"]) == sorted(["opened", "edited", "reopened", "labeled", "closed"])
    assert list(doc["jobs"]) == ["check"]
    check = doc["jobs"]["check"]
    assert "'lake-request'" in check["if"] and "'accepted'" in check["if"]
    assert check["if"].count("github.event.label.name") == 2, "skips the `accepted` and `lake-request` labels"
    assert "environment" not in check
    assert "secrets." not in yaml.safe_dump(check)
    assert check["timeout-minutes"] == 30
    assert check["permissions"] == {"contents": "write", "issues": "write", "actions": "write"}
    assert check["concurrency"] == {"group": "sartale-data", "cancel-in-progress": False}
    text = LAKE_REQUEST.read_text(encoding="utf-8")
    assert 'commit-data.sh "Update lake requests" app/public/data/requests.json' in text
    assert "--event-issue" not in text
    assert 'apply-actions.sh "$RUNNER_TEMP/actions.json"' in text


def failure_steps(steps):
    return [s for s in steps if "failure()" in str(s.get("if", ""))]


def test_failure_steps_also_run_when_cancelled():
    for path in DATA_WORKFLOWS:
        doc = load(path)
        failed = [s for _, job in jobs_of(doc) for s in failure_steps(job["steps"])]
        assert failed, f"{path.name} reports no failure"
        for s in failed:
            assert "cancelled()" in s["if"], path.name
        for job_name, job in jobs_of(doc):
            for s in job["steps"]:
                if runs_rebuild(s):
                    assert s["timeout-minutes"] < job["timeout-minutes"], "the job must outlive the rebuild"


def test_accept_failure_comments_and_labels():
    publish = accept_jobs()["publish"]
    (failed,) = failure_steps(publish["steps"])
    assert failed["if"].startswith("always()") and "needs.rebuild.result != 'success'" in failed["if"]
    body = failed["run"]
    assert "--body-file" in body
    assert '"rebuild failed"' in body
    assert "The rebuild failed; see" in body and "Nothing was published." in body
    assert "DEPLOY_FAILED" in body
    assert "gh issue close" not in body


def test_check_failure_neither_comments_nor_labels():
    (failed,) = failure_steps(load(LAKE_REQUEST)["jobs"]["check"]["steps"])
    assert "gh " not in failed["run"] and "rebuild failed" not in failed["run"]
    assert "GH_TOKEN" not in (failed.get("env") or {})


def test_data_checkouts_keep_no_credentials():
    for path in DATA_WORKFLOWS:
        for job_name, job in jobs_of(load(path)):
            for s in job["steps"]:
                if str(s.get("uses", "")).startswith("actions/checkout@"):
                    assert s["with"]["persist-credentials"] is False, f"{path.name}:{job_name}"
                if "GH_TOKEN" in (s.get("env") or {}):
                    assert not runs_rebuild(s)
            assert "GH_TOKEN" not in (job.get("env") or {}), f"{path.name}:{job_name}"
        assert "GH_TOKEN" not in (load(path).get("env") or {}), path.name


def test_commit_data_pushes_with_its_own_credential():
    text = (SCRIPTS / "commit-data.sh").read_text(encoding="utf-8")
    assert "GIT_CONFIG_KEY_0=http.https://github.com/.extraheader" in text
    assert "x-access-token" in text
    assert "deploy_failed=true" in text


def test_actions_are_pinned():
    def check(uses, where):
        if uses and not uses.startswith("./"):
            assert PINNED.match(uses), f"{where} uses {uses} without a commit SHA"

    for path in DATA_WORKFLOWS:
        for job_name, job in jobs_of(load(path)):
            for s in job["steps"]:
                check(s.get("uses"), f"{path.name}:{job_name}")
    for path in WORKFLOWS:  # and every earthdata job anywhere
        for job_name, job in jobs_of(load(path)):
            if env_name(job) == "earthdata":
                for s in job["steps"]:
                    check(s.get("uses"), f"{path.name}:{job_name}")
    for s in load(REBUILD)["runs"]["steps"]:
        check(s.get("uses"), "rebuild action")


def test_netrc_removed_always():
    steps = load(REBUILD)["runs"]["steps"]
    assert any(
        str(s.get("if", "")).strip() == "always()" and "rm -f ~/.netrc" in (s.get("run") or "")
        for s in steps
    )
    writes_at = next(i for i, s in enumerate(steps) if ".netrc" in (s.get("run") or "") and "printf" in s["run"])
    assert "set +x" in steps[writes_at]["run"] and "chmod 600" in steps[writes_at]["run"]
    assert "${{" not in steps[writes_at]["run"], "the login goes through env, not expressions"


def test_rebuild_action_order():
    doc = load(REBUILD)
    assert doc["runs"]["using"] == "composite"
    assert not doc.get("inputs")
    steps = doc["runs"]["steps"]
    runs = [s.get("run") or "" for s in steps]
    uses = [s.get("uses") or "" for s in steps]

    def at(word):
        return next(i for i, r in enumerate(runs) if word in r)

    assert at("lakes-search") < at("lakes-fetch") < at("lakes-build") < at("pytest tests -q")
    assert at("pytest tests -q") < at("npm test -- --run")
    assert "npm ci --ignore-scripts" in runs[at("npm test -- --run")]
    assert runs[at("lakes-fetch")].count("run_pipeline lakes-fetch") == 2, "lakes-fetch is retried once"
    assert any(u.startswith("mamba-org/setup-micromamba@") for u in uses)
    restore = next(s for s in steps if str(s.get("uses", "")).startswith("actions/cache/restore@"))
    assert restore["with"]["path"] == "data/lakes"
    assert restore["with"]["key"] == "lakes-${{ hashFiles('processing/lakes_in.json') }}-${{ github.run_id }}"
    assert restore["with"]["restore-keys"].strip() == "lakes-"
    save = next(s for s in steps if str(s.get("uses", "")).startswith("actions/cache/save@"))
    assert save["if"] == "success()", "a failed fetch does not overwrite the cache"
    for s in steps:
        if "run" in s:
            assert "shell" in s, "composite run steps need a shell"
            for bad in FORBIDDEN_IN_RUN + ("secrets.",):
                assert bad not in s["run"]


def test_no_allow_gate_fail():
    for path in GITHUB.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            assert "allow-gate-fail" not in path.read_text(encoding="utf-8"), path


def test_scripts_use_body_file():
    text = (SCRIPTS / "apply-actions.sh").read_text(encoding="utf-8")
    assert "--body-file" in text
    assert "--body " not in text and " -b " not in text


def test_commit_data_script():
    text = (SCRIPTS / "commit-data.sh").read_text(encoding="utf-8")
    assert "github-actions[bot]" in text
    assert "git pull --rebase origin main" in text
    assert "gh workflow run deploy.yml --ref main" in text
    assert "Co-Authored-By" not in text


def test_ensure_labels_creates_all_seven():
    text = (SCRIPTS / "ensure-labels.sh").read_text(encoding="utf-8")
    assert "--force" in text
    for name in LABELS:
        assert f'"{name}"' in text, name


def test_refresh_scheduled_weekly():
    doc = load(REFRESH)
    on = on_of(doc)
    assert on["schedule"] == [{"cron": "0 3 * * 1"}]
    assert "workflow_dispatch" in on
    rebuild, publish = doc["jobs"]["rebuild"], doc["jobs"]["publish"]
    assert rebuild["environment"] == "earthdata"
    assert rebuild["timeout-minutes"] == 360
    assert rebuild["permissions"] == {"contents": "read"}
    assert any(runs_rebuild(s) for s in rebuild["steps"])
    assert publish["needs"] == "rebuild" and "environment" not in publish
    text = REFRESH.read_text(encoding="utf-8")
    assert 'commit-data.sh "Weekly data refresh" app/public/data' in text
    assert "json_changed.py app/public/data/lakes.json built" in text


def test_data_jobs_start_deploy_through_commit_script():
    for path in DATA_WORKFLOWS:
        for job_name, job in jobs_of(load(path)):
            perms = job.get("permissions") or {}
            if perms.get("contents") == "write":
                assert perms.get("actions") == "write", f"{path.name}:{job_name} cannot start deploy.yml"
                assert any("commit-data.sh" in (s.get("run") or "") for s in job["steps"])


def test_run_scripts_survive_yaml_parsing():
    commit = next(s for s in accept_jobs()["publish"]["steps"] if "commit-data.sh" in (s.get("run") or ""))
    assert ('"Add requested lake from issue #$ISSUE" processing/lakes_in.json app/public/data'
            in commit["run"]), "the parsed command, not just the file text"


THREE_TIMES = ("The data changed three times while this lake was being added. "
               "A team member can add the accepted label again.")
UNSTARTED = "needs.rebuild.result == 'cancelled' && needs.rebuild.outputs.started != 'true'"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_write_jobs_have_no_environment_and_no_secrets(path):
    doc = load(path)
    for job_name, job in jobs_of(doc):
        if job_name == "deploy" and path.name == "deploy.yml":
            continue  # Pages deploy: pages/id-token write in the github-pages environment, no secrets
        if writes(job, doc):
            assert "environment" not in job, f"{path.name}:{job_name}"
            dumped = yaml.safe_dump(job).replace("secrets.GITHUB_TOKEN", "")
            assert "secrets." not in dumped, f"{path.name}:{job_name} sees a secret"


def test_rebuild_jobs_mark_their_start():
    for path in (LAKE_ACCEPT, REFRESH):
        job = load(path)["jobs"]["rebuild"]
        first = job["steps"][0]
        assert first["id"] == "started" and first["run"].strip() == 'echo "started=true" >> "$GITHUB_OUTPUT"'
        assert "if" not in first
        assert job["outputs"]["started"] == "${{ steps.started.outputs.started }}"


def test_accept_starts_again_when_stale_or_never_started():
    doc = load(LAKE_ACCEPT)
    attempt = on_of(doc)["workflow_dispatch"]["inputs"]["attempt"]
    assert attempt["default"] == "1" and attempt["required"] is False
    assert "inputs.attempt" in str(doc["env"]["ATTEMPT"])
    steps = doc["jobs"]["publish"]["steps"]
    install = next(s for s in steps if "data_artifact.py unpack" in (s.get("run") or ""))
    assert '6) echo "result=stale"' in install["run"]
    again = next(s for s in steps if "gh workflow run lake-accept.yml" in (s.get("run") or ""))
    assert again["if"].startswith("always()")
    assert "steps.install.outputs.result == 'stale'" in again["if"] and UNSTARTED in again["if"]
    assert '-f "issue=$ISSUE" -f "attempt=$((attempt + 1))"' in again["run"]
    assert "*[!0-9]*" in again["run"], "the attempt number must be digits"
    assert THREE_TIMES in again["run"] and '"rebuild failed"' in again["run"]
    (failed,) = failure_steps(steps)
    assert "steps.install.outputs.result != 'stale'" in failed["if"]
    assert f"!({UNSTARTED})" in failed["if"]


def test_refresh_waits_for_next_week_when_stale_or_never_started():
    steps = load(REFRESH)["jobs"]["publish"]["steps"]
    install = next(s for s in steps if "data_artifact.py unpack" in (s.get("run") or ""))
    assert '6) echo "result=stale"' in install["run"] and "GITHUB_STEP_SUMMARY" in install["run"]
    commit = next(s for s in steps if "commit-data.sh" in (s.get("run") or ""))
    assert "steps.install.outputs.result == 'ok'" in commit["if"]
    (failed,) = failure_steps(steps)
    assert "steps.install.outputs.result != 'stale'" in failed["if"] and f"!({UNSTARTED})" in failed["if"]
    unstarted = [s for s in steps if UNSTARTED in str(s.get("if", "")) and s is not failed]
    assert unstarted and "exit 1" not in unstarted[0]["run"]


def test_label_events_do_not_ask_the_events_api():
    perm = next(s for s in accept_jobs()["gate"]["steps"] if checks_permission(s))
    run = perm["run"]
    branch = run.index('if [ "$EVENT" = workflow_dispatch ]; then')
    other = run.index("else", branch)
    assert branch < run.index("approver.py") < other, "approver.py only for a dispatched run"
    assert run.count("approver.py") == 1
    assert 'approver="$SENDER"' in run[other:] and "date -u +%Y-%m-%dT%H:%M:%SZ" in run[other:]
    assert "^[A-Za-z0-9][A-Za-z0-9-]*$" in run, "the sender login is checked too"


def test_rebuild_skips_an_issue_no_longer_waiting():
    add = next(s for s in accept_jobs()["rebuild"]["steps"] if "lake-issue-accept" in (s.get("run") or ""))
    assert "waiting.py" in add["run"] and "decide skip" in add["run"]
    assert "'skip'" in accept_jobs()["publish"]["if"]
    migrated = "This request was approved before the new check existed. A team member must accept it again."
    assert migrated in LAKE_ACCEPT.read_text(encoding="utf-8")
