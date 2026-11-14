"""Requests to watch a new lake: validation and a NISAR coverage count."""
import math
import re
import unicodedata

from sartale.districts import DISTRICT_SOURCE, district_of
from sartale.lake_catalog import search_lake_passes, select_lake_passes
from sartale.lakes import Lake

BOUNDS = (34.4, 37.6, 70.8, 76.6)  # lat_min, lat_max, lon_min, lon_max
NEAR_KM = 1.0
MAX_OPEN = 200
EARTH_KM = 6371.0088
_DECIMAL = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?", re.ASCII)  # a number given as text: plain decimal digits only
# Wording the app must never use: a copy of BANNED_CLAIMS in app/src/content.ts (a test keeps them the same).
# A requested name lands in lakes.json, where the app's tests refuse these phrases.
BANNED_CLAIMS = (
    "detected flood", "flood detected", "damage", "damaged", "isolated", "risk score", "early warning",
    "detected change", "detected changes", "change detected", "changes detected", "change detection",
    "breach warning", "predict", "safe", "no risk",
    # "Watch" and "Alert" are allowed as the names of SARtale's levels only (Watch, Alert: growing), never as a flood or
    # outburst warning, a hazard level or an issued alert.
    "flood alert", "flood watch", "glof alert", "glof watch", "outburst alert", "outburst watch", "hazard alert",
    "risk alert", "red alert", "alert issued", "issued an alert", "warning issued",
)
# Whole words, case-insensitively, as findBannedClaims matches them (ASCII word boundaries, like JavaScript's \b)
_BANNED = [(phrase, re.compile(r"\b" + phrase.replace(" ", r"\s+") + r"\b", re.IGNORECASE | re.ASCII))
           for phrase in BANNED_CLAIMS]


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
    if isinstance(value, bool) or (isinstance(value, str) and not _DECIMAL.fullmatch(value.strip())):
        raise RequestError(f"{key} must be a number.")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise RequestError(f"{key} must be a number.") from None
    if not math.isfinite(number):
        raise RequestError(f"{key} must be a number.")
    return number


def find_banned_claims(text: str) -> list[str]:
    """The banned phrases found in the text, once each, in the order of BANNED_CLAIMS (findBannedClaims in content.ts)."""
    return [phrase for phrase, pattern in _BANNED if pattern.search(text)]


def banned_name_message(name: str) -> str | None:
    """The refusal for a name that uses a banned phrase; None when the name is fine."""
    found = find_banned_claims(name)
    if not found:
        return None
    return f"The name uses a phrase SARtale does not use (\"{found[0]}\"); please use the lake's usual name."


def banned_source_message(source: str) -> str | None:
    """The same for the source: it lands in lakes.json as the lake's coord_source."""
    found = find_banned_claims(source)
    if not found:
        return None
    return (f"The source uses a phrase SARtale does not use (\"{found[0]}\"); "
            "please describe where the coordinates come from.")


def _text(payload: dict, key: str, low: int, high: int) -> str:
    value = payload.get(key)
    text = value.strip() if isinstance(value, str) else ""
    if any(unicodedata.category(ch) in ("Cc", "Cf") for ch in text):
        raise RequestError(f"{key} must not contain control or invisible formatting characters.")
    if not low <= len(text) <= high:
        raise RequestError(f"{key} must be {low}–{high} characters.")
    return text


def validate(payload: dict, watched: list[Lake], open_requests: list[dict]) -> dict:
    """Clean a request payload. 400 for bad fields, 409 for a point near a watched lake or an open or accepted request."""
    lat, lon = _number(payload, "lat"), _number(payload, "lon")
    lat_min, lat_max, lon_min, lon_max = BOUNDS
    if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
        raise RequestError(
            f"The point must be in Gilgit-Baltistan or upper KP: {lat_min}–{lat_max} °N, {lon_min}–{lon_max} °E.")
    name = _text(payload, "name", 2, 80)
    banned = banned_name_message(name)
    if banned:
        raise RequestError(banned)
    source = _text(payload, "source", 3, 200)
    banned = banned_source_message(source)
    if banned:
        raise RequestError(banned)
    for lake in watched:
        if haversine_km(lat, lon, lake.lat, lake.lon) <= NEAR_KM:
            raise RequestError(f"Already watched: {lake.name}.", 409)
    for row in open_requests:
        if haversine_km(lat, lon, row["lat"], row["lon"]) <= NEAR_KM:
            raise RequestError(f"Already requested: {row['name']}.", 409)
    return {"name": name, "lat": lat, "lon": lon, "source": source}


def district_fields(lat: float, lon: float) -> dict:
    """The register's district, province and district_source for an accepted request's point. A point outside
    Gilgit-Baltistan and Khyber Pakhtunkhwa is refused (the request box also takes in parts of Azad Kashmir,
    Afghanistan and Ladakh)."""
    try:
        district, province = district_of(lon, lat)
    except ValueError:
        raise RequestError("The point is outside Gilgit-Baltistan and Khyber Pakhtunkhwa.", 409) from None
    return {"district": district, "province": province, "district_source": DISTRICT_SOURCE}


def coverage(lat: float, lon: float, search=search_lake_passes) -> dict:
    """Calibrated NISAR passes over a point: count, track keys, and first/last dates."""
    lake = Lake(id="request", name="request", lon=lon, lat=lat, coord_source="request", outline=None,
                role="watch", downstream=None, downstream_source=None)
    by_key = select_lake_passes(search(lake))
    dates = sorted(p.date for group in by_key.values() for p in group)
    return {"passes": len(dates), "tracks": sorted(by_key), "first": dates[0] if dates else None,
            "last": dates[-1] if dates else None}
