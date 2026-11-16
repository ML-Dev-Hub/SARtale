"""Guards on the GitHub workflows and the lake request issue form."""

import re
from pathlib import Path

import pytest
import yaml

from sartale.lake_issues import FIELDS

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.y*ml"))
FORM = ROOT / ".github" / "ISSUE_TEMPLATE" / "add-lake.yml"

REBUILD_ACTION = ROOT / ".github" / "actions" / "rebuild" / "action.yml"


def load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def jobs_of(doc):
    return (doc.get("jobs") or {}).items()


def test_workflows_exist():
    assert WORKFLOWS, "no workflow files found"


def script_steps(doc):
    """(job name, step) for every step of a workflow, or of a composite action."""
    jobs = doc.get("jobs") or {"composite": {"steps": (doc.get("runs") or {}).get("steps", [])}}
    return [(name, step) for name, job in jobs.items() for step in job.get("steps", [])]


@pytest.mark.parametrize("path", WORKFLOWS + [REBUILD_ACTION], ids=lambda p: p.name)
def test_no_expression_in_run_scripts(path):
    """No `${{ }}` at all in a script: every value, issue text or not, reaches it through `env:`."""
    for job_name, step in script_steps(load(path)):
        bodies = [step.get("run")]
        if str(step.get("uses", "")).startswith("actions/github-script"):
            bodies.append((step.get("with") or {}).get("script"))
        for body in bodies:
            if body is not None:
                assert "${{" not in body, f"{path.name}:{job_name}:{step.get('name')} puts an expression in a script"


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
    assert "refuse-team" in perm["run"] and "4) decide refuse-lookup" in perm["run"], "no valid approver: cannot check"
    assert "environment" not in gate and not writes(gate, {})
    assert "secrets." not in yaml.safe_dump(gate)
    assert rebuild["needs"] == "gate" and rebuild["if"] == "needs.gate.outputs.decision == 'allowed'"
    assert any(runs_rebuild(s) for s in rebuild["steps"])
    assert not any(runs_rebuild(s) for j in (gate, publish) for s in j["steps"])
    assert rebuild["environment"] == "earthdata" and rebuild["timeout-minutes"] == 360
    add = next(s for s in rebuild["steps"] if "lake-issue-accept" in (s.get("run") or ""))
    assert "--approved-at" in add["run"] and "needs.gate.outputs.approved_at" in str(add["env"]["APPROVED_AT"])
    assert CHANGED in add["run"]


