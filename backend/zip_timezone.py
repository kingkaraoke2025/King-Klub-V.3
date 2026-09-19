"""Reliable, offline US ZIP-code -> IANA timezone resolution.

Uses pgeocode (ZIP -> lat/lng from the GeoNames US dataset) + timezonefinder
(lat/lng -> IANA tz via polygon lookup). This is a proper geographic lookup, NOT a
simplistic ZIP-prefix heuristic, so DST is handled correctly by the IANA id.
"""
import math
import re

import pgeocode
from timezonefinder import TimezoneFinder

_ZIP_RE = re.compile(r"^\d{5}$")

# Heavy objects — build once at import.
_tf = TimezoneFinder()
_nomi = pgeocode.Nominatim("us")

# Human-friendly labels for common US IANA zones (display only; storage stays IANA).
_LABELS = {
    "America/New_York": "Eastern Time",
    "America/Chicago": "Central Time",
    "America/Denver": "Mountain Time",
    "America/Phoenix": "Mountain Time (no DST)",
    "America/Los_Angeles": "Pacific Time",
    "America/Anchorage": "Alaska Time",
    "Pacific/Honolulu": "Hawaii Time",
    "America/Adak": "Hawaii-Aleutian Time",
}


def tz_label(tz: str) -> str:
    return _LABELS.get(tz, tz)


def resolve_zip_timezone(zip_code: str):
    """Return {ok, zip, timezone, label, place_name, error}.

    ok=True only when a single valid US ZIP maps to a real IANA timezone.
    Never guesses — on any failure ok=False with a clear error message.
    """
    z = (zip_code or "").strip()
    if not _ZIP_RE.match(z):
        return {"ok": False, "zip": z, "timezone": None, "label": None,
                "place_name": None, "error": "Enter a valid 5-digit US ZIP code."}
    try:
        rec = _nomi.query_postal_code(z)
    except Exception:
        rec = None
    lat = getattr(rec, "latitude", None) if rec is not None else None
    lon = getattr(rec, "longitude", None) if rec is not None else None
    # pgeocode returns NaN for unknown ZIPs.
    if lat is None or lon is None or (isinstance(lat, float) and math.isnan(lat)) or (isinstance(lon, float) and math.isnan(lon)):
        return {"ok": False, "zip": z, "timezone": None, "label": None, "place_name": None,
                "error": f"ZIP code {z} was not found in the US ZIP database."}
    tz = _tf.timezone_at(lat=float(lat), lng=float(lon))
    if not tz:
        return {"ok": False, "zip": z, "timezone": None, "label": None, "place_name": None,
                "error": f"Timezone could not be determined for ZIP {z}. Please verify the ZIP code."}
    place = getattr(rec, "place_name", None)
    if isinstance(place, float) and math.isnan(place):
        place = None
    return {"ok": True, "zip": z, "timezone": tz, "label": tz_label(tz), "place_name": place, "error": None}
