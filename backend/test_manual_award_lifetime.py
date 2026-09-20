"""Legacy-parity test: a MANUAL KJ point award now mirrors the action value (+ first-time badge
bonus) to the singer's lifetime users.points, exactly ONCE, while keeping Event + Season awards.
Invariant proven per action: lifetime_delta == event_delta == season_delta (> 0). Idempotency:
same dedupe_key -> 409, no double; new dedupe -> awards again. Automatic song completion still
+10 once; add/cancel award nothing. Event/season isolation preserved."""
import os, uuid, datetime, jwt, requests
from pymongo import MongoClient

BASE = "http://localhost:8001/api"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
SEC = os.environ["JWT_SECRET"]
VENUE_A = "c9a5f1bb-2fd1-4143-97c2-336cb327ab14"

def tok(uid, admin=False):
    return jwt.encode({"user_id": uid, "is_admin": admin,
                       "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)},
                      SEC, algorithm="HS256")
def H(uid): return {"Authorization": f"Bearer {tok(uid)}"}
passed, failed = [], []
def check(n, c, x=""):
    (passed if c else failed).append(n); print(("PASS " if c else "FAIL ") + n + (f"  [{x}]" if x and not c else ""))

kj = requests.post(f"{BASE}/auth/login", json={"email": "kj@kingkaraoke2025.com", "password": "Kj!2026"}).json()
kj_tok, kj_id = kj["token"], kj["user"]["id"]
Hk = {"Authorization": f"Bearer {kj_tok}"}

# fresh singer (empty badges so badge bonuses are deterministic first-time awards)
em = f"mtest_{uuid.uuid4().hex[:8]}@t.com"
reg = requests.post(f"{BASE}/auth/register", json={"email": em, "password": "Pw!2026", "display_name": "MTest"}).json()
S = reg["user"]["id"]

# fresh active event at KJ's venue + seed participation (check-in)
ev = requests.post(f"{BASE}/admin/events", headers=Hk,
                   json={"venue_id": VENUE_A, "name": f"Manual {uuid.uuid4().hex[:6]}",
                         "event_date": "2026-07-02", "status": "active"}).json()
E = ev["id"]
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
db.event_participation.insert_one({"id": str(uuid.uuid4()), "user_id": S, "event_id": E, "venue_id": VENUE_A,
    "location_id": ev.get("location_id"), "event_points": 0, "songs_performed": 0, "badges_earned": [],
    "list_position": 1, "status": "checked_in", "checked_in_at": now, "created_at": now, "updated_at": now})

def snap():
    u = db.users.find_one({"id": S}, {"_id": 0, "points": 1})["points"]
    ep = db.event_participation.find_one({"user_id": S, "event_id": E}, {"_id": 0}).get("event_points", 0)
    sp = (db.season_participation.find_one({"user_id": S}, {"_id": 0}) or {}).get("points", 0)
    return u, ep, sp

def award(action_id, points, dedupe=None):
    return requests.post(f"{BASE}/events/{E}/award-points", headers=Hk,
                         json={"user_id": S, "points": points, "action_id": action_id,
                               "notes": "t", "dedupe_key": dedupe})

REPORT = None
for action, pts in [("sing_blindfolded", 250), ("random_song", 200), ("tiktok_post", 200),
                    ("bar_song", 100), ("bring_friend", 10)]:
    b = snap()
    r = award(action, pts, dedupe=f"t:{action}:{uuid.uuid4().hex}")
    a = snap()
    dl, de, ds = a[0]-b[0], a[1]-b[1], a[2]-b[2]
    check(f"{action}: lifetime==event==season delta & >0", dl == de == ds and dl > 0, f"L{dl} E{de} S{ds} resp{r.status_code}")
    check(f"{action}: lifetime includes action pts (>= {pts})", dl >= pts, f"{dl}")
    if action == "sing_blindfolded":
        REPORT = (b, a, dl)

# ---- Idempotency: SAME dedupe_key twice -> second is 409, lifetime/event/season move ONCE ----
dk = f"idem:{uuid.uuid4().hex}"
b = snap(); r1 = award("tip_kj", 10, dedupe=dk); m = snap(); r2 = award("tip_kj", 10, dedupe=dk); a = snap()
check("Same dedupe: first awards 200, second 409", r1.status_code == 200 and r2.status_code == 409, f"{r1.status_code}/{r2.status_code}")
check("Same dedupe: lifetime==event==season on the one award", (m[0]-b[0]) == (m[1]-b[1]) == (m[2]-b[2]) and (m[0]-b[0]) > 0, f"L{m[0]-b[0]} E{m[1]-b[1]} S{m[2]-b[2]}")
check("Same dedupe: NO change after the duplicate 409 (no double)", a == m, f"{m}->{a}")

# ---- Two SEPARATE legitimate awards of the same action -> awarded twice (lifetime==event==season) ----
b = snap()
award("tip_bartender", 10, dedupe=f"s1:{uuid.uuid4().hex}")
mid1 = snap()
award("tip_bartender", 10, dedupe=f"s2:{uuid.uuid4().hex}")
a = snap()
check("Two separate awards: each moved lifetime==event==season", (a[0]-b[0]) == (a[1]-b[1]) == (a[2]-b[2]) and (a[0]-b[0]) > (mid1[0]-b[0]) > 0, f"L{a[0]-b[0]} after1 {mid1[0]-b[0]}")

# ---- Automatic song completion still +10 once; add/cancel award nothing ----
b = snap()
add = requests.post(f"{BASE}/events/{E}/queue", headers=H(S), json={"song_title": "Z", "artist": "Z"})
mid = add.json()["id"]
check("Add song awards nothing", snap() == b)
requests.post(f"{BASE}/events/{E}/queue/{mid}/set-current", headers=Hk)
c1 = requests.post(f"{BASE}/events/{E}/queue/{mid}/complete", headers=Hk)
a = snap()
check("Song complete -> +10 lifetime/event/season once", a[0]-b[0] == 10 and a[1]-b[1] == 10 and a[2]-b[2] == 10 and c1.json().get("points_awarded") == 10, f"L{a[0]-b[0]}")
c2 = requests.post(f"{BASE}/events/{E}/queue/{mid}/complete", headers=Hk)
check("Repeat complete awards 0 (no double)", c2.json().get("points_awarded") == 0 and snap() == a)
# cancel a new song -> nothing
b = snap()
add2 = requests.post(f"{BASE}/events/{E}/queue", headers=H(S), json={"song_title": "Y", "artist": "Y"}).json()
requests.delete(f"{BASE}/events/{E}/queue/{add2['id']}", headers=H(S))
check("Cancel song awards nothing", snap() == b)

# ---- Event/season isolation: nothing leaked to another event ----
other_ep = db.event_participation.find_one({"user_id": S, "event_id": {"$ne": E}})
check("No participation created in any other event", other_ep is None)

print("\n--- REPORT (manual Blindfolded award) ---")
if REPORT:
    (bl, al, dl) = REPORT
    print(f"BEFORE lifetime/event/season: {bl}")
    print(f"AFTER  lifetime/event/season: {al}   (lifetime +{dl}, expect action 250 + badge 250 = 500)")

# ---- cleanup: remove the throwaway singer + event and all its data ----
for c in ("event_queue", "event_participation", "event_checkins", "event_checkin_attempts",
          "season_accomplishments"):
    db[c].delete_many({"event_id": E})
db.point_ledger.delete_many({"event_id": E})
db.point_ledger.delete_many({"user_id": S})
db.season_participation.delete_many({"user_id": S})
db.events.delete_one({"id": E})
db.users.delete_one({"id": S})

print(f"\n==== {len(passed)} passed, {len(failed)} failed ====")
if failed: print("FAILED:", failed)