def test_a_failed_permission_lookup_is_not_called_a_refusal_of_the_sender():
    gate, publish = accept_jobs()["gate"], accept_jobs()["publish"]
    perm = next(s for s in gate["steps"] if checks_permission(s))
    assert "|| perm=unknown" in perm["run"] and "perm=none" not in perm["run"]
    assert "unknown) decide refuse-lookup ;;" in perm["run"]
    assert perm["run"].index("unknown) decide refuse-lookup") < perm["run"].index("*) decide refuse-team")
    refuse = next(s for s in publish["steps"] if "refused.md" in (s.get("run") or "")
                  and "refuse-team" in str(s.get("if")))
    assert "refuse-lookup" in refuse["if"] and "needs.gate.outputs.decision" in str(refuse["env"]["DECISION"])
    run = refuse["run"]
    lookup = run.index('if [ "$DECISION" = refuse-lookup ]; then')
    other = run.index("else", lookup)
    assert "SARtale could not check who added the label; a team member can add it again." in run[lookup:other]
    assert "Only the SARtale team" not in run[lookup:other]
    assert "Only the SARtale team can accept a request." in run[other:]
    assert "--remove-label accepted" in run, "both remove the label, so adding it again starts a new check"


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
    assert list(doc.get("inputs") or {}) == ["max-new-lakes"]  # the only input: the fetch cap
    steps = doc["runs"]["steps"]
    runs = [s.get("run") or "" for s in steps]
    uses = [s.get("uses") or "" for s in steps]

    def at(word):
        return next(i for i, r in enumerate(runs) if word in r)

    assert at("lakes-search") < at("lakes-fetch") < at("lakes-build") < at("pytest tests -q")
    # the published lakes.json is kept before the build and compared with the new one after it
    assert at("git show HEAD:app/public/data/lakes.json") < at("lakes-build") < at("lakes-diff") < at("pytest tests -q")
    assert '--old "$RUNNER_TEMP/lakes.published.json"' in runs[at("lakes-diff")]
    # M8: the absence check runs before the build (the build carries its fresh evidence), after the published copy
    # is kept, without the Earthdata login; new sites get their first check after the build
    absence = at("lakes-absence")
    assert at("git show HEAD:app/public/data/lakes.json") < absence < at("lakes-build")
    assert "--only-missing" not in runs[absence]
    missing = at("lakes-absence --only-missing")
    assert at("lakes-build") < missing < at("lakes-diff")
    # the freeze check runs after the build (it flags the built passes and sets the statuses again) and before the
    # comparison, without the Earthdata login (NASA POWER and Earth Search need none), and never stops the run itself
    freeze = at("lakes-freeze")
    assert at("lakes-build") < missing < freeze < at("lakes-diff")
    assert "continue-on-error" not in steps[freeze]
    # a lake new to the register gets its height (lakes_in.json) before the build and the freeze check, without the
    # Earthdata login; the step fails soft inside the command, so it carries no continue-on-error either
    elevation = at("lakes-elevation")
    assert at("lakes-fetch") < elevation < at("lakes-build") < freeze
    assert "continue-on-error" not in steps[elevation]
    # the lakes without a current Sentinel-2 check are checked after the freeze check (which sets the statuses the
    # check sets again), before the comparison, without the login, failing soft inside the command
    check = at("lakes-check --stale-only")
    assert freeze < check < at("lakes-diff")
    assert "continue-on-error" not in steps[check]
    for i in (absence, missing, freeze, elevation, check):
        assert "unset EARTHDATA_USERNAME EARTHDATA_PASSWORD" in runs[i]
    assert '> "$RUNNER_TEMP/lakes.published.json"' in runs[at("git show HEAD:app/public/data/lakes.json")]
    assert "continue-on-error" not in steps[at("lakes-diff")], "a large drop must fail the rebuild"
    assert at("pytest tests -q") < at("npm test -- --run")
    assert "npm ci --ignore-scripts" in runs[at("npm test -- --run")]
    assert runs[at("lakes-fetch")].count("run_pipeline lakes-fetch") == 2, "lakes-fetch is retried once"
    # at most 12 new lakes per run unless the caller asks for more (refresh.yml's manual input), the retry too
    assert doc["inputs"]["max-new-lakes"]["default"] == "12"
    assert steps[at("lakes-fetch")]["env"]["MAX_NEW_LAKES"] == "${{ inputs.max-new-lakes }}"
    assert runs[at("lakes-fetch")].count('--max-new-lakes "$MAX_NEW_LAKES"') == 2
    assert "*[!0-9]*" in runs[at("lakes-fetch")], "a cap that is not a whole number stops the fetch"
    # 4 worker processes on the 2-vCPU, 7 GB runner (the reads wait on the network), the retry too; 4 checks at once
    assert runs[at("lakes-fetch")].count("--workers 4") == 2
    assert "--workers 4" in runs[check]
    # the restored cache is cropped to float16 windows after the fetch, before the build reads it, without the login
    shrink = at("lakes-cache-shrink")
    assert at("lakes-fetch") < shrink < at("lakes-build")
    assert "--dry-run" not in runs[shrink]
    assert "unset EARTHDATA_USERNAME EARTHDATA_PASSWORD" in runs[shrink]
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
            assert "${{" not in s["run"] and "secrets." not in s["run"]


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
    # a manual run may fetch more lakes new to the cache (after the cache was invalidated); scheduled runs fetch 12
    assert on["workflow_dispatch"]["inputs"]["max_new_lakes"]["default"] == "12"
    rebuild, publish = doc["jobs"]["rebuild"], doc["jobs"]["publish"]
    assert [s["with"] for s in rebuild["steps"] if runs_rebuild(s)] == [
        {"max-new-lakes": "${{ inputs.max_new_lakes || '12' }}"}]
    assert rebuild["environment"] == "earthdata"
    assert rebuild["timeout-minutes"] == 360
    assert rebuild["permissions"] == {"contents": "read"}
    assert any(runs_rebuild(s) for s in rebuild["steps"])
    assert publish["needs"] == "rebuild" and "environment" not in publish
    text = REFRESH.read_text(encoding="utf-8")
    assert 'commit-data.sh "Weekly data refresh" app/public/data' in text
    assert "json_changed.py app/public/data/lakes.json built" in text


