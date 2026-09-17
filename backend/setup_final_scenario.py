"""Deterministic, idempotent setup for the FINAL Phase 2 E2E verification (isolated dev DB).
Creates the named scenario + 4 role users with correct scopes + an out-of-scope 'Other'
hierarchy for negative isolation tests. Safe to re-run. Prints all IDs."""
import os
from datetime import datetime, timezone
from pathlib import Path

import bcrypt
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parent / ".env")
BASE = "http://localhost:8001/api"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
ADMIN_PW = os.environ.get("DEV_ADMIN_PASSWORD", "DevKing!2026")


def H(t):
    return {"Authorization": f"Bearer {t}"}


def login(email, pw):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    r.raise_for_status()
    return r.json()["token"]


def upsert_user(uid, email, name, pw, is_admin, role, scope):
    now = datetime.now(timezone.utc).isoformat()
    doc = {"id": uid, "email": email, "display_name": name,
           "password": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(),
           "title_preference": "male", "points": 0, "nightly_points": 0, "songs_performed": 0,
           "consecutive_visits": 0, "badges": [], "is_admin": is_admin, "role": role,
           "role_scope": scope, "created_at": now, "last_visit": now}
    if db.users.find_one({"email": email}):
        db.users.update_one({"email": email}, {"$set": {"is_admin": is_admin, "role": role,
                             "role_scope": scope, "password": doc["password"], "display_name": name}})
    else:
        db.users.insert_one(doc)


def get_or_create_location(t, name, **kw):
    for l in requests.get(f"{BASE}/admin/locations", headers=H(t)).json():
        if l["name"] == name:
            return l
    return requests.post(f"{BASE}/admin/locations", headers=H(t), json={"name": name, **kw}).json()


def get_or_create_venue(t, location_id, name):
    for v in requests.get(f"{BASE}/admin/venues", headers=H(t), params={"location_id": location_id}).json():
        if v["name"] == name:
            return v
    return requests.post(f"{BASE}/admin/venues", headers=H(t), json={"location_id": location_id, "name": name}).json()


def get_or_create_event(t, venue_id, name, date, status="active"):
    for e in requests.get(f"{BASE}/admin/events", headers=H(t)).json():
        if e["name"] == name and e["venue_id"] == venue_id:
            return e
    return requests.post(f"{BASE}/admin/events", headers=H(t),
                         json={"venue_id": venue_id, "name": name, "event_date": date, "status": status}).json()


if __name__ == "__main__":
    # global_admin must exist first
    upsert_user("dev-admin-0001", "dev-admin@kingkaraoke2025.com", "Dev Admin", ADMIN_PW, True, "global_admin", {"location_ids": [], "venue_ids": []})
    upsert_user("dev-singer-0001", "singer1@kingkaraoke2025.com", "Royal Singer One", "Singer!2026", False, "singer", {"location_ids": [], "venue_ids": []})
    upsert_user("dev-singer-0002", "singer2@kingkaraoke2025.com", "Royal Singer Two", "Singer!2026", False, "singer", {"location_ids": [], "venue_ids": []})
    admin = login("dev-admin@kingkaraoke2025.com", ADMIN_PW)

    # In-scope hierarchy
    loc = get_or_create_location(admin, "Test Location", city="Chicago", state="IL")
    ven = get_or_create_venue(admin, loc["id"], "Test Venue")
    evA = get_or_create_event(admin, ven["id"], "Test Karaoke Night", "2026-06-20")   # Event A
    evB = get_or_create_event(admin, ven["id"], "Second Night", "2026-06-21")          # Event B

    # Out-of-scope hierarchy (for negative tests)
    other_loc = get_or_create_location(admin, "Other Location", city="Dallas", state="TX")
    other_ven = get_or_create_venue(admin, other_loc["id"], "Other Venue")
    other_ev = get_or_create_event(admin, other_ven["id"], "Other Event", "2026-06-22")

    # Scoped staff users
    upsert_user("dev-lm-0001", "lm@kingkaraoke2025.com", "Location Manager", "Manager!2026", False, "location_manager", {"location_ids": [loc["id"]], "venue_ids": []})
    upsert_user("dev-kj-0001", "kj@kingkaraoke2025.com", "Venue KJ", "Kj!2026", False, "venue_kj", {"location_ids": [], "venue_ids": [ven["id"]]})

    print("SCENARIO READY")
    print("Test Location:", loc["id"])
    print("Test Venue:", ven["id"])
    print("Event A (Test Karaoke Night):", evA["id"])
    print("Event B (Second Night):", evB["id"])
    print("Other Location:", other_loc["id"])
    print("Other Venue:", other_ven["id"])
    print("Other Event:", other_ev["id"])
