"""Print the issue number of the next lake request waiting for an accept run, or `none`.

The drain step at the end of every accept and refresh publish job runs this and starts at most one accept, so
accepts queued out of `sartale-rebuild` by one another are worked off one at a time. The choice is the same as
reconcile's one dispatch per run (processing/sartale/accept_queue.py): the lowest-numbered open issue with
`lake-request` and `accepted`, without `rebuild failed`, whose requests.json entry was checked and is not accepted.

Calls `gh` with argument lists only. Prints only an issue number GitHub returned as an integer, or `none`.

Usage: python3 next_accept.py --feed app/public/data/requests.json [--exclude <issue-number>]
"""

import argparse
import json
import os
import sys
from pathlib import Path

from fetch_issues import parse_pages, run_gh

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "processing"))
from sartale.accept_queue import next_accept  # noqa: E402  (standard library only)


def waiting_issues(repo: str, runner=run_gh) -> list[dict]:
    pages = runner(["api", "--paginate", f"repos/{repo}/issues?labels=lake-request,accepted&state=open&per_page=100"])
    return [i for i in parse_pages(pages)
            if "pull_request" not in i and type(i.get("number")) is int and i["number"] > 0]


def main(argv=None, runner=run_gh) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--feed", required=True)
    p.add_argument("--exclude", type=int, help="the issue this run just handled")
    args = p.parse_args(argv)
    path = Path(args.feed)
    feed = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"requests": []}
    issues = waiting_issues(os.environ["GITHUB_REPOSITORY"], runner)
    found = next_accept(feed, issues, exclude={args.exclude} if args.exclude else ())
    print("none" if found is None else found)


if __name__ == "__main__":
    main()
