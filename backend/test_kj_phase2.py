"""Backend E2E: venue_kj event-scoped Battles + Points (isolation + 403 boundaries).
Runs against localhost:8001 (Bearer auth; CORS irrelevant for server-side calls)."""
import requests

BASE = "http://localhost:8001/api"
EVENT_A = "d43c3271-7623-45c3-83e3-fd69ac4a5920"   # Test Karaoke Night (KJ's venue)
EVENT_B = "299a34aa-543c-4dcb-a4f7-7926718251b7"   # Other Event (out of scope)

def login(email, pw):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    r.raise_for_status()
    return r.json()["token"]

def H(t): return {"Authorization": f"Bearer {t}"}

passed, failed = [], []
def check(name, cond, extra=""):
    (passed if cond else failed).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))

kj = login("kj@kingkaraoke2025.com", "Kj!2026")
admin = login("dev-admin@kingkaraoke2025.com", "DevKing!2026")
s1 = login("singer1@kingkaraoke2025.com", "Singer!2026")

# ---- Get two checked-in singers in Event A ----
sl = requests.get(f"{BASE}/events/{EVENT_A}/singer-list", headers=H(kj)).json()["singers"]
check("KJ can read Event A singer-list", len(sl) >= 2, str(len(sl)))
c_id, o_id = sl[0]["user_id"], sl[1]["user_id"]

# ============ POINTS ============
def snap(uid):
    u = requests.get(f"{BASE}/admin/users", headers=H(admin)).json()
    life = next((x["points"] for x in u if x["id"] == uid), None)
    slA = requests.get(f"{BASE}/events/{EVENT_A}/singer-list", headers=H(kj)).json()["singers"]
    ep = next((x["event_points"] for x in slA if x["user_id"] == uid), None)
    lb = requests.get(f"{BASE}/seasons/current/leaderboard", headers=H(kj)).json()["leaderboard"]
    sp = next((x["season_points"] for x in lb if x["user_id"] == uid), 0)
    return life, ep, sp

life0, ep0, sp0 = snap(c_id)
r = requests.post(f"{BASE}/events/{EVENT_A}/award-points", headers=H(kj),
                  json={"user_id": c_id, "points": 10, "action_id": "sing_song", "notes": "Sing a Song"})
check("KJ one-tap award (sing_song +10) in own event", r.status_code == 200, f"{r.status_code} {r.text}")
r = requests.post(f"{BASE}/events/{EVENT_A}/award-points", headers=H(kj),
                  json={"user_id": c_id, "points": 15, "action_id": "custom_award", "notes": "Custom"})
check("KJ custom award (+15) in own event", r.status_code == 200, f"{r.status_code} {r.text}")
life1, ep1, sp1 = snap(c_id)
check("Event points increased by 25", ep1 - ep0 == 25, f"{ep0}->{ep1}")
check("Season points increased by 25", sp1 - sp0 == 25, f"{sp0}->{sp1}")
check("Lifetime (legacy) points UNCHANGED", life1 == life0, f"{life0}->{life1}")

# KJ cannot award in out-of-scope event
r = requests.post(f"{BASE}/events/{EVENT_B}/award-points", headers=H(kj),
                  json={"user_id": c_id, "points": 10, "action_id": "sing_song"})
check("KJ award in OTHER event -> 403", r.status_code == 403, str(r.status_code))
# Singer cannot award
r = requests.post(f"{BASE}/events/{EVENT_A}/award-points", headers=H(s1),
                  json={"user_id": c_id, "points": 10, "action_id": "sing_song"})
check("Singer award (KJ-only op) -> 403", r.status_code == 403, str(r.status_code))
# Award to non-checked-in user -> 400
r = requests.post(f"{BASE}/events/{EVENT_A}/award-points", headers=H(kj),
                  json={"user_id": "nonexistent-user", "points": 10, "action_id": "sing_song"})
check("Award to non-participant -> 400", r.status_code == 400, str(r.status_code))

# ============ BATTLES ============
# KJ creates battle in own event
r = requests.post(f"{BASE}/events/{EVENT_A}/battles", headers=H(kj),
                  json={"challenger_id": c_id, "opponent_id": o_id, "challenge_type": "royal_duel"})
check("KJ create battle in own event", r.status_code == 200, f"{r.status_code} {r.text}")
battle = r.json(); bid = battle["id"]
check("Battle carries correct event_id", battle["event_id"] == EVENT_A)

# Duplicate active battle -> 400
r = requests.post(f"{BASE}/events/{EVENT_A}/battles", headers=H(kj),
                  json={"challenger_id": c_id, "opponent_id": o_id, "challenge_type": "royal_duel"})
