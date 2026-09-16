"""
Migration 0007 — additive user Role model (Phase 2, Step 7a).

Additive, idempotent, reversible, non-destructive:
  - Adds `role` to every user that lacks it:
      * is_admin == True  -> "global_admin"
      * otherwise          -> "singer"
  - Adds a default `role_scope` = {"location_ids": [], "venue_ids": []} to users lacking it.
  - NEVER overwrites an already-present `role` or `role_scope` (preserves manual
    assignments, e.g. location_manager/venue_kj), so re-running is a no-op.
  - Preserves the legacy `is_admin` field untouched.
  - Does NOT change any authorization behavior (enforcement is Step 7b).

Reverse (`--down`): unsets `role` and `role_scope` on all users. Legacy `is_admin`
and all other data remain intact, so the app returns to its pre-7a state.
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
MIGRATION_NAME = "0007_user_roles"

GLOBAL_ADMIN = "global_admin"
SINGER = "singer"
DEFAULT_SCOPE = {"location_ids": [], "venue_ids": []}


def log(direction, actions):
    db.migrations_log.insert_one({"migration": MIGRATION_NAME, "direction": direction,
                                  "actions": actions, "at": datetime.now(timezone.utc).isoformat()})
    print(f"[{direction}] {MIGRATION_NAME}")
    for a in actions:
        print("  -", a)


def up():
    # 1) admins without a role -> global_admin
    r_admin = db.users.update_many(
        {"role": {"$exists": False}, "is_admin": True},
        {"$set": {"role": GLOBAL_ADMIN}},
    )
    # 2) remaining users without a role -> singer
    r_singer = db.users.update_many(
        {"role": {"$exists": False}},
        {"$set": {"role": SINGER}},
    )
    # 3) users without a role_scope -> default empty scope
    r_scope = db.users.update_many(
        {"role_scope": {"$exists": False}},
        {"$set": {"role_scope": DEFAULT_SCOPE}},
    )
    log("up", [
        f"users.role=global_admin set on {r_admin.modified_count} legacy admin(s)",
        f"users.role=singer set on {r_singer.modified_count} user(s)",
        f"users.role_scope defaulted on {r_scope.modified_count} user(s)",
    ])


def down():
    r = db.users.update_many({}, {"$unset": {"role": "", "role_scope": ""}})
    log("down", [f"unset role/role_scope on {r.modified_count} user(s)"])


if __name__ == "__main__":
    down() if "--down" in sys.argv else up()
