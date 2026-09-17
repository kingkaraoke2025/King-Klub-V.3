"""Phase 2 end-to-end backend smoke test (isolated dev DB)."""
import os
import uuid
from pathlib import Path

import bcrypt
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parent / ".env")
BASE = "http://localhost:8001/api"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
RUN = uuid.uuid4().hex[:6]  # unique per run so re-runs don't collide on unique slugs

passed, failed = [], []


def check(name, cond, extra=""):
    (passed if cond else failed).append(name)
    print(("PASS " if cond else "FAIL ") + name + ((" :: " + str(extra)) if extra and not cond else ""))


def login(email, pw):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    return r.json().get("token") if r.ok else None


def H(t):
    return {"Authorization": f"Bearer {t}"}


# ---- Auth ----
admin = login("dev-admin@kingkaraoke2025.com", os.environ.get("DEV_ADMIN_PASSWORD", "DevKing!2026"))
check("admin login", bool(admin))
s1 = login("singer1@kingkaraoke2025.com", "Singer!2026")
s2 = login("singer2@kingkaraoke2025.com", "Singer!2026")
check("singer logins", bool(s1) and bool(s2))


def season_pts(uid):
    lb = requests.get(f"{BASE}/seasons/current/leaderboard", headers=H(admin)).json()
    row = next((r for r in lb["leaderboard"] if r["user_id"] == uid), None)
    return row["season_points"] if row else 0


s1_season_before = season_pts("dev-singer-0001")

# ---- Locations / Venues / Events ----
L1 = requests.post(f"{BASE}/admin/locations", headers=H(admin), json={"name": f"Downtown {RUN}", "city": "Chicago", "state": "IL"}).json()
L2 = requests.post(f"{BASE}/admin/locations", headers=H(admin), json={"name": f"Riverside {RUN}", "city": "St. Louis", "state": "MO"}).json()
V1 = requests.post(f"{BASE}/admin/venues", headers=H(admin), json={"location_id": L1["id"], "name": f"Royal Stage {RUN}"}).json()
V2 = requests.post(f"{BASE}/admin/venues", headers=H(admin), json={"location_id": L2["id"], "name": f"Crown Lounge {RUN}"}).json()
E1 = requests.post(f"{BASE}/admin/events", headers=H(admin), json={"venue_id": V1["id"], "name": f"Friday Night {RUN}", "event_date": "2026-06-12", "status": "active"}).json()
E2 = requests.post(f"{BASE}/admin/events", headers=H(admin), json={"venue_id": V2["id"], "name": f"Saturday Night {RUN}", "event_date": "2026-06-13", "status": "active"}).json()
check("create location/venue/event", all("id" in x for x in [L1, L2, V1, V2, E1, E2]), [L1, V1, E1])
check("event has denormalized location_id", E1.get("location_id") == L1["id"])

# ---- Event QR + check-in ----
qr1 = requests.get(f"{BASE}/admin/events/{E1['id']}/qr", headers=H(admin)).json()
qr2 = requests.get(f"{BASE}/admin/events/{E2['id']}/qr", headers=H(admin)).json()
check("event QR generated w/ token", "token" in qr1 and qr1.get("checkin_path", "").startswith("/e/checkin/"))

ci1 = requests.post(f"{BASE}/e/checkin/{qr1['token']}", headers=H(s1))
check("singer1 event check-in", ci1.ok and ci1.json().get("success") is True, ci1.text)
ci1b = requests.post(f"{BASE}/e/checkin/{qr1['token']}", headers=H(s1)).json()
check("duplicate check-in blocked", ci1b.get("already_checked_in") is True)
ci2 = requests.post(f"{BASE}/e/checkin/{qr2['token']}", headers=H(s2))
check("singer2 event check-in (event2)", ci2.ok and ci2.json().get("success") is True, ci2.text)

# tamper: change token should be rejected
bad = requests.post(f"{BASE}/e/checkin/{qr1['token'][:-2]}xx", headers=H(s2))
check("tampered QR token rejected", bad.status_code == 400)

# ---- Singer-list isolation ----
sl1 = requests.get(f"{BASE}/events/{E1['id']}/singer-list", headers=H(admin)).json()
sl2 = requests.get(f"{BASE}/events/{E2['id']}/singer-list", headers=H(admin)).json()
ids1 = {s["user_id"] for s in sl1["singers"]}
ids2 = {s["user_id"] for s in sl2["singers"]}
check("E1 singer-list has only singer1", ids1 == {"dev-singer-0001"}, ids1)
check("E2 singer-list has only singer2 (isolation)", ids2 == {"dev-singer-0002"}, ids2)

# ---- Event points + leaderboards (isolated) ----
aw = requests.post(f"{BASE}/events/{E1['id']}/award-points", headers=H(admin),
                   json={"user_id": "dev-singer-0001", "points": 50, "action_id": "sing_song"})
