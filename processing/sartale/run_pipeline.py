"""SARtale Lake Watch pipeline CLI: lakes-search, lakes-fetch, lakes-build, lakes-check, lake-requests-*."""
import argparse
import json
import os
import re
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from sartale.lake_catalog import Pass, coverage_report, search_lake_passes, select_lake_passes
from sartale.lakebuild import attabad_gate, build_lakes
from sartale.lakecheck import check_lake
from sartale.lake_requests import OPEN_STATES, RequestStore
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
    doc = build_lakes(lakes, Path(args.cache), out, built, checks)
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


def cmd_lakes_check(args) -> None:
    """Compare the radar water of chosen lakes with Sentinel-2 MNDWI water; write the rows and merge
    them into lakes.json (the lakes themselves are not rebuilt)."""
    lakes = {lk.id: lk for lk in load_lakes(Path(args.lakes_in))}
    path = Path(args.out) / "lakes.json"
    doc = _read_json(path)
    rows = []
    for lid in [x.strip() for x in args.lakes.split(",") if x.strip()]:
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

DEFAULT_DB = REPO_ROOT / "data" / "lake_requests.sqlite"


def _store(args) -> RequestStore:
    db = Path(args.db)
    db.parent.mkdir(parents=True, exist_ok=True)
    return RequestStore(db)


def _open_request(store: RequestStore, rid: int) -> dict:
    row = store.get(rid)
    if row is None:
        print(f"No request with id {rid}", file=sys.stderr)
        sys.exit(1)
    if row["state"] not in OPEN_STATES:
        print(f"Request {rid} is {row['state']}, not open", file=sys.stderr)
        sys.exit(1)
    return row


def cmd_lake_requests_serve(args) -> None:
    from sartale.requests_server import make_server

    store = _store(args)
    watched = load_lakes(REPO_ROOT / "processing" / "lakes_in.json")
    server = make_server(store, watched, host=args.host, port=args.port, allowed_origin=args.origin)
    print(f"Serving lake requests on http://{args.host}:{server.server_address[1]} (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopping")
    finally:
        server.server_close()


def cmd_lake_requests_list(args) -> None:
    rows = _store(args).list_open()
    for r in rows:
        print(f"{r['id']}: {r['name']} ({r['lat']}, {r['lon']}) [{r['state']}] source: {r['source']}")
        if r.get("detail"):
            print(f"    detail: {r['detail']}")
    print(f"{len(rows)} open requests")


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


def cmd_lake_requests_accept(args) -> None:
    store = _store(args)
    row = _open_request(store, args.id)
    lakes_in = Path(args.lakes_in)
    existing = _read_json(lakes_in)
    taken = {x["id"] for x in existing}
    entry = {"id": lake_slug(row["name"], taken), "name": row["name"], "lon": row["lon"], "lat": row["lat"],
             "role": args.role, "coord_source": f"Requested {row['created'][:10]}: {row['source']}",
             "outline": None, "downstream": None, "downstream_source": None}
    same = next((x for x in existing if x.get("name") == entry["name"] and x.get("coord_source") == entry["coord_source"]), None)
    if same:  # an earlier run wrote the entry but failed to mark the request: do not add a _2 duplicate
        store.set_state(args.id, "accepted")
        print(f"accepted {args.id}: {lakes_in} already has {same['id']}; nothing appended")
        return
    append_lake_entry(lakes_in, entry)
    store.set_state(args.id, "accepted")
    print(f"accepted {args.id} as {entry['id']} -> {lakes_in}")


