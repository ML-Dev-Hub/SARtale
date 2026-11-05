"""Lake requests as GitHub issues: parse the issue form, check each request, keep requests.json, act per issue.

Issue text is untrusted. Nothing here runs it, and no comment repeats it: reasons come from fixed messages,
the names of lakes the team already watches, or an issue number.
"""
import json
import math
import os
import re
from pathlib import Path

import requests

from sartale.config import MIN_LOOKS
from sartale.lake_requests import MAX_OPEN, RequestError, _text, coverage, validate
from sartale.lakes import Lake

FIELDS = {"Lake name": "name", "Latitude (°N)": "lat", "Longitude (°E)": "lon",
          "Where the coordinates come from": "source"}
STATE_LABELS = {"searched": "searched", "too_few_passes": "too few passes", "invalid": "invalid",
                "check_failed": "rebuild failed", "rejected": "rejected"}
CHECKED = ("searched", "too_few_passes")
CATALOGUE_DOWN = "The NASA catalogue did not answer."
_COORD = re.compile(r"^([+-]?\d+(?:\.\d+)?)\s*°?\s*[NnEe]?$")


def parse_issue_body(body: str) -> dict[str, str]:
    """Read an issue-form body (`### <label>` sections) into name, lat, lon and source."""
    sections, label = {}, None
    for line in (body or "").replace("\r\n", "\n").split("\n"):
        if line.startswith("### "):
            label = line[4:].strip()
            sections[label] = []
        elif label is not None:
            sections[label].append(line)
    if not all(label in sections for label in FIELDS):
        raise RequestError("This request was not made with the Add a lake form. "
                           "Open the form from the SARtale site and fill in every field.")
    out = {}
    for label, key in FIELDS.items():
        value = "\n".join(sections[label]).strip()
        out[key] = "" if value == "_No response_" else value
    return out


def _coord(text: str) -> str:
    """`36.2°N` and `74.0 °E` read as numbers; anything else is left for validate to refuse."""
    m = _COORD.match(text.strip())
    return m.group(1) if m else text


def _number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _labels(issue: dict) -> set[str]:
    return {label["name"] for label in issue.get("labels", [])}


def _entry(issue: dict, name, lat, lon, state: str, reason: str | None = None, found: dict | None = None) -> dict:
    found = found or {}
    return {"issue": issue["number"], "name": name, "lat": lat, "lon": lon, "state": state,
            "passes": found.get("passes"), "tracks": found.get("tracks", []),
            "first": found.get("first"), "last": found.get("last"), "reason": reason,
            "lake_id": None, "created": issue["created_at"]}


def _found(entry: dict) -> dict:
    return {k: entry[k] for k in ("passes", "tracks", "first", "last")}


def _check(issue: dict, watched: list[Lake], claimed: list[dict], open_count: int, before: dict | None,
           search) -> dict:
    """Parse, validate, apply the cap, then count passes. A catalogue error gives `check_failed`."""
    name, lat, lon = f"Request #{issue['number']}", None, None
    try:
        fields = parse_issue_body(issue.get("body", ""))
        fields["lat"], fields["lon"] = _coord(fields["lat"]), _coord(fields["lon"])
        name = (fields["name"] or name)[:80]
        lat, lon = _number(fields["lat"]), _number(fields["lon"])
        clean = validate(fields, watched, claimed)
    except RequestError as e:
        return _entry(issue, name, lat, lon, "invalid", str(e))
    name, lat, lon = clean["name"], clean["lat"], clean["lon"]
    if open_count >= MAX_OPEN:
        return _entry(issue, name, lat, lon, "invalid", "The request list is full; try again later.")
    if (before and before["state"] in CHECKED and before["lat"] == lat and before["lon"] == lon
            and before["name"] == name):
        return {**before, "created": issue["created_at"]}
    try:
        found = search(lat, lon)
    except (OSError, TimeoutError, requests.RequestException):
        return _entry(issue, name, lat, lon, "check_failed", CATALOGUE_DOWN)
    state = "searched" if found["passes"] >= MIN_LOOKS else "too_few_passes"
    return _entry(issue, name, lat, lon, state, None, found)


