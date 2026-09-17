"""
Phase 2, Step 4 — Event-scoped queue, rank perks, and singer-list reordering.

Extracted into its own module (low-risk) to avoid growing server.py further. It touches
ONLY the new event-scoped collections (`event_queue`, `event_perk_usage`, `event_participation`)
and never the legacy `queue`/`perk_usage` collections. Dependencies (db, manager, auth deps,
rank helpers) are injected by server.py via build_router() to avoid circular imports.

Isolation guarantees:
  - Every event_queue item carries event_id + venue_id + location_id; all reads filter by event_id.
  - The 5-songs / 30-min limit is evaluated per (user, event) using that event's check-in time.
  - Rank perks are recorded per (user, event) in event_perk_usage (unique) — no cross-event leak.
  - Queue/singer-list mutations only ever touch rows for the target event_id.
  - Live updates go through manager.broadcast_event(event_id, ...) → only that event's WS room.

Authorization note (Step 4): the current model has a single global is_admin flag. Any admin can
operate any event's queue/singer-list. Venue/KJ-scoped permissions are deferred to Step 7.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

import authz

MAX_SONGS_PER_WINDOW = 5
WINDOW_MINUTES = 30
MINUTES_PER_SONG = 4
OPEN_STATUSES = ("active", "scheduled")


class SongInput(BaseModel):
    song_title: str = Field(max_length=200)
    artist: str = Field(max_length=200)
    message_to_admin: Optional[str] = Field(default=None, max_length=250)


class ReorderQueue(BaseModel):
    new_position: int


class ReorderSinger(BaseModel):
    user_id: str
    new_position: int


def _now():
    return datetime.now(timezone.utc)


def _iso():
    return _now().isoformat()


def build_router(db, manager, get_current_user, get_admin_user, event_qr_enabled,
                 get_user_rank_name, rank_perks, award_ledger=None, song_points=10):
    router = APIRouter(prefix="/api")

    def _flag():
        if not event_qr_enabled:
            raise HTTPException(status_code=403, detail="Event QR system is disabled")

    async def _get_event(event_id):
        ev = await db.events.find_one({"id": event_id}, {"_id": 0})
        if not ev:
            raise HTTPException(status_code=404, detail="Event not found")
        return ev

    async def _event_open(ev):
        if ev["status"] not in OPEN_STATUSES:
            raise HTTPException(status_code=400, detail=f"Event is not open for queue actions (status: {ev['status']})")

    async def _next_position(event_id):
        last = await db.event_queue.find_one(
            {"event_id": event_id, "status": {"$in": ["pending", "current"]}}, sort=[("position", -1)])
        return (last["position"] + 1) if last else 1

    async def _recalc_positions(event_id):
        rows = await db.event_queue.find(
            {"event_id": event_id, "status": {"$in": ["pending", "current"]}}, {"_id": 0}
        ).sort("position", 1).to_list(500)
        for i, r in enumerate(rows):
            await db.event_queue.update_one(
                {"id": r["id"]}, {"$set": {"position": i + 1, "estimated_wait": i * MINUTES_PER_SONG}})

    # -------------------- Event QUEUE --------------------
    @router.post("/events/{event_id}/queue")
    async def add_event_song(event_id: str, data: SongInput, user: dict = Depends(get_current_user)):
        _flag()
        ev = await _get_event(event_id)
        authz.require_event_view(user, ev)
        await _event_open(ev)
        is_admin = user.get("is_admin", False)

        part = await db.event_participation.find_one({"user_id": user["id"], "event_id": event_id}, {"_id": 0})
        if not part and not is_admin:
            raise HTTPException(status_code=400, detail="Check in to this event first to add songs")

        songs_this_window = 0
        minutes_until_reset = WINDOW_MINUTES
        if not is_admin:
            checkin_time = datetime.fromisoformat(part["checked_in_at"].replace("Z", "+00:00"))
            mins_since = int((_now() - checkin_time).total_seconds() / 60)
            window = mins_since // WINDOW_MINUTES
            wstart = checkin_time + timedelta(minutes=window * WINDOW_MINUTES)
            wend = wstart + timedelta(minutes=WINDOW_MINUTES)
            songs_this_window = await db.event_queue.count_documents({
                "event_id": event_id, "user_id": user["id"],
                "created_at": {"$gte": wstart.isoformat(), "$lt": wend.isoformat()}})
            minutes_until_reset = WINDOW_MINUTES - (mins_since % WINDOW_MINUTES)
            if songs_this_window >= MAX_SONGS_PER_WINDOW:
                raise HTTPException(status_code=400,
                                    detail=f"You've added {MAX_SONGS_PER_WINDOW} songs this window at this event. "
                                           f"Limit resets in {minutes_until_reset} minutes!")

        message = (data.message_to_admin or None)
        if message and len(message) > 250:
            message = message[:250]
        position = await _next_position(event_id)
        item = {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "venue_id": ev["venue_id"],
            "location_id": ev.get("location_id"),
            "user_id": user["id"],
            "user_name": user["display_name"],
            "song_title": data.song_title,
            "artist": data.artist,
            "message_to_admin": message,
            "status": "pending",
            "position": position,
            "estimated_wait": (position - 1) * MINUTES_PER_SONG,
            "perk_protected": False,
            "created_at": _iso(),
            "updated_at": _iso(),
        }
        await db.event_queue.insert_one(item)
        item.pop("_id", None)
        await manager.broadcast_event(event_id, {"type": "EVENT_QUEUE_UPDATED", "action": "song_added",
                                                 "event_id": event_id, "item": item})
        if is_admin:
            return {**item, "songs_this_window": 0, "songs_remaining": 999, "window_resets_in": 0, "is_admin": True}
        return {**item, "songs_this_window": songs_this_window + 1,
                "songs_remaining": MAX_SONGS_PER_WINDOW - (songs_this_window + 1),
                "window_resets_in": minutes_until_reset}

    @router.get("/events/{event_id}/queue")
    async def get_event_queue(event_id: str, limit: int = 200, offset: int = 0,
                              user: dict = Depends(get_current_user)):
        _flag()
        ev = await _get_event(event_id)
        authz.require_event_view(user, ev)
        limit = max(1, min(limit, 500))
        offset = max(0, offset)
        rows = await db.event_queue.find(
            {"event_id": event_id, "status": {"$in": ["pending", "current"]}}, {"_id": 0}
        ).sort("position", 1).skip(offset).limit(limit).to_list(limit)
        return rows

    @router.get("/events/{event_id}/queue/my-status")
    async def my_event_queue_status(event_id: str, user: dict = Depends(get_current_user)):
        _flag()
        ev = await _get_event(event_id)
        authz.require_event_view(user, ev)
        is_admin = user.get("is_admin", False)
        part = await db.event_participation.find_one({"user_id": user["id"], "event_id": event_id}, {"_id": 0})
        if is_admin:
            mine = await db.event_queue.find(
                {"event_id": event_id, "user_id": user["id"], "status": {"$in": ["pending", "current"]}},
                {"_id": 0}).sort("position", 1).to_list(50)
            return {"checked_in": True, "is_admin": True, "can_add_songs": True, "songs_this_window": 0,
                    "songs_remaining": 999, "max_songs_per_window": 999, "window_resets_in": 0,
                    "my_songs": mine, "reason": None}
        if not part:
            return {"checked_in": False, "can_add_songs": False,
                    "reason": "Check in to this event first", "songs_this_window": 0,
                    "max_songs_per_window": MAX_SONGS_PER_WINDOW}
        checkin_time = datetime.fromisoformat(part["checked_in_at"].replace("Z", "+00:00"))
        mins_since = int((_now() - checkin_time).total_seconds() / 60)
        window = mins_since // WINDOW_MINUTES
        wstart = checkin_time + timedelta(minutes=window * WINDOW_MINUTES)
        wend = wstart + timedelta(minutes=WINDOW_MINUTES)
        reset_in = WINDOW_MINUTES - (mins_since % WINDOW_MINUTES)
        count = await db.event_queue.count_documents({
            "event_id": event_id, "user_id": user["id"],
            "created_at": {"$gte": wstart.isoformat(), "$lt": wend.isoformat()}})
        mine = await db.event_queue.find(
            {"event_id": event_id, "user_id": user["id"], "status": {"$in": ["pending", "current"]}},
            {"_id": 0}).sort("position", 1).to_list(50)
        can = count < MAX_SONGS_PER_WINDOW
        return {"checked_in": True, "can_add_songs": can, "songs_this_window": count,
                "songs_remaining": MAX_SONGS_PER_WINDOW - count, "max_songs_per_window": MAX_SONGS_PER_WINDOW,
                "window_resets_in": reset_in, "my_songs": mine,
                "reason": None if can else f"5 song limit reached. Resets in {reset_in} min!"}

    @router.delete("/events/{event_id}/queue/{item_id}")
    async def cancel_event_song(event_id: str, item_id: str, user: dict = Depends(get_current_user)):
        _flag()
        ev = await _get_event(event_id)
        authz.require_event_view(user, ev)
        item = await db.event_queue.find_one({"id": item_id, "event_id": event_id}, {"_id": 0})
        if not item:
            raise HTTPException(status_code=404, detail="Queue item not found in this event")
        if item["user_id"] != user["id"] and not authz.staff_can_access_event(user, ev):
            raise HTTPException(status_code=403, detail="Not authorized")
        await db.event_queue.update_one({"id": item_id}, {"$set": {"status": "cancelled", "updated_at": _iso()}})
        await _recalc_positions(event_id)
        await manager.broadcast_event(event_id, {"type": "EVENT_QUEUE_UPDATED", "action": "song_removed",
                                                 "event_id": event_id, "item_id": item_id})
        return {"message": "Removed from event queue"}

    @router.post("/events/{event_id}/queue/{item_id}/complete")
    async def complete_event_song(event_id: str, item_id: str, user: dict = Depends(get_current_user)):
        """Mark a song completed within the event. Staff-only, scope-checked."""
        _flag()
        ev = await _get_event(event_id)
        authz.require_event_staff(user, ev)
        item = await db.event_queue.find_one({"id": item_id, "event_id": event_id}, {"_id": 0})
        if not item:
            raise HTTPException(status_code=404, detail="Queue item not found in this event")
        if item["status"] == "completed":
            return {"message": "Song already completed", "points_awarded": 0, "already": True}
        await db.event_queue.update_one({"id": item_id}, {"$set": {"status": "completed", "updated_at": _iso()}})
        # Step 5: performed-song is a defined singer action -> idempotent event + season points (once per song item)
        awarded_pts = 0
        if award_ledger is not None:
            ev = await db.events.find_one({"id": event_id}, {"_id": 0})
            res = await award_ledger(user_id=item["user_id"], points=song_points, source="event_song",
                                     dedupe_key=f"song:{item_id}", event=ev)
            if res.get("awarded"):
                awarded_pts = song_points
                await db.event_participation.update_one(
                    {"user_id": item["user_id"], "event_id": event_id}, {"$inc": {"songs_performed": 1}})
        nxt = await db.event_queue.find_one({"event_id": event_id, "status": "pending"}, sort=[("position", 1)])
        if nxt:
            await db.event_queue.update_one({"id": nxt["id"]}, {"$set": {"status": "current"}})
        await _recalc_positions(event_id)
        await manager.broadcast_event(event_id, {"type": "EVENT_QUEUE_UPDATED", "action": "song_completed",
                                                 "event_id": event_id, "item_id": item_id})
        return {"message": "Song completed", "points_awarded": awarded_pts, "event_id": event_id}

    @router.post("/events/{event_id}/queue/{item_id}/set-current")
    async def set_current_event_song(event_id: str, item_id: str, user: dict = Depends(get_current_user)):
        _flag()
        ev = await _get_event(event_id)
        authz.require_event_staff(user, ev)
        item = await db.event_queue.find_one({"id": item_id, "event_id": event_id}, {"_id": 0})
        if not item:
            raise HTTPException(status_code=404, detail="Queue item not found in this event")
        await db.event_queue.update_many(
            {"event_id": event_id, "status": "current"}, {"$set": {"status": "pending"}})
        await db.event_queue.update_one({"id": item_id}, {"$set": {"status": "current", "updated_at": _iso()}})
        await manager.broadcast_event(event_id, {"type": "EVENT_QUEUE_UPDATED", "action": "song_now_playing",
                                                 "event_id": event_id, "item_id": item_id})
        return {"message": "Current song updated"}

    async def _swap(event_id, item_id, direction, admin):
        item = await db.event_queue.find_one({"id": item_id, "event_id": event_id, "status": "pending"}, {"_id": 0})
        if not item:
            raise HTTPException(status_code=404, detail="Queue item not found or not pending")
        cur = item["position"]
        if item.get("perk_protected") and cur <= 4:
            raise HTTPException(status_code=400, detail="This song used a perk and cannot be moved")
        if direction == "up":
            if cur <= 1:
                raise HTTPException(status_code=400, detail="Already at the top")
            new = cur - 1
        else:
            last = await db.event_queue.find_one(
                {"event_id": event_id, "status": "pending"}, sort=[("position", -1)])
            if not last or cur >= last["position"]:
                raise HTTPException(status_code=400, detail="Already at the bottom")
            new = cur + 1
        neighbor = await db.event_queue.find_one(
            {"event_id": event_id, "status": "pending", "position": new}, {"_id": 0})
        # symmetric perk-protection: never displace a perk-protected top-4 song (either direction)
        if neighbor and neighbor.get("perk_protected") and new <= 4:
            raise HTTPException(status_code=400, detail=f"Cannot move around a perk-protected song at position {new}")
        if neighbor:
            await db.event_queue.update_one({"id": neighbor["id"]}, {"$set": {
                "position": cur, "estimated_wait": (cur - 1) * MINUTES_PER_SONG}})
        await db.event_queue.update_one({"id": item_id}, {"$set": {
            "position": new, "estimated_wait": (new - 1) * MINUTES_PER_SONG, "updated_at": _iso()}})
        await manager.broadcast_event(event_id, {"type": "EVENT_QUEUE_UPDATED", "action": "queue_reordered",
                                                 "event_id": event_id})
        return {"message": f"Moved from #{cur} to #{new}", "old_position": cur, "new_position": new}

    @router.post("/events/{event_id}/queue/{item_id}/move-up")
    async def move_up(event_id: str, item_id: str, user: dict = Depends(get_current_user)):
        _flag()
        ev = await _get_event(event_id)
        authz.require_event_staff(user, ev)
        return await _swap(event_id, item_id, "up", user)

    @router.post("/events/{event_id}/queue/{item_id}/move-down")
    async def move_down(event_id: str, item_id: str, user: dict = Depends(get_current_user)):
        _flag()
        ev = await _get_event(event_id)
        authz.require_event_staff(user, ev)
        return await _swap(event_id, item_id, "down", user)

    @router.post("/events/{event_id}/queue/{item_id}/reorder")
    async def reorder_event_song(event_id: str, item_id: str, data: ReorderQueue,
                                 user: dict = Depends(get_current_user)):
        _flag()
        ev = await _get_event(event_id)
        authz.require_event_staff(user, ev)
        item = await db.event_queue.find_one({"id": item_id, "event_id": event_id, "status": "pending"}, {"_id": 0})
        if not item:
            raise HTTPException(status_code=404, detail="Queue item not found or not pending")
        cur = item["position"]
        new = data.new_position
        if cur == new:
            return {"message": "No change", "position": cur}
        if item.get("perk_protected") and cur <= 4:
            raise HTTPException(status_code=400, detail="This song used a perk and cannot be moved")
        allp = await db.event_queue.find(
            {"event_id": event_id, "status": "pending"}, {"_id": 0}).sort("position", 1).to_list(500)
        if new < 1 or new > len(allp):
            raise HTTPException(status_code=400, detail=f"Invalid position. Must be 1..{len(allp)}")
        if new < cur:
            await db.event_queue.update_many(
                {"event_id": event_id, "status": "pending", "position": {"$gte": new, "$lt": cur}},
                {"$inc": {"position": 1}})
        else:
            await db.event_queue.update_many(
                {"event_id": event_id, "status": "pending", "position": {"$gt": cur, "$lte": new}},
                {"$inc": {"position": -1}})
        await db.event_queue.update_one({"id": item_id}, {"$set": {"position": new, "updated_at": _iso()}})
        await _recalc_positions(event_id)
        await manager.broadcast_event(event_id, {"type": "EVENT_QUEUE_UPDATED", "action": "queue_reordered",
                                                 "event_id": event_id})
        return {"message": f"Moved from #{cur} to #{new}", "old_position": cur, "new_position": new}

    # -------------------- Event PERKS --------------------
    @router.get("/events/{event_id}/perk-status")
    async def event_perk_status(event_id: str, user: dict = Depends(get_current_user)):
        _flag()
        ev = await _get_event(event_id)
        authz.require_event_view(user, ev)
        rank_name = get_user_rank_name(user)
        perk = rank_perks.get(rank_name)
        if not perk:
            return {"has_perk": False, "rank": rank_name, "perk": None, "can_use": False,
                    "reason": "Your rank has no queue perk yet."}
        part = await db.event_participation.find_one({"user_id": user["id"], "event_id": event_id})
        if not part:
            return {"has_perk": True, "rank": rank_name, "perk": perk, "can_use": False,
                    "reason": "Check in to this event to use your perk"}
        used = await db.event_perk_usage.find_one({"user_id": user["id"], "event_id": event_id})
        if used:
            return {"has_perk": True, "rank": rank_name, "perk": perk, "can_use": False,
                    "reason": "You've already used your perk at this event"}
        qi = await db.event_queue.find_one({"user_id": user["id"], "event_id": event_id, "status": "pending"})
        if not qi:
            return {"has_perk": True, "rank": rank_name, "perk": perk, "can_use": False,
                    "reason": "Add a song to this event's queue first"}
        return {"has_perk": True, "rank": rank_name, "perk": perk, "can_use": True,
                "queue_position": qi["position"]}

    @router.post("/events/{event_id}/use-perk")
    async def use_event_perk(event_id: str, user: dict = Depends(get_current_user)):
        _flag()
        ev = await _get_event(event_id)
        authz.require_event_view(user, ev)
        rank_name = get_user_rank_name(user)
        perk = rank_perks.get(rank_name)
        if not perk:
            raise HTTPException(status_code=400, detail="Your rank has no queue perk")
        part = await db.event_participation.find_one({"user_id": user["id"], "event_id": event_id})
        if not part:
            raise HTTPException(status_code=400, detail="Check in to this event first")
        if await db.event_perk_usage.find_one({"user_id": user["id"], "event_id": event_id}):
            raise HTTPException(status_code=400, detail="You've already used your perk at this event")
        qi = await db.event_queue.find_one(
            {"user_id": user["id"], "event_id": event_id, "status": "pending"}, {"_id": 0})
        if not qi:
            raise HTTPException(status_code=400, detail="You don't have a pending song in this event")
        old = qi["position"]
        new = max(1, old - perk["value"]) if perk["type"] == "jump_ahead" else perk["value"]
        if old <= new:
            raise HTTPException(status_code=400, detail=f"You're already at position {old}")
        # record usage FIRST (unique index is the guard) so a mid-operation failure can't leave the
        # queue reordered without the perk being consumed
        try:
            await db.event_perk_usage.insert_one({
                "id": str(uuid.uuid4()), "user_id": user["id"], "event_id": event_id,
                "rank": rank_name, "perk_type": perk["type"], "old_position": old, "new_position": new,
                "used_at": _iso()})
        except DuplicateKeyError:
            raise HTTPException(status_code=400, detail="You've already used your perk at this event")
        shift = await db.event_queue.find(
            {"event_id": event_id, "status": "pending", "position": {"$gte": new, "$lt": old}}, {"_id": 0}
        ).to_list(500)
        for s in shift:
            await db.event_queue.update_one({"id": s["id"]}, {"$set": {
                "position": s["position"] + 1, "estimated_wait": s["position"] * MINUTES_PER_SONG}})
        await db.event_queue.update_one({"id": qi["id"]}, {"$set": {
            "position": new, "estimated_wait": (new - 1) * MINUTES_PER_SONG, "perk_protected": new <= 4,
            "updated_at": _iso()}})
        await manager.broadcast_event(event_id, {"type": "EVENT_PERK_USED", "event_id": event_id,
                                                 "user_name": user["display_name"], "rank": rank_name,
                                                 "old_position": old, "new_position": new})
        return {"message": f"Perk activated! Moved from #{old} to #{new}",
                "old_position": old, "new_position": new, "perk_used": perk["description"]}

    # -------------------- Singer-list reorder --------------------
    @router.post("/events/{event_id}/singer-list/reorder")
    async def reorder_singer_list(event_id: str, data: ReorderSinger, user: dict = Depends(get_current_user)):
        """KJ manual reorder of an event's singer list. Only changes list_position within THIS event;
        never touches check-in timestamps or any other event."""
        _flag()
        ev = await _get_event(event_id)
        authz.require_event_staff(user, ev)
        target = await db.event_participation.find_one(
            {"user_id": data.user_id, "event_id": event_id}, {"_id": 0})
        if not target:
            raise HTTPException(status_code=404, detail="Singer is not in this event's list")
        rows = await db.event_participation.find(
            {"event_id": event_id}, {"_id": 0}).sort("list_position", 1).to_list(1000)
        n = len(rows)
        new = data.new_position
        if new < 1 or new > n:
            raise HTTPException(status_code=400, detail=f"Invalid position. Must be 1..{n}")
        cur = target.get("list_position")
        if cur == new:
            return {"message": "No change", "position": cur}
        if new < cur:
            await db.event_participation.update_many(
                {"event_id": event_id, "list_position": {"$gte": new, "$lt": cur}},
                {"$inc": {"list_position": 1}, "$set": {"updated_at": _iso()}})
        else:
            await db.event_participation.update_many(
                {"event_id": event_id, "list_position": {"$gt": cur, "$lte": new}},
                {"$inc": {"list_position": -1}, "$set": {"updated_at": _iso()}})
        await db.event_participation.update_one(
            {"user_id": data.user_id, "event_id": event_id},
            {"$set": {"list_position": new, "updated_at": _iso()}})
        await manager.broadcast_event(event_id, {"type": "EVENT_SINGER_LIST_REORDERED",
                                                 "event_id": event_id, "user_id": data.user_id,
                                                 "new_position": new})
        return {"message": f"Moved singer from #{cur} to #{new}", "old_position": cur, "new_position": new}

    return router
