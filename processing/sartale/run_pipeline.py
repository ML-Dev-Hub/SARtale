"""SARtale pipeline CLI. Later tasks add `build` and `sites`."""
import argparse
from pathlib import Path

from sartale import config
from sartale.catalog import search_cmr, select_stack, write_manifest


def cmd_search(args) -> None:
    stack = select_stack(search_cmr(), config.STACK_ID, config.MODE, config.POLE)
    write_manifest(stack, Path(args.out))
    for g in stack:
        print(g.start.date(), g.crid, g.accuracy, g.coverage, g.name)
    print(f"{len(stack)} granules -> {args.out}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="run_pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("search", help="search CMR and write a manifest")
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_search)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
