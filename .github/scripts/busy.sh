#!/usr/bin/env bash
# Usage: busy.sh
# Prints `busy` if another lake-accept.yml or refresh.yml run is queued, waiting or in progress, else `idle`.
# Asked before an accept is started for a waiting request (the publish drain steps, and reconcile's dispatch
# in apply-actions.sh): only one accept can wait in the `sartale-rebuild` queue, so a start while another
# accept or refresh is active would push that one out or duplicate it. The active run's own drain step, or
# the daily check, starts the waiting accept later. A failed lookup prints `busy` (fail safe).
# The JSON goes to files and is parsed by busy.py; the shell never reads it.
set -uo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

for workflow in lake-accept.yml refresh.yml; do
  if ! gh run list --repo "${GITHUB_REPOSITORY:-}" --workflow "$workflow" --json databaseId,status \
      --limit 100 > "$work/$workflow.json"; then
    echo "busy.sh: could not list the runs of $workflow; counting them as active" >&2
    echo busy
    exit 0
  fi
done
python3 "$here/busy.py" "$work/lake-accept.yml.json" "$work/refresh.yml.json" || echo busy
