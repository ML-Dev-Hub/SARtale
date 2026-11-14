"""Helpers shared by the register and inventory tests (imported as `from conftest import ...`)."""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROCESSING = REPO / "processing"
APP_DATA = REPO / "app" / "public" / "data"
# What every register row now carries: the district and province its point lies in, and where that comes from.
DISTRICT_FIELDS = {"district": "Hunza", "province": "GB", "district_source": "test districts"}


def load_json(rel):
    """A JSON file by absolute path, repo-relative path ("processing/lakes_in.json") or processing-relative path
    ("inventory/new_lakes.json")."""
    p = Path(rel)
    if not p.is_absolute():
        p = REPO / rel if (REPO / rel).exists() else PROCESSING / rel
    return json.loads(p.read_text(encoding="utf-8"))


def write_register(tmp_path, rows) -> Path:
    """Write register rows to a lakes_in.json in tmp_path and return its path."""
    p = Path(tmp_path) / "lakes_in.json"
    p.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return p
