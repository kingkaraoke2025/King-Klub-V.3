"""
Migration 0008 — point_ledger orphan janitor (Phase 2, Step 7d).

NON-DESTRUCTIVE by design:
  - Default run (`up`, no flags): REPORT ONLY. Scans point_ledger for rows whose event_id
    references an event that no longer exists (event_id=None rows are legitimate lifetime/
    season awards and are ignored). Prints counts + a sample; changes NOTHING.
  - `--quarantine`: additively TAGS orphan rows with is_orphan=True + orphaned_at. It NEVER
    deletes a ledger row and never touches dedupe_key/points, so idempotency and the
    lifetime/event/season point separation stay intact.
  - `--down`: unsets is_orphan / orphaned_at (reverses the tag only).

Nothing here is destructive; legitimate historical records are preserved.
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
client = MongoClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
MIGRATION_NAME = "0008_ledger_orphan_janitor"


def log(direction, actions):
    db.migrations_log.insert_one({"migration": MIGRATION_NAME, "direction": direction,
                                  "actions": actions, "at": datetime.now(timezone.utc).isoformat()})
    print(f"[{direction}] {MIGRATION_NAME}")
    for a in actions:
        print("  -", a)


def _orphan_ids():
    rows = list(db.point_ledger.find({"event_id": {"$ne": None}}, {"_id": 0, "id": 1, "event_id": 1}))
    event_ids = list({r["event_id"] for r in rows})
    existing = {e["id"] for e in db.events.find({"id": {"$in": event_ids}}, {"_id": 0, "id": 1})} if event_ids else set()
    return [r["id"] for r in rows if r["event_id"] not in existing], len(rows)


def up(quarantine=False):
    orphan_ids, scanned = _orphan_ids()
    if not quarantine:
        log("up", [f"REPORT ONLY: scanned={scanned} event-linked rows, orphans={len(orphan_ids)} (no changes)"])
        return
    if orphan_ids:
        db.point_ledger.update_many(
            {"id": {"$in": orphan_ids}},
            {"$set": {"is_orphan": True, "orphaned_at": datetime.now(timezone.utc).isoformat()}})
    log("up", [f"quarantine tagged is_orphan=True on {len(orphan_ids)} row(s); none deleted"])


def down():
    r = db.point_ledger.update_many({"is_orphan": True}, {"$unset": {"is_orphan": "", "orphaned_at": ""}})
    log("down", [f"untagged is_orphan on {r.modified_count} row(s)"])


if __name__ == "__main__":
    if "--down" in sys.argv:
        down()
    else:
        up(quarantine="--quarantine" in sys.argv)
