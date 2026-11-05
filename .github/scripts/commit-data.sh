#!/usr/bin/env bash
# Usage: commit-data.sh "<fixed message>" <paths...>
# Commits the given paths as github-actions[bot] (no trailer) if they changed, rebases on origin/main and
# pushes (3 attempts), then starts deploy.yml, since pushes made with GITHUB_TOKEN start no workflow.
# Writes pushed=true to $GITHUB_OUTPUT once the push went through. Exits 1 if all three pushes fail.
set -euo pipefail

message="$1"
shift

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
until git pull --rebase origin main && git push origin HEAD:main; do
  echo "commit-data: push attempt $attempt failed" >&2
  git rebase --abort >/dev/null 2>&1 || true
  if [ "$attempt" -ge 3 ]; then
    exit 1
  fi
  attempt=$((attempt + 1))
  sleep $((wait_s * attempt))
done
echo "commit-data: pushed $(git rev-parse --short HEAD) to main"
if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "pushed=true" >> "$GITHUB_OUTPUT"
fi

gh workflow run deploy.yml --ref main
