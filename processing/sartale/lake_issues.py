"""Lake requests as GitHub issues: parse the issue form, check each request, keep requests.json, act per issue.

Issue text is untrusted. Nothing here runs it, and no comment repeats it: reasons come from fixed messages,
the names of lakes the team already watches, or an issue number.
"""
import hashlib
import json
import math
import os
import re
import unicodedata
from pathlib import Path

import requests

from sartale.accept_queue import CHECKED, next_accept
from sartale.config import MIN_LOOKS
from sartale.lake_requests import MAX_OPEN, RequestError, _text, banned_name_message, coverage, validate
from sartale.lakes import Lake

FIELDS = {"Lake name": "name", "Latitude (°N)": "lat", "Longitude (°E)": "lon",
          "Where the coordinates come from": "source"}
STATE_LABELS = {"searched": "searched", "too_few_passes": "too few passes", "invalid": "invalid",
                "check_failed": "rebuild failed", "rejected": "rejected"}
FORM_CHANGED = "The request form was changed; open a new request from the SARtale site."
CATALOGUE_DOWN = "NASA's catalogue did not answer; the team will retry."
CHANGED_AFTER_APPROVAL = "This request changed after it was approved. A team member must accept it again."
APPROVED_BEFORE_HASHES = ("This request was approved before the new check existed. "
                          "A team member must accept it again.")
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
        raise RequestError(FORM_CHANGED)
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


def _entry(issue: dict, name, lat, lon, state: str, reason: str | None = None, found: dict | None = None,
           values: tuple[str | None, str | None] = (None, None)) -> dict:
    found = found or {}
    return {"issue": issue["number"], "name": name, "lat": lat, "lon": lon, "state": state,
            "passes": found.get("passes"), "tracks": found.get("tracks", []),
            "first": found.get("first"), "last": found.get("last"), "reason": reason,
            "lake_id": None, "created": issue["created_at"], "values_sha256": values[0], "values_at": values[1]}


def values_sha256(name: str, lat: float, lon: float, source: str) -> str:
    """SHA-256 of the checked values (name, lat, lon, source) after the check's normalisation, joined by newlines.

    The team approves these values; an approval stands only while the issue still hashes the same.
    """
    text = "\n".join([name, repr(float(lat)), repr(float(lon)), source])
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def issue_values_sha256(issue: dict) -> str | None:
    """The hash of an issue's current values, or None when they do not pass the field rules."""
    try:
        fields = parse_issue_body(issue.get("body", ""))
        name, source = _text(fields, "name", 2, 80), _text(fields, "source", 3, 200)
    except RequestError:
        return None
    lat, lon = _number(_coord(fields["lat"])), _number(_coord(fields["lon"]))
    if lat is None or lon is None:
        return None
    return values_sha256(name, lat, lon, source)


def _values(digest: str, before: dict | None, now: str) -> tuple[str, str]:
    """The hash and the time these values were first recorded (kept while the hash stays the same)."""
    if before and before.get("values_sha256") == digest and before.get("values_at"):
        return digest, before["values_at"]
    return digest, now


def _clean_reason(text: str | None) -> str | None:
    """The team's closing comment, without control or invisible formatting characters, at most 200 characters."""
    if not text:
        return None
    kept = "".join(ch for ch in text if unicodedata.category(ch) not in ("Cc", "Cf")).strip()
    return kept[:200] or None


def _found(entry: dict) -> dict:
    return {k: entry[k] for k in ("passes", "tracks", "first", "last")}


def _check(issue: dict, watched: list[Lake], claimed: list[dict], open_count: int, before: dict | None,
           search, now: str = "") -> dict:
    """Parse, validate, apply the cap, then count passes. A catalogue error gives `check_failed`."""
    name, lat, lon = f"Request #{issue['number']}", None, None
    try:
        fields = parse_issue_body(issue.get("body", ""))
        fields["lat"], fields["lon"] = _coord(fields["lat"]), _coord(fields["lon"])
        try:
            text = _text(fields, "name", 2, 80)  # only text that passes the name rules reaches requests.json
            if banned_name_message(text) is None:
                name = text
        except RequestError:
            pass
        lat, lon = _number(fields["lat"]), _number(fields["lon"])
        clean = validate(fields, watched, claimed)
    except RequestError as e:
        return _entry(issue, name, lat, lon, "invalid", str(e))
    name, lat, lon = clean["name"], clean["lat"], clean["lon"]
    if open_count >= MAX_OPEN:
        return _entry(issue, name, lat, lon, "invalid", "The request list is full; try again later.")
    values = _values(values_sha256(name, lat, lon, clean["source"]), before, now)
    if (before and before["state"] in CHECKED and before["lat"] == lat and before["lon"] == lon
            and before["name"] == name):
        return {**before, "created": issue["created_at"], "values_sha256": values[0], "values_at": values[1]}
    try:
        found = search(lat, lon)
    except (OSError, TimeoutError, requests.RequestException):
        return _entry(issue, name, lat, lon, "check_failed", CATALOGUE_DOWN, values=values)
    state = "searched" if found["passes"] >= MIN_LOOKS else "too_few_passes"
    return _entry(issue, name, lat, lon, state, None, found, values)


