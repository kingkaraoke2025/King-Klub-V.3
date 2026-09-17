"""Idempotent DEV seed for the isolated Phase 2 workspace (safe to re-run).
Creates a global_admin and two singers. No production data involved."""
import os
from datetime import datetime, timezone
from pathlib import Path

import bcrypt
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parent / ".env")
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _hash(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def upsert_user(uid, email, name, pw, is_admin, role, scope=None):
    now = datetime.now(timezone.utc).isoformat()
    existing = db.users.find_one({"email": email})
    doc = {
        "id": uid, "email": email, "display_name": name, "password": _hash(pw),
        "title_preference": "male", "referred_by": None, "points": 0, "nightly_points": 0,
        "songs_performed": 0, "consecutive_visits": 0, "badges": [], "is_admin": is_admin,
        "role": role, "role_scope": scope or {"location_ids": [], "venue_ids": []},
        "created_at": now, "last_visit": now,
    }
    if existing:
        db.users.update_one({"email": email}, {"$set": {
            "password": doc["password"], "is_admin": is_admin, "role": role,
            "role_scope": doc["role_scope"], "display_name": name}})
        print(f"updated {email} ({role})")
    else:
        db.users.insert_one(doc)
        print(f"created {email} ({role})")


if __name__ == "__main__":
    pw = os.environ.get("DEV_ADMIN_PASSWORD", "DevKing!2026")
    upsert_user("dev-admin-0001", "dev-admin@kingkaraoke2025.com", "Dev Admin", pw, True, "global_admin")
    upsert_user("dev-singer-0001", "singer1@kingkaraoke2025.com", "Royal Singer One", "Singer!2026", False, "singer")
    upsert_user("dev-singer-0002", "singer2@kingkaraoke2025.com", "Royal Singer Two", "Singer!2026", False, "singer")
    print("seed done")
