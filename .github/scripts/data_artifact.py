"""Hand the rebuilt data from the read-only rebuild job to the publish job, and nothing else.

  pack   --repo R --out D                      (rebuild job) copy the allowed outputs of R into D with a manifest
  unpack --repo R --from D                     (publish job) check D, then copy the data files into R
  accept --repo R --from D --issue N --actions A
                                               (publish job, after unpack) mark issue N accepted in R's
                                               requests.json and write the accept comment for apply-actions.sh

Allowed paths: processing/lakes_in.json, app/public/data/lakes.json, app/public/data/requests.json and
app/public/data/lakes/**. `unpack` refuses symlinks, paths outside those, files missing from the manifest or
not matching its SHA-256, and data rebuilt on an older main than the publish checkout (the manifest records
the git object ids of the inputs it started from). It never writes requests.json: the publish job's copy may
have newer entries, so `accept` changes only the accepted issue's entry, and only if the values the team
approved are still those of the current entry.

Exit codes: 2 bad artifact, 5 the request changed during the rebuild, 6 main changed during the rebuild.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

LAKES_IN = "processing/lakes_in.json"
LAKES_JSON = "app/public/data/lakes.json"
REQUESTS = "app/public/data/requests.json"
PICTURES = "app/public/data/lakes"
FILES = (LAKES_IN, LAKES_JSON, REQUESTS)
BASE = (LAKES_IN, LAKES_JSON, PICTURES)  # inputs that only the rebuild jobs change
MANIFEST = "manifest.json"
SEGMENT = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]*$")
LAKE_ID = re.compile(r"^[a-z0-9_]+$")
SITE = "https://saeedahmadicp.github.io/SARtale/#lakes/"
CHECKED = ("searched", "too_few_passes")


class Refused(Exception):
    def __init__(self, message, code=2):
        super().__init__(message)
        self.code = code


def allowed(path: str) -> bool:
    """True for the four allowed outputs: the three files and plain relative paths below the pictures folder."""
    if path in FILES:
        return True
    if not path.startswith(PICTURES + "/") or "\\" in path:
        return False
    parts = path[len(PICTURES) + 1:].split("/")
    return all(SEGMENT.match(p) and p not in (".", "..") for p in parts)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_object(repo: Path, path: str) -> str | None:
    r = subprocess.run(["git", "rev-parse", f"HEAD:{path}"], cwd=repo, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def _walk(root: Path):
    """Every file below root as (relative posix path, Path); refuses symlinks anywhere."""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in dirnames + filenames:
            full = Path(dirpath) / name
            if full.is_symlink():
                raise Refused(f"symlink in the data: {full.relative_to(root).as_posix()}")
        for name in filenames:
            full = Path(dirpath) / name
            yield full.relative_to(root).as_posix(), full


def pack(repo: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    files = {}
    wanted = [p for p in FILES if (repo / p).is_file()]
    if (repo / PICTURES).is_dir():
        wanted += [f"{PICTURES}/{rel}" for rel, _ in _walk(repo / PICTURES)]
    for rel in wanted:
        src = repo / rel
        if src.is_symlink() or not allowed(rel):
            raise Refused(f"not an allowed output: {rel}")
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        files[rel] = sha256(dst)
    manifest = {"version": 1, "base": {p: git_object(repo, p) for p in BASE}, "files": files}
    (out / MANIFEST).write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def check(src: Path) -> dict:
    """Validate an unpacked artifact; returns its manifest."""
    if (src / MANIFEST).is_symlink() or not (src / MANIFEST).is_file():
        raise Refused("the data have no manifest")
    manifest = json.loads((src / MANIFEST).read_text(encoding="utf-8"))
    files = manifest.get("files")
    if not isinstance(files, dict) or not isinstance(manifest.get("base"), dict):
        raise Refused("the manifest is malformed")
    found = {rel for rel, _ in _walk(src)} - {MANIFEST}
    if found != set(files):
        raise Refused("the data and the manifest list different files")
    for rel, digest in files.items():
        if not isinstance(rel, str) or not allowed(rel):
            raise Refused(f"not an allowed output: {rel!r}")
        if sha256(src / rel) != digest:
            raise Refused(f"checksum mismatch: {rel}")
    for required in (LAKES_IN, LAKES_JSON):
        if required not in files:
            raise Refused(f"the data lack {required}")
    return manifest


def _target(repo: Path, rel: str) -> Path:
    """The destination in the repository; refuses a symlink anywhere on the way."""
    dst = repo / rel
    probe = dst
    while probe != repo:
        if probe.is_symlink():
            raise Refused(f"symlink in the repository at {probe.relative_to(repo).as_posix()}")
        probe = probe.parent
    return dst


def unpack(repo: Path, src: Path) -> list[str]:
    manifest = check(src)
    for path in BASE:
        if manifest["base"].get(path) != git_object(repo, path):
            raise Refused(f"main changed {path} while the data were rebuilt", 6)
    files = manifest["files"]
    copied = []
    for rel in sorted(files):
        if rel == REQUESTS:
            continue  # see accept
        dst = _target(repo, rel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src / rel, dst)
        copied.append(rel)
    pictures = repo / PICTURES
    if pictures.is_dir():
        for rel, full in list(_walk(pictures)):
            if f"{PICTURES}/{rel}" not in files:
                full.unlink()  # a picture the build pruned
        for dirpath, dirnames, filenames in os.walk(pictures, topdown=False):
            if Path(dirpath) != pictures and not os.listdir(dirpath):
                os.rmdir(dirpath)
    return copied


def accept(repo: Path, src: Path, number: int) -> list[dict]:
    check(src)
    if REQUESTS not in json.loads((src / MANIFEST).read_text(encoding="utf-8"))["files"]:
        raise Refused("the data lack requests.json")
    built = next((r for r in json.loads((src / REQUESTS).read_text(encoding="utf-8"))["requests"]
                  if r.get("issue") == number), None)
    if not built or built.get("state") != "accepted" or not LAKE_ID.match(str(built.get("lake_id") or "")):
        raise Refused(f"the data do not accept issue #{number}")
    path = _target(repo, REQUESTS)
    feed = json.loads(path.read_text(encoding="utf-8"))
    at = next((i for i, r in enumerate(feed["requests"]) if r.get("issue") == number), None)
    current = feed["requests"][at] if at is not None else None
    if (current is None or current.get("state") not in CHECKED + ("accepted",)
            or not built.get("values_sha256") or current.get("values_sha256") != built["values_sha256"]):
        raise Refused(f"issue #{number} changed while the data were rebuilt", 5)
    feed["requests"][at] = dict(current, state="accepted", lake_id=built["lake_id"])
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes((json.dumps(feed, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    os.replace(tmp, path)
    return [{"issue": number, "comment": f"Accepted. The lake is now watched: {SITE}{built['lake_id']}",
             "add": [], "remove": ["searched", "too few passes", "rebuild failed"], "close": True,
             "dispatch": False}]


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("pack", "unpack", "accept"):
        s = sub.add_parser(name)
        s.add_argument("--repo", default=".")
        s.add_argument("--out" if name == "pack" else "--from", dest="dir", required=True)
        if name == "accept":
            s.add_argument("--issue", type=int, required=True)
            s.add_argument("--actions", required=True)
    args = p.parse_args(argv)
    repo, folder = Path(args.repo).resolve(), Path(args.dir)
    try:
        if args.command == "pack":
            print(f"packed {len(pack(repo, folder)['files'])} files")
        elif args.command == "unpack":
            print(f"installed {len(unpack(repo, folder))} files")
        else:
            actions = accept(repo, folder, args.issue)
            Path(args.actions).write_text(json.dumps(actions, indent=1) + "\n", encoding="utf-8")
            print(f"issue #{args.issue} marked accepted")
    except Refused as e:
        print(f"data_artifact: {e}", file=sys.stderr)
        raise SystemExit(e.code) from None


if __name__ == "__main__":
    main()
