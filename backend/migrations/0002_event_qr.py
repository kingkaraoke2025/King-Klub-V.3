"""
Migration 0002 — Event-scoped QR check-in collections (additive, idempotent, logged, reversible).

UP:
  - Ensures indexes on `event_checkins` (unique on user_id+event_id -> duplicate-checkin guard)
    and `event_checkin_attempts` (audit trail).

DOWN (--down):
  - Drops ONLY the indexes this migration created. Does NOT delete check-in or audit data.

Touches no legacy user/checkin/queue/points/settings data.
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

MIGRATION_NAME = "0002_event_qr"
client = MongoClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

INDEX_SPECS = {
    "event_checkins": [
        ("uniq_id", [("id", ASCENDING)], {"unique": True}),
        ("uniq_user_event", [("user_id", ASCENDING), ("event_id", ASCENDING)], {"unique": True}),
        ("event_id", [("event_id", ASCENDING)], {}),
        ("venue_id", [("venue_id", ASCENDING)], {}),
        ("location_id", [("location_id", ASCENDING)], {}),
    ],
    "event_checkin_attempts": [
        ("uniq_id", [("id", ASCENDING)], {"unique": True}),
        ("event_id", [("event_id", ASCENDING)], {}),
        ("user_id", [("user_id", ASCENDING)], {}),
        ("at", [("at", DESCENDING)], {}),
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


def up():
    actions = []
    for coll, specs in INDEX_SPECS.items():
        for name, keys, kwargs in specs:
            db[coll].create_index(keys, name=name, **kwargs)
            actions.append(f"index {coll}.{name}")
    log("up", actions)


def down():
    actions = []
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