def build_feed(issues: list[dict], watched: list[Lake], previous: dict | None, search=None,
               now: str = "") -> dict:
    """Recompute the whole request list from every `lake-request` issue, oldest issue first, newest listed first."""
    search = search or coverage  # looked up at call time so tests can replace it
    before = {r["issue"]: r for r in (previous or {}).get("requests", [])}
    entries, claimed, open_count = [], [], 0
    for issue in sorted(issues, key=lambda i: i["number"]):
        number, old, labels = issue["number"], before.get(issue["number"]), _labels(issue)
        if old and old["state"] == "accepted":
            entry = dict(old)  # edits after approval are ignored
        elif issue["state"] == "closed":  # not accepted by the accept job, whatever its labels say
            if "invalid" in labels:
                entry = _entry(issue, (old or {}).get("name") or f"Request #{number}",
                               (old or {}).get("lat"), (old or {}).get("lon"), "invalid",
                               (old or {}).get("reason") or "The request was closed as not valid.")
            else:
                entry = _entry(issue, (old or {}).get("name") or f"Request #{number}",
                               (old or {}).get("lat"), (old or {}).get("lon"), "rejected",
                               _clean_reason(issue.get("close_reason")), _found(old) if old else None)
        else:  # an `accepted` label alone changes nothing: only accept_entry, after the permission check, does
            entry = _check(issue, watched, claimed, open_count, old, search, now)
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
    label = STATE_LABELS.get(state)
    return {"comment": _comment(entry), "add": [label] if label else [],
            "remove": [v for k, v in STATE_LABELS.items() if k != state],
            "close": state == "invalid"}


def _comment(entry: dict) -> str | None:
    state, comment = entry["state"], None
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
        comment = CATALOGUE_DOWN
    return comment


def reconcile_actions(feed: dict, issues: list[dict], previous: dict | None) -> list[dict]:
    """Actions for every issue whose labels disagree with its entry in the feed.

    The state label is the "already told" marker: the comment goes out only together with a missing state label,
    so a lost comment is sent again on the next run and a delivered one never twice. Stale state labels are
    removed, an open invalid request is closed, and an open checked request that carries `accepted` but is not
    accepted in the feed is marked for a new accept run (`dispatch`) unless a rebuild already failed for it.
    `rebuild failed` stays on a checked request (it marks a failed accept) unless the last check had failed.
    """
    old = {r["issue"]: r for r in (previous or {}).get("requests", [])}
    rows = []
    for issue in sorted(issues, key=lambda i: i["number"]):
        number, labels = issue["number"], _labels(issue)
        entry = _find(feed, number)
        if entry is None:
            continue
        was = old.get(number) or {}
        # an approval covers the values the team saw: an edit since the last check voids it, and so does an
        # approval given while requests.json had no hashes yet (nothing to compare with)
        pending = "accepted" in labels and entry["state"] != "accepted" and issue["state"] == "open"
        migrated = pending and bool(was) and "values_sha256" not in was
        void = migrated or (pending and was.get("values_sha256") is not None
                            and entry.get("values_sha256") != was["values_sha256"])
        rows.append((issue, labels, entry, was, migrated, void))
    # one dispatch per run, so the next does not replace a pending one; same choice as the publish drain step
    chosen = next_accept(feed, issues, exclude={r[0]["number"] for r in rows if r[5]})
    out = []
    for issue, labels, entry, was, migrated, void in rows:
        number, state = issue["number"], entry["state"]
        want = STATE_LABELS.get(state)  # None for accepted: the team's own label stays
        keep = {want}
        if state in CHECKED and was.get("state", state) != "check_failed":
            keep.add("rebuild failed")
        add = [want] if want and want not in labels else []
        remove = [v for v in STATE_LABELS.values() if v not in keep and v in labels]
        close = state == "invalid" and issue["state"] == "open"
        if void:
            remove.append("accepted")
        dispatch = number == chosen
        comment = _comment(entry) if add else None
        if void:
            reason = APPROVED_BEFORE_HASHES if migrated else CHANGED_AFTER_APPROVAL
            comment = reason + (f"\n\n{comment}" if comment else "")
        if add or remove or close or dispatch:
            out.append({"issue": number, "comment": comment, "add": add,
                        "remove": remove, "close": close, "dispatch": dispatch})
    return out


def accept_entry(feed: dict, issue: dict, lakes_in: Path, today: str, approved_at: str | None = None) -> str:
    """Add the requested lake to lakes_in.json using the values the last check recorded. Safe to repeat.

    Refused when the issue no longer hashes to the checked values, or when the approval (`approved_at`, the time
    the team added `accepted`) is older than the time those values were recorded.
    """
    from sartale.run_pipeline import append_lake_entry, lake_slug  # run_pipeline imports this module

    number = issue["number"]
    entry = _find(feed, number)
    if entry is None or entry["state"] not in CHECKED + ("accepted",):
        raise RequestError(f"Issue #{number} has no checked request that can be accepted.", 409)
    if "values_sha256" not in entry:
        raise RequestError(APPROVED_BEFORE_HASHES, 409)  # checked by the previous version
    if not entry["values_sha256"] or issue_values_sha256(issue) != entry["values_sha256"]:
        raise RequestError(CHANGED_AFTER_APPROVAL, 409)
    if approved_at is not None and approved_at < (entry.get("values_at") or ""):
        raise RequestError(CHANGED_AFTER_APPROVAL, 409)
    lakes_in = Path(lakes_in)
    rows = json.loads(lakes_in.read_text(encoding="utf-8"))
    marker = f"(issue #{number}):"
    ours = re.compile(rf"^Requested \S+ {re.escape(marker)} ")  # the prefix written below, not source text
    same = next((r for r in rows if ours.match(r.get("coord_source", ""))), None)
    if same is None:
        source = _text(parse_issue_body(issue.get("body", "")), "source", 3, 200)
        lake = {"id": lake_slug(entry["name"], {r["id"] for r in rows}), "name": entry["name"],
                "lon": entry["lon"], "lat": entry["lat"], "role": "watch",
                "coord_source": f"Requested {today} {marker} {source}",
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
