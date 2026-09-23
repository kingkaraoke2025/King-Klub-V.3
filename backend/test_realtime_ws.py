"""
Phase 2 REALTIME (WebSocket) acceptance test — automated two-client proxy for the
"KingKota (KJ) + Jabby (singer) on two devices" manual test.

It opens TWO genuinely separate authenticated WS connections to the per-event room
(/api/ws/events/{event_id}?token=...) — one venue_kj, one singer — then drives real
HTTP actions and asserts the broadcast is actually delivered over the WS channel to
the authorized recipient (NOT by calling the same endpoint twice).

Also verifies: WS auth rejection (no token / out-of-scope KJ), event isolation
(A's activity never reaches a B subscriber), and the new EVENT_UPDATED status broadcast.

Business rules / authorization are unchanged — this only observes broadcasts.
Run:  cd /app/backend && python test_realtime_ws.py
"""
import os, uuid, json, asyncio, datetime, jwt, requests, websockets
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).parent / ".env")
BASE = "http://localhost:8001/api"
WS_TMPL = "ws://localhost:8001/api/ws/events/{eid}?token={tok}"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
SEC = os.environ["JWT_SECRET"]

passed, failed = [], []
def check(n, c, x=""):
    (passed if c else failed).append(n)
    print(("PASS " if c else "FAIL ") + n + (f"  [{x}]" if x and not c else ""))

def login(email, pw):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    r.raise_for_status()
    return r.json()

def register(name):
    email = f"rt_{uuid.uuid4().hex[:8]}@test.com"
    r = requests.post(f"{BASE}/auth/register", json={
        "email": email, "password": "Test!2026", "display_name": name, "title_preference": "male"})
    r.raise_for_status()
    d = r.json()
    return d["user"]["id"], d["token"], email

def H(tok): return {"Authorization": f"Bearer {tok}"}

async def try_connect(eid, tok):
    try:
        return await asyncio.wait_for(websockets.connect(WS_TMPL.format(eid=eid, tok=tok)), timeout=6)
    except Exception:
        return None

async def drain(ws, seconds=2.0):
    """Collect all realtime messages arriving within `seconds` (ignores pong)."""
    out = []
    try:
        while True:
            m = await asyncio.wait_for(ws.recv(), timeout=seconds)
            if m == "pong":
                continue
            try: out.append(json.loads(m))
            except Exception: pass
            seconds = 0.6  # after first msg, short window to gather the burst
    except asyncio.TimeoutError:
        pass
    return out

def types(msgs): return [m.get("type") for m in msgs]
def actions(msgs): return [(m.get("type"), m.get("action")) for m in msgs]