def test_both_publish_jobs_commit_the_register_when_the_rebuild_measured_a_height():
    """I2: the rebuild may add a lake's height to processing/lakes_in.json (lakes-elevation); unpack copies it into the
    publish checkout, so both publish jobs must commit it with the data, or the rebase before the push fails on the
    unstaged change. The refresh also publishes when only the register changed."""
    refresh = next(s for s in load(REFRESH)["jobs"]["publish"]["steps"] if "commit-data.sh" in (s.get("run") or ""))
    run = refresh["run"].replace("\\\n", " ")
    assert re.search(r'commit-data\.sh "Weekly data refresh"\s+app/public/data\s+processing/lakes_in\.json', run)
    assert 'git status --porcelain -- processing/lakes_in.json' in run and '[ -z "$register" ]' in run
    accept = next(s for s in accept_jobs()["publish"]["steps"] if "commit-data.sh" in (s.get("run") or ""))
    assert "processing/lakes_in.json app/public/data" in accept["run"]
    import importlib.util
    spec = importlib.util.spec_from_file_location("data_artifact", SCRIPTS / "data_artifact.py")
    da = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(da)
    assert da.LAKES_IN in da.BASE and da.LAKES_IN not in da.SCIENCE and da.allowed(da.LAKES_IN)


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


def test_accept_starts_again_only_when_stale():
    doc = load(LAKE_ACCEPT)
    attempt = on_of(doc)["workflow_dispatch"]["inputs"]["attempt"]
    assert attempt["default"] == "1" and attempt["required"] is False
    assert "inputs.attempt" in str(doc["env"]["ATTEMPT"])
    steps = doc["jobs"]["publish"]["steps"]
    install = next(s for s in steps if "data_artifact.py unpack" in (s.get("run") or ""))
    assert '6) echo "result=stale"' in install["run"]
    again = next(s for s in steps if "attempt=$((attempt + 1))" in (s.get("run") or ""))
    assert again["id"] == "again" and again["if"].startswith("always()")
    assert "steps.install.outputs.result == 'stale'" in again["if"]
    assert "cancelled" not in again["if"], "the three tries count stale bases only"
    assert '-f "issue=$ISSUE" -f "attempt=$((attempt + 1))"' in again["run"]
    assert "*[!0-9]*" in again["run"], "the attempt number must be digits"
    assert 'echo "restarted=true" >> "$GITHUB_OUTPUT"' in again["run"]
    assert THREE_TIMES in again["run"] and '"rebuild failed"' in again["run"]
    assert "The rebuild failed" not in again["run"], "giving up is only ever about stale data"
    (failed,) = failure_steps(steps)
    assert "steps.install.outputs.result != 'stale'" in failed["if"]
    assert f"!({UNSTARTED})" in failed["if"]
    # M4: a stale base found after the rebase, just before the push, starts the accept again too
    names = [s.get("name", "") for s in steps]
    commit = next(s for s in steps if "commit-data.sh" in (s.get("run") or ""))
    assert 'DATA_ARTIFACT="$RUNNER_TEMP/lake-data"' in commit["run"]
    assert '6) echo "result=stale" >> "$GITHUB_OUTPUT"' in commit["run"]
    assert "steps.commit.outputs.result == 'stale'" in again["if"]
    assert names.index(commit["name"]) < names.index(again["name"]), "again must run after the commit step"
    assert "steps.commit.outputs.result != 'stale'" in failed["if"]
    close = next(s for s in steps if s.get("name") == "Comment and close the issue")
    assert "steps.commit.outputs.result != 'stale'" in close["if"]


