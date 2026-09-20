"""Venue KJ venue/event management + safe delete/archive + isolation."""
import time, requests
BASE = "http://localhost:8001/api"
VENUE_A = "c9a5f1bb-2fd1-4143-97c2-336cb327ab14"   # Test Venue (KJ authorized)
TEST_LOC = "fdaf90b8-e714-4889-a2be-bb50e216d8c9"  # Test Location
E_A = "d43c3271-7623-45c3-83e3-fd69ac4a5920"       # event at Test Venue (has participants)
OTHER_VENUE = None  # resolved below
def H(t): return {"Authorization": f"Bearer {t}"}
def login(e, p): return requests.post(f"{BASE}/auth/login", json={"email": e, "password": p}).json()["token"]
passed, failed = [], []
def check(n, c, x=""):
    (passed if c else failed).append(n); print(("PASS " if c else "FAIL ") + n + (f"  [{x}]" if x and not c else ""))

admin = login("dev-admin@kingkaraoke2025.com", "DevKing!2026")
kj = login("kj@kingkaraoke2025.com", "Kj!2026")
singer = login("singer1@kingkaraoke2025.com", "Singer!2026")

venues = requests.get(f"{BASE}/admin/venues", headers=H(admin)).json()
other = next((v for v in venues if v["id"] != VENUE_A), None)
OTHER_VENUE = other["id"] if other else None

# KJ can EDIT own venue
r = requests.put(f"{BASE}/admin/venues/{VENUE_A}", headers=H(kj), json={"location_id": TEST_LOC, "name": "Test Venue", "address": "123 Karaoke Ln"})
check("KJ edits own venue", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
# KJ CANNOT edit another venue
if OTHER_VENUE:
    check("KJ edits unauthorized venue -> 403", requests.put(f"{BASE}/admin/venues/{OTHER_VENUE}", headers=H(kj), json={"location_id": TEST_LOC, "name": "x"}).status_code == 403)
    check("KJ delete unauthorized venue -> 403", requests.delete(f"{BASE}/admin/venues/{OTHER_VENUE}", headers=H(kj)).status_code == 403)
    check("KJ archive unauthorized venue -> 403", requests.post(f"{BASE}/admin/venues/{OTHER_VENUE}/archive", headers=H(kj)).status_code == 403)

# KJ cannot delete/archive Locations (unchanged)
check("KJ delete location still 403", requests.delete(f"{BASE}/admin/locations/{TEST_LOC}", headers=H(kj)).status_code == 403)
check("KJ archive location still 403", requests.post(f"{BASE}/admin/locations/{TEST_LOC}/archive", headers=H(kj)).status_code == 403)

# Venue WITH events -> 409, then archive/unarchive by KJ
d = requests.delete(f"{BASE}/admin/venues/{VENUE_A}", headers=H(kj))
check("Delete venue w/ dependents -> 409", d.status_code == 409 and "dependents" in (d.json().get("detail") or {}), str(d.json())[:120])
check("KJ archive own venue OK", requests.post(f"{BASE}/admin/venues/{VENUE_A}/archive", headers=H(kj)).status_code == 200)
check("KJ unarchive own venue OK", requests.post(f"{BASE}/admin/venues/{VENUE_A}/unarchive", headers=H(kj)).status_code == 200)

# KJ creates a fresh empty venue? No — venue creation stays admin/LM. Admin makes empty venue in KJ scope, assign to KJ, KJ hard-deletes it.
nv = requests.post(f"{BASE}/admin/venues", headers=H(admin), json={"location_id": TEST_LOC, "name": f"Empty Venue {int(time.time())}"}).json()
nvid = nv["id"]
# authorize KJ for this venue too
kj_id = requests.get(f"{BASE}/auth/me", headers=H(kj)).json()["id"]
requests.put(f"{BASE}/admin/users/{kj_id}/staff", headers=H(admin), json={"role": "venue_kj", "staff_active": True, "venue_ids": [VENUE_A, nvid]})
kj = login("kj@kingkaraoke2025.com", "Kj!2026")  # refresh (scope from DB anyway)
check("KJ hard-deletes empty authorized venue", requests.delete(f"{BASE}/admin/venues/{nvid}", headers=H(kj)).status_code == 200)
# restore KJ scope
requests.put(f"{BASE}/admin/users/{kj_id}/staff", headers=H(admin), json={"role": "venue_kj", "staff_active": True, "venue_ids": [VENUE_A]})
kj = login("kj@kingkaraoke2025.com", "Kj!2026")

# EVENTS: KJ manages own venue's events; delete w/deps -> 409; archive/unarchive
check("KJ reads own event", requests.get(f"{BASE}/admin/events/{E_A}", headers=H(kj)).status_code == 200)
de = requests.delete(f"{BASE}/admin/events/{E_A}", headers=H(kj))
check("Delete event w/ history -> 409", de.status_code == 409 and "dependents" in (de.json().get("detail") or {}), str(de.json())[:120])
check("KJ archive own event OK", requests.post(f"{BASE}/admin/events/{E_A}/archive", headers=H(kj)).status_code == 200)
check("KJ unarchive own event OK", requests.post(f"{BASE}/admin/events/{E_A}/unarchive", headers=H(kj)).status_code == 200)
# KJ creates fresh empty event at own venue, then hard-deletes it
ne = requests.post(f"{BASE}/admin/events", headers=H(kj), json={"venue_id": VENUE_A, "name": f"Empty Event {int(time.time())}", "event_date": "2026-08-01", "status": "scheduled"})
check("KJ creates event at own venue", ne.status_code == 200, f"{ne.status_code} {ne.text[:120]}")
neid = ne.json()["id"]
check("KJ hard-deletes empty own event", requests.delete(f"{BASE}/admin/events/{neid}", headers=H(kj)).status_code == 200)

# Cross-venue event isolation
E_B = "299a34aa-543c-4dcb-a4f7-7926718251b7"
check("KJ delete other-venue event -> 403", requests.delete(f"{BASE}/admin/events/{E_B}", headers=H(kj)).status_code == 403)
check("KJ archive other-venue event -> 403", requests.post(f"{BASE}/admin/events/{E_B}/archive", headers=H(kj)).status_code == 403)

# Singer cannot manage
check("Singer edit venue -> 403", requests.put(f"{BASE}/admin/venues/{VENUE_A}", headers=H(singer), json={"location_id": TEST_LOC, "name": "x"}).status_code == 403)
check("Singer delete event -> 403", requests.delete(f"{BASE}/admin/events/{E_A}", headers=H(singer)).status_code == 403)

# Inactive KJ blocked
requests.put(f"{BASE}/admin/users/{kj_id}/staff", headers=H(admin), json={"role": "venue_kj", "staff_active": False, "venue_ids": [VENUE_A]})
kj_off = login("kj@kingkaraoke2025.com", "Kj!2026")
check("Inactive KJ edit venue -> 403", requests.put(f"{BASE}/admin/venues/{VENUE_A}", headers=H(kj_off), json={"location_id": TEST_LOC, "name": "x"}).status_code == 403)
check("Inactive KJ delete event -> 403", requests.delete(f"{BASE}/admin/events/{E_A}", headers=H(kj_off)).status_code == 403)
requests.put(f"{BASE}/admin/users/{kj_id}/staff", headers=H(admin), json={"role": "venue_kj", "staff_active": True, "venue_ids": [VENUE_A]})

print(f"\n==== {len(passed)} passed, {len(failed)} failed ====")
if failed: print("FAILED:", failed)
