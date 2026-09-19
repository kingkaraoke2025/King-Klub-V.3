"""
King Klub — Phase 2 data model (additive foundation).

Framework-agnostic Pydantic models for the multi-location / multi-venue structure.
These models are NOT yet wired into request behavior (server.py is untouched).
They exist so migrations, tests, and later steps share one canonical definition.

Design notes / separation of concerns:
  - GLOBAL lifetime singer info  -> stays on the existing `users` collection (unchanged).
  - LOCATION-specific info        -> `locations` + derived aggregates by location_id.
  - VENUE-specific info           -> `venues` + derived aggregates by venue_id.
  - EVENT-specific info           -> `events` + `event_participation` (points/list/history per event).

Isolation guarantee: all event activity is keyed by event_id (and denormalized
venue_id / location_id), so a singer's activity at Venue A never mixes with Venue B.
Multiple events may be status="active" at the same time — there is NO global singleton.
Nothing here hardcodes a single-venue or single-timezone assumption.
"""
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


def slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "item"


class EventStatus(str, Enum):
    draft = "draft"
    scheduled = "scheduled"
    active = "active"
    ended = "ended"
    cancelled = "cancelled"
    archived = "archived"


class ParticipationStatus(str, Enum):
    registered = "registered"
    checked_in = "checked_in"
    active = "active"
    left = "left"


class BaseDoc(BaseModel):
    """UUID-string convention matching the existing codebase (no ObjectId exposed)."""

    model_config = ConfigDict(extra="ignore", use_enum_values=True)

    def to_mongo(self) -> dict:
        return self.model_dump()

    @classmethod
    def from_mongo(cls, doc: Optional[dict]):
        if not doc:
            return None
        data = dict(doc)
        data.pop("_id", None)
        return cls(**data)


class Location(BaseDoc):
    id: str = Field(default_factory=_uuid)
    name: str
    slug: str = ""
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "USA"
    zip_code: Optional[str] = None  # US ZIP; drives automatic timezone resolution
    timezone: str = "America/Chicago"  # per-location IANA tz (no global hardcode)
    active: bool = True
    archived: bool = False  # soft-delete when dependent data exists
    is_sample: bool = False
    is_default_legacy: bool = False
    env: str = "production"
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)

    def model_post_init(self, __context) -> None:
        if not self.slug:
            self.slug = slugify(self.name)


class Venue(BaseDoc):
    id: str = Field(default_factory=_uuid)
    location_id: str
    name: str
    slug: str = ""
    address: Optional[str] = None
    timezone: Optional[str] = None  # None => inherit from location
    active: bool = True
    is_sample: bool = False
    is_default_legacy: bool = False
    env: str = "production"
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)

    def model_post_init(self, __context) -> None:
        if not self.slug:
            self.slug = slugify(self.name)


class Event(BaseDoc):
    id: str = Field(default_factory=_uuid)
    venue_id: str
    location_id: str  # denormalized for fast/safe scoping & isolation
    name: str
    slug: str = ""
    event_date: str  # "YYYY-MM-DD" in the venue's local timezone
    status: EventStatus = EventStatus.draft
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    qr_secret: Optional[str] = None  # reserved for Step 2 (event-scoped QR); unused now
    is_sample: bool = False
    is_default_legacy: bool = False
    env: str = "production"
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)

    def model_post_init(self, __context) -> None:
        if not self.slug:
            self.slug = slugify(self.name) or "main"


class EventParticipation(BaseDoc):
    """One record per (singer, event). Preserves per-event history and keeps
    venues/events isolated. Global lifetime totals remain on `users`."""

    id: str = Field(default_factory=_uuid)
    user_id: str
    event_id: str
    venue_id: str  # denormalized
    location_id: str  # denormalized
    event_points: int = 0
    songs_performed: int = 0
    badges_earned: List[str] = Field(default_factory=list)
    list_position: Optional[int] = None
    status: ParticipationStatus = ParticipationStatus.registered
    checked_in_at: Optional[str] = None
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


# Collection name constants (single source of truth for later steps)
COL_LOCATIONS = "locations"
COL_VENUES = "venues"
COL_EVENTS = "events"
COL_PARTICIPATION = "event_participation"
