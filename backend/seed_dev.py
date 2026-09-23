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


def ensure_staff_scope():
    """Deterministically guarantee the canonical DEV staff (Venue KJ + Location Manager) keep a
    valid authorization scope, so the KJ Events list never silently goes empty after test runs.

    IMPORTANT: this only FILLS a missing/empty scope — it will NOT overwrite a manually
    configured non-empty assignment (respects deliberate DEV changes). It never touches
    production (isolated dev DB only) and never demotes an active staff member."""
    loc = db.locations.find_one({"name": "Test Location"}, {"_id": 0, "id": 1})
    ven = db.venues.find_one({"name": "Test Venue"}, {"_id": 0, "id": 1})

    def _ensure(email, name, pw, role, scope_key, scope_id):
        u = db.users.find_one({"email": email})
        canonical = {"location_ids": [], "venue_ids": []}
        canonical[scope_key] = [scope_id] if scope_id else []
        if not u:
            now = datetime.now(timezone.utc).isoformat()
            db.users.insert_one({
                "id": f"dev-{role}-0001", "email": email, "display_name": name,
                "password": _hash(pw), "title_preference": "male", "referred_by": None,
                "points": 0, "nightly_points": 0, "songs_performed": 0, "consecutive_visits": 0,
                "badges": [], "is_admin": False, "role": role, "staff_active": True,
                "role_scope": canonical, "created_at": now, "last_visit": now})
            print(f"created {email} ({role}) scope={canonical}")
            return
        current = u.get("role_scope") or {"location_ids": [], "venue_ids": []}
        # Only (re)fill when the relevant scope list is empty/missing — never clobber manual config.
        if not current.get(scope_key):
            db.users.update_one({"email": email}, {"$set": {
                "role": role, "staff_active": True, "role_scope": canonical}})
            print(f"restored {email} ({role}) scope={canonical}")
        else:
            print(f"kept {email} existing scope={current.get(scope_key)}")

    if ven:
        _ensure("kj@kingkaraoke2025.com", "Venue KJ", "Kj!2026", "venue_kj", "venue_ids", ven["id"])
    if loc:
        _ensure("lm@kingkaraoke2025.com", "Location Manager", "Manager!2026", "location_manager", "location_ids", loc["id"])


def ensure_active_event():
    """Idempotently guarantee the KJ's Test Venue has ONE active event, so the KJ Console
    always has a 'Run Show' target out-of-the-box (dev DB only). Never creates a second one
    if an active event already exists there; never touches production."""
    loc = db.locations.find_one({"name": "Test Location"}, {"_id": 0, "id": 1})
    ven = db.venues.find_one({"name": "Test Venue"}, {"_id": 0, "id": 1, "location_id": 1})
    if not ven:
        print("no Test Venue — skipping active-event seed")
        return
    location_id = ven.get("location_id") or (loc or {}).get("id")
    existing = db.events.find_one({"venue_id": ven["id"], "status": "active"}, {"_id": 0, "id": 1})
    if existing:
        print(f"kept active event {existing['id']} for Test Venue")
        return
    now = datetime.now(timezone.utc)
    ev = {
        "id": "dev-event-0001", "venue_id": ven["id"], "location_id": location_id,
        "name": "Dev Karaoke Night", "slug": "dev-karaoke-night",
        "event_date": now.strftime("%Y-%m-%d"), "status": "active",
        "starts_at": None, "ends_at": None, "qr_secret": None,
        "is_sample": True, "is_default_legacy": False, "env": "development",
        "created_at": now.isoformat(), "updated_at": now.isoformat(),
    }
    db.events.update_one({"id": ev["id"]}, {"$set": ev}, upsert=True)
    print(f"created active event {ev['id']} for Test Venue")


if __name__ == "__main__":
    pw = os.environ.get("DEV_ADMIN_PASSWORD", "DevKing!2026")
    upsert_user("dev-admin-0001", "dev-admin@kingkaraoke2025.com", "Dev Admin", pw, True, "global_admin")
    upsert_user("dev-singer-0001", "singer1@kingkaraoke2025.com", "Royal Singer One", "Singer!2026", False, "singer")
    upsert_user("dev-singer-0002", "singer2@kingkaraoke2025.com", "Royal Singer Two", "Singer!2026", False, "singer")
    upsert_user("dev-singer-0003", "dakota@hotmail.com", "King Kota", "Dakota!2026", False, "singer")
    ensure_staff_scope()
    ensure_active_event()
    print("seed done")
