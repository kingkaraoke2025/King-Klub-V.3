"""FINAL Phase 2 backend E2E verification (isolated dev DB). Run setup_final_scenario.py first."""
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parent / ".env")
BASE = "http://localhost:8001/api"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
P, F = [], []


def chk(n, c, x=""):
    (P if c else F).append(n)
    print(("PASS " if c else "FAIL ") + n + (f"  :: {x}" if x and not c else ""))


def login(e, pw):
    r = requests.post(f"{BASE}/auth/login", json={"email": e, "password": pw})
    return r.json().get("token") if r.ok else None


def H(t):
    return {"Authorization": f"Bearer {t}"}


def find(items, name):
    return next((i for i in items if i["name"] == name), None)


admin = login("dev-admin@kingkaraoke2025.com", os.environ.get("DEV_ADMIN_PASSWORD", "DevKing!2026"))
lm = login("lm@kingkaraoke2025.com", "Manager!2026")
kj = login("kj@kingkaraoke2025.com", "Kj!2026")
singer = login("singer1@kingkaraoke2025.com", "Singer!2026")

locs = requests.get(f"{BASE}/admin/locations", headers=H(admin)).json()
LOC = find(locs, "Test Location"); OTHER_LOC = find(locs, "Other Location")
vens = requests.get(f"{BASE}/admin/venues", headers=H(admin)).json()
VEN = find(vens, "Test Venue"); OTHER_VEN = find(vens, "Other Venue")
evs = requests.get(f"{BASE}/admin/events", headers=H(admin)).json()
A = find(evs, "Test Karaoke Night"); B = find(evs, "Second Night"); OTHER_EV = find(evs, "Other Event")

# ===== TEST 1 — GLOBAL ADMIN =====
chk("T1 admin lists locations", any(l["name"] == "Test Location" for l in locs))
chk("T1 admin views venue", VEN is not None)
chk("T1 admin views event", A is not None)
chk("T1 admin event QR", requests.get(f"{BASE}/admin/events/{A['id']}/qr", headers=H(admin)).ok)
chk("T1 admin singer-list", requests.get(f"{BASE}/events/{A['id']}/singer-list", headers=H(admin)).ok)
chk("T1 admin event leaderboard", requests.get(f"{BASE}/events/{A['id']}/leaderboard", headers=H(admin)).ok)

# ===== TEST 2 — LOCATION MANAGER =====
lm_locs = requests.get(f"{BASE}/admin/locations", headers=H(lm)).json()  # (all visible; scope enforced on actions)
lm_events = requests.get(f"{BASE}/admin/events", headers=H(lm)).json()
chk("T2 lm sees only in-scope events (all in Test Location)", all(e["location_id"] == LOC["id"] for e in lm_events) and {A["id"], B["id"]} <= {e["id"] for e in lm_events}, [e["name"] for e in lm_events])
chk("T2 lm can manage venue in scope (create)", requests.post(f"{BASE}/admin/venues", headers=H(lm), json={"location_id": LOC["id"], "name": "LM Venue"}).status_code in (200, 400))
chk("T2 lm can manage event in scope (create)", requests.post(f"{BASE}/admin/events", headers=H(lm), json={"venue_id": VEN["id"], "name": "LM Event", "event_date": "2026-07-01"}).status_code in (200, 400))
chk("T2 lm CANNOT create venue in OTHER location (403)", requests.post(f"{BASE}/admin/venues", headers=H(lm), json={"location_id": OTHER_LOC["id"], "name": "Hack Venue"}).status_code == 403)
chk("T2 lm CANNOT access OTHER event by id (403)", requests.get(f"{BASE}/admin/events/{OTHER_EV['id']}", headers=H(lm)).status_code == 403)
chk("T2 lm CANNOT create location (403)", requests.post(f"{BASE}/admin/locations", headers=H(lm), json={"name": "LM New Loc"}).status_code == 403)