check("award event points", aw.ok, aw.text)
lb1 = requests.get(f"{BASE}/events/{E1['id']}/leaderboard", headers=H(admin)).json()
lb2 = requests.get(f"{BASE}/events/{E2['id']}/leaderboard", headers=H(admin)).json()
top1 = lb1["leaderboard"][0] if lb1["leaderboard"] else {}
check("E1 leaderboard shows singer1 event points (10 checkin + 50)", top1.get("user_id") == "dev-singer-0001" and top1.get("event_points") == 60, lb1)
check("E2 leaderboard does NOT include singer1", all(r["user_id"] != "dev-singer-0001" for r in lb2["leaderboard"]))

# ---- Season ----
cur = requests.get(f"{BASE}/seasons/current", headers=H(s1)).json()
check("season current returned", "season" in cur and cur["season"].get("is_current"))
s1_season_after = season_pts("dev-singer-0001")
check("season leaderboard aggregates singer1 (+10 checkin +50 award = +60 this run)", s1_season_after - s1_season_before == 60, (s1_season_before, s1_season_after))

# ---- Event queue + perks ----
addq = requests.post(f"{BASE}/events/{E1['id']}/queue", headers=H(s1),
                     json={"song_title": "Bohemian Rhapsody", "artist": "Queen"})
check("add song to event queue", addq.ok, addq.text)
q = requests.get(f"{BASE}/events/{E1['id']}/queue", headers=H(admin)).json()
check("event queue has 1 item", len(q) == 1, q)
perk = requests.get(f"{BASE}/events/{E1['id']}/perk-status", headers=H(s1)).json()
check("perk-status returns (Peasant no perk)", perk.get("has_perk") in (False, True))

# ---- Legacy retirement ----
lg1 = requests.get(f"{BASE}/venue/qr-data", headers=H(admin))
lg2 = requests.post(f"{BASE}/checkin/somecode", headers=H(s1))
lg3 = requests.get(f"{BASE}/leaderboard/tonight")
check("legacy venue/qr-data retired (403)", lg1.status_code == 403)
check("legacy checkin retired (403)", lg2.status_code == 403)
check("legacy leaderboard/tonight retired (403)", lg3.status_code == 403)

# ---- Authorization / isolation enforcement ----
# singer cannot hit staff endpoints
check("singer denied /admin/events (403)", requests.get(f"{BASE}/admin/events", headers=H(s1)).status_code == 403)
check("singer denied award-points (403)", requests.post(f"{BASE}/events/{E1['id']}/award-points", headers=H(s1), json={"user_id": "dev-singer-0001", "points": 5}).status_code == 403)

# venue_kj scoped to V1 only
now = ci1.json()
db.users.update_one({"email": "singer2@kingkaraoke2025.com"}, {"$set": {}})  # no-op keep singer2 a singer
db.users.update_one({"id": "dev-singer-0001"}, {"$set": {}})
kj_pw = "Kj!2026"
db.users.delete_one({"email": "kj@kingkaraoke2025.com"})
db.users.insert_one({"id": "dev-kj-0001", "email": "kj@kingkaraoke2025.com", "display_name": "KJ One",
                     "password": bcrypt.hashpw(kj_pw.encode(), bcrypt.gensalt()).decode(),
                     "points": 0, "nightly_points": 0, "songs_performed": 0, "consecutive_visits": 0,
                     "badges": [], "is_admin": False, "role": "venue_kj",
                     "role_scope": {"location_ids": [], "venue_ids": [V1["id"]]},
                     "created_at": "2026-01-01T00:00:00+00:00", "last_visit": "2026-01-01T00:00:00+00:00"})
kj = login("kj@kingkaraoke2025.com", kj_pw)
kj_events = requests.get(f"{BASE}/admin/events", headers=H(kj)).json()
check("venue_kj sees only own-venue events", {e["id"] for e in kj_events} == {E1["id"]}, [e["id"] for e in kj_events])
check("venue_kj can act on E1 (in scope)", requests.get(f"{BASE}/admin/events/{E1['id']}", headers=H(kj)).status_code == 200)
check("venue_kj DENIED E2 by changing id (403)", requests.get(f"{BASE}/admin/events/{E2['id']}", headers=H(kj)).status_code == 403)
check("venue_kj DENIED award-points on E2 (403)", requests.post(f"{BASE}/events/{E2['id']}/award-points", headers=H(kj), json={"user_id": "dev-singer-0002", "points": 5}).status_code == 403)

# ---- Cron ----
c_no = requests.post(f"{BASE}/cron/season-reset")
c_yes = requests.post(f"{BASE}/cron/season-reset", headers={"x-cron-secret": os.environ["WEBHOOK_CRON_SECRET"]})
check("cron rejects missing secret (403)", c_no.status_code == 403)
check("cron accepts valid secret", c_yes.ok and c_yes.json().get("ok") is True, c_yes.text)

print("\n==== RESULT:", len(passed), "passed,", len(failed), "failed ====")
if failed:
    print("FAILED:", failed)