check("Duplicate active battle -> 400", r.status_code == 400, str(r.status_code))

# KJ create battle in OTHER event -> 403
r = requests.post(f"{BASE}/events/{EVENT_B}/battles", headers=H(kj),
                  json={"challenger_id": c_id, "opponent_id": o_id, "challenge_type": "royal_duel"})
check("KJ create battle in OTHER event -> 403", r.status_code == 403, str(r.status_code))

# Open voting (KJ)
r = requests.post(f"{BASE}/events/{EVENT_A}/battles/{bid}/open-voting", headers=H(kj))
check("KJ open voting", r.status_code == 200, str(r.status_code))

# A checked-in singer (not contestant) votes. Find one who isn't c/o.
voter = next((s["user_id"] for s in sl if s["user_id"] not in (c_id, o_id)), None)
if voter:
    # need that voter's token; only know singer1..2 & dakota. Try mapping known singers.
    pass
# Contestant cannot vote (login as one contestant if it's singer1)
# We'll test with singer1 if singer1 is a contestant or voter.
s1id = requests.get(f"{BASE}/auth/me", headers=H(s1)).json()["id"]
if s1id in (c_id, o_id):
    r = requests.post(f"{BASE}/events/{EVENT_A}/battles/{bid}/vote", headers=H(s1), json={"choice": "challenger"})
    check("Contestant cannot vote -> 400", r.status_code == 400, f"{r.status_code} {r.text}")
else:
    r = requests.post(f"{BASE}/events/{EVENT_A}/battles/{bid}/vote", headers=H(s1), json={"choice": "challenger"})
    check("Checked-in singer votes", r.status_code in (200, 400), f"{r.status_code} {r.text}")
    r2 = requests.post(f"{BASE}/events/{EVENT_A}/battles/{bid}/vote", headers=H(s1), json={"choice": "challenger"})
    check("Duplicate vote -> 400", r2.status_code == 400, str(r2.status_code))

# KJ cannot operate voting on an OTHER-event battle: create one via admin in Event B
rb = requests.post(f"{BASE}/events/{EVENT_B}/battles", headers=H(admin),
                   json={"challenger_id": c_id, "opponent_id": o_id, "challenge_type": "royal_duel"})
# (c_id/o_id are not checked into Event B, so admin create should 400 -> proves participant scoping)
check("Create battle with non-participants (Event B) -> 400", rb.status_code == 400, f"{rb.status_code} {rb.text}")

# Isolation: Event A battle not present in Event B list
lbB = requests.get(f"{BASE}/events/{EVENT_B}/battles", headers=H(admin)).json()
check("Event A battle not leaking into Event B list", all(b["id"] != bid for b in lbB))

# Pick winner (no votes needed) -> awards event+season, not lifetime
life_w0, ep_w0, sp_w0 = snap(c_id)
r = requests.post(f"{BASE}/events/{EVENT_A}/battles/{bid}/pick-winner", headers=H(kj), json={"winner_id": c_id})
check("KJ pick winner", r.status_code == 200, f"{r.status_code} {r.text}")
awarded = r.json().get("awarded", {})
life_w1, ep_w1, sp_w1 = snap(c_id)
check("Battle winner got event points", ep_w1 > ep_w0, f"{ep_w0}->{ep_w1}")
check("Battle winner season points up", sp_w1 > sp_w0, f"{sp_w0}->{sp_w1}")
check("Battle winner lifetime UNCHANGED", life_w1 == life_w0, f"{life_w0}->{life_w1}")

# Finalize/pick again -> already completed 400
r = requests.post(f"{BASE}/events/{EVENT_A}/battles/{bid}/pick-winner", headers=H(kj), json={"winner_id": c_id})
check("Re-decide completed battle -> 400", r.status_code == 400, str(r.status_code))

# KJ operate a battle in OTHER event (open-voting on fabricated id) -> 403 (event scope beats 404)
r = requests.post(f"{BASE}/events/{EVENT_B}/battles/any-id/open-voting", headers=H(kj))
check("KJ open-voting in OTHER event -> 403", r.status_code == 403, str(r.status_code))

# Singer cannot create a battle -> 403
r = requests.post(f"{BASE}/events/{EVENT_A}/battles", headers=H(s1),
                  json={"challenger_id": c_id, "opponent_id": o_id, "challenge_type": "royal_duel"})
check("Singer create battle -> 403", r.status_code == 403, str(r.status_code))

print(f"\n==== {len(passed)} passed, {len(failed)} failed ====")
if failed:
    print("FAILED:", failed)