async def main():
    created_events, reg_users = [], []
    try:
        # ---- Sessions: KJ (KingKota proxy) + singers (Jabby proxy + others) ----
        kj = login("kj@kingkaraoke2025.com", "Kj!2026")
        kj_tok = kj["token"]
        me = requests.get(f"{BASE}/auth/me", headers=H(kj_tok)).json()
        venue_id = (me.get("role_scope") or {}).get("venue_ids", [None])[0]
        check("KJ has an authorized venue", bool(venue_id), str(me.get("role_scope")))
        if not venue_id:
            raise SystemExit("KJ not authorized for any venue in DEV — cannot run realtime test")

        def mk_event(status="active"):
            eid = requests.post(f"{BASE}/admin/events", headers=H(kj_tok), json={
                "venue_id": venue_id, "name": f"RT {uuid.uuid4().hex[:6]}",
                "event_date": "2026-07-10", "status": status}).json()["id"]
            created_events.append(eid)
            return eid

        A, B = mk_event(), mk_event()

        # Three singers: s1 & s2 are battle contestants, s3 is a voter (contestants can't vote).
        s1_id, s1_tok, _ = register("Jabby")
        s2_id, s2_tok, _ = register("RivalSinger")
        s3_id, s3_tok, _ = register("VoterSinger")
        reg_users += [s1_id, s2_id, s3_id]

        qrA = requests.get(f"{BASE}/admin/events/{A}/qr", headers=H(kj_tok)).json()["token"]
        qrB = requests.get(f"{BASE}/admin/events/{B}/qr", headers=H(kj_tok)).json()["token"]

        # ================= WS AUTH / AUTHORIZATION =================
        no_tok = await try_connect(A, "not-a-real-token")
        check("WS rejects connection with invalid/no token", no_tok is None)
        if no_tok: await no_tok.close()

        # A venue_kj connecting to an event OUTSIDE their venue scope must be rejected.
        other_venue = db.venues.find_one({"id": {"$ne": venue_id}}, {"_id": 0, "id": 1})
        if other_venue:
            other_ev = db.events.find_one({"venue_id": other_venue["id"]}, {"_id": 0, "id": 1})
            if other_ev:
                bad = await try_connect(other_ev["id"], kj_tok)
                check("WS rejects KJ subscribing to an out-of-scope event", bad is None)
                if bad: await bad.close()

        # Authorized connects (kept open for the whole scenario).
        ws_kj = await try_connect(A, kj_tok)
        ws_s1 = await try_connect(A, s1_tok)
        ws_isoA = await try_connect(A, kj_tok)   # isolation probe: subscribed to A only
        check("KJ authorized WS to event A is accepted", ws_kj is not None)
        check("Singer authorized WS to event A is accepted", ws_s1 is not None)
        await drain(ws_kj, 0.5); await drain(ws_s1, 0.5); await drain(ws_isoA, 0.5)

        # ================= CHECK-IN broadcast =================
        requests.post(f"{BASE}/e/checkin/{qrA}", headers=H(s1_tok))
        kj_msgs = await drain(ws_kj)
        check("KJ receives EVENT_SINGER_CHECKED_IN when Jabby checks in",
              "EVENT_SINGER_CHECKED_IN" in types(kj_msgs), types(kj_msgs))
        # check in s2 & s3 too (needed for battle) and drain
        requests.post(f"{BASE}/e/checkin/{qrA}", headers=H(s2_tok))
        requests.post(f"{BASE}/e/checkin/{qrA}", headers=H(s3_tok))
        await drain(ws_kj); await drain(ws_s1); await drain(ws_isoA)

        # ================= SONG SUBMIT broadcast =================
        requests.post(f"{BASE}/events/{A}/queue", headers=H(s1_tok),
                      json={"song_title": "Bohemian Rhapsody", "artist": "Queen"})
        kj_msgs = await drain(ws_kj)
        check("KJ receives EVENT_QUEUE_UPDATED(song_added) when Jabby submits a song",
              ("EVENT_QUEUE_UPDATED", "song_added") in actions(kj_msgs), actions(kj_msgs))

        # ================= QUEUE CHANGE (set current) reaches BOTH KJ + singer =================
        q = requests.get(f"{BASE}/events/{A}/queue", headers=H(kj_tok)).json()
        item = next((i for i in q if i["status"] == "pending"), None)
        if item:
            requests.post(f"{BASE}/events/{A}/queue/{item['id']}/set-current", headers=H(kj_tok))
            kj_msgs = await drain(ws_kj); s1_msgs = await drain(ws_s1)
            check("KJ receives queue update on set-current", "EVENT_QUEUE_UPDATED" in types(kj_msgs), types(kj_msgs))
            check("Singer (Jabby) also receives the queue change live", "EVENT_QUEUE_UPDATED" in types(s1_msgs), types(s1_msgs))
            # ---- COMPLETE song ----
            requests.post(f"{BASE}/events/{A}/queue/{item['id']}/complete", headers=H(kj_tok))
            kj_msgs = await drain(ws_kj); s1_msgs = await drain(ws_s1)
            check("KJ receives EVENT_QUEUE_UPDATED(song_completed)",
                  ("EVENT_QUEUE_UPDATED", "song_completed") in actions(kj_msgs), actions(kj_msgs))
            check("Singer receives the song-completed update live", "EVENT_QUEUE_UPDATED" in types(s1_msgs))

        # ================= AWARD POINTS broadcast (KJ + singer) =================
        requests.post(f"{BASE}/events/{A}/award-points", headers=H(kj_tok), json={
            "user_id": s1_id, "points": 25, "action_id": "custom_award", "notes": "rt",
            "dedupe_key": f"rt:{uuid.uuid4().hex}"})
        kj_msgs = await drain(ws_kj); s1_msgs = await drain(ws_s1)
        check("KJ receives EVENT_POINTS_AWARDED on manual award", "EVENT_POINTS_AWARDED" in types(kj_msgs), types(kj_msgs))
        check("Singer (Jabby) receives EVENT_POINTS_AWARDED live", "EVENT_POINTS_AWARDED" in types(s1_msgs), types(s1_msgs))

        # ================= EVENT-SCOPED BATTLE lifecycle =================
        bt = requests.get(f"{BASE}/events/{A}/battle-types", headers=H(kj_tok)).json()
        btype = bt[0]["id"] if bt else None
        if btype:
            bid = requests.post(f"{BASE}/events/{A}/battles", headers=H(kj_tok), json={
                "challenger_id": s1_id, "opponent_id": s2_id, "challenge_type": btype}).json().get("id")
            kj_msgs = await drain(ws_kj); s1_msgs = await drain(ws_s1)
            check("KJ receives EVENT_BATTLE_UPDATED(created)", ("EVENT_BATTLE_UPDATED", "created") in actions(kj_msgs), actions(kj_msgs))
            check("Singer sees the battle appear live", "EVENT_BATTLE_UPDATED" in types(s1_msgs), types(s1_msgs))
            if bid:
                # open voting
                requests.post(f"{BASE}/events/{A}/battles/{bid}/open-voting", headers=H(kj_tok))
                s1_msgs = await drain(ws_s1)
                check("Eligible singer receives voting_open live", ("EVENT_BATTLE_UPDATED", "voting_open") in actions(s1_msgs), actions(s1_msgs))
                # a NON-contestant votes -> vote count broadcast
                requests.post(f"{BASE}/events/{A}/battles/{bid}/vote", headers=H(s3_tok), json={"choice": "challenger"})
                kj_msgs = await drain(ws_kj)
                check("KJ receives EVENT_BATTLE_UPDATED(vote) on a vote", ("EVENT_BATTLE_UPDATED", "vote") in actions(kj_msgs), actions(kj_msgs))
                # finalize by picking a winner (no tie handling needed)
                requests.post(f"{BASE}/events/{A}/battles/{bid}/pick-winner", headers=H(kj_tok), json={"winner_id": s1_id})
                kj_msgs = await drain(ws_kj); s1_msgs = await drain(ws_s1)
                check("KJ receives EVENT_BATTLE_UPDATED(completed) on finalize", ("EVENT_BATTLE_UPDATED", "completed") in actions(kj_msgs), actions(kj_msgs))
                check("Singer receives the battle result live", "EVENT_BATTLE_UPDATED" in types(s1_msgs))

        # ================= EVENT STATUS change broadcast (new EVENT_UPDATED) =================
        requests.put(f"{BASE}/admin/events/{A}/status", headers=H(kj_tok), json={"status": "active"})
        kj_msgs = await drain(ws_kj)
        check("KJ receives EVENT_UPDATED on status change", "EVENT_UPDATED" in types(kj_msgs), types(kj_msgs))

        # ================= EVENT ISOLATION: activity in B never reaches A's subscriber =================
        await drain(ws_isoA, 0.5)  # clear
        requests.post(f"{BASE}/e/checkin/{qrB}", headers=H(s2_tok))       # check into B
        requests.post(f"{BASE}/events/{B}/queue", headers=H(s2_tok),
                      json={"song_title": "Isolation Test", "artist": "Nobody"})  # submit in B
        isoA_msgs = await drain(ws_isoA, 2.0)
        check("Event A subscriber receives NOTHING from event B activity (isolation)",
              len(isoA_msgs) == 0, f"leaked: {actions(isoA_msgs)}")

        for ws in (ws_kj, ws_s1, ws_isoA):
            if ws: await ws.close()

    finally:
        # ---- cleanup all fixtures we created (DEV DB only) ----
        for e in created_events:
            for c in ("event_queue", "event_participation", "event_checkins", "event_checkin_attempts",
                      "season_accomplishments", "event_challenges", "event_challenge_votes", "perk_usage"):
                db[c].delete_many({"event_id": e})
            db.point_ledger.delete_many({"event_id": e})
            db.events.delete_one({"id": e})
        for uid in reg_users:
            db.users.delete_one({"id": uid})
            db.season_participation.delete_many({"user_id": uid})
            db.point_ledger.delete_many({"user_id": uid})

    print(f"\n==== {len(passed)} passed, {len(failed)} failed ====")
    if failed:
        print("FAILED:", failed)


if __name__ == "__main__":
    asyncio.run(main())
