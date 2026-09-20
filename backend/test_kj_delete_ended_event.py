"""DEFINITIVE RULE test: an active authorized venue_kj may permanently delete an ENDED event
even when it holds historical data; all event-owned records are purged. Non-ended events with
history stay protected (409). Archived (even prev=ended) stay on archive/restore (409).
Isolation: singer/cross-venue/inactive-KJ cannot delete."""
import os, time, uuid, requests
from pymongo import MongoClient

BASE = "http://localhost:8001/api"
VENUE_A = "c9a5f1bb-2fd1-4143-97c2-336cb327ab14"
E_B_VENUE_EVENT = "299a34aa-543c-4dcb-a4f7-7926718251b7"  # other-venue event
db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "king_klub_phase2_dev")]

def H(t): return {"Authorization": f"Bearer {t}"}
def login(e, p): return requests.post(f"{BASE}/auth/login", json={"email": e, "password": p}).json()["token"]
passed, failed = [], []
def check(n, c, x=""):
    (passed if c else failed).append(n); print(("PASS " if c else "FAIL ") + n + (f"  [{x}]" if x and not c else ""))

admin = login("dev-admin@kingkaraoke2025.com", "DevKing!2026")
kj = login("kj@kingkaraoke2025.com", "Kj!2026")
singer = login("singer1@kingkaraoke2025.com", "Singer!2026")

OWNED = ["event_queue", "event_challenge_votes", "event_challenges", "event_perk_usage",
         "perk_usage", "event_participation", "event_checkins", "event_checkin_attempts",
         "season_accomplishments", "point_ledger"]

def seed_history(event_id):
    """Insert one row of every event-owned kind so the event clearly has history."""
    for coll in OWNED:
        db[coll].insert_one({"id": str(uuid.uuid4()), "event_id": event_id,
                             "dedupe_key": str(uuid.uuid4()), "_seed": True})

def make_event(status):
    r = requests.post(f"{BASE}/admin/events", headers=H(kj),
                      json={"venue_id": VENUE_A, "name": f"T {status} {uuid.uuid4().hex[:6]}",
                            "event_date": "2026-08-01", "status": status})
    return r.json()["id"]

def owned_count(event_id):
    return sum(db[c].count_documents({"event_id": event_id}) for c in OWNED)

# --- 1. ENDED event WITH history -> KJ permanent delete succeeds + purges everything ---
ev = make_event("ended")
seed_history(ev)
before = owned_count(ev)
check("Ended event has seeded history", before == len(OWNED), f"{before}")
r = requests.delete(f"{BASE}/admin/events/{ev}", headers=H(kj))
check("KJ deletes ENDED event w/ history -> 200", r.status_code == 200, f"{r.status_code} {r.text[:160]}")
check("Delete response reports purged_history", r.status_code == 200 and r.json().get("purged_history") is True, r.text[:120])
check("Event document gone", db.events.count_documents({"id": ev}) == 0)
check("All event-owned history purged", owned_count(ev) == 0, f"remaining={owned_count(ev)}")
# ensure we didn't nuke venue/location/users
check("Venue NOT deleted", db.venues.count_documents({"id": VENUE_A}) == 1)

# --- 1b. AUDIT record was written BEFORE purge and survives the deletion ---
aud = db.event_deletion_audit.find_one({"event_id": ev}, {"_id": 0})
check("Audit record created for deleted ended event", aud is not None)
if aud:
    check("Audit has actor id + name", bool(aud.get("actor_user_id")) and "actor_display_name" in aud)
    check("Audit has event/venue/location identity", aud.get("event_name") and aud.get("venue_id") == VENUE_A and "venue_name" in aud and "location_name" in aud)
    check("Audit action = permanent_delete_ended_event", aud.get("action") == "permanent_delete_ended_event")
    check("Audit stores NO detailed history rows", not any(k in aud for k in ("participants_list", "queue", "battles", "votes", "singers")))

# --- 1c. Probing: unknown / already-deleted id -> non-disclosing 403 (not 404) ---
check("Delete already-deleted ended id -> 403", requests.delete(f"{BASE}/admin/events/{ev}", headers=H(kj)).status_code == 403)
check("Delete nonexistent id -> 403", requests.delete(f"{BASE}/admin/events/{uuid.uuid4()}", headers=H(kj)).status_code == 403)


