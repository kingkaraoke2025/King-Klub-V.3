"""
Regression for the "End Event -> React crash / 422" incident.

Proves the CORRECT operation boundary:
  - Pure status change (Active -> Ended) goes through the dedicated
    PUT /admin/events/{id}/status endpoint: 200, DB actually flips to 'ended',
    and an EVENT_UPDATED(status_changed) is broadcast to a subscribed WS client.
  - Authorization is unchanged: global_admin OK, in-scope venue_kj OK, singer 403,
    out-of-scope KJ 403.
  - The general PUT /admin/events/{id} still ENFORCES required fields (missing
    event_date -> 422) — validation was NOT weakened.
  - Ended-event business rules unchanged: event stays visible (historical), its
    participation history is intact, and new check-ins are rejected.

Run: cd /app/backend && python test_event_end_status.py
"""
import os, uuid, json, asyncio, datetime, jwt, requests, websockets
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).parent / ".env")
BASE = "http://localhost:8001/api"
WS_TMPL = "ws://localhost:8001/api/ws/events/{eid}?token={tok}"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

passed, failed = [], []
def check(n, c, x=""):
    (passed if c else failed).append(n)
    print(("PASS " if c else "FAIL ") + n + (f"  [{x}]" if x and not c else ""))

def login(email, pw):
    return requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw}).json()
def H(tok): return {"Authorization": f"Bearer {tok}"}


async def drain(ws, seconds=2.0):
    out = []
    try:
        while True:
            m = await asyncio.wait_for(ws.recv(), timeout=seconds)
            if m == "pong": continue
            try: out.append(json.loads(m))
            except Exception: pass
            seconds = 0.6
    except asyncio.TimeoutError:
        pass
    return out


