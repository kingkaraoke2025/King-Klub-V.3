"""QR/check-in event-scope regression for the 'already checked in on a new event' incident.
Proves: (1) each event's QR token carries ITS OWN event id (incident IDs 2753aec5 vs 580016f2);
(2) a singer checked into event A can independently check into a different active event B;
(3) event A's QR only checks the singer into A, never B; (4) an ended event blocks check-in.
Backend check-in logic is unchanged — this asserts it was already correctly event-scoped."""
import os, uuid, json, base64, datetime, jwt, requests
from pymongo import MongoClient

BASE = "http://localhost:8001/api"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
SEC = os.environ["JWT_SECRET"]
VENUE_KJ = "c9a5f1bb-2fd1-4143-97c2-336cb327ab14"          # kj@ authorized venue (Test Venue)
SOFAS_VENUE = "81926fc6-6af3-4032-99fb-cc47917a368c"       # incident venue (Sofas Corner)
KOTA = "942d41c3-11d7-44a6-b719-71da1fcbfd94"              # KJ authorized for Sofas venue
INCIDENT_OLD = "2753aec5-5203-456e-a9c0-9ae73e1d5b2b"      # Test karaoke (active)
INCIDENT_NEW = "580016f2-0d1b-445b-a3e0-caf0a41fb364"      # new event (ended)

def tok(uid, admin=False):
    return jwt.encode({"user_id": uid, "is_admin": admin,
                       "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)},
                      SEC, algorithm="HS256")
def H(uid): return {"Authorization": f"Bearer {tok(uid)}"}
passed, failed = [], []
def check(n, c, x=""):
    (passed if c else failed).append(n); print(("PASS " if c else "FAIL ") + n + (f"  [{x}]" if x and not c else ""))

def token_eid(token):
    raw = token.split(".")[0]
    return json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode())["e"]

kj = requests.post(f"{BASE}/auth/login", json={"email": "kj@kingkaraoke2025.com", "password": "Kj!2026"}).json()
kj_tok = kj["token"]
Hk = {"Authorization": f"Bearer {kj_tok}"}
# use whatever venue kj@ is actually authorized for (scope can drift in DEV)
_me = requests.get(f"{BASE}/auth/me", headers=Hk).json()
VENUE_KJ = (_me.get("role_scope") or {}).get("venue_ids", [VENUE_KJ])[0]
singer = requests.post(f"{BASE}/auth/login", json={"email": "singer1@kingkaraoke2025.com", "password": "Singer!2026"}).json()
s_id = singer["user"]["id"]
Hs = {"Authorization": f"Bearer {singer['token']}"}

# ---- INCIDENT: each event's QR token resolves to ITS OWN id ----
qOld = requests.get(f"{BASE}/admin/events/{INCIDENT_OLD}/qr", headers=H(KOTA))
qNew = requests.get(f"{BASE}/admin/events/{INCIDENT_NEW}/qr", headers=H(KOTA))
check("QR mint for old incident event 200", qOld.status_code == 200, f"{qOld.status_code}")
check("QR mint for new incident event 200", qNew.status_code == 200, f"{qNew.status_code}")
if qOld.status_code == 200 and qNew.status_code == 200:
    eOld = token_eid(qOld.json()["token"]); eNew = token_eid(qNew.json()["token"])
    check("Old event QR token carries 2753aec5", eOld == INCIDENT_OLD, eOld)
    check("NEW event QR token carries 580016f2 (NOT 2753aec5)", eNew == INCIDENT_NEW and eNew != INCIDENT_OLD, eNew)

# ---- Two fresh ACTIVE events at the KJ's venue for check-in isolation ----
def mk(status="active"):
    return requests.post(f"{BASE}/admin/events", headers=Hk,
                         json={"venue_id": VENUE_KJ, "name": f"QR {uuid.uuid4().hex[:6]}",
                               "event_date": "2026-07-03", "status": status}).json()["id"]
A, B = mk(), mk()
tokA = requests.get(f"{BASE}/admin/events/{A}/qr", headers=Hk).json()["token"]
tokB = requests.get(f"{BASE}/admin/events/{B}/qr", headers=Hk).json()["token"]
check("Event A QR token == A", token_eid(tokA) == A)
check("Event B QR token == B and != A", token_eid(tokB) == B and token_eid(tokB) != A)

# make sure singer starts fresh on both
for e in (A, B):
    db.event_participation.delete_many({"user_id": s_id, "event_id": e})

# singer checks into A via A's QR
rA = requests.post(f"{BASE}/e/checkin/{tokA}", headers=Hs)
check("Singer checks into A -> success", rA.status_code == 200 and rA.json().get("event_id") == A and rA.json().get("already_checked_in") is False, rA.text[:150])
# A's QR again -> already checked in to A (not B)
rA2 = requests.post(f"{BASE}/e/checkin/{tokA}", headers=Hs)
check("A's QR again -> already_checked_in for A", rA2.json().get("already_checked_in") is True and rA2.json().get("event_id") == A, rA2.text[:120])
# singer INDEPENDENTLY checks into B via B's QR
rB = requests.post(f"{BASE}/e/checkin/{tokB}", headers=Hs)
check("Singer checks into B independently -> success", rB.status_code == 200 and rB.json().get("event_id") == B and rB.json().get("already_checked_in") is False, rB.text[:150])
# A's QR must NOT have created a B participation
check("A's QR did NOT check singer into B", db.event_participation.find_one({"user_id": s_id, "event_id": B}) is not None and rA.json().get("event_id") != B)
check("Separate participation rows exist for A and B", db.event_participation.count_documents({"user_id": s_id, "event_id": {"$in": [A, B]}}) == 2)

# ---- Ended event blocks check-in (backend rule, unchanged) ----
C = mk("active")
tokC = requests.get(f"{BASE}/admin/events/{C}/qr", headers=Hk).json()["token"]
db.events.update_one({"id": C}, {"$set": {"status": "ended"}})   # deterministic status flip
rC = requests.post(f"{BASE}/e/checkin/{tokC}", headers=Hs)
check("Ended event check-in blocked -> 400 not open", rC.status_code == 400 and "not open" in rC.text.lower(), f"{rC.status_code} {rC.text[:120]}")
# the real incident new event (580016f2, ended) also blocks
rNew = requests.post(f"{BASE}/e/checkin/{qNew.json()['token']}", headers=Hs) if qNew.status_code == 200 else None
check("Incident new event 580016f2 (ended) blocks check-in (not 'already checked in')",
      rNew is not None and rNew.status_code == 400, (rNew.text[:120] if rNew else "no token"))

# cleanup fresh events + participation
for e in (A, B, C):
    for c in ("event_queue", "event_participation", "event_checkins", "event_checkin_attempts", "season_accomplishments"):
        db[c].delete_many({"event_id": e})
    db.point_ledger.delete_many({"event_id": e})
    db.events.delete_one({"id": e})
db.season_participation.update_one({"user_id": s_id}, {"$inc": {"points": -20}})  # reverse 2 check-in season pts
db.users.update_one({"id": s_id}, {"$inc": {"points": -20}})                       # reverse 2 lifetime check-in pts

print(f"\n==== {len(passed)} passed, {len(failed)} failed ====")
if failed: print("FAILED:", failed)
