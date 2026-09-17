"""
Migration 0006 — Idempotent point ledger index (additive, idempotent, reversible).
Creates the unique dedupe_key index on point_ledger that makes event/season awards
safe against retries and duplicate calls. No legacy data touched.
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
client = MongoClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
MIGRATION_NAME = "0006_point_ledger"

SPECS = [("uniq_id", [("id", ASCENDING)], {"unique": True}),
         ("uniq_dedupe", [("dedupe_key", ASCENDING)], {"unique": True}),
         ("user_id", [("user_id", ASCENDING)], {}),
         ("event_id", [("event_id", ASCENDING)], {})]


def log(direction, actions):
    db.migrations_log.insert_one({"migration": MIGRATION_NAME, "direction": direction,
                                  "actions": actions, "at": datetime.now(timezone.utc).isoformat()})
    print(f"[{direction}] {MIGRATION_NAME}")
    for a in actions:
        print("  -", a)


def up():
    for name, keys, kw in SPECS:
        db.point_ledger.create_index(keys, name=name, **kw)
    log("up", [f"index point_ledger.{n}" for n, _, _ in SPECS])


def down():
    existing = {i["name"] for i in db.point_ledger.list_indexes()}
    dropped = []
    for name, _k, _kw in SPECS:
        if name in existing and name != "_id_":
            db.point_ledger.drop_index(name)
            dropped.append(name)
    log("down", [f"dropped point_ledger.{n}" for n in dropped])


if __name__ == "__main__":
    down() if "--down" in sys.argv else up()
