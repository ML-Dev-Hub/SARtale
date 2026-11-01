"""SARtale pipeline CLI. A later task adds `sites`."""
import argparse
from pathlib import Path

from sartale import config
from sartale.catalog import search_cmr, select_stack, write_manifest
from sartale.products import build_products

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
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