def cmd_lake_issues(args) -> None:
    """Recompute requests.json from every lake-request issue and write the actions for the event's issue."""
    from sartale import lake_issues

    issues = _read_json(Path(args.issues))
    feed_path = Path(args.feed)
    previous = _read_json(feed_path) if feed_path.exists() else None
    old = next((r["state"] for r in (previous or {}).get("requests", []) if r["issue"] == args.event_issue), None)
    feed = lake_issues.build_feed(issues, load_lakes(Path(args.lakes_in)), previous,
                                  now=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    lake_issues.write_feed(feed, feed_path)
    actions = lake_issues.issue_actions(feed, args.event_issue, old)
    Path(args.actions).write_text(json.dumps(actions, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(feed['requests'])} requests; issue #{args.event_issue}: {actions['add'] or 'no change'}")


def cmd_lake_issue_accept(args) -> None:
    from sartale import lake_issues

    issue = next((i for i in _read_json(Path(args.issues)) if i["number"] == args.issue), None)
    if issue is None:
        raise SystemExit(f"issue #{args.issue} is not in {args.issues}")
    feed_path = Path(args.feed)
    feed = _read_json(feed_path)
    lake_id = lake_issues.accept_entry(feed, issue, Path(args.lakes_in), args.today)
    lake_issues.write_feed(feed, feed_path)
    print(lake_id)


def cmd_lake_requests_reject(args) -> None:
    store = _store(args)
    _open_request(store, args.id)
    store.set_state(args.id, "rejected", args.reason)
    print(f"rejected {args.id}")


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
    lb.add_argument("--allow-gate-fail", action="store_true",
                    help="exit 0 even when the Attabad gate fails (default: exit 1)")
    lb.set_defaults(func=cmd_lakes_build)
    lc = sub.add_parser("lakes-check", help="compare radar lake water with Sentinel-2 MNDWI water")
    lc.add_argument("--lakes-in", default=str(REPO_ROOT / "processing" / "lakes_in.json"))
    lc.add_argument("--cache", default=str(REPO_ROOT / "data" / "lakes"))
    lc.add_argument("--out", default=str(REPO_ROOT / "app" / "public" / "data"), help="folder holding lakes.json")
    lc.add_argument("--checks", default=str(REPO_ROOT / "processing" / "lake_checks.json"))
    lc.add_argument("--lakes", default="attabad,khurdopin,passu,shisper", help="comma-separated lake ids")
    lc.set_defaults(func=cmd_lakes_check)

    rs = sub.add_parser("lake-requests-serve", help="serve the lake request API (never downloads NISAR data)")
    rs.add_argument("--host", default="127.0.0.1")
    rs.add_argument("--port", type=int, default=8787)
    rs.add_argument("--db", default=str(DEFAULT_DB))
    rs.add_argument("--origin", default="http://localhost:5173")
    rs.set_defaults(func=cmd_lake_requests_serve)
    rl = sub.add_parser("lake-requests-list", help="list open lake requests with their source")
    rl.add_argument("--db", default=str(DEFAULT_DB))
    rl.set_defaults(func=cmd_lake_requests_list)
    ra = sub.add_parser("lake-requests-accept", help="add an open request to lakes_in.json and mark it accepted")
    ra.add_argument("id", type=int)
    ra.add_argument("--role", default="watch")
    ra.add_argument("--db", default=str(DEFAULT_DB))
    ra.add_argument("--lakes-in", default=str(REPO_ROOT / "processing" / "lakes_in.json"))
    ra.set_defaults(func=cmd_lake_requests_accept)
    rr = sub.add_parser("lake-requests-reject", help="reject an open lake request")
    rr.add_argument("id", type=int)
    rr.add_argument("--reason", required=True)
    rr.add_argument("--db", default=str(DEFAULT_DB))
    rr.set_defaults(func=cmd_lake_requests_reject)

    li = sub.add_parser("lake-issues", help="turn lake-request issues into requests.json and the event issue's actions")
    li.add_argument("--issues", required=True, help="JSON list of every issue labelled lake-request")
    li.add_argument("--feed", default=str(REPO_ROOT / "app" / "public" / "data" / "requests.json"))
    li.add_argument("--lakes-in", default=str(REPO_ROOT / "processing" / "lakes_in.json"))
    li.add_argument("--event-issue", type=int, required=True)
    li.add_argument("--actions", required=True, help="where to write the comment, labels and close flag")
    li.set_defaults(func=cmd_lake_issues)
    lia = sub.add_parser("lake-issue-accept", help="add an approved request to lakes_in.json and print the lake id")
    lia.add_argument("--issues", required=True)
    lia.add_argument("--feed", default=str(REPO_ROOT / "app" / "public" / "data" / "requests.json"))
    lia.add_argument("--issue", type=int, required=True)
    lia.add_argument("--lakes-in", default=str(REPO_ROOT / "processing" / "lakes_in.json"))
    lia.add_argument("--today", required=True, help="YYYY-MM-DD")
    lia.set_defaults(func=cmd_lake_issue_accept)
    return parser


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
