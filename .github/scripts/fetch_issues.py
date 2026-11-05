"""Write every `lake-request` issue (REST shape) to a JSON file for `run_pipeline lake-issues`.

Calls `gh` with argument lists only, never through a shell. Issue text is data here and never leaves the file.

For a closed issue without `accepted` or `invalid`, `close_reason` is the body of the team's last comment
(author association OWNER, MEMBER or COLLABORATOR), else None.

With --confirmed-from <requests.json>, the `accepted` label is dropped from every issue whose entry there is not
already `accepted`: only the accept job, after its permission check, may turn a request into an accepted one.
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
    team = [c for c in comments if c.get("author_association") in TEAM]
    return team[-1].get("body") if team else None


def fetch(repo: str, runner=run_gh, confirmed_from: dict | None = None) -> list[dict]:
    pages = runner(["api", "--paginate", f"repos/{repo}/issues?labels=lake-request&state=all&per_page=100"])
    issues = [i for i in parse_pages(pages) if "pull_request" not in i]
    if confirmed_from is not None:
        confirmed = {r["issue"] for r in confirmed_from.get("requests", []) if r.get("state") == "accepted"}
        for i in issues:
            if i["number"] not in confirmed:
                i["labels"] = [lb for lb in i.get("labels", []) if lb.get("name") != "accepted"]
    for i in issues:
        i["close_reason"] = None
        if i.get("state") == "closed" and not _names(i) & {"accepted", "invalid"}:
            i["close_reason"] = _close_reason(repo, i["number"], runner)
    return issues


def main(argv=None, runner=run_gh) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", required=True)
    p.add_argument("--confirmed-from", help="requests.json; drop `accepted` labels it does not confirm")
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
