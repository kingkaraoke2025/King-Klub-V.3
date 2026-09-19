"""Location ZIP -> IANA timezone + safe delete/archive + authorization."""
import time, requests
BASE = "http://localhost:8001/api"
def H(t): return {"Authorization": f"Bearer {t}"}
def login(e, p): return requests.post(f"{BASE}/auth/login", json={"email": e, "password": p}).json()["token"]
passed, failed = [], []
def check(n, c, x=""):
    (passed if c else failed).append(n); print(("PASS " if c else "FAIL ") + n + (f"  [{x}]" if x and not c else ""))

admin = login("dev-admin@kingkaraoke2025.com", "DevKing!2026")
kj = login("kj@kingkaraoke2025.com", "Kj!2026")
singer = login("singer1@kingkaraoke2025.com", "Singer!2026")

# ZIP -> IANA
for z, tzexp in [("84301", "America/Denver"), ("60601", "America/Chicago"), ("10001", "America/New_York"), ("90001", "America/Los_Angeles")]:
    r = requests.get(f"{BASE}/admin/locations/zip-timezone", headers=H(admin), params={"zip": z}).json()
    check(f"ZIP {z} -> {tzexp}", r.get("ok") and r.get("timezone") == tzexp, str(r))
# invalid/ambiguous -> not ok, no guess
check("Invalid ZIP -> not ok", requests.get(f"{BASE}/admin/locations/zip-timezone", headers=H(admin), params={"zip": "abcde"}).json().get("ok") is False)
check("Unknown ZIP -> not ok", requests.get(f"{BASE}/admin/locations/zip-timezone", headers=H(admin), params={"zip": "00000"}).json().get("ok") is False)

# create with zip stores IANA
c = requests.post(f"{BASE}/admin/locations", headers=H(admin), json={"name": f"ZipLoc {int(time.time())}", "zip_code": "84301"})
check("Create with ZIP stores IANA tz", c.status_code == 200 and c.json().get("timezone") == "America/Denver" and c.json().get("zip_code") == "84301", str(c.json())[:120])
lid = c.json()["id"]
# edit changes zip -> recalculates
u = requests.put(f"{BASE}/admin/locations/{lid}", headers=H(admin), json={"name": c.json()["name"], "zip_code": "10001"})
check("Edit ZIP recalculates tz", u.status_code == 200 and u.json().get("timezone") == "America/New_York", str(u.json().get("timezone")))
# invalid zip on create -> 400, no save
check("Invalid ZIP create -> 400", requests.post(f"{BASE}/admin/locations", headers=H(admin), json={"name": "Bad", "zip_code": "00000"}).status_code == 400)
# location without zip still usable (existing behavior)
c2 = requests.post(f"{BASE}/admin/locations", headers=H(admin), json={"name": f"NoZip {int(time.time())}"})
check("Create without ZIP still works (default tz)", c2.status_code == 200 and c2.json().get("timezone"), str(c2.json().get("timezone")))
lid2 = c2.json()["id"]

# authorization
check("KJ cannot zip-lookup -> 403", requests.get(f"{BASE}/admin/locations/zip-timezone", headers=H(kj), params={"zip": "84301"}).status_code == 403)
check("KJ cannot create location -> 403", requests.post(f"{BASE}/admin/locations", headers=H(kj), json={"name": "x"}).status_code == 403)
check("KJ cannot delete location -> 403", requests.delete(f"{BASE}/admin/locations/{lid}", headers=H(kj)).status_code == 403)
check("KJ cannot archive location -> 403", requests.post(f"{BASE}/admin/locations/{lid}/archive", headers=H(kj)).status_code == 403)
check("Singer cannot delete location -> 403", requests.delete(f"{BASE}/admin/locations/{lid}", headers=H(singer)).status_code == 403)

# safe delete: no-deps hard delete OK
check("No-dep location hard delete OK", requests.delete(f"{BASE}/admin/locations/{lid}", headers=H(admin)).status_code == 200)
requests.delete(f"{BASE}/admin/locations/{lid2}", headers=H(admin))
# location WITH deps -> 409, archive instead
TL = "fdaf90b8-e714-4889-a2be-bb50e216d8c9"  # Test Location (has venues/events/staff)
d = requests.delete(f"{BASE}/admin/locations/{TL}", headers=H(admin))
check("Location with deps hard delete -> 409", d.status_code == 409 and "dependents" in (d.json().get("detail") or {}), str(d.json())[:120])
check("Archive location OK", requests.post(f"{BASE}/admin/locations/{TL}/archive", headers=H(admin)).status_code == 200)
arch = next((l for l in requests.get(f"{BASE}/admin/locations", headers=H(admin)).json() if l["id"] == TL), None)
check("Archived flag set + data preserved", arch and arch.get("archived") is True, str(arch)[:80] if arch else "missing")
check("Archived location's venues still exist", requests.get(f"{BASE}/admin/venues", headers=H(admin), params={"location_id": TL}).status_code == 200)
check("Unarchive OK", requests.post(f"{BASE}/admin/locations/{TL}/unarchive", headers=H(admin)).status_code == 200)

print(f"\n==== {len(passed)} passed, {len(failed)} failed ====")
if failed: print("FAILED:", failed)
