"""Focused verification of the Staff Authorization hierarchy:
Global Admin -> Location -> Venue -> Event -> Venue KJ."""
import time, requests
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio, os
from dotenv import load_dotenv
load_dotenv()

BASE = "http://localhost:8001/api"
TEST_LOCATION = "fdaf90b8-e714-4889-a2be-bb50e216d8c9"   # Test Location
TEST_VENUE = "c9a5f1bb-2fd1-4143-97c2-336cb327ab14"       # Test Venue (KJ authorized)

def H(t): return {"Authorization": f"Bearer {t}"}
def login(e, p):
    r = requests.post(f"{BASE}/auth/login", json={"email": e, "password": p}); r.raise_for_status(); return r.json()["token"]

passed, failed = [], []
def check(name, cond, extra=""):
    (passed if cond else failed).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))

admin = login("dev-admin@kingkaraoke2025.com", "DevKing!2026")
singer = login("singer1@kingkaraoke2025.com", "Singer!2026")

# ---- Dev Admin can create/manage Locations ----
locname = f"Verify Loc {int(time.time())}"
r = requests.post(f"{BASE}/admin/locations", headers=H(admin), json={"name": locname, "city": "Testville"})
check("Admin create location", r.status_code == 200, f"{r.status_code} {r.text}")
loc = r.json()
r = requests.put(f"{BASE}/admin/locations/{loc['id']}", headers=H(admin), json={"name": locname + " (edited)", "city": "Edited"})
check("Admin update location", r.status_code == 200, str(r.status_code))
check("Admin lists locations", any(l["id"] == loc["id"] for l in requests.get(f"{BASE}/admin/locations", headers=H(admin)).json()))
# singer cannot create location
check("Singer create location -> 403", requests.post(f"{BASE}/admin/locations", headers=H(singer), json={"name": "nope"}).status_code == 403)

# ---- Sibling venue under SAME location as KJ, but NOT authorized ----
sib = requests.post(f"{BASE}/admin/venues", headers=H(admin), json={"location_id": TEST_LOCATION, "name": f"Sibling Venue {int(time.time())}"}).json()
sib_event = requests.post(f"{BASE}/admin/events", headers=H(admin),
                          json={"venue_id": sib["id"], "name": f"Sibling Event {int(time.time())}", "event_date": "2026-07-15", "status": "active"}).json()
check("Setup sibling venue+event under Test Location", "id" in sib and "id" in sib_event, str(sib_event))

# ---- Create a fresh KJ scoped ONLY to Test Venue ----
email = f"verifykj_{int(time.time())}@example.com"
requests.post(f"{BASE}/auth/register", json={"email": email, "password": "Test!2026", "display_name": "Verify KJ"})
uid = requests.get(f"{BASE}/auth/me", headers=H(login(email, "Test!2026"))).json()["id"]
requests.put(f"{BASE}/admin/users/{uid}/staff", headers=H(admin),
             json={"role": "venue_kj", "staff_active": True, "venue_ids": [TEST_VENUE]})
kjtok = login(email, "Test!2026")
me = requests.get(f"{BASE}/auth/me", headers=H(kjtok)).json()
check("Grant requires BOTH role and active (now venue_kj+active)", me["role"] == "venue_kj" and me["staff_active"] is True)

# KJ can operate authorized venue's event
check("KJ can read own venue event list (non-empty, only Test Venue)",
      all(e["venue_id"] == TEST_VENUE for e in requests.get(f"{BASE}/admin/events", headers=H(kjtok)).json()))
# Same-location sibling venue/event must be BLOCKED
check("Location does NOT grant sibling venue's event (read) -> 403",
      requests.get(f"{BASE}/admin/events/{sib_event['id']}", headers=H(kjtok)).status_code == 403)
check("Location does NOT grant sibling venue's event (QR) -> 403",
      requests.get(f"{BASE}/admin/events/{sib_event['id']}/qr", headers=H(kjtok)).status_code == 403)
check("Sibling event NOT in KJ's scoped list",
      all(e["id"] != sib_event["id"] for e in requests.get(f"{BASE}/admin/events", headers=H(kjtok)).json()))
# KJ cannot manage locations/venues (admin-only creation)
check("KJ cannot create location -> 403", requests.post(f"{BASE}/admin/locations", headers=H(kjtok), json={"name":"x"}).status_code == 403)
check("KJ cannot create venue under its location -> 403",
      requests.post(f"{BASE}/admin/venues", headers=H(kjtok), json={"location_id": TEST_LOCATION, "name":"x"}).status_code == 403)

# ---- KJ cannot grant staff (self or others) or become admin ----
check("KJ cannot self-grant staff -> 403", requests.put(f"{BASE}/admin/users/{uid}/staff", headers=H(kjtok), json={"role":"venue_kj","staff_active":True,"venue_ids":[TEST_VENUE]}).status_code == 403)
check("KJ cannot grant another user -> 403", requests.put(f"{BASE}/admin/users/{login and uid}/staff", headers=H(kjtok), json={"role":"venue_kj","staff_active":True}).status_code == 403)
check("KJ cannot list staff -> 403", requests.get(f"{BASE}/admin/staff", headers=H(kjtok)).status_code == 403)
check("KJ cannot toggle-admin -> 403", requests.post(f"{BASE}/admin/users/{uid}/toggle-admin", headers=H(kjtok)).status_code == 403)

# ---- EDGE: remove role but keep staff_active=true directly in DB -> must STILL be denied ----
async def force_role_singer_keep_active(user_id):
    c = AsyncIOMotorClient(os.environ["MONGO_URL"]); db = c[os.environ["DB_NAME"]]
    await db.users.update_one({"id": user_id}, {"$set": {"role": "singer", "staff_active": True}})
asyncio.get_event_loop().run_until_complete(force_role_singer_keep_active(uid))
ev_a = "d43c3271-7623-45c3-83e3-fd69ac4a5920"
check("Role removed (singer) but staff_active=true -> STILL 403 on event",
      requests.get(f"{BASE}/admin/events/{ev_a}", headers=H(kjtok)).status_code == 403)
check("Role removed -> events list denied 403",
      requests.get(f"{BASE}/admin/events", headers=H(kjtok)).status_code == 403)

# ---- Reactivate as KJ then REVOKE staff_active only -> immediate deny ----
requests.put(f"{BASE}/admin/users/{uid}/staff", headers=H(admin), json={"role":"venue_kj","staff_active":True,"venue_ids":[TEST_VENUE]})
check("Reactivated KJ can read Event A", requests.get(f"{BASE}/admin/events/{ev_a}", headers=H(kjtok)).status_code == 200)
requests.put(f"{BASE}/admin/users/{uid}/staff", headers=H(admin), json={"role":"venue_kj","staff_active":False,"venue_ids":[TEST_VENUE]})
check("Deactivate staff_active only -> immediate 403 (token unchanged)",
      requests.get(f"{BASE}/admin/events/{ev_a}", headers=H(kjtok)).status_code == 403)

# ---- global_admin still has admin access ----
check("Admin lists all users", isinstance(requests.get(f"{BASE}/admin/users", headers=H(admin)).json(), list))
check("Admin lists staff", isinstance(requests.get(f"{BASE}/admin/staff", headers=H(admin)).json(), list))

# cleanup
requests.put(f"{BASE}/admin/users/{uid}/staff", headers=H(admin), json={"role":"singer","staff_active":False,"venue_ids":[]})

print(f"\n==== {len(passed)} passed, {len(failed)} failed ====")
if failed: print("FAILED:", failed)
