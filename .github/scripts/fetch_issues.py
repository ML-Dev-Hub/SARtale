"""Write every `lake-request` issue (REST shape) to a JSON file for `run_pipeline lake-issues`.

Calls `gh` with argument lists only, never through a shell. Issue text is data here and never leaves the file.

For a closed issue that is not `invalid` and not accepted, `close_reason` is the body of the team's last comment
(author association OWNER, MEMBER or COLLABORATOR, and not a bot), else None. An issue counts as accepted when
requests.json (--confirmed-from) says so; without that file, when it carries the `accepted` label.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

TEAM = {"OWNER", "MEMBER", "COLLABORATOR"}


def run_gh(args: list[str]) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True, encoding="utf-8").stdout


def parse_pages(text: str) -> list:
    """`gh api --paginate` prints one JSON array per page, back to back; flatten them."""
    decoder, items, at = json.JSONDecoder(), [], 0
    while True:
        while at < len(text) and text[at].isspace():
            at += 1
        if at >= len(text):
            return items
        page, at = decoder.raw_decode(text, at)
        items.extend(page if isinstance(page, list) else [page])


def _names(issue: dict) -> set[str]:
    return {lb["name"] for lb in issue.get("labels", [])}


def _close_reason(repo: str, number: int, runner) -> str | None:
    comments = parse_pages(runner(["api", "--paginate", f"repos/{repo}/issues/{int(number)}/comments?per_page=100"]))
    team = [c for c in comments
            if c.get("author_association") in TEAM and (c.get("user") or {}).get("type") != "Bot"]
    return team[-1].get("body") if team else None


def fetch(repo: str, runner=run_gh, confirmed_from: dict | None = None) -> list[dict]:
    pages = runner(["api", "--paginate", f"repos/{repo}/issues?labels=lake-request&state=all&per_page=100"])
    issues = [i for i in parse_pages(pages) if "pull_request" not in i]
    if confirmed_from is None:
        accepted = {i["number"] for i in issues if "accepted" in _names(i)}
    else:
        accepted = {r["issue"] for r in confirmed_from.get("requests", []) if r.get("state") == "accepted"}
    for i in issues:
        i["close_reason"] = None
        if i.get("state") == "closed" and "invalid" not in _names(i) and i["number"] not in accepted:
            i["close_reason"] = _close_reason(repo, i["number"], runner)
    return issues


def main(argv=None, runner=run_gh) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", required=True)
    p.add_argument("--confirmed-from", help="requests.json: which requests are accepted")
    args = p.parse_args(argv)
    repo = os.environ["GITHUB_REPOSITORY"]
    feed = None
    if args.confirmed_from:
        path = Path(args.confirmed_from)
        feed = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"requests": []}
    issues = fetch(repo, runner, feed)
    Path(args.out).write_text(json.dumps(issues, ensure_ascii=False), encoding="utf-8")
    print(f"{len(issues)} lake-request issues", file=sys.stderr)


if __name__ == "__main__":
    main()
