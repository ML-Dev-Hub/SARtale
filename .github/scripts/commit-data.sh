#!/usr/bin/env bash
# Usage: commit-data.sh "<fixed message>" <paths...>
# Commits the given paths as github-actions[bot] (no trailer) if they changed, rebases on origin/main and
# pushes (3 attempts), then starts deploy.yml, since pushes made with GITHUB_TOKEN start no workflow.
#
# The checkout keeps no credential (persist-credentials: false). GH_TOKEN, set only on the step that runs
# this script, is handed to git for the pull and the push alone, through GIT_CONFIG_* variables: never in
# .git/config, never on a command line.
#
# Writes pushed=true to $GITHUB_OUTPUT once the push went through, and deploy_failed=true if the deploy
# could not be started (exit 1). Exits 1 if all three pushes fail.
set -euo pipefail

message="$1"
shift

output() {
  if [ -n "${GITHUB_OUTPUT:-}" ]; then echo "$1" >> "$GITHUB_OUTPUT"; fi
}

with_token() {
  if [ -n "${GH_TOKEN:-}" ]; then
    local header
    header="AUTHORIZATION: basic $(printf 'x-access-token:%s' "$GH_TOKEN" | base64 | tr -d '\n')"
    GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=http.https://github.com/.extraheader GIT_CONFIG_VALUE_0="$header" "$@"
  else
    "$@"
  fi
}

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

git add -- "$@"
if git diff --cached --quiet; then
  echo "commit-data: no changes in $*"
  exit 0
fi
git commit --quiet -m "$message"

wait_s="${COMMIT_DATA_WAIT:-15}"
attempt=1
until with_token git pull --rebase origin main && with_token git push origin HEAD:main; do
  echo "commit-data: push attempt $attempt failed" >&2
  git rebase --abort >/dev/null 2>&1 || true
  if [ "$attempt" -ge 3 ]; then
    exit 1
  fi
  attempt=$((attempt + 1))
  sleep $((wait_s * attempt))
done
echo "commit-data: pushed $(git rev-parse --short HEAD) to main"
output "pushed=true"

if ! gh workflow run deploy.yml --ref main; then
  echo "commit-data: the data are on main, but deploy.yml did not start" >&2
  output "deploy_failed=true"
  exit 1
fi
