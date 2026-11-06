"""Print `busy` if any listed lake-accept.yml or refresh.yml run other than this one is active, else `idle`.

busy.sh writes `gh run list --json databaseId,status` for both workflows to files and passes them here, so the
JSON is parsed in Python and never by the shell. Leaves out this run ($GITHUB_RUN_ID). Anything unreadable
prints `busy`: skipping a start is safe, and the daily check retries it.

Usage: python3 busy.py <runs.json>...
"""

import json
import os
import sys
from pathlib import Path

ACTIVE = {"queued", "in_progress", "waiting", "requested", "pending"}


def active_runs(lists: list, own: int | None) -> list[int]:
    found = []
    for runs in lists:
        if not isinstance(runs, list):
            raise ValueError("a run list is not a list")
        for run in runs:
            number = run.get("databaseId") if isinstance(run, dict) else None
            if type(number) is not int:
                raise ValueError("a run has no integer id")
            if run.get("status") in ACTIVE and number != own:
                found.append(number)
    return found


def main(argv=None) -> None:
    paths = sys.argv[1:] if argv is None else argv
    try:
        if not paths:
            raise ValueError("no run lists")
        own = os.environ.get("GITHUB_RUN_ID", "")
        lists = [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]
        active = active_runs(lists, int(own) if own.isdigit() else None)
    except Exception as e:  # noqa: BLE001  any failure fails safe
        print(f"busy.py: could not read the run lists ({type(e).__name__}); counting them as active",
              file=sys.stderr)
        print("busy")
        return
    if active:
        print(f"busy.py: active runs {active}", file=sys.stderr)
    print("busy" if active else "idle")


if __name__ == "__main__":
    main()
