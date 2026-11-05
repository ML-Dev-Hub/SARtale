"""Guards on the GitHub workflows and the lake request issue form."""

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