# --- 2. Non-ended (scheduled) event WITH history stays protected (409) ---
ev2 = make_event("scheduled")
seed_history(ev2)
r = requests.delete(f"{BASE}/admin/events/{ev2}", headers=H(kj))
check("Scheduled event w/ history -> 409", r.status_code == 409 and "dependents" in (r.json().get("detail") or {}), f"{r.status_code}")
check("Scheduled event history NOT purged", owned_count(ev2) == len(OWNED))
# active status too
requests.put(f"{BASE}/admin/events/{ev2}", headers=H(kj), json={"name": "x", "event_date": "2026-08-01", "status": "active"})
check("Active event w/ history -> 409", requests.delete(f"{BASE}/admin/events/{ev2}", headers=H(kj)).status_code == 409)

# --- 3. Archived event (prev ended) is NOT eligible for the special delete path (409) ---
ev3 = make_event("ended")
seed_history(ev3)
requests.post(f"{BASE}/admin/events/{ev3}/archive", headers=H(kj))  # status -> archived, prev_status ended
r = requests.delete(f"{BASE}/admin/events/{ev3}", headers=H(kj))
check("Archived (prev ended) event w/ history -> 409", r.status_code == 409, f"{r.status_code} {r.text[:120]}")
check("Archived event history NOT purged", owned_count(ev3) == len(OWNED))

# --- 4. Isolation on the ENDED delete path ---
ev4 = make_event("ended")
seed_history(ev4)
check("Singer delete ended event -> 403", requests.delete(f"{BASE}/admin/events/{ev4}", headers=H(singer)).status_code == 403)
check("Singer did NOT purge history", owned_count(ev4) == len(OWNED))
# cross-venue ended event: force E_B to ended, KJ (not authorized) must 403
db.events.update_one({"id": E_B_VENUE_EVENT}, {"$set": {"status": "ended"}})
check("KJ delete other-venue ENDED event -> 403", requests.delete(f"{BASE}/admin/events/{E_B_VENUE_EVENT}", headers=H(kj)).status_code == 403)
check("Other-venue event still present", db.events.count_documents({"id": E_B_VENUE_EVENT}) == 1)
# inactive KJ blocked
kj_id = requests.get(f"{BASE}/auth/me", headers=H(kj)).json()["id"]
requests.put(f"{BASE}/admin/users/{kj_id}/staff", headers=H(admin), json={"role": "venue_kj", "staff_active": False, "venue_ids": [VENUE_A]})
kj_off = login("kj@kingkaraoke2025.com", "Kj!2026")
check("Inactive KJ delete ended event -> 403", requests.delete(f"{BASE}/admin/events/{ev4}", headers=H(kj_off)).status_code == 403)
requests.put(f"{BASE}/admin/users/{kj_id}/staff", headers=H(admin), json={"role": "venue_kj", "staff_active": True, "venue_ids": [VENUE_A]})
kj = login("kj@kingkaraoke2025.com", "Kj!2026")
# now authorized active KJ cleans up ev4 (ended)
r = requests.delete(f"{BASE}/admin/events/{ev4}", headers=H(kj))
check("Re-activated KJ deletes ended ev4 -> 200", r.status_code == 200, f"{r.status_code}")

# --- 5. AUDIT trail endpoint: scoping + security ---
# KJ sees own-venue deletions (ev + ev4 were at VENUE_A)
kj_aud = requests.get(f"{BASE}/admin/event-deletions", headers=H(kj))
check("KJ can read audit endpoint -> 200", kj_aud.status_code == 200)
kj_rows = kj_aud.json().get("deletions", []) if kj_aud.status_code == 200 else []
check("KJ audit shows own-venue deletion(s)", any(x["event_id"] == ev for x in kj_rows))
check("KJ audit rows all within KJ venue scope", all(x.get("venue_id") == VENUE_A for x in kj_rows), str([x.get('venue_id') for x in kj_rows])[:160])
# Admin sees everything (>= KJ count)
adm_aud = requests.get(f"{BASE}/admin/event-deletions", headers=H(admin))
check("Admin can read audit endpoint -> 200", adm_aud.status_code == 200)
check("Admin audit count >= KJ audit count", len(adm_aud.json().get("deletions", [])) >= len(kj_rows))
# Singer denied
check("Singer cannot read audit endpoint -> 403", requests.get(f"{BASE}/admin/event-deletions", headers=H(singer)).status_code == 403)
# Audit is immutable via API (no PUT/DELETE routes) -> DELETE on the collection path 405/404
check("No audit mutation route (DELETE) -> 404/405", requests.delete(f"{BASE}/admin/event-deletions", headers=H(kj)).status_code in (404, 405))

# cleanup seeded rows / leftover events
for e in (ev2, ev3):
    for c in OWNED: db[c].delete_many({"event_id": e})
    db.events.delete_one({"id": e})
db.events.update_one({"id": E_B_VENUE_EVENT}, {"$set": {"status": "scheduled"}})

print(f"\n==== {len(passed)} passed, {len(failed)} failed ====")
if failed: print("FAILED:", failed)