def test_refresh_refuses_a_stale_base_after_the_rebase_and_says_why():
    """M4: the refresh passes the artifact to commit-data.sh, and exit 6 (at unpack or after the rebase) says that
    main changed the data or the method code, not only that an accepted lake was published."""
    doc = load(REFRESH)
    publish = doc["jobs"]["publish"]
    stale = publish["env"]["STALE"]
    assert "accepted lake" in stale and "method code" in stale and "nothing was published" in stale
    commit = next(s for s in publish["steps"] if "commit-data.sh" in (s.get("run") or ""))
    assert 'DATA_ARTIFACT="$RUNNER_TEMP/lake-data"' in commit["run"]
    assert '6) echo "$STALE" >> "$GITHUB_STEP_SUMMARY"' in commit["run"]
    install = next(s for s in publish["steps"] if "data_artifact.py unpack" in (s.get("run") or ""))
    assert '"$STALE"' in install["run"]
    assert "An accepted lake was published while this refresh ran" not in REFRESH.read_text(encoding="utf-8")


def test_an_accept_that_never_started_ends_quietly():
    steps = accept_jobs()["publish"]["steps"]
    unstarted = [s for s in steps if UNSTARTED in str(s.get("if", ""))]
    quiet = [s for s in unstarted if f"!({UNSTARTED})" not in s["if"]]
    (note,) = quiet
    assert "GH_TOKEN" not in (note.get("env") or {}) and "gh " not in note["run"]
    assert "GITHUB_STEP_SUMMARY" in note["run"]
    for s in unstarted:
        if s is not note:
            assert f"!({UNSTARTED})" in s["if"], f"{s.get('name')} must not run for a queued-out rebuild"
    dispatching = [s for s in steps if "gh workflow run" in (s.get("run") or "")]
    assert len(dispatching) == 2  # start this one again (stale), and the drain
    for s in dispatching:
        assert UNSTARTED not in s["if"] or f"!({UNSTARTED})" in s["if"]


def drain_step(path):
    steps = load(path)["jobs"]["publish"]["steps"]
    return steps[-1], steps


@pytest.mark.parametrize("path", (LAKE_ACCEPT, REFRESH), ids=lambda p: p.name)
def test_publish_ends_by_starting_one_waiting_accept(path):
    drain, steps = drain_step(path)
    run = drain["run"]
    assert drain["if"].startswith("always()") and f"!({UNSTARTED})" in drain["if"]
    assert "python3 .github/scripts/next_accept.py --feed app/public/data/requests.json" in run
    assert "GH_TOKEN" in drain["env"] and "secrets." not in yaml.safe_dump(drain)
    assert run.count("gh workflow run") == 1, "at most one accept per run"
    digits, dispatch = run.index("''|*[!0-9]*)"), run.index("gh workflow run")
    assert digits < dispatch, "the issue number is checked as digits before it is used"
    assert 'gh workflow run lake-accept.yml --ref main -f "issue=$next" -f attempt=1' in run
    assert "${{" not in run
    checkout = next(s for s in steps if str(s.get("uses", "")).startswith("actions/checkout@"))
    assert "if" not in checkout, "the drain step reads requests.json from the checkout"


def test_accept_drain_skips_its_own_issue_and_a_restart():
    drain, _ = drain_step(LAKE_ACCEPT)
    assert '--exclude "$ISSUE"' in drain["run"]
    assert "steps.again.outputs.restarted != 'true'" in drain["if"]


