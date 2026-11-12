"""SARtale Lake Watch pipeline CLI: lakes-search, lakes-fetch, lakes-build, lakes-check, lakes-absence, lakes-freeze,
lakes-elevation, lakes-diff, lake-issues, lake-issue-accept."""
import argparse
import json
import os
import re
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from sartale.lake_catalog import Pass, coverage_report, search_lake_passes, select_lake_passes
from sartale.lakebuild import (
    PASSES_JSON,
    apply_absence,
    attabad_gate,
    build_lakes,
    carried_absence,
    read_listed,
    unlisted_windows,
)
from sartale.lakecheck import check_lake
from sartale.lake_requests import RequestError
from sartale.lakes import load_lakes
from sartale.remote import fetch_lake_passes

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cmd_lakes_search(args) -> None:
    """Search CMR for the passes over every lake, write passes.json, print one coverage line per lake."""
    lakes = load_lakes(Path(args.lakes_in))
    passes = {lake.id: select_lake_passes(search_lake_passes(lake)) for lake in lakes}
    doc = {
        "searched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lakes": {lid: {k: [asdict(p) for p in v] for k, v in by_key.items()} for lid, by_key in passes.items()},
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    for row in coverage_report(lakes, passes):
        tracks = ", ".join(f"{k} x{n}" for k, n in sorted(row["tracks"].items())) or "no passes"
        print(f"{row['id']} ({row['role']}): {tracks}; enough looks: {'yes' if row['enough_looks'] else 'no'}")
    print(f"{len(lakes)} lakes -> {out}")
    if lakes and not any(by_key for by_key in passes.values()):
        print("lakes-search found no pass for any lake: the catalogue is probably down or has moved; stopping",
              file=sys.stderr)
        sys.exit(1)


def fetch_all(lakes, doc: dict, out: Path, session, fetch=fetch_lake_passes) -> list[str]:
    """Fetch pass by pass so one persistent failure does not stop the run. Returns one note per failed pass."""
    import time

    failures, total, t0 = [], 0.0, time.time()
    for lake in lakes:
        if lake.id not in doc:
            print(f"{lake.id}: not in passes.json, run lakes-search first")
            continue
        passes = [Pass(**row) for rows in doc[lake.id].values() for row in rows]
        stats: dict = {}
        cached = 0
        for p in passes:
            try:
                cached += len(fetch(lake, [p], out, session, stats))
            except Exception as e:  # noqa: BLE001 - keep going; the summary lists it
                note = f"{lake.id} {p.date} {p.key}: {type(e).__name__}"  # no URL: it is signed
                failures.append(note)
                print(f"FAILED {note}", flush=True)
        mb = stats.get("fetched", 0) / 1e6
        total += mb
        print(f"{lake.id}: {cached}/{len(passes)} passes cached, {mb:.1f} MB fetched, {stats.get('requests', 0)} requests", flush=True)
    print(f"total {total:.1f} MB in {time.time() - t0:.0f} s")
    if failures:
        print(f"{len(failures)} passes failed (rerun lakes-fetch to retry):")
        for n in failures:
            print(f"  {n}")
    return failures


def cmd_lakes_fetch(args) -> None:
    """Cache a window for every selected pass of every lake in the register (restartable)."""
    import sys

    import requests

    lakes = load_lakes(Path(args.lakes_in))
    doc = json.loads(Path(args.passes).read_text(encoding="utf-8"))["lakes"]
    if fetch_all(lakes, doc, Path(args.out), requests.Session()):
        sys.exit(1)


def write_json_atomic(path: Path, doc) -> None:
    """Write JSON to `path` via a .tmp file and an atomic replace, so a crash never leaves half a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, allow_nan=False), encoding="utf-8")
    os.replace(tmp, path)


def prune_lake_images(out: Path, doc: dict) -> list[Path]:
    """Delete files and folders under `out`/lakes/ that lakes.json no longer references. Touches nothing else.
    Returns what was removed."""
    root = (Path(out) / "lakes").resolve()
    if not root.is_dir():
        return []
    keep = set()
    for lk in doc["lakes"]:
        for key in ("latest_hh", "water"):
            rel = (lk.get("images") or {}).get(key)
            if rel:
                keep.add((Path(out) / rel).resolve())
    keep_dirs = {k.parent for k in keep}
    removed = []
    for item in sorted(root.rglob("*"), key=lambda q: len(q.parts), reverse=True):
        r = item.resolve()
        if root not in r.parents:
            continue
        if item.is_file() and r not in keep:
            item.unlink()
            removed.append(item)
        elif item.is_dir() and r not in keep_dirs and not any(item.iterdir()):
            item.rmdir()
            removed.append(item)
    return removed


def cmd_lakes_build(args) -> None:
    lakes = load_lakes(Path(args.lakes_in))
    out = Path(args.out)
    built = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    checks_path = Path(args.checks)
    checks = json.loads(checks_path.read_text(encoding="utf-8")) if checks_path.is_file() else []
    listed = read_listed(Path(args.cache) / PASSES_JSON)
    if listed is None:
        print(f"no {Path(args.cache) / PASSES_JSON}: run lakes-search first (the build uses only the passes it lists)",
              file=sys.stderr)
        sys.exit(1)
    for lake in lakes:
        gone = unlisted_windows(Path(args.cache) / lake.id, listed.get(lake.id, set()))
        if gone:
            print(f"{lake.id}: ignoring {len(gone)} cached window(s) the catalogue no longer lists: {', '.join(gone)}")
    previous_path = Path(args.previous) if args.previous else out / "lakes.json"
    previous = _read_json(previous_path) if previous_path.is_file() else None
    doc = build_lakes(lakes, Path(args.cache), out, built, checks, previous=previous)
    write_json_atomic(out / "lakes.json", doc)
    for gone in prune_lake_images(out, doc):
        print(f"removed stale {gone.relative_to(out)}")
    for lk in doc["lakes"]:
        st = lk["status"]
        print(f"{lk['id']}: {st['status']}, looks {st['looks']}, cloud-window looks {lk['cloud_window_looks']}, "
              f"track {st['track']}, latest {st['latest_date']}, directions {''.join(lk['directions']) or '-'}, "
              f"excluded {len(lk['excluded'])}, limits {lk['limits']}")
    g = attabad_gate(doc)
    for k, v in g["tracks"].items():
        print(f"gate track {k}: attabad {v['attabad']:.3f} km2, shisper {v['shisper']:.3f} km2, ratio {v['ratio']:.2f}")
    print(f"gate: median ratio {g['median_ratio']} (need >= 2), attabad status {g['attabad_status']}, "
          f"cloud-window looks {g['attabad_cloud_window_looks']} (need >= 3): {'PASS' if g['pass'] else 'FAIL'}")
    print(f"{len(doc['lakes'])} lakes -> {out / 'lakes.json'}")
    if not g["pass"]:
        if args.allow_gate_fail:
            print("Attabad gate FAILED; continuing because --allow-gate-fail was given")
        else:
            print("Attabad gate FAILED: lakes.json was written for inspection; do not ship it "
                  "(pass --allow-gate-fail to exit 0)")
            sys.exit(1)


def check_ids(lakes, chosen: str | None) -> list[str]:
    """The lake ids to check: the comma-separated `chosen`, or by default every register lake that holds a lake now
    (a site with lake_state "no_lake" has no lake to compare)."""
    if chosen:
        return [x.strip() for x in chosen.split(",") if x.strip()]
    return [lk.id for lk in lakes if lk.lake_state != "no_lake"]


def cmd_lakes_check(args) -> None:
    """Compare the radar water of chosen lakes with Sentinel-2 MNDWI water; write the rows and merge
    them into lakes.json (the lakes themselves are not rebuilt)."""
    lakes = {lk.id: lk for lk in load_lakes(Path(args.lakes_in))}
    path = Path(args.out) / "lakes.json"
    doc = _read_json(path)
    rows = []
    for lid in check_ids(list(lakes.values()), args.lakes):
        series = next(lk["series"] for lk in doc["lakes"] if lk["id"] == lid)
        row = check_lake(lakes[lid], Path(args.cache), series)
        rows.append(row)
        if "note" in row:
            print(f"{lid}: {row['note']}")
        else:
            print(f"{lid}: NISAR {row['nisar_date']} {row['nisar_track']} vs S2 {row['s2_date']} {row['s2_id']} | "
                  f"zone radar {row['radar_km2']:.3f} km2, optical {row['optical_km2']:.3f} km2, "
                  f"error {row['area_error_pct'] if row['area_error_pct'] is None else round(row['area_error_pct'], 1)} %, "
                  f"IoU {row['iou'] if row['iou'] is None else round(row['iou'], 3)} | window radar {row['window_radar_km2']:.3f}, "
                  f"optical {row['window_optical_km2']:.3f}, IoU {row['window_iou']}")
    write_json_atomic(Path(args.checks), rows)
    doc["checks"] = rows
    write_json_atomic(path, doc)
    print(f"{len(rows)} checks -> {args.checks} and {path}")


def cmd_lakes_absence(args) -> None:
    """Re-check every site the register holds as "no lake now" with Sentinel-2, all year, and write the dated
    evidence into lakes.json (`absence_checked`): the newest scene whose lake zone is clear of cloud, snow and ice
    (`lakecheck.absence_check`). Water on more than the site's forming share turns it into "Lake may be forming".
    When no scene qualifies, or the search fails, the last evidence stands with the date of this search, and the
    site says that no clear, snow-free view has come since; neither fails the run.

    The rebuild runs it before lakes-build, on the published lakes.json, so the build that follows uses the new
    evidence (and keeps the radar water layer of a site where a lake may be forming). A site the published file does
    not list yet is skipped then; `--only-missing`, after the build, checks just the sites still without evidence."""
    from sartale.lakecheck import absence_check

    today = args.today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = Path(args.out) / "lakes.json"
    if not path.is_file():
        print(f"no {path}: nothing to re-check yet (lakes-build writes it)")
        return
    doc = _read_json(path)
    by_id = {lk["id"]: i for i, lk in enumerate(doc["lakes"])}
    for lake in load_lakes(Path(args.lakes_in)):
        if lake.lake_state != "no_lake":
            continue
        if lake.id not in by_id:
            print(f"{lake.id}: not in {path.name} yet; checked after the build")
            continue
        i = by_id[lake.id]
        prior = carried_absence(doc, lake)
        if args.only_missing and prior is not None:
            continue
        try:
            row = absence_check(lake, today, prior)
        except Exception as e:  # noqa: BLE001 - keep the last evidence; the app shows its date
            print(f"{lake.id}: absence check failed ({type(e).__name__}); the last evidence stands")
            row = prior
        doc["lakes"][i] = apply_absence(doc["lakes"][i], row)
        lk = doc["lakes"][i]
        ev = lk.get("absence_checked")
        when = "no evidence"
        if ev:
            when = f"{ev['date']} {ev['s2_id']} water {ev['water_share']:.4f} snow {ev['snow_share']:.4f}"
            if ev.get("no_view_since"):
                when += " (no clear, snow-free view since)"
            p = ev.get("pending_scene")
            if p:
                when += f"; one scene waits for a second: {p['date']} {p['s2_id']} water {p['water_share']:.4f}"
        print(f"{lake.id}: {lk['status']['status']} ({lk['lake_state']}); {when}")
    write_json_atomic(path, doc)


def freeze_line(lk: dict) -> str:
    """One log line on a lake's freeze state."""
    f = lk.get("freeze")
    if not f:
        return f"{lk['id']}: no freeze state ({lk.get('lake_state', 'lake')}); status {lk['status']['status']}"
    s2 = f.get("s2")
    seen = (f"S2 {s2['date']} {s2['s2_id']} clear {s2['clear_share']:.2f} snow {s2['snow_share']:.2f} "
            f"water {s2['water_share']:.2f}" if s2 else ("S2 none clear" if f.get("s2_searched") else "S2 not searched"))
    return (f"{lk['id']}: {f['state']} since {f.get('since') or '-'}; air to {f.get('temp_through') or '-'}, "
            f"cold run {f.get('cold_run_days')}, warm run {f.get('warm_run_days')}, FDD {f.get('fdd_since_sep')}, "
            f"7-day mean {f.get('t2m_mean_7d')} C; {seen}; frozen passes {f.get('frozen_passes', 0)}; "
            f"status {lk['status']['status']}")


def cmd_lakes_freeze(args) -> None:
    """Work out each lake's freeze state from NASA POWER air temperature at the lake's height (and a clear Sentinel-2
    scene for a cold lake), flag the passes taken while it was frozen, and set the statuses again in lakes.json. Runs
    after lakes-build, needs no login, and never fails the run for a failed download: the lake is then "not assessed"
    and keeps the usual assessment."""
    from sartale.freeze import freeze_lake

    today = args.today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = Path(args.out) / "lakes.json"
    if not path.is_file():
        print(f"no {path}: run lakes-build first")
        return
    doc = _read_json(path)
    by_id = {lk["id"]: i for i, lk in enumerate(doc["lakes"])}
    for lake in load_lakes(Path(args.lakes_in)):
        if lake.id not in by_id:
            continue
        i = by_id[lake.id]
        doc["lakes"][i] = freeze_lake(lake, doc["lakes"][i], today)
        print(freeze_line(doc["lakes"][i]), flush=True)
    write_json_atomic(path, doc)


def cmd_lakes_elevation(args) -> None:
    """Measure the lake surface height (Copernicus DEM GLO-30) of every register lake that has none yet and write it
    into lakes_in.json, once. The freeze check needs it."""
    from sartale.elevation import lake_elevation, set_elevation

    path = Path(args.lakes_in)
    for lake in load_lakes(path):
        if lake.elevation_m is not None:
            print(f"{lake.id}: {lake.elevation_m:g} m (already measured)")
            continue
        got = lake_elevation(lake)
        if got is None:
            print(f"{lake.id}: no Copernicus DEM value; the freeze check stays not assessed")
            continue
        set_elevation(path, lake.id, *got)
        print(f"{lake.id}: {got[0]} m ({got[1]})")


def cmd_lakes_diff(args) -> None:
    """Compare the previous lakes.json with the new one: print added and dropped passes per lake, write them to
    the job summary, warn for every dropped pass and backwards latest date, fail above the drop threshold."""
    from sartale.lakes_diff import diff_lakes, summary_markdown, text_report, warnings

    old_path = Path(args.old)
    if not old_path.is_file():
        print(f"no previous lakes.json at {old_path}; nothing to compare")
        return
    result = diff_lakes(_read_json(old_path), _read_json(Path(args.new)))
    print(text_report(result))
    for w in warnings(result):
        print(w)
    summary = args.summary or os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(summary_markdown(result))
    if result["fail"]:
        print(f"::error::{result['fail']}")
        sys.exit(1)


def lake_slug(name: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "lake"
    slug, n = base, 2
    while slug in taken:
        slug, n = f"{base}_{n}", n + 1
    return slug


def append_lake_entry(path: Path, entry: dict) -> None:
    """Insert one entry before the final `]` of lakes_in.json, touching nothing else but one comma."""
    text = Path(path).read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in text else "\n"
    close = text.rindex("]")
    last = len(text[:close].rstrip())
    if text[last - 1] != "}":
        raise ValueError(f"{path}: expected the last entry to end with }}")
    d = lambda v: json.dumps(v, ensure_ascii=False)  # noqa: E731
    keys = list(entry)
    first = ", ".join(f"{d(k)}: {d(entry[k])}" for k in keys[:5])
    second = ", ".join(f"{d(k)}: {d(entry[k])}" for k in keys[5:])
    new = text[:last] + "," + nl + "  {" + first + "," + nl + "   " + second + "}" + nl + text[close:]
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(new.encode("utf-8"))
    os.replace(tmp, path)


def cmd_lake_issues(args) -> None:
    """Recompute requests.json from every lake-request issue; write actions for every issue that needs one."""
    from sartale import lake_issues

    issues = _read_json(Path(args.issues))
    feed_path = Path(args.feed)
    previous = _read_json(feed_path) if feed_path.exists() else None
    feed = lake_issues.build_feed(issues, load_lakes(Path(args.lakes_in)), previous,
                                  now=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    lake_issues.write_feed(feed, feed_path)
    actions = lake_issues.reconcile_actions(feed, issues, previous)
    Path(args.actions).write_text(json.dumps(actions, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(feed['requests'])} requests; actions for issues {[a['issue'] for a in actions] or 'none'}")


def cmd_lake_issue_accept(args) -> None:
    from sartale import lake_issues

    issue = next((i for i in _read_json(Path(args.issues)) if i["number"] == args.issue), None)
    if issue is None:
        raise SystemExit(f"issue #{args.issue} is not in {args.issues}")
    feed_path = Path(args.feed)
    feed = _read_json(feed_path)
    try:
        lake_id = lake_issues.accept_entry(feed, issue, Path(args.lakes_in), args.today, args.approved_at)
    except RequestError as e:
        print(f"lake-issue-accept: {e}", file=sys.stderr)
        raise SystemExit(1) from None
    lake_issues.write_feed(feed, feed_path)
    actions = [{"issue": args.issue, "comment": lake_issues.ACCEPTED_COMMENT.format(lake_id=lake_id),
               "add": [], "remove": ["searched", "too few passes", "rebuild failed"], "close": True}]
    Path(args.actions).write_text(json.dumps(actions, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(lake_id)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="run_pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    k = sub.add_parser("lakes-search", help="search CMR for NISAR passes over each lake and report coverage")
    k.add_argument("--lakes-in", default=str(REPO_ROOT / "processing" / "lakes_in.json"))
    k.add_argument("--out", default=str(REPO_ROOT / "data" / "lakes" / "passes.json"))
    k.set_defaults(func=cmd_lakes_search)

    lf = sub.add_parser("lakes-fetch", help="cache a 6 km window per lake pass over HTTP range requests (restartable)")
    lf.add_argument("--lakes-in", default=str(REPO_ROOT / "processing" / "lakes_in.json"))
    lf.add_argument("--passes", default=str(REPO_ROOT / "data" / "lakes" / "passes.json"))
    lf.add_argument("--out", default=str(REPO_ROOT / "data" / "lakes"))
    lf.set_defaults(func=cmd_lakes_fetch)
    lb = sub.add_parser("lakes-build", help="build lakes.json and per-lake images from the cached windows")
    lb.add_argument("--lakes-in", default=str(REPO_ROOT / "processing" / "lakes_in.json"))
    lb.add_argument("--cache", default=str(REPO_ROOT / "data" / "lakes"))
    lb.add_argument("--out", default=str(REPO_ROOT / "app" / "public" / "data"))
    lb.add_argument("--checks", default=str(REPO_ROOT / "processing" / "lake_checks.json"),
                    help="rows written by lakes-check, merged into lakes.json when the file exists")
    lb.add_argument("--previous", default=None,
                    help="the lakes.json this build replaces, for each no-lake site's last absence check "
                         "(default: the lakes.json in --out)")
    lb.add_argument("--allow-gate-fail", action="store_true",
                    help="exit 0 even when the Attabad gate fails (default: exit 1)")
    lb.set_defaults(func=cmd_lakes_build)
    lc = sub.add_parser("lakes-check", help="compare radar lake water with Sentinel-2 MNDWI water")
    lc.add_argument("--lakes-in", default=str(REPO_ROOT / "processing" / "lakes_in.json"))
    lc.add_argument("--cache", default=str(REPO_ROOT / "data" / "lakes"))
    lc.add_argument("--out", default=str(REPO_ROOT / "app" / "public" / "data"), help="folder holding lakes.json")
    lc.add_argument("--checks", default=str(REPO_ROOT / "processing" / "lake_checks.json"))
    lc.add_argument("--lakes", default=None,
                    help="comma-separated lake ids (default: every register lake except those with no lake now)")
    lc.set_defaults(func=cmd_lakes_check)

    la = sub.add_parser("lakes-absence", help="re-check the sites with no lake now with Sentinel-2 (all year; clear, "
                                              "snow-free scenes only)")
    la.add_argument("--lakes-in", default=str(REPO_ROOT / "processing" / "lakes_in.json"))
    la.add_argument("--out", default=str(REPO_ROOT / "app" / "public" / "data"), help="folder holding lakes.json")
    la.add_argument("--today", default=None, help="YYYY-MM-DD (default: today, UTC)")
    la.add_argument("--only-missing", action="store_true",
                    help="check only the sites without carried evidence (after lakes-build, for new sites)")
    la.set_defaults(func=cmd_lakes_absence)

    lz = sub.add_parser("lakes-freeze", help="freeze state of each lake from NASA POWER air temperature (and Sentinel-2 "
                                             "for a cold lake); flags passes taken while frozen")
    lz.add_argument("--lakes-in", default=str(REPO_ROOT / "processing" / "lakes_in.json"))
    lz.add_argument("--out", default=str(REPO_ROOT / "app" / "public" / "data"), help="folder holding lakes.json")
    lz.add_argument("--today", default=None, help="YYYY-MM-DD (default: today, UTC)")
    lz.set_defaults(func=cmd_lakes_freeze)

    le = sub.add_parser("lakes-elevation", help="measure each lake's surface height once (Copernicus DEM) into "
                                                "lakes_in.json")
    le.add_argument("--lakes-in", default=str(REPO_ROOT / "processing" / "lakes_in.json"))
    le.set_defaults(func=cmd_lakes_elevation)

    ld = sub.add_parser("lakes-diff", help="compare a previous lakes.json with the new one, pass by pass")
    ld.add_argument("--old", required=True, help="the previously published lakes.json")
    ld.add_argument("--new", default=str(REPO_ROOT / "app" / "public" / "data" / "lakes.json"))
    ld.add_argument("--summary", help="Markdown file to append to (default: $GITHUB_STEP_SUMMARY when set)")
    ld.set_defaults(func=cmd_lakes_diff)

    li = sub.add_parser("lake-issues", help="turn lake-request issues into requests.json and the event issue's actions")
    li.add_argument("--issues", required=True, help="JSON list of every issue labelled lake-request")
    li.add_argument("--feed", default=str(REPO_ROOT / "app" / "public" / "data" / "requests.json"))
    li.add_argument("--lakes-in", default=str(REPO_ROOT / "processing" / "lakes_in.json"))
    li.add_argument("--event-issue", type=int, help="ignored; every issue is reconciled")
    li.add_argument("--actions", required=True, help="where to write the list of per-issue actions")
    li.set_defaults(func=cmd_lake_issues)
    lia = sub.add_parser("lake-issue-accept", help="add an approved request to lakes_in.json and print the lake id")
    lia.add_argument("--issues", required=True)
    lia.add_argument("--feed", default=str(REPO_ROOT / "app" / "public" / "data" / "requests.json"))
    lia.add_argument("--issue", type=int, required=True)
    lia.add_argument("--lakes-in", default=str(REPO_ROOT / "processing" / "lakes_in.json"))
    lia.add_argument("--today", required=True, help="YYYY-MM-DD")
    lia.add_argument("--approved-at", help="when the team added `accepted` (YYYY-MM-DDTHH:MM:SSZ)")
    lia.add_argument("--actions", required=True, help="where to write the comment, labels and close flag")
    lia.set_defaults(func=cmd_lake_issue_accept)
    return parser


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