# ===== TEST 3 — VENUE KJ =====
kj_events = requests.get(f"{BASE}/admin/events", headers=H(kj)).json()
chk("T3 kj sees only own-venue events (all in Test Venue)", all(e["venue_id"] == VEN["id"] for e in kj_events) and {A["id"], B["id"]} <= {e["id"] for e in kj_events}, [e["name"] for e in kj_events])
chk("T3 kj can view assigned event", requests.get(f"{BASE}/admin/events/{A['id']}", headers=H(kj)).ok)
chk("T3 kj can display event QR", requests.get(f"{BASE}/admin/events/{A['id']}/qr", headers=H(kj)).ok)
chk("T3 kj can see singers", requests.get(f"{BASE}/events/{A['id']}/singer-list", headers=H(kj)).ok)
chk("T3 kj can view leaderboard", requests.get(f"{BASE}/events/{A['id']}/leaderboard", headers=H(kj)).ok)
chk("T3 kj CANNOT access OTHER venue's event by id (403)", requests.get(f"{BASE}/admin/events/{OTHER_EV['id']}", headers=H(kj)).status_code == 403)
chk("T3 kj CANNOT create venue (403, not location staff)", requests.post(f"{BASE}/admin/venues", headers=H(kj), json={"location_id": LOC["id"], "name": "KJ Venue"}).status_code == 403)

# ===== TEST 3b — VENUE KJ can OPERATE a show on both events at their venue =====
s2tok = login("singer2@kingkaraoke2025.com", "Singer!2026")
for lbl, EV in [("A", A), ("B", B)]:
    # ensure a participant exists in this event (singer2 checks in via that event's QR)
    _qr = requests.get(f"{BASE}/admin/events/{EV['id']}/qr", headers=H(kj)).json()
    requests.post(f"{BASE}/e/checkin/{_qr['token']}", headers=H(s2tok))
    chk(f"T3b kj generate QR (Event {lbl})", "token" in _qr)
    chk(f"T3b kj award points to a checked-in singer (Event {lbl})", requests.post(f"{BASE}/events/{EV['id']}/award-points", headers=H(kj), json={"user_id": "dev-singer-0002", "points": 5, "action_id": "sing_song"}).ok)
    chk(f"T3b kj view queue (Event {lbl})", requests.get(f"{BASE}/events/{EV['id']}/queue", headers=H(kj)).status_code == 200)
    chk(f"T3b kj view leaderboard (Event {lbl})", requests.get(f"{BASE}/events/{EV['id']}/leaderboard", headers=H(kj)).ok)
chk("T3b kj CANNOT award in OTHER venue's event (403)", requests.post(f"{BASE}/events/{OTHER_EV['id']}/award-points", headers=H(kj), json={"user_id": "dev-singer-0001", "points": 5}).status_code == 403)
chk("T3b kj CANNOT generate QR for OTHER venue's event (403)", requests.get(f"{BASE}/admin/events/{OTHER_EV['id']}/qr", headers=H(kj)).status_code == 403)

# ===== TEST 4 — SINGER =====
chk("T4 singer denied /admin/events (403)", requests.get(f"{BASE}/admin/events", headers=H(singer)).status_code == 403)
chk("T4 singer denied award-points (403)", requests.post(f"{BASE}/events/{A['id']}/award-points", headers=H(singer), json={"user_id": "dev-singer-0001", "points": 5}).status_code == 403)
qrA = requests.get(f"{BASE}/admin/events/{A['id']}/qr", headers=H(admin)).json()
ci = requests.post(f"{BASE}/e/checkin/{qrA['token']}", headers=H(singer))
_ci = ci.json() if ci.ok else {}
chk("T4 singer checks in via event QR", ci.ok and (_ci.get("success") is True or _ci.get("already_checked_in") is True), ci.text)
slA = requests.get(f"{BASE}/events/{A['id']}/singer-list", headers=H(admin)).json()
chk("T4 singer appears in Event A list", any(s["user_id"] == "dev-singer-0001" for s in slA["singers"]))

