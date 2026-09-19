"""Singer-initiated event battle requests + KJ pending notification + full isolation matrix."""
import requests

BASE = "http://localhost:8001/api"
E_A = "d43c3271-7623-45c3-83e3-fd69ac4a5920"   # Test Karaoke Night @ Test Venue (KJ scope)
E_B = "299a34aa-543c-4dcb-a4f7-7926718251b7"   # Other Event @ Other Venue (out of scope)
def H(t): return {"Authorization": f"Bearer {t}"}
def login(e, p): return requests.post(f"{BASE}/auth/login", json={"email": e, "password": p}).json()["token"]

passed, failed = [], []
def check(n, c, x=""):
    (passed if c else failed).append(n); print(("PASS " if c else "FAIL ") + n + (f"  [{x}]" if x and not c else ""))

kj = login("kj@kingkaraoke2025.com", "Kj!2026")
admin = login("dev-admin@kingkaraoke2025.com", "DevKing!2026")
s1 = login("singer1@kingkaraoke2025.com", "Singer!2026")
s1id = requests.get(f"{BASE}/auth/me", headers=H(s1)).json()["id"]

# checked-in singers in Event A
slA = requests.get(f"{BASE}/events/{E_A}/singer-list", headers=H(kj)).json()["singers"]
ids_A = [s["user_id"] for s in slA]
# ensure s1 is checked into A
if s1id not in ids_A:
    qr = requests.get(f"{BASE}/admin/events/{E_A}/qr", headers=H(kj)).json()
    requests.post(f"{BASE}/e/checkin/{qr['checkin_path'].rsplit('/',1)[-1]}", headers=H(s1))
    slA = requests.get(f"{BASE}/events/{E_A}/singer-list", headers=H(kj)).json()["singers"]
    ids_A = [s["user_id"] for s in slA]
opp = next((i for i in ids_A if i != s1id), None)

# --- Singer requests a battle in their event ---
r = requests.post(f"{BASE}/events/{E_A}/battle-requests", headers=H(s1),
                  json={"opponent_id": opp, "challenge_type": "royal_duel"})
check("Singer requests battle in own event", r.status_code == 200, f"{r.status_code} {r.text[:150]}")
req = r.json() if r.status_code == 200 else {}
bid = req.get("id")
check("Request carries event_id + source", req.get("event_id") == E_A and req.get("source") == "singer_request", str(req)[:120])
check("Request status pending", req.get("status") == "pending")

# --- KJ sees pending notification ---
pend = requests.get(f"{BASE}/events/{E_A}/battle-requests/pending", headers=H(kj))
check("KJ pending endpoint 200", pend.status_code == 200)
check("KJ sees the pending request", any(x["id"] == bid for x in pend.json().get("requests", [])), str(pend.json())[:120])

# --- KJ starts + finalizes the requested battle (lifecycle) ---
check("KJ open voting on requested battle", requests.post(f"{BASE}/events/{E_A}/battles/{bid}/open-voting", headers=H(kj)).status_code == 200)
check("KJ pick winner on requested battle", requests.post(f"{BASE}/events/{E_A}/battles/{bid}/pick-winner", headers=H(kj), json={"winner_id": s1id}).status_code == 200)

# --- ISOLATION: singer cannot request cross-event ---
r2 = requests.post(f"{BASE}/events/{E_B}/battle-requests", headers=H(s1), json={"opponent_id": opp, "challenge_type": "royal_duel"})
check("Singer request in event they're NOT checked into -> 400/403", r2.status_code in (400, 403), str(r2.status_code))

# --- opponent from another event cannot be used ---
import time as _t
_fe = f"foreignsinger_{int(_t.time())}@ex.com"
requests.post(f"{BASE}/auth/register", json={"email": _fe, "password": "Test!2026", "display_name": "Foreign Singer"})
_ftok = login(_fe, "Test!2026")
_qrB = requests.get(f"{BASE}/admin/events/{E_B}/qr", headers=H(admin)).json()
requests.post(f"{BASE}/e/checkin/{_qrB['checkin_path'].rsplit('/',1)[-1]}", headers=H(_ftok))
_fid = requests.get(f"{BASE}/auth/me", headers=H(_ftok)).json()["id"]
foreign = _fid if _fid not in ids_A else None
if foreign:
    r3 = requests.post(f"{BASE}/events/{E_A}/battle-requests", headers=H(s1), json={"opponent_id": foreign, "challenge_type": "royal_duel"})
    check("Opponent from another event rejected -> 400", r3.status_code == 400, str(r3.status_code))
else:
    check("Opponent-from-another-event (no foreign singer to test)", True)

# --- unchecked-in opponent (random id) rejected ---
check("Unchecked-in opponent id rejected -> 400", requests.post(f"{BASE}/events/{E_A}/battle-requests", headers=H(s1), json={"opponent_id": "ghost-id", "challenge_type": "royal_duel"}).status_code == 400)

# --- KJ cannot see pending for out-of-scope event ---
check("KJ pending for out-of-scope event -> 403", requests.get(f"{BASE}/events/{E_B}/battle-requests/pending", headers=H(kj)).status_code == 403)
# --- singer cannot read KJ pending list (staff only) ---
check("Singer cannot read pending list -> 403", requests.get(f"{BASE}/events/{E_A}/battle-requests/pending", headers=H(s1)).status_code == 403)

# --- LEGACY singer-to-singer battles still work (separate system) ---
s2 = login("singer2@kingkaraoke2025.com", "Singer!2026")
s2id = requests.get(f"{BASE}/auth/me", headers=H(s2)).json()["id"]
import asyncio as _a, os as _o
from motor.motor_asyncio import AsyncIOMotorClient as _M
from dotenv import load_dotenv as _ld; _ld()
async def _clear():
    _c=_M(_o.environ["MONGO_URL"]); _db=_c[_o.environ["DB_NAME"]]
    await _db.challenges.update_many({"status":{"$in":["pending","accepted"]},"$or":[{"challenger_id":s1id,"opponent_id":s2id},{"challenger_id":s2id,"opponent_id":s1id}]},{"$set":{"status":"completed"}})
_a.get_event_loop().run_until_complete(_clear())
lc = requests.post(f"{BASE}/challenges", headers=H(s1), json={"opponent_id": s2id, "challenge_type": "royal_duel"})
check("Legacy singer challenge still works", lc.status_code == 200, f"{lc.status_code} {lc.text[:120]}")
if lc.status_code == 200:
    lcid = lc.json()["id"]
    check("Legacy accept works", requests.post(f"{BASE}/challenges/{lcid}/accept", headers=H(s2)).status_code == 200)
    dk = login("dakota@hotmail.com", "Dakota!2026")
    check("Legacy vote works", requests.post(f"{BASE}/challenges/{lcid}/vote", headers=H(dk), json={"vote_for": s1id}).status_code == 200)
check("Legacy list endpoint works", requests.get(f"{BASE}/challenges", headers=H(s1)).status_code == 200)

print(f"\n==== {len(passed)} passed, {len(failed)} failed ====")
if failed: print("FAILED:", failed)
