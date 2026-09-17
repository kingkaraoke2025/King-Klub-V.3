"""
Migration 0003 — Backfill legacy check-ins into the event-scoped model (additive, idempotent, reversible).

Maps every legacy `checkins` record to the Default-Legacy Location->Venue->Event (from migration 0001),
creating one `event_participation` (+ one `event_checkins`) per legacy singer, clearly marked
`is_backfill=True`, `source="legacy_backfill"`. The original `checkins` collection is NEVER modified.

Safety: writing is OFF by default (dry-run). Requires --execute to write.

Usage:
  python migrations/0003_backfill_legacy_checkins.py               # dry-run report + ensure index
  python migrations/0003_backfill_legacy_checkins.py --execute     # perform backfill
  python migrations/0003_backfill_legacy_checkins.py --down        # reverse (remove backfilled only)
"""
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient
from pymongo.errors import DuplicateKeyError

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")
sys.path.insert(0, str(ROOT_DIR))
from models_phase2 import EventParticipation  # noqa: E402

MIGRATION_NAME = "0003_backfill_legacy_checkins"
client = MongoClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def log(direction, actions):
    db.migrations_log.insert_one({"migration": MIGRATION_NAME, "direction": direction,
                                  "actions": actions, "at": _now_iso()})
    print(f"[{direction}] {MIGRATION_NAME}")
    for a in actions:
        print("  -", a)


def ensure_indexes():
    db.event_participation.create_index(
        [("event_id", ASCENDING), ("list_position", ASCENDING)], name="event_list_position"
    )


def _default_legacy():
    loc = db.locations.find_one({"is_default_legacy": True})
    ven = db.venues.find_one({"is_default_legacy": True})
    ev = db.events.find_one({"is_default_legacy": True})
    return loc, ven, ev


def backfill(execute: bool = False):
    ensure_indexes()
    loc, ven, ev = _default_legacy()
    if not (loc and ven and ev):
        raise RuntimeError("Default-Legacy hierarchy missing — run migration 0001 first.")

    grouped = list(db.checkins.aggregate([
        {"$group": {
            "_id": "$user_id",
            "count": {"$sum": 1},
            "first": {"$min": "$timestamp"},
            "dates": {"$addToSet": "$date"},
        }},
        {"$sort": {"first": 1}},
    ]))

    existing = db.event_participation.count_documents({"event_id": ev["id"]})
    pos = existing
    summary = {"legacy_singers": len(grouped), "created": 0, "skipped_existing": 0, "execute": execute}
    actions = []

    for g in grouped:
        uid = g["_id"]
        if not uid:
            continue
        if db.event_participation.find_one({"user_id": uid, "event_id": ev["id"]}):
            summary["skipped_existing"] += 1
            continue
        pos += 1
        if execute:
            doc = EventParticipation(
                user_id=uid, event_id=ev["id"], venue_id=ven["id"], location_id=loc["id"],
                checked_in_at=g.get("first") or _now_iso(), status="checked_in", list_position=pos,
            ).to_mongo()
            doc.update({
                "is_backfill": True,
                "source": "legacy_backfill",
                "legacy_checkin_count": g["count"],
                "legacy_dates": g.get("dates", []),
            })
            db.event_participation.insert_one(doc)
            try:
                db.event_checkins.insert_one({
                    "id": str(uuid.uuid4()), "user_id": uid, "event_id": ev["id"],
                    "venue_id": ven["id"], "location_id": loc["id"],
                    "checked_in_at": g.get("first") or _now_iso(),
                    "is_backfill": True, "source": "legacy_backfill",
                })
            except DuplicateKeyError:
                pass
        summary["created"] += 1

    actions.append(f"default_legacy_event={ev['id']}")
    actions.append(f"summary={summary}")
    if not execute:
        actions.append("DRY-RUN: no documents written (pass --execute to apply)")
    log("execute" if execute else "dry_run", actions)
    return summary


def reverse():
    r1 = db.event_participation.delete_many({"is_backfill": True})
    r2 = db.event_checkins.delete_many({"is_backfill": True})
    log("down", [f"deleted {r1.deleted_count} backfilled participations",
                 f"deleted {r2.deleted_count} backfilled event_checkins",
                 "legacy `checkins` untouched"])
    return {"participations_removed": r1.deleted_count, "checkins_removed": r2.deleted_count}


if __name__ == "__main__":
    if "--down" in sys.argv:
        reverse()
    elif "--execute" in sys.argv:
        backfill(execute=True)
    else:
        backfill(execute=False)
