"""
Migration 0001 — Phase 2 data model foundation (additive, idempotent, logged, reversible).

UP:
  - Normalizes existing new-collection docs (adds slug/updated_at where missing).
  - Ensures indexes + uniqueness constraints on locations/venues/events/event_participation.
  - Creates a canonical Default-Legacy hierarchy (Location->Venue->Event) used later as
    the backfill target for pre-Phase-2 records. Marked is_default_legacy=True.

DOWN (--down):
  - Removes ONLY the is_default_legacy docs and drops the indexes this migration created.
  - Does NOT touch legacy data, sample data, or field normalizations (those are additive/harmless).

Never modifies or deletes any existing/legacy user, checkin, queue, points, or settings data.

Usage:
  python migrations/0001_phase2_data_model.py          # up
  python migrations/0001_phase2_data_model.py --down   # down
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from models_phase2 import (  # noqa: E402
    COL_EVENTS,
    COL_LOCATIONS,
    COL_PARTICIPATION,
    COL_VENUES,
    Event,
    EventStatus,
    Location,
    Venue,
    slugify,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

MIGRATION_NAME = "0001_phase2_data_model"

client = MongoClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def log(direction: str, actions: list):
    entry = {
        "migration": MIGRATION_NAME,
        "direction": direction,
        "actions": actions,
        "at": _now_iso(),
    }
    db.migrations_log.insert_one(dict(entry))
    print(f"[{direction}] {MIGRATION_NAME}")
    for a in actions:
        print("  -", a)


# Index specs owned by this migration (name -> (collection, keys, kwargs))
INDEX_SPECS = {
    "locations": [
        ("uniq_id", [("id", ASCENDING)], {"unique": True}),
        ("uniq_slug", [("slug", ASCENDING)], {"unique": True}),
        ("uniq_name", [("name", ASCENDING)], {"unique": True}),
        ("active", [("active", ASCENDING)], {}),
    ],
    "venues": [
        ("uniq_id", [("id", ASCENDING)], {"unique": True}),
        ("location_id", [("location_id", ASCENDING)], {}),
        ("uniq_location_slug", [("location_id", ASCENDING), ("slug", ASCENDING)], {"unique": True}),
    ],
    "events": [
        ("uniq_id", [("id", ASCENDING)], {"unique": True}),
        ("venue_id", [("venue_id", ASCENDING)], {}),
        ("location_id", [("location_id", ASCENDING)], {}),
        ("status", [("status", ASCENDING)], {}),
        ("event_date", [("event_date", ASCENDING)], {}),
        ("uniq_venue_date_slug", [("venue_id", ASCENDING), ("event_date", ASCENDING), ("slug", ASCENDING)], {"unique": True}),
    ],
    "event_participation": [
        ("uniq_id", [("id", ASCENDING)], {"unique": True}),
        ("uniq_user_event", [("user_id", ASCENDING), ("event_id", ASCENDING)], {"unique": True}),
        ("user_id", [("user_id", ASCENDING)], {}),
        ("event_id", [("event_id", ASCENDING)], {}),
        ("venue_id", [("venue_id", ASCENDING)], {}),
        ("location_id", [("location_id", ASCENDING)], {}),
        ("event_leaderboard", [("event_id", ASCENDING), ("event_points", DESCENDING)], {}),
        ("venue_user", [("venue_id", ASCENDING), ("user_id", ASCENDING)], {}),
        ("location_user", [("location_id", ASCENDING), ("user_id", ASCENDING)], {}),
    ],
}


def normalize_existing_docs():
    actions = []
    # locations
    for doc in db[COL_LOCATIONS].find({}):
        upd = {}
        if not doc.get("slug"):
            upd["slug"] = slugify(doc.get("name", ""))
        if doc.get("is_default_legacy") is None:
            upd["is_default_legacy"] = False
        if "updated_at" not in doc:
            upd["updated_at"] = _now_iso()
        if upd:
            db[COL_LOCATIONS].update_one({"id": doc["id"]}, {"$set": upd})
            actions.append(f"normalized location {doc['id']} -> {list(upd)}")
    # venues
    for doc in db[COL_VENUES].find({}):
        upd = {}
        if not doc.get("slug"):
            upd["slug"] = slugify(doc.get("name", ""))
        if "timezone" not in doc:
            upd["timezone"] = None
        if doc.get("is_default_legacy") is None:
            upd["is_default_legacy"] = False
        if "updated_at" not in doc:
            upd["updated_at"] = _now_iso()
        if upd:
            db[COL_VENUES].update_one({"id": doc["id"]}, {"$set": upd})
            actions.append(f"normalized venue {doc['id']} -> {list(upd)}")
    # events
    for doc in db[COL_EVENTS].find({}):
        upd = {}
        if not doc.get("slug"):
            upd["slug"] = slugify(doc.get("name", "")) or "main"
        if "qr_secret" not in doc:
            upd["qr_secret"] = None
        if doc.get("is_default_legacy") is None:
            upd["is_default_legacy"] = False
        if "updated_at" not in doc:
            upd["updated_at"] = _now_iso()
        if upd:
            db[COL_EVENTS].update_one({"id": doc["id"]}, {"$set": upd})
            actions.append(f"normalized event {doc['id']} -> {list(upd)}")
    return actions


def ensure_indexes():
    actions = []
    for coll, specs in INDEX_SPECS.items():
        for name, keys, kwargs in specs:
            db[coll].create_index(keys, name=name, **kwargs)
            actions.append(f"index {coll}.{name}")
    return actions


def create_default_legacy():
    actions = []
    loc = db[COL_LOCATIONS].find_one({"is_default_legacy": True})
    if not loc:
        location = Location(
            name="Legacy — Unassigned",
            slug="legacy-unassigned",
            city=None,
            state=None,
            timezone="America/Chicago",
            active=False,
            is_default_legacy=True,
            env="system",
        )
        db[COL_LOCATIONS].insert_one(location.to_mongo())
        loc = location.to_mongo()
        actions.append(f"created default-legacy location {loc['id']}")

    venue = db[COL_VENUES].find_one({"is_default_legacy": True})
    if not venue:
        v = Venue(
            location_id=loc["id"],
            name="Legacy Venue",
            slug="legacy-venue",
            active=False,
            is_default_legacy=True,
            env="system",
        )
        db[COL_VENUES].insert_one(v.to_mongo())
        venue = v.to_mongo()
        actions.append(f"created default-legacy venue {venue['id']}")

    event = db[COL_EVENTS].find_one({"is_default_legacy": True})
    if not event:
        e = Event(
            venue_id=venue["id"],
            location_id=loc["id"],
            name="Legacy Historical Activity",
            slug="legacy-historical",
            event_date="1970-01-01",
            status=EventStatus.archived,
            is_default_legacy=True,
            env="system",
        )
        db[COL_EVENTS].insert_one(e.to_mongo())
        actions.append(f"created default-legacy event {e.id}")
    return actions


def up():
    actions = []
    actions += normalize_existing_docs()
    actions += ensure_indexes()
    actions += create_default_legacy()
    log("up", actions)


def down():
    actions = []
    # remove default-legacy docs only
    for coll in [COL_EVENTS, COL_VENUES, COL_LOCATIONS]:
        r = db[coll].delete_many({"is_default_legacy": True})
        actions.append(f"deleted {r.deleted_count} default-legacy from {coll}")
    # drop indexes this migration created
    for coll, specs in INDEX_SPECS.items():
        existing = {i["name"] for i in db[coll].list_indexes()}
        for name, _keys, _kw in specs:
            if name in existing and name != "_id_":
                try:
                    db[coll].drop_index(name)
                    actions.append(f"dropped index {coll}.{name}")
                except Exception as exc:  # noqa: BLE001
                    actions.append(f"skip drop {coll}.{name}: {exc}")
    log("down", actions)


if __name__ == "__main__":
    if "--down" in sys.argv:
        down()
    else:
        up()
