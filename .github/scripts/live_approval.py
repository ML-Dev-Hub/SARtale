"""Re-read a lake-request issue live, immediately before an accepted lake is published, and check that the approval
still stands.

The rebuild takes a long time. In that time the author can edit or close the issue, or the team can take `accepted`
away or give it again. The publish job runs this script just before it commits, and publishes only on exit 0:

  - the issue is still open and carries `lake-request` and `accepted`;
  - the last account to add `accepted` is the same approver the gate checked, at the same time (within
    TIME_SLACK_S: for a label event the gate records the issue's update time, which GitHub sets with the event);
  - the issue's values (name, latitude, longitude, source) still hash to the values the rebuild used
    (`values_sha256` of the issue's entry in the rebuilt requests.json).

Otherwise it writes one fixed sentence (never issue text) to --why and exits 7. Any other failure (gh, a malformed
artifact) exits non-zero as well, so the check fails closed.

This script runs on the runner's own python3, without the `sartale` package, so it keeps a copy of the hash rule of
sartale.lake_issues.issue_values_sha256; test_workflow_scripts checks that the two agree.

Usage: python3 live_approval.py --issue N --approver LOGIN --approved-at T --from ARTIFACT_DIR --why FILE
"""

import argparse
import hashlib
import json
import math
import os
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

from approver import approval, NotWaiting
from fetch_issues import run_gh

CHANGED = 7
TIME_SLACK_S = 120
REQUESTS = "app/public/data/requests.json"
FIELDS = {"Lake name": "name", "Latitude (°N)": "lat", "Longitude (°E)": "lon",
          "Where the coordinates come from": "source"}
_COORD = re.compile(r"^([+-]?[0-9]+(?:\.[0-9]+)?)\s*°?\s*[NnEe]?$", re.ASCII)

NOT_OPEN = "This request was closed or lost the accepted label while the lake data were rebuilt, so nothing was published."
OTHER_APPROVAL = ("The approval of this request changed while the lake data were rebuilt (accepted was removed or "
                  "added again), so nothing was published. A team member can accept it again.")
EDITED = "This request changed after it was approved. A team member must accept it again."


# --- a copy of sartale.lake_issues.issue_values_sha256 (and the helpers it uses) ---------------------------------

def _parse(body: str) -> dict[str, str] | None:
    sections, label = {}, None
    for line in (body or "").replace("\r\n", "\n").split("\n"):
        if line.startswith("### "):
            label = line[4:].strip()
            sections[label] = []
        elif label is not None:
            sections[label].append(line)
    if not all(label in sections for label in FIELDS):
        return None
    out = {}
    for label, key in FIELDS.items():
        value = "\n".join(sections[label]).strip()
        out[key] = "" if value == "_No response_" else value
    return out


def _text(fields: dict, key: str, low: int, high: int) -> str | None:
    value = fields.get(key)
    text = value.strip() if isinstance(value, str) else ""
    if any(unicodedata.category(ch) in ("Cc", "Cf") for ch in text) or not low <= len(text) <= high:
        return None
    return text


def _number(text: str) -> float | None:
    m = _COORD.match((text or "").strip())
    if not m:
        return None
    try:
        n = float(m.group(1))
    except ValueError:
        return None
    return n if math.isfinite(n) else None


def issue_values_sha256(issue: dict) -> str | None:
    fields = _parse(issue.get("body") or "")
    if fields is None:
        return None
    name, source = _text(fields, "name", 2, 80), _text(fields, "source", 3, 200)
    lat, lon = _number(fields["lat"]), _number(fields["lon"])
    if name is None or source is None or lat is None or lon is None:
        return None
    text = "\n".join([name, repr(float(lat)), repr(float(lon)), source])
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- the check ----------------------------------------------------------------------------------------------------

def _when(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")


def built_values(artifact: Path, number: int) -> str:
    feed = json.loads((Path(artifact) / REQUESTS).read_text(encoding="utf-8"))
    entry = next((r for r in feed.get("requests", []) if r.get("issue") == number), None)
    digest = (entry or {}).get("values_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError(f"the rebuilt requests.json has no values hash for issue #{number}")
    return digest


def recheck(repo: str, number: int, approver: str, approved_at: str, values: str, runner=run_gh) -> str | None:
    """None when the approval still stands; else the fixed sentence that says why it does not."""
    try:
        found = approval(repo, number, runner)  # also checks: open, lake-request and accepted
    except NotWaiting:
        return NOT_OPEN
    if found is None:
        return OTHER_APPROVAL
    login, when = found
    if login != approver or abs((_when(when) - _when(approved_at)).total_seconds()) > TIME_SLACK_S:
        return OTHER_APPROVAL
    issue = json.loads(runner(["api", f"repos/{repo}/issues/{int(number)}"]))
    if issue_values_sha256(issue) != values:
        return EDITED
    return None


def main(argv=None, runner=run_gh) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--issue", type=int, required=True)
    p.add_argument("--approver", required=True)
    p.add_argument("--approved-at", required=True)
    p.add_argument("--from", dest="artifact", required=True)
    p.add_argument("--why", required=True)
    args = p.parse_args(argv)
    values = built_values(Path(args.artifact), args.issue)
    why = recheck(os.environ["GITHUB_REPOSITORY"], args.issue, args.approver, args.approved_at, values, runner)
    if why:
        Path(args.why).write_text(why + "\n", encoding="utf-8")
        print(f"issue #{args.issue}: {why}", file=sys.stderr)
        raise SystemExit(CHANGED)
    print(f"issue #{args.issue}: the approval still stands")


if __name__ == "__main__":
    main()
