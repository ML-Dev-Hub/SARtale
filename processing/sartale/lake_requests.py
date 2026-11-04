"""Requests to watch a new lake: validation, a small SQLite store, and a NISAR coverage count."""
import json
import math
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from sartale.lake_catalog import search_lake_passes, select_lake_passes
from sartale.lakes import Lake

BOUNDS = (34.4, 37.6, 70.8, 76.6)  # lat_min, lat_max, lon_min, lon_max
NEAR_KM = 1.0
RATE_PER_HOUR = 5
MAX_OPEN = 200
STATES = ("queued", "searched", "search_failed", "accepted", "rejected")
OPEN_STATES = ("queued", "searched", "search_failed")
DEFAULT_PATH = Path("data/lake_requests.sqlite")
EARTH_KM = 6371.0088


class RequestError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_KM * math.asin(math.sqrt(a))


def _number(payload: dict, key: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool):
        raise RequestError(f"{key} must be a number.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise RequestError(f"{key} must be a number.") from None
    if not math.isfinite(number):
        raise RequestError(f"{key} must be a number.")
    return number


def _text(payload: dict, key: str, low: int, high: int) -> str:
    value = payload.get(key)
    text = value.strip() if isinstance(value, str) else ""
    if not low <= len(text) <= high:
        raise RequestError(f"{key} must be {low}–{high} characters.")
    return text


def validate(payload: dict, watched: list[Lake], open_requests: list[dict]) -> dict:
    """Clean a request payload. 400 for bad fields, 409 for a point near a watched lake or open request."""
    lat, lon = _number(payload, "lat"), _number(payload, "lon")
    lat_min, lat_max, lon_min, lon_max = BOUNDS
    if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
        raise RequestError(
            f"The point must be in Gilgit-Baltistan or upper KP: {lat_min}–{lat_max} °N, {lon_min}–{lon_max} °E.")
    name = _text(payload, "name", 2, 80)
    source = _text(payload, "source", 3, 200)
    for lake in watched:
        if haversine_km(lat, lon, lake.lat, lake.lon) <= NEAR_KM:
            raise RequestError(f"Already watched: {lake.name}.", 409)
    for row in open_requests:
        if haversine_km(lat, lon, row["lat"], row["lon"]) <= NEAR_KM:
            raise RequestError(f"Already requested: {row['name']}.", 409)
    return {"name": name, "lat": lat, "lon": lon, "source": source}


class RequestStore:
    def __init__(self, path: Path = DEFAULT_PATH):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock, self._db:
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS requests ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, lat REAL NOT NULL, "
                "lon REAL NOT NULL, source TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'queued', "
                "passes INTEGER, tracks TEXT NOT NULL DEFAULT '[]', first TEXT, last TEXT, reason TEXT, "
                "addr TEXT NOT NULL, created_ts REAL NOT NULL)")

    @staticmethod
    def _row(r: sqlite3.Row) -> dict:
        return {
            "id": r["id"], "name": r["name"], "lat": r["lat"], "lon": r["lon"], "source": r["source"],
            "state": r["state"], "passes": r["passes"], "tracks": json.loads(r["tracks"]),
            "first": r["first"], "last": r["last"], "reason": r["reason"],
            "created": datetime.fromtimestamp(r["created_ts"], timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    def add(self, clean: dict, addr: str, now: float) -> dict:
        with self._lock, self._db:
            cur = self._db.execute(
                "INSERT INTO requests (name, lat, lon, source, addr, created_ts) VALUES (?, ?, ?, ?, ?, ?)",
                (clean["name"], clean["lat"], clean["lon"], clean["source"], addr, now))
            rid = cur.lastrowid
        return self.get(rid)

    def get(self, rid: int) -> dict | None:
        with self._lock:
            r = self._db.execute("SELECT * FROM requests WHERE id = ?", (rid,)).fetchone()
        return self._row(r) if r else None

    def list_open(self) -> list[dict]:
        marks = ",".join("?" * len(OPEN_STATES))
        with self._lock:
            rows = self._db.execute(
                f"SELECT * FROM requests WHERE state IN ({marks}) ORDER BY created_ts DESC, id DESC",
                OPEN_STATES).fetchall()
        return [self._row(r) for r in rows]

    def recent_count(self, addr: str, since: float) -> int:
        with self._lock:
            return self._db.execute(
                "SELECT COUNT(*) FROM requests WHERE addr = ? AND created_ts >= ?", (addr, since)).fetchone()[0]

    def open_count(self) -> int:
        marks = ",".join("?" * len(OPEN_STATES))
        with self._lock:
            return self._db.execute(
                f"SELECT COUNT(*) FROM requests WHERE state IN ({marks})", OPEN_STATES).fetchone()[0]

    def set_searched(self, rid: int, passes: int, tracks: list[str], first: str | None, last: str | None) -> None:
        with self._lock, self._db:
            self._db.execute(
                "UPDATE requests SET state = 'searched', passes = ?, tracks = ?, first = ?, last = ?, "
                "reason = NULL WHERE id = ?", (passes, json.dumps(tracks), first, last, rid))

    def set_failed(self, rid: int, reason: str) -> None:
        with self._lock, self._db:
            self._db.execute(
                "UPDATE requests SET state = 'search_failed', reason = ? WHERE id = ?", (reason, rid))

    def set_state(self, rid: int, state: str, reason: str | None = None) -> None:
        if state not in STATES:
            raise ValueError(f"state must be one of {STATES}, got {state!r}")
        with self._lock, self._db:
            self._db.execute("UPDATE requests SET state = ?, reason = ? WHERE id = ?", (state, reason, rid))


def coverage(lat: float, lon: float, search=search_lake_passes) -> dict:
    """Calibrated NISAR passes over a point: count, track keys, and first/last dates."""
    lake = Lake(id="request", name="request", lon=lon, lat=lat, coord_source="request", outline=None,
                role="watch", downstream=None, downstream_source=None)
    by_key = select_lake_passes(search(lake))
    dates = sorted(p.date for group in by_key.values() for p in group)
    return {"passes": len(dates), "tracks": sorted(by_key), "first": dates[0] if dates else None,
            "last": dates[-1] if dates else None}
