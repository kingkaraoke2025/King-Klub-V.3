"""Sing Song = +10, event + season + lifetime scoped, idempotent. Verifies KJ completing a
singer's queued song awards exactly +10 to the singer's event_points, season points AND the
lifetime users.points (so it shows on the singer dashboard), tied to the correct event/season,
never to another singer/event/season, and never double-counts on repeat/duplicate completes."""
import os, datetime, uuid, jwt, requests
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
def login(e, p): return requests.post(f"{BASE}/auth/login", json={"email": e, "password": p}).json()

passed, failed = [], []
def check(n, c, x=""):
    (passed if c else failed).append(n); print(("PASS " if c else "FAIL ") + n + (f"  [{x}]" if x and not c else ""))

admin = login("dev-admin@kingkaraoke2025.com", "DevKing!2026")["token"]
kj = login("kj@kingkaraoke2025.com", "Kj!2026")
kj_tok = kj["token"]; kj_id = kj["user"]["id"]
singer = login("singer1@kingkaraoke2025.com", "Singer!2026")
s_tok = singer["token"]; s_id = singer["user"]["id"]
Ha = {"Authorization": f"Bearer {admin}"}
Hk = {"Authorization": f"Bearer {kj_tok}"}
Hs = {"Authorization": f"Bearer {s_tok}"}

# fresh active event at KJ's venue
ev = requests.post(f"{BASE}/admin/events", headers=Hk,
                   json={"venue_id": VENUE_A, "name": f"SongPts {uuid.uuid4().hex[:6]}",
                         "event_date": "2026-07-01", "status": "active"}).json()
E = ev["id"]

def snap():
    u = db.users.find_one({"id": s_id}, {"_id": 0, "points": 1}) or {"points": 0}
    ep = db.event_participation.find_one({"user_id": s_id, "event_id": E}, {"_id": 0, "event_points": 1}) or {"event_points": 0}
    sp = db.season_participation.find_one({"user_id": s_id}, {"_id": 0, "points": 1}) or {"points": 0}
    return u["points"], ep["event_points"], sp["points"]

# singer must be checked in — seed participation + check-in directly (QR flow covered elsewhere)
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
db.event_participation.update_one(
    {"user_id": s_id, "event_id": E},
    {"$setOnInsert": {"id": str(uuid.uuid4()), "user_id": s_id, "event_id": E,
                      "venue_id": VENUE_A, "location_id": ev.get("location_id"),
                      "event_points": 0, "songs_performed": 0, "badges_earned": [],
                      "list_position": 1, "status": "checked_in", "checked_in_at": now,
                      "created_at": now, "updated_at": now}},
    upsert=True)
check("Singer participation seeded", db.event_participation.find_one({"user_id": s_id, "event_id": E}) is not None)

before = snap()
# singer adds a song
add = requests.post(f"{BASE}/events/{E}/queue", headers=Hs, json={"song_title": "T", "artist": "A"})
check("Singer add song 200", add.status_code == 200, f"{add.status_code} {add.text[:120]}")
item = add.json()["id"]
requests.post(f"{BASE}/events/{E}/queue/{item}/set-current", headers=Hk)
comp = requests.post(f"{BASE}/events/{E}/queue/{item}/complete", headers=Hk)
check("KJ complete song 200 + points_awarded 10", comp.status_code == 200 and comp.json().get("points_awarded") == 10, comp.text[:150])
after = snap()
check("Lifetime users.points +10", after[0] - before[0] == 10, f"{before[0]}->{after[0]}")
check("Event event_points +10", after[1] - before[1] == 10, f"{before[1]}->{after[1]}")
check("Season points +10", after[2] - before[2] == 10, f"{before[2]}->{after[2]}")

# ledger scope: event id + season id correct, tied to this singer only
led = db.point_ledger.find_one({"dedupe_key": f"song:{item}"}, {"_id": 0})
check("event_song ledger tied to correct event", led and led["event_id"] == E and led["user_id"] == s_id)
sp_doc = db.season_participation.find_one({"user_id": s_id}, {"_id": 0})
active_season = db.seasons.find_one({"status": "active"}, {"_id": 0, "id": 1})
check("Season points on the CURRENT active season", sp_doc and sp_doc["season_id"] == active_season["id"])

# duplicate prevention
d = requests.post(f"{BASE}/events/{E}/queue/{item}/complete", headers=Hk)
check("Repeat complete awards 0 (already)", d.status_code == 200 and d.json().get("points_awarded") == 0)
after2 = snap()
check("No double-count after repeat", after2 == after, f"{after}->{after2}")

# not awarded to another singer
other = db.event_participation.find_one({"user_id": kj_id, "event_id": E})
check("KJ (other user) got no event points from singer's song", (other or {}).get("event_points", 0) == 0)

# cleanup: reverse this test's awards (song event+season+lifetime), then delete the event
db.users.update_one({"id": s_id}, {"$inc": {"points": -10}})            # reverse lifetime_song
db.season_participation.update_one({"user_id": s_id}, {"$inc": {"points": -10}})  # reverse season song
for c in ("event_queue", "event_participation", "event_checkins", "event_checkin_attempts",
          "season_accomplishments"):
    db[c].delete_many({"event_id": E})
db.point_ledger.delete_many({"event_id": E})
db.events.delete_one({"id": E})

print(f"\n==== {len(passed)} passed, {len(failed)} failed ====")
if failed: print("FAILED:", failed)
