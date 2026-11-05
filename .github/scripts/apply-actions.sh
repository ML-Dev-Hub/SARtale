#!/usr/bin/env bash
# Usage: apply-actions.sh <actions.json>
# Applies a list of {"issue": n, "comment": str|null, "add": [labels], "remove": [labels], "close": bool,
# "dispatch": bool} to the issues. Comments go through a file (--body-file) and labels through quoted
# arguments; no command is ever built from text. Every entry is checked before anything is applied:
# issue numbers are positive integers and labels are among the seven SARtale labels.
# `dispatch` starts lake-accept.yml for that issue again (an accept run that GitHub dropped).
set -euo pipefail

actions="$1"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

python3 - "$actions" "$work" <<'PY'
import json, sys
from pathlib import Path

ALLOWED = {"lake-request", "searched", "too few passes", "accepted", "rebuild failed", "invalid", "rejected"}
doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
out = Path(sys.argv[2])
if not isinstance(doc, list):
    sys.exit("apply-actions: expected a list of actions")
for at, a in enumerate(doc):
    number = a.get("issue")
    if type(number) is not int or number <= 0:
        sys.exit(f"apply-actions: entry {at} has no valid issue number")
    for key in ("add", "remove"):
        if any(x not in ALLOWED for x in a.get(key) or []):
            sys.exit(f"apply-actions: unknown label in entry {at} {key!r}")
for at, a in enumerate(doc):
    d = out / f"{at:05d}"
    d.mkdir()
    (d / "issue").write_bytes(str(a["issue"]).encode())
    for key in ("add", "remove"):  # LF on any OS
        (d / key).write_bytes("".join(x + "\n" for x in a.get(key) or []).encode("utf-8"))
    if a.get("comment"):
        (d / "comment").write_bytes(a["comment"].encode("utf-8"))
    (d / "close").write_bytes(b"yes" if a.get("close") is True else b"no")
    (d / "dispatch").write_bytes(b"yes" if a.get("dispatch") is True else b"no")
PY

for d in "$work"/*/; do
  [ -d "$d" ] || continue
  number="$(cat "$d/issue")"
  case "$number" in
    ''|*[!0-9]*) echo "apply-actions: bad issue number" >&2; exit 2 ;;
  esac

  if [ -f "$d/comment" ]; then
    gh issue comment "$number" --body-file "$d/comment"
  fi

  while IFS= read -r label; do
    if [ -n "$label" ]; then gh issue edit "$number" --add-label "$label"; fi
  done < "$d/add"

  if [ -s "$d/remove" ]; then
    gh issue view "$number" --json labels --jq '.labels[].name' > "$d/current"
    while IFS= read -r label; do
      if [ -n "$label" ] && grep -Fxq -- "$label" "$d/current"; then
        gh issue edit "$number" --remove-label "$label"
      fi
    done < "$d/remove"
  fi

  if [ "$(cat "$d/close")" = yes ]; then
    if grep -Fxq invalid "$d/add" || [ ! -f "$d/comment" ]; then
      gh issue close "$number" --reason "not planned"
    else
      gh issue close "$number"
    fi
  fi

  if [ "$(cat "$d/dispatch")" = yes ]; then
    gh workflow run lake-accept.yml --ref main -f "issue=$number"
  fi
done
