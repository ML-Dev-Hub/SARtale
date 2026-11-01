"""SARtale pipeline CLI: search, download, build, sites, rebuild, preview."""
import argparse
import json
from pathlib import Path

from sartale import config
from sartale.browse import build_preview
from sartale.catalog import search_cmr, select_stack, utc_date, write_manifest
from sartale.download import download
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


def cmd_sites(args) -> None:
    sites_in = json.loads(Path(args.sites_in).read_text(encoding="utf-8"))
    sites = build_sites(Path(args.gcov_dir), Path(args.manifest), sites_in, args.radius_m)
    write_sites(sites, Path(args.out))
    _print_site_checks(sites, Path(args.out))


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
    """`build` and `sites` on every verified date, with the same checks printed."""
    gcov_dir, out_dir = Path(args.gcov_dir), Path(args.out_dir)
    search = json.loads(Path(args.manifest_in).read_text(encoding="utf-8"))
    dates = verified_dates(search["granules"], gcov_dir)
    if not dates:
        raise ValueError(f"No verified GCOV file in {gcov_dir}")
    print(f"{len(dates)} dates: {', '.join(dates)}", flush=True)
    manifest = build_products(gcov_dir, dates, Path(args.manifest_in), out_dir, Path(args.cog_dir))
    _print_build_checks(manifest, out_dir)
    sites_in = json.loads(Path(args.sites_in).read_text(encoding="utf-8"))
    sites = build_sites(gcov_dir, out_dir / "manifest.json", sites_in, args.radius_m)
    write_sites(sites, out_dir / "sites.json")
    _print_site_checks(sites, out_dir / "sites.json")


def cmd_preview(args) -> None:
    manifest = build_preview(Path(args.browse_dir), Path(args.footprints), Path(args.out_dir))
    print(f"{len(manifest['dates'])} dates, {manifest['pixel_m']} m per pixel -> {Path(args.out_dir) / 'manifest.json'}")


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
    t = sub.add_parser("sites", help="sample site curves and the stable control")
    t.add_argument("--gcov-dir", required=True, help="directory holding <granule>.h5 files")
    t.add_argument("--manifest", required=True, help="app manifest.json written by `build`")
    t.add_argument("--sites-in", required=True,
                   help="JSON list of {id, name, lon, lat, role}")
    t.add_argument("--out", default=str(REPO_ROOT / "app" / "public" / "data" / "sites.json"))
    t.add_argument("--radius-m", type=float, default=150.0)
    t.set_defaults(func=cmd_sites)
    r = sub.add_parser("rebuild", help="build and sites on every verified date, printing the same checks")
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
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
