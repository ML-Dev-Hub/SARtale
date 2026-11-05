"""Print `changed` or `same`: does a JSON file differ from its committed version, ignoring one top-level key?

Usage: python3 json_changed.py <path> <ignored-key>
"""

import json
import subprocess
import sys
from pathlib import Path


def changed(old_text: str | None, new_text: str, key: str) -> bool:
    if old_text is None:
        return True
    old, new = json.loads(old_text), json.loads(new_text)
    for doc in (old, new):
        if isinstance(doc, dict):
            doc.pop(key, None)
    return old != new


def committed(path: str) -> str | None:
    r = subprocess.run(["git", "show", f"HEAD:{path}"], capture_output=True, text=True, encoding="utf-8")
    return r.stdout if r.returncode == 0 else None


def main(argv=None) -> None:
    path, key = (argv or sys.argv[1:])
    print("changed" if changed(committed(path), Path(path).read_text(encoding="utf-8"), key) else "same")


if __name__ == "__main__":
    main()
