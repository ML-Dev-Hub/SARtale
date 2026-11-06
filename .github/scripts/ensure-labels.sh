#!/usr/bin/env bash
# Creates (or updates) the seven SARtale lake request labels. Safe to run every time.
set -euo pipefail

gh label create "lake-request" --color 1d76db --description "A request to watch a new lake" --force
gh label create "searched" --color 0e8a16 --description "Checked: enough NISAR passes" --force
gh label create "too few passes" --color fbca04 --description "Checked: fewer NISAR passes than a trend needs" --force
gh label create "accepted" --color 5319e7 --description "The team accepts the lake (team only)" --force
gh label create "rebuild failed" --color d93f0b --description "The check or the rebuild failed; the team will retry" --force
gh label create "invalid" --color e4e669 --description "The request cannot be used" --force
gh label create "rejected" --color b60205 --description "The team closed the request" --force
