"""Backend E2E: Staff (Venue KJ) authorization model.
Signup grants no staff; only global_admin grants/activates/scopes; deactivation is immediate."""
import time, requests

BASE = "http://localhost:8001/api"
VENUE_A = "c9a5f1bb-2fd1-4143-97c2-336cb327ab14"   # Test Venue (in KJ scope)
EVENT_A = "d43c3271-7623-45c3-83e3-fd69ac4a5920"   # Test Karaoke Night @ Test Venue
EVENT_B = "299a34aa-543c-4dcb-a4f7-7926718251b7"   # Other Event (Other Venue)

def H(t): return {"Authorization": f"Bearer {t}"}
def login(e, p): 
    r = requests.post(f"{BASE}/auth/login", json={"email": e, "password": p}); r.raise_for_status(); return r.json()["token"]

passed, failed = [], []
def check(name, cond, extra=""):
    (passed if cond else failed).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))

admin = login("dev-admin@kingkaraoke2025.com", "DevKing!2026")
singer = login("singer1@kingkaraoke2025.com", "Singer!2026")

# 1. New signup -> singer, no staff
email = f"kjtest_{int(time.time())}@example.com"
reg = requests.post(f"{BASE}/auth/register", json={"email": email, "password": "Test!2026", "display_name": "KJ Test"}).json()
uid = reg["user"]["id"]; utok = reg["user"] and login(email, "Test!2026")
me = requests.get(f"{BASE}/auth/me", headers=H(utok)).json()
check("New signup role=singer", me["role"] == "singer", me.get("role"))
check("New signup staff_active=False", me["staff_active"] is False, str(me.get("staff_active")))
check("New signup denied events list -> 403", requests.get(f"{BASE}/admin/events", headers=H(utok)).status_code == 403)
check("New signup event op -> 403", requests.get(f"{BASE}/admin/events/{EVENT_A}", headers=H(utok)).status_code == 403)

# 2. Grant venue_kj but INACTIVE
r = requests.put(f"{BASE}/admin/users/{uid}/staff", headers=H(admin),
                 json={"role": "venue_kj", "staff_active": False, "venue_ids": [VENUE_A]})
check("Admin grants venue_kj (inactive)", r.status_code == 200, f"{r.status_code} {r.text}")
me = requests.get(f"{BASE}/auth/me", headers=H(utok)).json()
check("Role now venue_kj", me["role"] == "venue_kj")
check("Still inactive", me["staff_active"] is False)
check("Inactive KJ denied events list -> 403", requests.get(f"{BASE}/admin/events", headers=H(utok)).status_code == 403)
check("Inactive KJ event op -> 403", requests.get(f"{BASE}/admin/events/{EVENT_A}", headers=H(utok)).status_code == 403)
check("Inactive KJ QR -> 403", requests.get(f"{BASE}/admin/events/{EVENT_A}/qr", headers=H(utok)).status_code == 403)

# 3. Activate
r = requests.put(f"{BASE}/admin/users/{uid}/staff", headers=H(admin),
                 json={"role": "venue_kj", "staff_active": True, "venue_ids": [VENUE_A]})
check("Admin activates staff", r.status_code == 200)
me = requests.get(f"{BASE}/auth/me", headers=H(utok)).json()
check("Now active", me["staff_active"] is True)
evs = requests.get(f"{BASE}/admin/events", headers=H(utok)).json()
check("Active KJ sees ONLY Venue A events", len(evs) > 0 and all(e["venue_id"] == VENUE_A for e in evs), str([e['venue_id'] for e in evs]))
check("Active KJ can read Event A", requests.get(f"{BASE}/admin/events/{EVENT_A}", headers=H(utok)).status_code == 200)
check("Active KJ QR Event A 200", requests.get(f"{BASE}/admin/events/{EVENT_A}/qr", headers=H(utok)).status_code == 200)
check("Active KJ blocked from Event B (other venue) -> 403", requests.get(f"{BASE}/admin/events/{EVENT_B}", headers=H(utok)).status_code == 403)
check("Active KJ battles in Event B -> 403", requests.post(f"{BASE}/events/{EVENT_B}/battles", headers=H(utok), json={"challenger_id":"x","opponent_id":"y","challenge_type":"royal_duel"}).status_code == 403)

# 4. Revoke (back to singer)
r = requests.put(f"{BASE}/admin/users/{uid}/staff", headers=H(admin), json={"role": "singer", "staff_active": False, "venue_ids": []})
check("Admin revokes staff", r.status_code == 200)
me = requests.get(f"{BASE}/auth/me", headers=H(utok)).json()
check("Revoked -> role singer", me["role"] == "singer")
check("Revoked -> immediate 403 on Event A (token unchanged)", requests.get(f"{BASE}/admin/events/{EVENT_A}", headers=H(utok)).status_code == 403)
check("Revoked -> events list denied 403", requests.get(f"{BASE}/admin/events", headers=H(utok)).status_code == 403)

# 5. Privilege boundaries
check("Singer cannot list staff -> 403", requests.get(f"{BASE}/admin/staff", headers=H(singer)).status_code == 403)
check("Singer cannot call set_staff -> 403", requests.put(f"{BASE}/admin/users/{uid}/staff", headers=H(singer), json={"role":"venue_kj","staff_active":True,"venue_ids":[VENUE_A]}).status_code == 403)
# reactivate our test KJ then confirm KJ cannot self-grant/admin
requests.put(f"{BASE}/admin/users/{uid}/staff", headers=H(admin), json={"role":"venue_kj","staff_active":True,"venue_ids":[VENUE_A]})
check("KJ cannot self-manage staff -> 403", requests.put(f"{BASE}/admin/users/{uid}/staff", headers=H(utok), json={"role":"venue_kj","staff_active":True,"venue_ids":[VENUE_A]}).status_code == 403)
check("KJ cannot list all users -> 403", requests.get(f"{BASE}/admin/users", headers=H(utok)).status_code == 403)
check("KJ cannot toggle-admin -> 403", requests.post(f"{BASE}/admin/users/{uid}/toggle-admin", headers=H(utok)).status_code == 403)
# 6. Cannot assign global_admin via staff endpoint
check("Cannot set role=global_admin -> 400", requests.put(f"{BASE}/admin/users/{uid}/staff", headers=H(admin), json={"role":"global_admin","staff_active":True}).status_code == 400)
# 7. Cannot grant with phantom venue
check("Unknown venue rejected -> 400", requests.put(f"{BASE}/admin/users/{uid}/staff", headers=H(admin), json={"role":"venue_kj","staff_active":True,"venue_ids":["nope-123"]}).status_code == 400)
# 8. Admin cannot modify another admin's staff via this endpoint
admin_id = requests.get(f"{BASE}/auth/me", headers=H(admin)).json()["id"]
check("Cannot modify global_admin via staff endpoint -> 403", requests.put(f"{BASE}/admin/users/{admin_id}/staff", headers=H(admin), json={"role":"singer","staff_active":False}).status_code == 403)

# cleanup: revoke test user
requests.put(f"{BASE}/admin/users/{uid}/staff", headers=H(admin), json={"role":"singer","staff_active":False,"venue_ids":[]})

print(f"\n==== {len(passed)} passed, {len(failed)} failed ====")
if failed: print("FAILED:", failed)