def test_publish_runs_for_every_allowed_rebuild():
    # a rebuild that decided 'done' or 'skip' still held the queue: publish runs, but only the drain does work
    publish = accept_jobs()["publish"]
    assert publish["if"] == ("always() && (needs.gate.outputs.decision == 'refuse-team' || "
                             "needs.gate.outputs.decision == 'refuse-lookup' || "
                             "needs.gate.outputs.decision == 'allowed')")
    for s in publish["steps"]:
        if "commit-data.sh" in (s.get("run") or "") or "data_artifact.py" in (s.get("run") or ""):
            assert "'ok'" in s["if"] or "decision == 'rebuild'" in s["if"]


def test_daily_reconcile_needs_no_secrets():
    doc = load(LAKE_REQUEST)
    assert on_of(doc)["schedule"] == [{"cron": "17 4 * * *"}]
    check = doc["jobs"]["check"]
    assert check["if"].startswith("github.event_name == 'schedule' || github.event_name == 'workflow_dispatch' ||")
    assert "environment" not in check and "secrets." not in yaml.safe_dump(check)
    run = " ".join(s.get("run") or "" for s in check["steps"])
    assert "lake-issues" in run and "apply-actions.sh" in run
    (failed,) = failure_steps(check["steps"])
    assert "''|*[!0-9]*)" in failed["run"], "the daily run has no issue number"


def test_label_events_take_the_approval_time_from_the_event():
    perm = next(s for s in accept_jobs()["gate"]["steps"] if checks_permission(s))
    assert perm["env"]["LABELED_AT"] == "${{ github.event.issue.updated_at }}"
    run = perm["run"]
    other = run.index("else", run.index('if [ "$EVENT" = workflow_dispatch ]; then'))
    branch = run[other:run.index("fi\n", run.index("decide refuse-lookup", other)) + 3]
    assert 'approved_at="$LABELED_AT"' in branch and "date -u" not in run
    assert "'^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$'" in branch
    assert "decide refuse-lookup; exit 0" in branch, "a missing or malformed time: the check could not be made"


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
    assert 'approver="$SENDER"' in run[other:] and 'approved_at="$LABELED_AT"' in run[other:]
    assert "^[A-Za-z0-9][A-Za-z0-9-]*$" in run, "the sender login is checked too"


def test_rebuild_skips_an_issue_no_longer_waiting():
    add = next(s for s in accept_jobs()["rebuild"]["steps"] if "lake-issue-accept" in (s.get("run") or ""))
    assert "waiting.py" in add["run"] and "decide skip" in add["run"]
    publish = accept_jobs()["publish"]
    assert "needs.gate.outputs.decision == 'allowed'" in publish["if"], "a skip still drains the queue"
    for s in publish["steps"][1:-1]:  # between the checkout and the drain, every step needs its own reason
        assert "if" in s, s.get("name")


ISSUE_WRITES = ("gh issue comment", "gh issue edit", "gh issue close", "apply-actions.sh")


def test_publish_touches_an_issue_only_for_a_named_outcome():
    # a 'skip' or 'done' rebuild reaches publish too: nothing may comment or label on a bare always()
    steps = accept_jobs()["publish"]["steps"]
    touching = [s for s in steps if any(w in (s.get("run") or "") for w in ISSUE_WRITES)]
    assert len(touching) >= 6
    for s in touching:
        cond = str(s.get("if", ""))
        assert "decision ==" in cond or "result ==" in cond, f"{s.get('name')}: {cond!r}"
        assert cond.strip() != "always()"
    drain, _ = drain_step(LAKE_ACCEPT)
    assert not any(w in drain["run"] for w in ISSUE_WRITES)


def calls_busy(job):
    return any("busy.sh" in (s.get("run") or "") or "apply-actions.sh" in (s.get("run") or "")
               for s in job["steps"])


@pytest.mark.parametrize("path", (LAKE_ACCEPT, REFRESH), ids=lambda p: p.name)
def test_drain_asks_for_active_runs_first(path):
    drain, _ = drain_step(path)
    run = drain["run"]
    ask = run.index('if [ "$(bash .github/scripts/busy.sh)" != idle ]; then')
    assert ask < run.index("next_accept.py") < run.index("gh workflow run")
    note = run[ask:run.index("fi", ask)]
    assert "GITHUB_STEP_SUMMARY" in note and "exit 0" in note


