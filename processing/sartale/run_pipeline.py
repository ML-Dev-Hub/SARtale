"""SARtale Lake Watch pipeline CLI: lakes-search, lakes-fetch, lakes-build, lakes-check."""
import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from sartale.lake_catalog import Pass, coverage_report, search_lake_passes, select_lake_passes
from sartale.lakebuild import attabad_gate, build_lakes
from sartale.lakecheck import check_lake
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


def main(argv=None) -> None:
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
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
