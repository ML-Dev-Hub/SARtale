"""Which lake request should get the next accept run. Standard library only.

Used by reconcile (lake_issues.reconcile_actions) and by the drain step at the end of every accept and refresh
publish job (.github/scripts/next_accept.py), which runs without the conda environment. Only one accept can wait
in the `sartale-rebuild` queue, so both start at most one: the lowest-numbered request that is waiting.
"""

CHECKED = ("searched", "too_few_passes")


def _labels(issue: dict) -> set[str]:
    return {lb.get("name") for lb in issue.get("labels", [])}


def awaits_accept(issue: dict, state: str | None) -> bool:
    """An open request the team accepted, whose last check passed, not accepted yet, and not failed since."""
    labels = _labels(issue)
    return (issue.get("state") == "open" and {"lake-request", "accepted"} <= labels
            and "rebuild failed" not in labels and state in CHECKED)


def next_accept(feed: dict, issues: list[dict], exclude=()) -> int | None:
    """The lowest-numbered issue waiting for an accept run, leaving out `exclude`; None if there is none."""
    states = {r.get("issue"): r.get("state") for r in (feed or {}).get("requests", [])}
    skip = set(exclude)
    for issue in sorted(issues, key=lambda i: i["number"]):
        number = issue["number"]
        if number not in skip and awaits_accept(issue, states.get(number)):
            return number
    return None