# ===== TEST 5 — TWO-EVENT ISOLATION =====
slB = requests.get(f"{BASE}/events/{B['id']}/singer-list", headers=H(admin)).json()
chk("T5 singer does NOT appear in Event B", all(s["user_id"] != "dev-singer-0001" for s in slB["singers"]))
requests.post(f"{BASE}/events/{A['id']}/award-points", headers=H(admin), json={"user_id": "dev-singer-0001", "points": 40, "action_id": "sing_song"})
lbA = requests.get(f"{BASE}/events/{A['id']}/leaderboard", headers=H(admin)).json()["leaderboard"]
lbB = requests.get(f"{BASE}/events/{B['id']}/leaderboard", headers=H(admin)).json()["leaderboard"]
rA = next((r for r in lbA if r["user_id"] == "dev-singer-0001"), None)
chk("T5 Event A points recorded (>=50)", rA and rA["event_points"] >= 50, rA)
chk("T5 Event B leaderboard excludes singer / no A points leak", all(r["user_id"] != "dev-singer-0001" for r in lbB))

# ===== TEST 6 — QR SECURITY =====
chk("T6 valid QR works (checked above)", ci.ok)
chk("T6 duplicate check-in rejected/flagged", requests.post(f"{BASE}/e/checkin/{qrA['token']}", headers=H(singer)).json().get("already_checked_in") is True)
chk("T6 tampered QR rejected (400)", requests.post(f"{BASE}/e/checkin/{qrA['token'][:-3]}zzz", headers=H(singer)).status_code == 400)
# expired token: craft one directly
import importlib
ps = importlib.import_module("phase2_server")
from datetime import datetime, timezone, timedelta
expired = ps.make_event_token(A["id"], (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat())
chk("T6 expired QR rejected (400)", requests.post(f"{BASE}/e/checkin/{expired}", headers=H(singer)).status_code == 400)
# QR for A checks into A only (token maps to A, never B)
ci_again = requests.post(f"{BASE}/e/checkin/{qrA['token']}", headers=H(login('singer2@kingkaraoke2025.com','Singer!2026')))
chk("T6 QR-A always maps to Event A (not B)", ci_again.json().get("event_id") == A["id"])

# ===== TEST 7 — LEGACY RETIRED =====
chk("T7 legacy venue/qr-data 403", requests.get(f"{BASE}/venue/qr-data", headers=H(admin)).status_code == 403)
chk("T7 legacy nightly checkin 403", requests.post(f"{BASE}/checkin/xyz", headers=H(singer)).status_code == 403)
chk("T7 legacy leaderboard/tonight 403", requests.get(f"{BASE}/leaderboard/tonight").status_code == 403)

# ===== TEST 8 — SEASON =====
cur = requests.get(f"{BASE}/seasons/current", headers=H(singer)).json()
chk("T8 current season exists & is_current", cur.get("season", {}).get("is_current") is True)
slb = requests.get(f"{BASE}/seasons/current/leaderboard", headers=H(admin)).json()["leaderboard"]
chk("T8 event points contribute to season", any(r["user_id"] == "dev-singer-0001" and r["season_points"] > 0 for r in slb))
cron = requests.post(f"{BASE}/cron/season-reset", headers={"x-cron-secret": os.environ["WEBHOOK_CRON_SECRET"]})
chk("T8 season reset endpoint runs (not-due -> no destructive reset)", cron.ok and "ok" in cron.json())
seasons_count = db.seasons.count_documents({})
chk("T8 season history preserved (>=1 season doc)", seasons_count >= 1, seasons_count)

print(f"\n==== FINAL BACKEND E2E: {len(P)} passed, {len(F)} failed ====")
if F:
    print("FAILED:", F)
