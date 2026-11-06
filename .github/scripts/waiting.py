"""Print `yes` if the issue is still an open `lake-request` issue carrying `accepted`, else `no`.

Reads the list fetch_issues.py wrote, so a queued accept run notices a label the team or a check run removed
while it waited.

Usage: python3 waiting.py <issues.json> <issue-number>
"""

import json
import sys
from pathlib import Path


def is_waiting(issues: list[dict], number: int) -> bool:
    found = next((i for i in issues if i.get("number") == number), None)
    names = {lb.get("name") for lb in (found or {}).get("labels", [])}
    return bool(found) and found.get("state") == "open" and {"lake-request", "accepted"} <= names


def main(argv=None) -> None:
    path, number = argv or sys.argv[1:]
    issues = json.loads(Path(path).read_text(encoding="utf-8"))
    print("yes" if is_waiting(issues, int(number)) else "no")


if __name__ == "__main__":
    main()