def build_feed(issues: list[dict], watched: list[Lake], previous: dict | None, search=coverage,
               now: str = "") -> dict:
    """Recompute the whole request list from every `lake-request` issue, oldest issue first, newest listed first."""
    before = {r["issue"]: r for r in (previous or {}).get("requests", [])}
    entries, claimed, open_count = [], [], 0
    for issue in sorted(issues, key=lambda i: i["number"]):
        number, old, labels = issue["number"], before.get(issue["number"]), _labels(issue)
        if old and old["state"] == "accepted":
            entry = dict(old)  # edits after approval are ignored
        elif issue["state"] == "closed" and "accepted" not in labels:
            if "invalid" in labels:
                entry = _entry(issue, (old or {}).get("name") or f"Request #{number}",
                               (old or {}).get("lat"), (old or {}).get("lon"), "invalid",
                               (old or {}).get("reason") or "The request was closed as not valid.")
            else:
                entry = _entry(issue, (old or {}).get("name") or f"Request #{number}",
                               (old or {}).get("lat"), (old or {}).get("lon"), "rejected",
                               None, _found(old) if old else None)
        elif "accepted" in labels and (old is None or old["state"] in CHECKED):
            entry = dict(old) if old else _check(issue, watched, claimed, 0, None, search)
            if entry["state"] in CHECKED:
                entry["state"] = "accepted"  # the values stay those of the last check
        else:
            entry = _check(issue, watched, claimed, open_count, old, search)
        entries.append(entry)
        if entry["state"] == "accepted" or (issue["state"] == "open" and entry["state"] in CHECKED + ("check_failed",)):
            if entry["lat"] is not None and entry["lon"] is not None:
                claimed.append({"name": f"issue #{number}", "lat": entry["lat"], "lon": entry["lon"]})
        if issue["state"] == "open" and entry["state"] in CHECKED + ("check_failed",):
            open_count += 1
    entries.sort(key=lambda e: e["issue"], reverse=True)
    return {"updated": now, "requests": entries}


def _find(feed: dict, number: int) -> dict | None:
    return next((r for r in feed["requests"] if r["issue"] == number), None)


def issue_actions(feed: dict, number: int, previous_state: str | None) -> dict:
    """Comment, labels and close for one issue. Nothing when its state did not change."""
    entry = _find(feed, number)
    if entry is None or entry["state"] == previous_state:
        return {"comment": None, "add": [], "remove": [], "close": False}
    state = entry["state"]
    comment = None
    if state == "searched":
        tracks = len(entry["tracks"])
        comment = (f"Checked against NASA's catalogue: {entry['passes']} NISAR passes over this point on "
                   f"{tracks} {'track' if tracks == 1 else 'tracks'}, {entry['first']} to {entry['last']}. "
                   "The team decides whether this lake is watched.")
    elif state == "too_few_passes":
        comment = (f"Checked against NASA's catalogue: {entry['passes']} NISAR passes over this point, fewer than "
                   f"the {MIN_LOOKS} needed for a trend. The team still decides whether this lake is watched.")
    elif state == "invalid":
        comment = f"This request cannot be used. {entry['reason']}"
    elif state == "check_failed":
        comment = f"{CATALOGUE_DOWN} The team will retry."
    elif state == "accepted" and entry.get("lake_id"):
        comment = f"This lake is now watched: #lakes/{entry['lake_id']}"
    label = STATE_LABELS.get(state)
    return {"comment": comment, "add": [label] if label else [],
            "remove": [v for k, v in STATE_LABELS.items() if k != state],
            "close": state == "invalid"}


def accept_entry(feed: dict, issue: dict, lakes_in: Path, today: str) -> str:
    """Add the requested lake to lakes_in.json using the values the last check recorded. Safe to repeat."""
    from sartale.run_pipeline import append_lake_entry, lake_slug  # run_pipeline imports this module

    number = issue["number"]
    entry = _find(feed, number)
    if entry is None or entry["state"] not in CHECKED + ("accepted",):
        raise RequestError(f"Issue #{number} has no checked request that can be accepted.", 409)
    lakes_in = Path(lakes_in)
    rows = json.loads(lakes_in.read_text(encoding="utf-8"))
    marker = f"(issue #{number})"
    same = next((r for r in rows if marker in r.get("coord_source", "")), None)
    if same is None:
        source = _text(parse_issue_body(issue.get("body", "")), "source", 3, 200)
        lake = {"id": lake_slug(entry["name"], {r["id"] for r in rows}), "name": entry["name"],
                "lon": entry["lon"], "lat": entry["lat"], "role": "watch",
                "coord_source": f"Requested {today} {marker}: {source}",
                "outline": None, "downstream": None, "downstream_source": None}
        append_lake_entry(lakes_in, lake)
        same = lake
    entry["state"], entry["lake_id"] = "accepted", same["id"]
    return same["id"]


def write_feed(feed: dict, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(feed, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)
