"""Print who approved a lake request: the last account to add the `accepted` label to the issue.

Used by a dispatched accept run, where the sender is the workflow, not a person. Prints nothing and exits 3
when the issue is no longer an open `lake-request` issue carrying `accepted`, or no such label event exists.
The caller checks the printed login's permission; any other failure exits non-zero, so the check fails closed.

Usage: python3 approver.py --issue <n>
"""

import argparse
import json
import os
import re
import sys

from fetch_issues import parse_pages, run_gh

LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")


def approver(repo: str, number: int, runner=run_gh) -> str | None:
    number = int(number)
    issue = json.loads(runner(["api", f"repos/{repo}/issues/{number}"]))
    names = {lb.get("name") for lb in issue.get("labels", [])}
    if issue.get("state") != "open" or "pull_request" in issue or not {"lake-request", "accepted"} <= names:
        return None
    events = parse_pages(runner(["api", "--paginate", f"repos/{repo}/issues/{number}/events?per_page=100"]))
    added = [e for e in events if e.get("event") == "labeled" and (e.get("label") or {}).get("name") == "accepted"]
    login = ((added[-1].get("actor") or {}).get("login") or "") if added else ""
    return login if LOGIN.match(login) else None


def main(argv=None, runner=run_gh) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--issue", type=int, required=True)
    args = p.parse_args(argv)
    login = approver(os.environ["GITHUB_REPOSITORY"], args.issue, runner)
    if login is None:
        print(f"issue #{args.issue} is not waiting for an accept", file=sys.stderr)
        raise SystemExit(3)
    print(login)


if __name__ == "__main__":
    main()