def test_reconcile_dispatch_asks_for_active_runs_first():
    text = (SCRIPTS / "apply-actions.sh").read_text(encoding="utf-8")
    ask = text.index('if [ "$(bash "$here/busy.sh")" = idle ]; then')
    assert ask < text.index("gh workflow run lake-accept.yml") < text.index("GITHUB_STEP_SUMMARY", ask)
    assert text.count("gh workflow run") == 1


def test_jobs_that_ask_for_runs_can_read_actions_and_issues():
    for path in DATA_WORKFLOWS:
        for job_name, job in jobs_of(load(path)):
            if calls_busy(job):
                assert job["permissions"].get("actions") in ("read", "write"), f"{path.name}:{job_name}"
    for path in (LAKE_ACCEPT, REFRESH):
        perms = load(path)["jobs"]["publish"]["permissions"]
        assert perms.get("issues") in ("read", "write"), f"{path.name}: next_accept.py lists issues"
    assert load(REFRESH)["jobs"]["publish"]["permissions"] == {"contents": "write", "issues": "read",
                                                               "actions": "write"}
    migrated = "This request was approved before the new check existed. A team member must accept it again."
    assert migrated in LAKE_ACCEPT.read_text(encoding="utf-8")


SINGLE_LINE_RUN = re.compile(r"^\s*(?:-\s+)?run:[ \t]+(?![|>])(\S.*)$")


@pytest.mark.parametrize("path", WORKFLOWS + [REBUILD], ids=lambda p: p.name)
def test_single_line_run_values_have_no_comment_marker(path):
    # in a plain YAML scalar " #" starts a comment and silently cuts the command (see the round-3 commit bug)
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = SINGLE_LINE_RUN.match(line)
        if m:
            assert " #" not in m.group(1), f"{path.name}:{n}: {line.strip()}"


def test_single_line_run_pattern():
    assert SINGLE_LINE_RUN.match('      - run: echo "a #b"')
    assert SINGLE_LINE_RUN.match("        run: bash x.sh  # note").group(1) == "bash x.sh  # note"
    assert not SINGLE_LINE_RUN.match("        run: |  # a block")
    assert not SINGLE_LINE_RUN.match("        run: >-")


def test_a_manual_run_creates_the_labels_and_reconciles_like_the_daily_run():
    """Issue forms drop labels that do not exist, so the owner runs this once before the first request."""
    doc = load(LAKE_REQUEST)
    on = on_of(doc)
    assert "workflow_dispatch" in on and not (on["workflow_dispatch"] or {}).get("inputs"), "no event issue"
    check = doc["jobs"]["check"]
    # a dispatch passes the job `if` on its own, without an issue's labels
    head = check["if"].split("(contains(")[0]
    assert "github.event_name == 'workflow_dispatch'" in head
    names = [s.get("name") for s in check["steps"]]
    labels = names.index("Make sure the labels exist")
    assert labels < names.index("List every lake request") < names.index("Check the requests")
    assert "ensure-labels.sh" in check["steps"][labels]["run"] and "if" not in check["steps"][labels]
    assert not any("if" in s and "event_name" in str(s["if"]) for s in check["steps"]), "every step runs on dispatch"


def test_only_a_confirmed_non_team_permission_gets_the_team_only_refusal():
    """No usable time, no valid sender or a failed lookup are could-not-check cases, never a team refusal."""
    perm = next(s for s in accept_jobs()["gate"]["steps"] if checks_permission(s))
    run = perm["run"]
    assert run.count("decide refuse-team") == 1, "only the permission answer can refuse someone"
    team = run.index("decide refuse-team")
    assert run.rindex('case "$perm" in', 0, team) < team, "inside the case on the looked-up permission"
    assert run.count("decide refuse-lookup") == 4  # approver.py exit 4, bad time, bad sender, failed lookup
