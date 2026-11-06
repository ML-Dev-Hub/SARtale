"""Print who approved a lake request and when: the last `labeled` event that added `accepted` to the issue.

Prints two lines, the login and the event time (YYYY-MM-DDTHH:MM:SSZ). The caller checks the login's permission
(for a label event it uses the sender, who just added the label) and passes the time to lake-issue-accept, so an
approval older than the checked values is refused.

Exit 3: the issue is no longer an open `lake-request` issue carrying `accepted` (nothing to do).
Exit 4: it carries `accepted` but no valid approver can be found (refuse, as for someone outside the team).
Any other failure exits non-zero as well, so the check fails closed.

Usage: python3 approver.py --issue <n>
"""

import argparse
import json
import os
import re
import sys

from fetch_issues import parse_pages, run_gh

LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
WHEN = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
NOT_WAITING, NO_APPROVER = 3, 4


class NotWaiting(Exception):
    pass


def approval(repo: str, number: int, runner=run_gh) -> tuple[str, str] | None:
    """(login, time) of the last account that added `accepted`; None if none is valid; NotWaiting if moot."""
    number = int(number)
    issue = json.loads(runner(["api", f"repos/{repo}/issues/{number}"]))
    names = {lb.get("name") for lb in issue.get("labels", [])}
    if issue.get("state") != "open" or "pull_request" in issue or not {"lake-request", "accepted"} <= names:
        raise NotWaiting(number)
    events = parse_pages(runner(["api", "--paginate", f"repos/{repo}/issues/{number}/events?per_page=100"]))
    added = [e for e in events if e.get("event") == "labeled" and (e.get("label") or {}).get("name") == "accepted"]
    if not added:
        return None
    login, when = (added[-1].get("actor") or {}).get("login") or "", added[-1].get("created_at") or ""
    return (login, when) if LOGIN.match(login) and WHEN.match(when) else None


def approver(repo: str, number: int, runner=run_gh) -> str | None:
    try:
        found = approval(repo, number, runner)
    except NotWaiting:
        return None
    return found[0] if found else None


def main(argv=None, runner=run_gh) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--issue", type=int, required=True)
    args = p.parse_args(argv)
    try:
        found = approval(os.environ["GITHUB_REPOSITORY"], args.issue, runner)
    except NotWaiting:
        print(f"issue #{args.issue} is not waiting for an accept", file=sys.stderr)
        raise SystemExit(NOT_WAITING) from None
    if found is None:
        print(f"issue #{args.issue} has no valid approver", file=sys.stderr)
        raise SystemExit(NO_APPROVER)
    print(found[0])
    print(found[1])


if __name__ == "__main__":
    main()
