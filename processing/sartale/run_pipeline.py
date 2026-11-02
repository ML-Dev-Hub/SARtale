"""SARtale pipeline CLI: search, download, build, change, sites, rebuild, preview, lakes-search, lakes-fetch, lakes-build, lakes-check."""
import argparse
import json
import os
import shutil
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from sartale import config
from sartale.browse import build_preview
from sartale.catalog import search_cmr, select_stack, utc_date, write_manifest
from sartale.change import add_change_scores, build_change
from sartale.download import download
from sartale.lake_catalog import Pass, coverage_report, search_lake_passes, select_lake_passes
from sartale.lakebuild import attabad_gate, build_lakes
from sartale.lakecheck import check_lake
from sartale.lakes import load_lakes
from sartale.remote import fetch_lake_passes
from sartale.products import build_products
from sartale.sites import (
    build_sites,
    control_warnings,
    spread_without_interference_date,
    stability_report,
    write_sites,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def cmd_search(args) -> None:
    stack = select_stack(search_cmr(), config.STACK_ID, config.MODE, config.POLE)
    write_manifest(stack, Path(args.out))
    for g in stack:
        print(g.start.date(), g.crid, g.accuracy, g.coverage, g.name)
    print(f"{len(stack)} granules -> {args.out}")


def _print_build_checks(manifest: dict, out_dir: Path) -> None:
    sizes = [f.stat().st_size / 1e6 for f in (out_dir / "frames").iterdir()]
    print(f"{len(sizes)} frames, largest {max(sizes):.1f} MB, total {sum(sizes):.0f} MB, "
          f"about {manifest['pixel_m']} m per display pixel")
    print(f"composite: {', '.join(manifest['composite_dates'])}; stretch dB: {manifest['stretch_db']}")
    for e in manifest["dates"]:
        if e.get("flag"):
            print(f"flag {e['date']}: {e['flag']}")
    print(f"{len(manifest['dates'])} dates -> {out_dir / 'manifest.json'}")


def cmd_build(args) -> None:
    dates = [d.strip() for d in args.dates.split(",") if d.strip()]
    manifest = build_products(Path(args.gcov_dir), dates, Path(args.manifest_in),
                              Path(args.out_dir), Path(args.cog_dir))
    _print_build_checks(manifest, Path(args.out_dir))


def cmd_download(args) -> None:
    dates = [d.strip() for d in args.dates.split(",") if d.strip()]
    paths = download(Path(args.manifest), dates, Path(args.out))
    print(f"{len(paths)} files in {args.out}")


def _print_site_checks(sites: list[dict], out: Path) -> None:
    for s in sites:
        for pol in ("hh_db", "hv_db"):
            rep = stability_report([p[pol] for p in s["series"]])
            clean = spread_without_interference_date(s["series"], pol)
            print(f"{s['id']} ({s['role']}) {pol}: spread {rep['spread_db']} dB, {clean} dB without 2 Jul, "
                  f"{rep['n_valid']} valid")
    for message in control_warnings(sites):
        print(f"WARNING: {message}")
    print(f"{len(sites)} sites -> {out}")


def _read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cmd_sites(args) -> None:
    sites = build_sites(Path(args.gcov_dir), Path(args.manifest), _read_json(args.sites_in), args.radius_m)
    add_change_scores(sites, _read_json(args.manifest), Path(args.cog_dir), args.radius_m)
    write_sites(sites, Path(args.out))
    _print_site_checks(sites, Path(args.out))


def _print_change_checks(change: dict | None) -> None:
    if not change:
        return
    step = change["step"]
    print(f"change: mean step at least {step['min_step_db']} dB and stability {step['min_stability']}, same direction in HH and HV, "
          f"{100 * step['flagged_share']:.2f}% of the window flagged")
    print(f"change: threshold {change['threshold']}, shared scale up to {change['scale_max']}")
    print(f"change: baseline {', '.join(change['baseline_dates'])}")
    for e in change["excluded"]:
        print(f"change: excluded {e['date']}: {e['reason']}")
    for d, removed in change["removed_offsets_db"].items():
        print(f"change: {d} removed {removed}")


def cmd_change(args) -> None:
    """The change layer alone, from the COGs. No other frame is written, and an existing sites.json gains its scores."""
    out_dir, cog_dir = Path(args.out_dir), Path(args.cog_dir)
    _print_change_checks(build_change(cog_dir, out_dir, _read_json(args.sites_in), args.radius_m))
    path = out_dir / "sites.json"
    if path.is_file():
        write_sites(add_change_scores(_read_json(path), _read_json(out_dir / "manifest.json"), cog_dir, args.radius_m), path)


def verified_dates(granules: list[dict], gcov_dir: Path) -> list[str]:
    """Dates of the search-manifest granules with a complete file. `download` only names a file <granule>.h5
    after its MD5 matched, so a file of CMR's size is a verified one; *.part files are never looked at."""
    dates = []
    for g in granules:
        date = utc_date(g)
        if not g.get("size"):
            raise ValueError(f"The manifest has no size for {date}; run `search` again to refresh it")
        path = Path(gcov_dir) / f"{g['name']}.h5"
        if not path.is_file():
            print(f"not used: {date} (no complete file)")
        elif path.stat().st_size != g["size"]:
            print(f"not used: {date} (size differs from CMR)")
        else:
            dates.append(date)
    return dates


def cmd_rebuild(args) -> None:
    """`build`, `change` and `sites` on every verified date, with the same checks printed."""
    gcov_dir, out_dir, cog_dir = Path(args.gcov_dir), Path(args.out_dir), Path(args.cog_dir)
    search = _read_json(args.manifest_in)
    dates = verified_dates(search["granules"], gcov_dir)
    if not dates:
        raise ValueError(f"No verified GCOV file in {gcov_dir}")
    print(f"{len(dates)} dates: {', '.join(dates)}", flush=True)
    manifest = build_products(gcov_dir, dates, Path(args.manifest_in), out_dir, cog_dir)
    _print_build_checks(manifest, out_dir)
    sites_in = _read_json(args.sites_in)
    _print_change_checks(build_change(cog_dir, out_dir, sites_in, args.radius_m))
    sites = build_sites(gcov_dir, out_dir / "manifest.json", sites_in, args.radius_m)
    add_change_scores(sites, _read_json(out_dir / "manifest.json"), cog_dir, args.radius_m)
    write_sites(sites, out_dir / "sites.json")
    _print_site_checks(sites, out_dir / "sites.json")


def cmd_preview(args) -> None:
    manifest = build_preview(Path(args.browse_dir), Path(args.footprints), Path(args.out_dir))
    print(f"{len(manifest['dates'])} dates, {manifest['pixel_m']} m per pixel -> {Path(args.out_dir) / 'manifest.json'}")


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
    s = sub.add_parser("search", help="search CMR and write a manifest")
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_search)
    d = sub.add_parser("download", help="download the GCOV files for some dates (uses ~/.netrc, resumes, verifies size and MD5)")
    d.add_argument("--manifest", required=True, help="manifest written by `search` (needs size and md5)")
    d.add_argument("--dates", required=True, help="comma-separated UTC dates, e.g. 2026-07-26,2026-08-19,2026-09-12,2026-10-18")
    d.add_argument("--out", default=str(REPO_ROOT / "data" / "gcov"), help="folder for <granule>.h5 files")
    d.set_defaults(func=cmd_download)
    b = sub.add_parser("build", help="build overlays, COGs and manifest from GCOV files")
    b.add_argument("--gcov-dir", required=True, help="directory holding <granule>.h5 files")
    b.add_argument("--dates", required=True, help="comma-separated UTC dates, e.g. 2026-07-26,2026-08-19,2026-09-12,2026-10-18")
    b.add_argument("--manifest-in", required=True, help="manifest written by `search`")
    b.add_argument("--out-dir", default=str(REPO_ROOT / "app" / "public" / "data"))
    b.add_argument("--cog-dir", default=str(REPO_ROOT / "data" / "cog"))
    b.set_defaults(func=cmd_build)
    c = sub.add_parser("change", help="statistical change layer from the COGs; touches no other frame")
    c.add_argument("--cog-dir", default=str(REPO_ROOT / "data" / "cog"))
    c.add_argument("--out-dir", default=str(REPO_ROOT / "app" / "public" / "data"))
    c.add_argument("--sites-in", default=str(REPO_ROOT / "processing" / "sites_in.json"))
    c.add_argument("--radius-m", type=float, default=150.0)
    c.set_defaults(func=cmd_change)
    t = sub.add_parser("sites", help="sample site curves and the stable control")
    t.add_argument("--gcov-dir", required=True, help="directory holding <granule>.h5 files")
    t.add_argument("--manifest", required=True, help="app manifest.json written by `build`")
    t.add_argument("--sites-in", required=True,
                   help="JSON list of {id, name, lon, lat, role}")
    t.add_argument("--out", default=str(REPO_ROOT / "app" / "public" / "data" / "sites.json"))
    t.add_argument("--cog-dir", default=str(REPO_ROOT / "data" / "cog"), help="where the change score COGs are")
    t.add_argument("--radius-m", type=float, default=150.0)
    t.set_defaults(func=cmd_sites)
    r = sub.add_parser("rebuild", help="build, change and sites on every verified date, printing the same checks")
    r.add_argument("--gcov-dir", default=str(REPO_ROOT / "data" / "gcov"), help="directory holding <granule>.h5 files")
    r.add_argument("--manifest-in", default=str(REPO_ROOT / "data" / "manifest_h0.json"),
                   help="manifest written by `search` (needs size)")
    r.add_argument("--sites-in", default=str(REPO_ROOT / "processing" / "sites_in.json"))
    r.add_argument("--out-dir", default=str(REPO_ROOT / "app" / "public" / "data"))
    r.add_argument("--cog-dir", default=str(REPO_ROOT / "data" / "cog"))
    r.add_argument("--radius-m", type=float, default=150.0)
    r.set_defaults(func=cmd_rebuild)
    p = sub.add_parser("preview", help="build web frames and manifest from NASA's public browse PNGs (display-scaled, not dB)")
    p.add_argument("--browse-dir", default=str(REPO_ROOT / "data" / "browse"),
                   help="folder with *_LATLON.png files and browse_manifest.json")
    p.add_argument("--footprints", default=str(REPO_ROOT / "processing" / "reference" / "cmr_footprints.json"),
                   help="CMR footprints JSON: {'footprints': {granule: [[lon, lat] x 4]}}")
    p.add_argument("--out-dir", default=str(REPO_ROOT / "app" / "public" / "data"))
    p.set_defaults(func=cmd_preview)
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
