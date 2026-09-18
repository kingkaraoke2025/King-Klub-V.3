"""
Phase 2 — Event-scoped Battles (Karaoke duels).

A fully isolated, event-scoped re-implementation of the Phase 1 battle system. Unlike the
legacy global `challenges` collection, every battle here belongs to exactly ONE event and is
operated only by staff who are in scope for that event (venue_kj for their venue, location
manager for their location, global admin everywhere). Points earned by winners/participants
are attributed to the EVENT and the current SEASON via the shared idempotent award ledger —
never to the legacy lifetime `users.points` system.

Isolation guarantees:
  - Every battle carries event_id + venue_id + location_id; all reads filter by event_id.
  - Every KJ operation loads the event from the DB and runs authz.require_event_staff(user, ev)
    so a manually-changed event_id/battle_id can never reach another venue's event.
  - Contestants must both be checked into THIS event (event_participation).
  - Votes live in `event_challenge_votes`, unique per (challenge, voter); a voter must be a
    checked-in participant of the same event.
  - Winner/participant points go through award_ledger (event + season only), dedupe-keyed per
    battle so finalize/pick-winner can never double-count.

Collections (additive, created on first use):
  - event_challenges
  - event_challenge_votes
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import authz

OPEN_STATUSES = ("active", "scheduled")


def _iso():
    return datetime.now(timezone.utc).isoformat()


class BattleCreate(BaseModel):
    challenger_id: str
    opponent_id: str
    challenge_type: str


class VoteBody(BaseModel):
    choice: str  # "challenger" | "opponent"


class PickWinnerBody(BaseModel):
    winner_id: str


def build_router(db, manager, get_current_user, event_qr_enabled, challenge_types,
                 award_ledger=None):
    router = APIRouter(prefix="/api")

    def _flag():
        if not event_qr_enabled:
            raise HTTPException(status_code=403, detail="Event system is disabled")

    async def _get_event(event_id):
        ev = await db.events.find_one({"id": event_id}, {"_id": 0})
        if not ev:
            raise HTTPException(status_code=404, detail="Event not found")
        return ev

    async def _get_battle(event_id, battle_id):
        b = await db.event_challenges.find_one({"id": battle_id, "event_id": event_id}, {"_id": 0})
        if not b:
            raise HTTPException(status_code=404, detail="Battle not found in this event")
        return b

    async def _names(ids):
        rows = await db.users.find(
            {"id": {"$in": list({i for i in ids if i})}},
            {"_id": 0, "id": 1, "display_name": 1}).to_list(100000)
        return {u["id"]: u.get("display_name", "Unknown") for u in rows}

    async def _vote_counts(battle_id):
        rows = await db.event_challenge_votes.find({"challenge_id": battle_id}, {"_id": 0}).to_list(100000)
        c = sum(1 for r in rows if r.get("choice") == "challenger")
        o = sum(1 for r in rows if r.get("choice") == "opponent")
        return c, o, rows

    async def _decorate(b, umap, my_id=None):
        c, o, votes = await _vote_counts(b["id"])
        mine = next((v["choice"] for v in votes if v.get("voter_id") == my_id), None) if my_id else None
        tinfo = challenge_types.get(b["type"], {"name": b["type"]})
        return {
            **b,
            "challenger_name": umap.get(b["challenger_id"], "Unknown"),
            "opponent_name": umap.get(b["opponent_id"], "Unknown"),
            "winner_name": umap.get(b.get("winner_id"), None) if b.get("winner_id") else None,
            "type_info": tinfo,
            "votes_challenger": c,
            "votes_opponent": o,
            "vote_count": c + o,
            "my_vote": mine,
        }

    async def _require_checked_in(event_id, user_id, label):
        part = await db.event_participation.find_one(
            {"user_id": user_id, "event_id": event_id, "status": "checked_in"}, {"_id": 0})
        if not part:
            raise HTTPException(status_code=400, detail=f"{label} is not checked into this event")

    # -------------------- LIST (staff + participant view) --------------------
    @router.get("/events/{event_id}/battles")
    async def list_event_battles(event_id: str, user: dict = Depends(get_current_user)):
        _flag()
        ev = await _get_event(event_id)
        authz.require_event_view(user, ev)  # singers may see battles to vote
        rows = await db.event_challenges.find({"event_id": event_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
        umap = await _names([i for b in rows for i in (b["challenger_id"], b["opponent_id"], b.get("winner_id"))])
        return [await _decorate(b, umap, my_id=user["id"]) for b in rows]

    @router.get("/events/{event_id}/battle-types")
    async def battle_types(event_id: str, user: dict = Depends(get_current_user)):
        _flag()
        ev = await _get_event(event_id)
        authz.require_event_view(user, ev)
        return [{"id": k, **v} for k, v in challenge_types.items()]

    # -------------------- CREATE (staff, scope-checked) --------------------
    @router.post("/events/{event_id}/battles")
    async def create_event_battle(event_id: str, data: BattleCreate, user: dict = Depends(get_current_user)):
        _flag()
        ev = await _get_event(event_id)
        authz.require_event_staff(user, ev)
        if ev["status"] not in OPEN_STATUSES:
            raise HTTPException(status_code=400, detail=f"Event is not open (status: {ev['status']})")
        if data.challenge_type not in challenge_types:
            raise HTTPException(status_code=400, detail="Invalid challenge type")
        if data.challenger_id == data.opponent_id:
            raise HTTPException(status_code=400, detail="A singer cannot battle themselves")
        await _require_checked_in(event_id, data.challenger_id, "Challenger")
        await _require_checked_in(event_id, data.opponent_id, "Opponent")
        existing = await db.event_challenges.find_one({
            "event_id": event_id, "status": {"$in": ["pending", "voting"]},
            "$or": [
                {"challenger_id": data.challenger_id, "opponent_id": data.opponent_id},
                {"challenger_id": data.opponent_id, "opponent_id": data.challenger_id},
            ]}, {"_id": 0})
        if existing:
            raise HTTPException(status_code=400, detail="An active battle already exists between these singers in this event")
        battle = {
            "id": str(uuid.uuid4()), "event_id": event_id, "venue_id": ev["venue_id"],
            "location_id": ev.get("location_id"), "challenger_id": data.challenger_id,
            "opponent_id": data.opponent_id, "type": data.challenge_type, "status": "pending",
            "voting_open": False, "winner_id": None, "created_by": user["id"],
            "created_at": _iso(), "updated_at": _iso(),
        }
        await db.event_challenges.insert_one(dict(battle))
        battle.pop("_id", None)
        umap = await _names([battle["challenger_id"], battle["opponent_id"]])
        await manager.broadcast_event(event_id, {"type": "EVENT_BATTLE_UPDATED", "action": "created",
                                                 "event_id": event_id, "battle_id": battle["id"]})
        return await _decorate(battle, umap, my_id=user["id"])

    # -------------------- VOTING (staff, scope-checked) --------------------
    @router.post("/events/{event_id}/battles/{battle_id}/open-voting")
    async def open_voting(event_id: str, battle_id: str, user: dict = Depends(get_current_user)):
        _flag()
        ev = await _get_event(event_id)
        authz.require_event_staff(user, ev)
        b = await _get_battle(event_id, battle_id)
        if b["status"] == "completed":
            raise HTTPException(status_code=400, detail="Battle already completed")
        await db.event_challenges.update_one({"id": battle_id, "event_id": event_id},
                                             {"$set": {"status": "voting", "voting_open": True, "updated_at": _iso()}})
        await manager.broadcast_event(event_id, {"type": "EVENT_BATTLE_UPDATED", "action": "voting_open",
                                                 "event_id": event_id, "battle_id": battle_id})
        return {"message": "Voting opened", "battle_id": battle_id}

    @router.post("/events/{event_id}/battles/{battle_id}/close-voting")
    async def close_voting(event_id: str, battle_id: str, user: dict = Depends(get_current_user)):
        _flag()
        ev = await _get_event(event_id)
        authz.require_event_staff(user, ev)
        await _get_battle(event_id, battle_id)
        await db.event_challenges.update_one({"id": battle_id, "event_id": event_id},
                                             {"$set": {"voting_open": False, "updated_at": _iso()}})
        await manager.broadcast_event(event_id, {"type": "EVENT_BATTLE_UPDATED", "action": "voting_closed",
                                                 "event_id": event_id, "battle_id": battle_id})
        return {"message": "Voting closed", "battle_id": battle_id}

    # -------------------- VOTE (checked-in participant) --------------------
    @router.post("/events/{event_id}/battles/{battle_id}/vote")
    async def vote_battle(event_id: str, battle_id: str, data: VoteBody, user: dict = Depends(get_current_user)):
        _flag()
        ev = await _get_event(event_id)
        authz.require_event_view(user, ev)
        b = await _get_battle(event_id, battle_id)
        if not b.get("voting_open"):
            raise HTTPException(status_code=400, detail="Voting is not open for this battle")
        if data.choice not in ("challenger", "opponent"):
            raise HTTPException(status_code=400, detail="Vote must be 'challenger' or 'opponent'")
        await _require_checked_in(event_id, user["id"], "You")
        if user["id"] in (b["challenger_id"], b["opponent_id"]):
            raise HTTPException(status_code=400, detail="Contestants cannot vote in their own battle")
        if await db.event_challenge_votes.find_one({"challenge_id": battle_id, "voter_id": user["id"]}, {"_id": 0}):
            raise HTTPException(status_code=400, detail="You have already voted in this battle")
        await db.event_challenge_votes.insert_one({
            "id": str(uuid.uuid4()), "challenge_id": battle_id, "event_id": event_id,
            "voter_id": user["id"], "choice": data.choice, "at": _iso()})
        c, o, _ = await _vote_counts(battle_id)
        await manager.broadcast_event(event_id, {"type": "EVENT_BATTLE_UPDATED", "action": "vote",
                                                 "event_id": event_id, "battle_id": battle_id})
        return {"message": "Vote recorded", "votes_challenger": c, "votes_opponent": o}

    async def _award_and_complete(event_id, ev, b, winner_id):
        loser_id = b["opponent_id"] if winner_id == b["challenger_id"] else b["challenger_id"]
        tinfo = challenge_types.get(b["type"], {"points_winner": 50, "points_participant": 25})
        awarded = {"winner": 0, "loser": 0}
        if award_ledger is not None:
            rw = await award_ledger(user_id=winner_id, points=tinfo.get("points_winner", 50),
                                    source="battle_win", dedupe_key=f"battlewin:{b['id']}", event=ev,
                                    to_event=True, to_season=True, to_lifetime=False)
            if rw.get("awarded"):
                awarded["winner"] = tinfo.get("points_winner", 50)
            rl = await award_ledger(user_id=loser_id, points=tinfo.get("points_participant", 25),
                                    source="battle_participant", dedupe_key=f"battlepart:{b['id']}", event=ev,
                                    to_event=True, to_season=True, to_lifetime=False)
            if rl.get("awarded"):
                awarded["loser"] = tinfo.get("points_participant", 25)
        await db.event_challenges.update_one(
            {"id": b["id"], "event_id": event_id},
            {"$set": {"status": "completed", "voting_open": False, "winner_id": winner_id, "updated_at": _iso()}})
        await manager.broadcast_event(event_id, {"type": "EVENT_BATTLE_UPDATED", "action": "completed",
                                                 "event_id": event_id, "battle_id": b["id"], "winner_id": winner_id})
        return awarded, loser_id

    # -------------------- FINALIZE (by votes) --------------------
    @router.post("/events/{event_id}/battles/{battle_id}/finalize")
    async def finalize_battle(event_id: str, battle_id: str, user: dict = Depends(get_current_user)):
        _flag()
        ev = await _get_event(event_id)
        authz.require_event_staff(user, ev)
        b = await _get_battle(event_id, battle_id)
        if b["status"] == "completed":
            raise HTTPException(status_code=400, detail="Battle already completed")
        c, o, _ = await _vote_counts(battle_id)
        if c == o:
            raise HTTPException(status_code=400, detail="Battle is tied — use pick-winner to decide")
        winner_id = b["challenger_id"] if c > o else b["opponent_id"]
        awarded, loser_id = await _award_and_complete(event_id, ev, b, winner_id)
        umap = await _names([winner_id, loser_id])
        return {"message": f"{umap.get(winner_id, 'Winner')} wins the battle!", "battle_id": battle_id,
                "winner_id": winner_id, "winner_name": umap.get(winner_id), "awarded": awarded}

    # -------------------- PICK WINNER (staff decides) --------------------
    @router.post("/events/{event_id}/battles/{battle_id}/pick-winner")
    async def pick_winner(event_id: str, battle_id: str, data: PickWinnerBody,
                          user: dict = Depends(get_current_user)):
        _flag()
        ev = await _get_event(event_id)
        authz.require_event_staff(user, ev)
        b = await _get_battle(event_id, battle_id)
        if b["status"] == "completed":
            raise HTTPException(status_code=400, detail="Battle already completed")
        if data.winner_id not in (b["challenger_id"], b["opponent_id"]):
            raise HTTPException(status_code=400, detail="Winner must be one of the two contestants")
        awarded, loser_id = await _award_and_complete(event_id, ev, b, data.winner_id)
        umap = await _names([data.winner_id, loser_id])
        return {"message": f"{umap.get(data.winner_id, 'Winner')} wins the battle!", "battle_id": battle_id,
                "winner_id": data.winner_id, "winner_name": umap.get(data.winner_id), "awarded": awarded}

    # -------------------- CANCEL --------------------
    @router.post("/events/{event_id}/battles/{battle_id}/cancel")
    async def cancel_battle(event_id: str, battle_id: str, user: dict = Depends(get_current_user)):
        _flag()
        ev = await _get_event(event_id)
        authz.require_event_staff(user, ev)
        b = await _get_battle(event_id, battle_id)
        if b["status"] == "completed":
            raise HTTPException(status_code=400, detail="Cannot cancel a completed battle")
        await db.event_challenges.update_one({"id": battle_id, "event_id": event_id},
                                             {"$set": {"status": "cancelled", "voting_open": False, "updated_at": _iso()}})
        await manager.broadcast_event(event_id, {"type": "EVENT_BATTLE_UPDATED", "action": "cancelled",
                                                 "event_id": event_id, "battle_id": battle_id})
        return {"message": "Battle cancelled", "battle_id": battle_id}

    return router