async def main():
    created, reg = [], []
    try:
        admin = login("dev-admin@kingkaraoke2025.com", "DevKing!2026")["token"]
        kj = login("kj@kingkaraoke2025.com", "Kj!2026")["token"]
        singer = login("singer1@kingkaraoke2025.com", "Singer!2026")
        s_tok, s_id = singer["token"], singer["user"]["id"]

        me = requests.get(f"{BASE}/auth/me", headers=H(kj)).json()
        venue_id = (me.get("role_scope") or {}).get("venue_ids", [None])[0]
        check("KJ has an authorized venue", bool(venue_id))

        def mk(tok, vid, status="active"):
            eid = requests.post(f"{BASE}/admin/events", headers=H(tok), json={
                "venue_id": vid, "name": f"End {uuid.uuid4().hex[:6]}",
                "event_date": "2026-06-15", "status": status}).json()["id"]
            created.append(eid)
            return eid

        # ---------- Admin: Active -> Ended via dedicated status endpoint ----------
        eA = mk(admin, venue_id)
        r = requests.put(f"{BASE}/admin/events/{eA}/status", headers=H(admin), json={"status": "ended"})
        check("ADMIN status endpoint Active->Ended -> 200", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
        check("ADMIN response body has status=ended (string, not object)",
              isinstance(r.json().get("status"), str) and r.json().get("status") == "ended", r.text[:120])
        check("ADMIN event actually ENDED in DB", db.events.find_one({"id": eA}).get("status") == "ended")

        # ---------- KJ: Active -> Ended, and EVENT_UPDATED broadcast is delivered ----------
        eK = mk(kj, venue_id)
        ws = await asyncio.wait_for(websockets.connect(WS_TMPL.format(eid=eK, tok=kj)), timeout=6)
        await drain(ws, 0.5)
        r = requests.put(f"{BASE}/admin/events/{eK}/status", headers=H(kj), json={"status": "ended"})
        check("KJ status endpoint Active->Ended -> 200", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
        msgs = await drain(ws)
        types_actions = [(m.get("type"), m.get("action"), m.get("status")) for m in msgs]
        check("EVENT_UPDATED(status_changed, ended) broadcast to subscribed client",
              ("EVENT_UPDATED", "status_changed", "ended") in types_actions, str(types_actions))
        await ws.close()

        # ---------- Authorization unchanged ----------
        eS = mk(admin, venue_id)
        rSinger = requests.put(f"{BASE}/admin/events/{eS}/status", headers=H(s_tok), json={"status": "ended"})
        check("SINGER blocked from status endpoint -> 403", rSinger.status_code == 403, f"{rSinger.status_code}")

        # out-of-scope KJ (different venue) blocked
        other_v = db.venues.find_one({"id": {"$ne": venue_id}}, {"_id": 0, "id": 1})
        if other_v:
            eOther = requests.post(f"{BASE}/admin/events", headers=H(admin), json={
                "venue_id": other_v["id"], "name": f"Oth {uuid.uuid4().hex[:6]}",
                "event_date": "2026-06-15", "status": "active"}).json().get("id")
            if eOther:
                created.append(eOther)
                rOut = requests.put(f"{BASE}/admin/events/{eOther}/status", headers=H(kj), json={"status": "ended"})
                check("Out-of-scope KJ blocked from status endpoint -> 403", rOut.status_code == 403, f"{rOut.status_code}")

        # ---------- General PUT still ENFORCES required fields (NOT weakened) ----------
        eV = mk(admin, venue_id)
        rBad = requests.put(f"{BASE}/admin/events/{eV}", headers=H(admin),
                            json={"venue_id": venue_id, "name": "x", "status": "ended"})  # no event_date
        check("General PUT still 422 when event_date missing (validation NOT weakened)",
              rBad.status_code == 422, f"{rBad.status_code}")
        check("422 detail is the Pydantic array shape (frontend must stringify it)",
              isinstance(rBad.json().get("detail"), list), type(rBad.json().get("detail")).__name__)

        # ---------- Ended-event business rules unchanged ----------
        # check a singer into an ACTIVE event, then end it, and confirm history stays + new check-in blocked
        eEnd = mk(admin, venue_id)
        tokQR = requests.get(f"{BASE}/admin/events/{eEnd}/qr", headers=H(admin)).json()["token"]
        rc = requests.post(f"{BASE}/e/checkin/{tokQR}", headers=H(s_tok))
        check("Singer checks into event while ACTIVE", rc.status_code == 200, rc.text[:120])
        part_before = db.event_participation.count_documents({"event_id": eEnd})
        requests.put(f"{BASE}/admin/events/{eEnd}/status", headers=H(admin), json={"status": "ended"})
        check("Ended event still visible/historical (event doc present)", db.events.find_one({"id": eEnd}) is not None)
        check("Ended event participation history preserved",
              db.event_participation.count_documents({"event_id": eEnd}) == part_before and part_before >= 1)
        rc2 = requests.post(f"{BASE}/e/checkin/{tokQR}", headers=H(s_tok))
        check("New check-in into ENDED event rejected (400 not open)",
              rc2.status_code == 400 and "not open" in rc2.text.lower(), f"{rc2.status_code} {rc2.text[:120]}")

    finally:
        for e in created:
            for c in ("event_queue", "event_participation", "event_checkins", "event_checkin_attempts",
                      "season_accomplishments", "event_challenges", "event_challenge_votes", "perk_usage"):
                db[c].delete_many({"event_id": e})
            db.point_ledger.delete_many({"event_id": e})
            db.events.delete_one({"id": e})
        # reverse the one real check-in's season/lifetime points (check-in awards +10 each)
        db.season_participation.update_one({"user_id": s_id}, {"$inc": {"points": -10}})
        db.users.update_one({"id": s_id}, {"$inc": {"points": -10}})

    print(f"\n==== {len(passed)} passed, {len(failed)} failed ====")
    if failed: print("FAILED:", failed)


if __name__ == "__main__":
    asyncio.run(main())
