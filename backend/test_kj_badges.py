"""Verify KJ event-award badge behavior: unlock, idempotency, milestone, event/season attribution, isolation."""
import time, requests, asyncio, os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
load_dotenv()

BASE = "http://localhost:8001/api"
E_A = "d43c3271-7623-45c3-83e3-fd69ac4a5920"
VENUE_A = "c9a5f1bb-2fd1-4143-97c2-336cb327ab14"
def H(t): return {"Authorization": f"Bearer {t}"}
def login(e, p): return requests.post(f"{BASE}/auth/login", json={"email": e, "password": p}).json()["token"]

passed, failed = [], []
def check(n, c, x=""):
    (passed if c else failed).append(n); print(("PASS " if c else "FAIL ") + n + (f"  [{x}]" if x and not c else ""))

async def dbget(uid):
    c = AsyncIOMotorClient(os.environ["MONGO_URL"]); db = c[os.environ["DB_NAME"]]
    u = await db.users.find_one({"id": uid}, {"_id": 0, "badges": 1, "points": 1, "songs_performed": 1})
    accs = await db.accomplishments.count_documents({"user_id": uid})
    return u, accs

kj = login("kj@kingkaraoke2025.com", "Kj!2026")
admin = login("dev-admin@kingkaraoke2025.com", "DevKing!2026")

# Fresh singer checked into Event A via a fresh check-in token
sl = requests.get(f"{BASE}/events/{E_A}/singer-list", headers=H(kj)).json()["singers"]
kota = next((s for s in sl if "kota" in s["display_name"].lower()), None)
target = kota or sl[0]
uid = target["user_id"]
u0, acc0 = asyncio.get_event_loop().run_until_complete(dbget(uid))
life0 = u0["points"]; had_rw = "random_warrior" in u0["badges"]

# --- Award random_song -> random_warrior badge ---
r = requests.post(f"{BASE}/events/{E_A}/award-points", headers=H(kj),
                  json={"user_id": uid, "points": 200, "action_id": "random_song", "notes": "Random Song Challenge"})
check("Award random_song returns 200", r.status_code == 200, f"{r.status_code} {r.text}")
body = r.json()
u1, acc1 = asyncio.get_event_loop().run_until_complete(dbget(uid))
check("random_warrior badge now on user", "random_warrior" in u1["badges"], str(u1["badges"]))
if not had_rw:
    check("Response reports badge earned", "random_warrior" in body.get("badges_earned", []), str(body))
    check("Accomplishment recorded", acc1 == acc0 + 1, f"{acc0}->{acc1}")
check("Lifetime points mirror manual award (legacy parity: action +200, +200 badge if first-time)",
      u1["points"] == life0 + 200 + (0 if had_rw else 200), f"{life0}->{u1['points']} had_rw={had_rw}")

# --- Idempotency: repeat random_song -> no duplicate badge ---
r2 = requests.post(f"{BASE}/events/{E_A}/award-points", headers=H(kj),
                   json={"user_id": uid, "points": 200, "action_id": "random_song", "notes": "again"})
u2, acc2 = asyncio.get_event_loop().run_until_complete(dbget(uid))
check("No duplicate random_warrior badge", u2["badges"].count("random_warrior") == 1)
check("No duplicate accomplishment for same badge", acc2 == acc1, f"{acc1}->{acc2}")
check("Second call reports no new badge", "random_warrior" not in r2.json().get("badges_earned", []))

# --- Milestone: fresh user, first sing_song -> first_song badge ---
email = f"badgekj_{int(time.time())}@ex.com"
reg = requests.post(f"{BASE}/auth/register", json={"email": email, "password": "Test!2026", "display_name": "Badge KJ"}).json()
nuid = reg["user"]["id"]
# check them into Event A: get QR token as KJ, then checkin as the new user
qr = requests.get(f"{BASE}/admin/events/{E_A}/qr", headers=H(kj)).json()
token = qr["checkin_path"].rsplit("/", 1)[-1]
ntok = login(email, "Test!2026")
ci = requests.post(f"{BASE}/e/checkin/{token}", headers=H(ntok))
check("Fresh singer checked into Event A", ci.status_code == 200, f"{ci.status_code} {ci.text[:120]}")
nu0, _ = asyncio.get_event_loop().run_until_complete(dbget(nuid))
r3 = requests.post(f"{BASE}/events/{E_A}/award-points", headers=H(kj),
                   json={"user_id": nuid, "points": 10, "action_id": "sing_song", "notes": "Sing a Song"})
check("Award sing_song 200", r3.status_code == 200, f"{r3.status_code} {r3.text}")
nu1, _ = asyncio.get_event_loop().run_until_complete(dbget(nuid))
check("songs_performed incremented", nu1["songs_performed"] == nu0["songs_performed"] + 1, f"{nu0['songs_performed']}->{nu1['songs_performed']}")
check("first_song milestone badge unlocked", "first_song" in nu1["badges"], str(nu1["badges"]))
check("Lifetime mirrors legacy: +10 check-in, +10 sing_song, +10 first_song badge = 30", nu1["points"] == 30, str(nu1["points"]))

# --- Singer-facing badge display still works (GET badges/me) ---
bm = requests.get(f"{BASE}/auth/me", headers=H(ntok))
check("Singer-facing badge display (/auth/me) shows first_song", bm.status_code == 200 and "first_song" in bm.json().get("badges", []), str(bm.status_code)+" "+str(bm.json().get("badges")))

# --- Isolation: KJ cannot award (or badge) in another event ---
r4 = requests.post(f"{BASE}/events/299a34aa-543c-4dcb-a4f7-7926718251b7/award-points", headers=H(kj),
                   json={"user_id": nuid, "points": 200, "action_id": "random_song"})
check("KJ award+badge in other event -> 403", r4.status_code == 403, str(r4.status_code))

# --- Singer cannot self-award badges ---
r5 = requests.post(f"{BASE}/events/{E_A}/award-points", headers=H(ntok),
                   json={"user_id": nuid, "points": 200, "action_id": "random_song"})
check("Singer self-award -> 403", r5.status_code == 403, str(r5.status_code))

# cleanup fresh user staff (none) — leave as singer
print(f"\n==== {len(passed)} passed, {len(failed)} failed ====")
if failed: print("FAILED:", failed)
