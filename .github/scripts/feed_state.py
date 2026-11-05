"""Print the state requests.json records for one issue, or `none`.

Usage: python3 feed_state.py <requests.json> <issue-number>
"""

import json
import sys
from pathlib import Path


def state(feed: dict, number: int) -> str:
    return next((r["state"] for r in feed.get("requests", []) if r.get("issue") == number), "none")


def main(argv=None) -> None:
    path, number = argv or sys.argv[1:]
    feed = json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else {}
    print(state(feed, int(number)))


if __name__ == "__main__":
    main()
