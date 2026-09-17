"""
Migration 0004 — Event-scoped queue collections + legacy queue backfill (additive, idempotent, reversible).

UP (default run): ensures indexes on `event_queue` and `event_perk_usage`, then DRY-RUN reports
how many legacy `queue` rows would be backfilled. No data written without --execute.

--execute : maps each legacy `queue` row to `event_queue` under the Default-Legacy event
            (from migration 0001), marked is_backfill=True, source="legacy_backfill",
            legacy_queue_id=<orig id>. Idempotent (skips rows already mapped).

--down    : removes ONLY is_backfill event_queue rows. Never touches the legacy `queue` collection.
"""
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

MIGRATION_NAME = "0004_event_queue"
client = MongoClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

INDEX_SPECS = {
    "event_queue": [
        ("uniq_id", [("id", ASCENDING)], {"unique": True}),
        ("event_status_position", [("event_id", ASCENDING), ("status", ASCENDING), ("position", ASCENDING)], {}),
        ("event_user", [("event_id", ASCENDING), ("user_id", ASCENDING)], {}),
        ("user_id", [("user_id", ASCENDING)], {}),
        ("created_at", [("created_at", ASCENDING)], {}),
    ],
    "event_perk_usage": [
        ("uniq_id", [("id", ASCENDING)], {"unique": True}),
        ("uniq_user_event", [("user_id", ASCENDING), ("event_id", ASCENDING)], {"unique": True}),
        ("event_id", [("event_id", ASCENDING)], {}),
    ],
}


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def log(direction, actions):
    db.migrations_log.insert_one({"migration": MIGRATION_NAME, "direction": direction,
                                  "actions": actions, "at": _now_iso()})
    print(f"[{direction}] {MIGRATION_NAME}")
    for a in actions:
        print("  -", a)


def ensure_indexes():
    for coll, specs in INDEX_SPECS.items():
        for name, keys, kwargs in specs:
            db[coll].create_index(keys, name=name, **kwargs)


def _default_legacy():
    return (db.locations.find_one({"is_default_legacy": True}),
            db.venues.find_one({"is_default_legacy": True}),
            db.events.find_one({"is_default_legacy": True}))


def backfill(execute: bool = False):
    ensure_indexes()
    loc, ven, ev = _default_legacy()
    if not (loc and ven and ev):
        raise RuntimeError("Default-Legacy hierarchy missing — run migration 0001 first.")
    legacy = list(db.queue.find({}))
    summary = {"legacy_rows": len(legacy), "created": 0, "skipped_existing": 0, "execute": execute}
    base = db.event_queue.count_documents({"event_id": ev["id"]})
    pos = base
    for row in legacy:
        if db.event_queue.find_one({"legacy_queue_id": row["id"], "event_id": ev["id"]}):
            summary["skipped_existing"] += 1
            continue
        pos += 1
        if execute:
            db.event_queue.insert_one({
                "id": uuid.uuid4().hex,
                "event_id": ev["id"], "venue_id": ven["id"], "location_id": loc["id"],
                "user_id": row.get("user_id"), "user_name": row.get("user_name"),
                "song_title": row.get("song_title"), "artist": row.get("artist"),
                "message_to_admin": row.get("message_to_admin"),
                "status": row.get("status", "completed"), "position": row.get("position", pos),
                "estimated_wait": row.get("estimated_wait", 0),
                "perk_protected": row.get("perk_protected", False),
                "created_at": row.get("created_at", _now_iso()), "updated_at": _now_iso(),
                "is_backfill": True, "source": "legacy_backfill", "legacy_queue_id": row["id"],
            })
        summary["created"] += 1
    actions = [f"default_legacy_event={ev['id']}", f"summary={summary}"]
    if not execute:
        actions.append("DRY-RUN: no documents written (pass --execute to apply)")
    log("execute" if execute else "dry_run", actions)
    return summary


def reverse():
    r = db.event_queue.delete_many({"is_backfill": True})
    log("down", [f"deleted {r.deleted_count} backfilled event_queue rows", "legacy `queue` untouched"])
    return {"event_queue_removed": r.deleted_count}


if __name__ == "__main__":
    if "--down" in sys.argv:
        reverse()
    elif "--execute" in sys.argv:
        backfill(execute=True)
    else:
        backfill(execute=False)
