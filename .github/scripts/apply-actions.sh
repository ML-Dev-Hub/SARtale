#!/usr/bin/env bash
# Usage: apply-actions.sh <issue-number> <actions.json>
# Applies {"comment": str|null, "add": [labels], "remove": [labels], "close": bool} to one issue.
# The comment goes through a file (--body-file) and labels through quoted arguments; no command is
# ever built from text. Labels must be one of the seven SARtale labels.
set -euo pipefail

number="$1"
actions="$2"
case "$number" in
  ''|*[!0-9]*) echo "apply-actions: issue number must be digits" >&2; exit 2 ;;
esac

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

python3 - "$actions" "$work" <<'PY'
import json, sys
from pathlib import Path

ALLOWED = {"lake-request", "searched", "too few passes", "accepted", "rebuild failed", "invalid", "rejected"}
doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
out = Path(sys.argv[2])
for key in ("add", "remove"):
    labels = doc.get(key) or []
    bad = [x for x in labels if x not in ALLOWED]
    if bad:
        sys.exit(f"apply-actions: unknown label in {key!r}")
    (out / key).write_bytes("".join(x + "\n" for x in labels).encode("utf-8"))  # LF on any OS
if doc.get("comment"):
    (out / "comment").write_bytes(doc["comment"].encode("utf-8"))
(out / "close").write_bytes(b"yes" if doc.get("close") is True else b"no")
PY

if [ -f "$work/comment" ]; then
  gh issue comment "$number" --body-file "$work/comment"
fi

while IFS= read -r label; do
  if [ -n "$label" ]; then gh issue edit "$number" --add-label "$label"; fi
done < "$work/add"

if [ -s "$work/remove" ]; then
  gh issue view "$number" --json labels --jq '.labels[].name' > "$work/current"
  while IFS= read -r label; do
    if [ -n "$label" ] && grep -Fxq -- "$label" "$work/current"; then
      gh issue edit "$number" --remove-label "$label"
    fi
  done < "$work/remove"
fi

if [ "$(cat "$work/close")" = yes ]; then
  if grep -Fxq invalid "$work/add"; then
    gh issue close "$number" --reason "not planned"
  else
    gh issue close "$number"
  fi
fi
