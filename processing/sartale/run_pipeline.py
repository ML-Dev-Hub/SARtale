"""SARtale pipeline CLI: search, build, sites, preview."""
import argparse
import json
from pathlib import Path

from sartale import config
from sartale.browse import build_preview
from sartale.catalog import search_cmr, select_stack, write_manifest
from sartale.products import build_products
from sartale.sites import build_sites, stability_report, write_sites

REPO_ROOT = Path(__file__).resolve().parents[2]


def cmd_search(args) -> None:
    stack = select_stack(search_cmr(), config.STACK_ID, config.MODE, config.POLE)
    write_manifest(stack, Path(args.out))
    for g in stack:
        print(g.start.date(), g.crid, g.accuracy, g.coverage, g.name)
    print(f"{len(stack)} granules -> {args.out}")


def cmd_build(args) -> None:
    dates = [d.strip() for d in args.dates.split(",") if d.strip()]
    manifest = build_products(Path(args.gcov_dir), dates, Path(args.manifest_in),
                              Path(args.out_dir), Path(args.cog_dir))
    print(f"{len(manifest['dates'])} dates -> {Path(args.out_dir) / 'manifest.json'}")


def cmd_sites(args) -> None:
    sites_in = json.loads(Path(args.sites_in).read_text(encoding="utf-8"))
    sites = build_sites(Path(args.gcov_dir), Path(args.manifest), sites_in, args.radius_m)
    write_sites(sites, Path(args.out))
    for s in sites:
        for pol in ("hh_db", "hv_db"):
            rep = stability_report([p[pol] for p in s["series"]])
            print(f"{s['id']} ({s['role']}) {pol}: spread {rep['spread_db']} dB, {rep['n_valid']} valid")
    print(f"{len(sites)} sites -> {args.out}")


def cmd_preview(args) -> None:
    manifest = build_preview(Path(args.browse_dir), Path(args.footprints), Path(args.out_dir))
    print(f"{len(manifest['dates'])} dates, {manifest['pixel_m']} m per pixel -> {Path(args.out_dir) / 'manifest.json'}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="run_pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("search", help="search CMR and write a manifest")
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_search)
    b = sub.add_parser("build", help="build overlays, COGs and manifest from GCOV files")
    b.add_argument("--gcov-dir", required=True, help="directory holding <granule>.h5 files")
    b.add_argument("--dates", required=True, help="comma-separated UTC dates, e.g. 2026-07-02,2026-08-19")
    b.add_argument("--manifest-in", required=True, help="manifest written by `search`")
    b.add_argument("--out-dir", default=str(REPO_ROOT / "app" / "public" / "data"))
    b.add_argument("--cog-dir", default=str(REPO_ROOT / "data" / "cog"))
    b.set_defaults(func=cmd_build)
    t = sub.add_parser("sites", help="sample site curves and the stable control")
    t.add_argument("--gcov-dir", required=True, help="directory holding <granule>.h5 files")
    t.add_argument("--manifest", required=True, help="app manifest.json written by `build`")
    t.add_argument("--sites-in", required=True,
                   help="JSON list of {id, name, lon, lat, role}")
    t.add_argument("--out", default=str(REPO_ROOT / "app" / "public" / "data" / "sites.json"))
    t.add_argument("--radius-m", type=float, default=150.0)
    t.set_defaults(func=cmd_sites)
    p = sub.add_parser("preview", help="build web frames and manifest from NASA's public browse PNGs (display-scaled, not dB)")
    p.add_argument("--browse-dir", default=str(REPO_ROOT / "data" / "browse"),
                   help="folder with *_LATLON.png files and browse_manifest.json")
    p.add_argument("--footprints", default=str(REPO_ROOT / "processing" / "reference" / "cmr_footprints.json"),
                   help="CMR footprints JSON: {'footprints': {granule: [[lon, lat] x 4]}}")
    p.add_argument("--out-dir", default=str(REPO_ROOT / "app" / "public" / "data"))
    p.set_defaults(func=cmd_preview)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
