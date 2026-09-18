"""
Phase 2 integration layer — wires the event/season modules into the base King Klub
server WITHOUT modifying legacy behaviour.

It adds (all under /api):
  - Admin management of locations / venues / events (scope-enforced).
  - Event-scoped QR generation and the Phase 2 check-in route  POST /api/e/checkin/{token}.
  - Event singer-list (scope/participation enforced).
  - Mounts the event queue/perk router (phase2_events) and the points/season router
    (phase2_seasons).
  - WebSocket /api/ws/events/{event_id} with per-event authorization.
  - Cron endpoint POST /api/cron/season-reset (shared-secret protected).
  - Startup hook: ensure current season + run annual auto-reset if due.

Isolation is enforced on the backend: every event is loaded from the DB and the
caller's DB role/scope is checked via authz — a client can never reach another
location/venue/event by changing an id.
"""
import base64
import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import (APIRouter, Depends, HTTPException, Query, Request, WebSocket,
                     WebSocketDisconnect)
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

import authz
import phase2_battles
import phase2_events
import phase2_seasons
from models_phase2 import Event, Location, Venue

# ---- Config (env-driven, dev-safe defaults) --------------------------------
EVENT_QR_ENABLED = os.environ.get("EVENT_QR_ENABLED", "true").lower() == "true"
EVENT_QR_SECRET = os.environ.get("EVENT_QR_SECRET", os.environ.get("VENUE_SECRET", "dev-event-secret"))
LEGACY_NIGHTLY_ENABLED = os.environ.get("LEGACY_NIGHTLY_ENABLED", "false").lower() == "true"
EVENT_CHECKIN_POINTS = int(os.environ.get("EVENT_CHECKIN_POINTS", "10"))
EVENT_SONG_POINTS = int(os.environ.get("EVENT_SONG_POINTS", "10"))
QR_TTL_HOURS = int(os.environ.get("EVENT_QR_TTL_HOURS", "18"))
WEBHOOK_CRON_SECRET = os.environ.get("WEBHOOK_CRON_SECRET", "dev-cron-secret")
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"

SEASON_CFG = {
    "timezone": os.environ.get("SEASON_TIMEZONE", os.environ.get("VENUE_TIMEZONE", "America/Chicago")),
    "reset_month": int(os.environ.get("SEASON_RESET_MONTH", "1")),
    "reset_day": int(os.environ.get("SEASON_RESET_DAY", "2")),
    "auto_enabled": os.environ.get("SEASON_AUTO_RESET_ENABLED", "true").lower() == "true",
}


def _iso():
    return datetime.now(timezone.utc).isoformat()


# ---- Signed event QR token -------------------------------------------------
def make_event_token(event_id: str, exp_iso: str) -> str:
    payload = {"e": event_id, "exp": exp_iso}
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(EVENT_QR_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()[:24]
    return f"{raw}.{sig}"


def parse_event_token(token: str) -> str:
    try:
        raw, _, sig = token.partition(".")
        expect = hmac.new(EVENT_QR_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()[:24]
        if not hmac.compare_digest(sig, expect):
            raise ValueError("bad signature")
        padded = raw + "=" * (-len(raw) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or tampered QR token")
    if datetime.fromisoformat(payload["exp"]) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="QR code has expired")
    return payload["e"]


# ---- Request models --------------------------------------------------------
class LocationInput(BaseModel):
    name: str
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "USA"
    timezone: str = "America/Chicago"


class VenueInput(BaseModel):
    location_id: str
    name: str
    address: Optional[str] = None
    timezone: Optional[str] = None


class EventInput(BaseModel):
    venue_id: str
    name: str
    event_date: str
    status: str = "scheduled"
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None


class EventStatusInput(BaseModel):
    status: str


def register_phase2(app, api_router, db, manager, get_current_user, get_admin_user,
                    get_rank, get_user_rank_name, rank_perks, challenge_types=None):
    """Attach all Phase 2 endpoints/routers/hooks. Called from server.py before
    app.include_router(api_router)."""

    async def award_ledger_bound(*, user_id, points, source, dedupe_key, event=None,
                                 to_event=True, to_season=True, to_lifetime=False):
        return await phase2_seasons.award_ledger(
            db, get_rank, SEASON_CFG, user_id=user_id, points=points, source=source,
            dedupe_key=dedupe_key, event=event, to_event=to_event, to_season=to_season,
            to_lifetime=to_lifetime)

    def _flag():
        if not EVENT_QR_ENABLED:
            raise HTTPException(status_code=403, detail="Event QR system is disabled")

    async def _get_event(event_id):
        ev = await db.events.find_one({"id": event_id}, {"_id": 0})
        if not ev:
            raise HTTPException(status_code=404, detail="Event not found")
        return ev

    # -------------------- LOCATIONS (global_admin only) --------------------
    @api_router.get("/admin/locations")
    async def list_locations(user: dict = Depends(get_current_user)):
        authz.require_staff(user)
        rows = await db.locations.find({}, {"_id": 0}).sort("created_at", 1).to_list(1000)
        return rows

    @api_router.post("/admin/locations")
    async def create_location(data: LocationInput, user: dict = Depends(get_current_user)):
        authz.require_global_admin(user)
        loc = Location(**data.model_dump()).to_mongo()
        try:
            await db.locations.insert_one(dict(loc))
        except DuplicateKeyError:
            raise HTTPException(status_code=400, detail="A location with this name already exists")
        loc.pop("_id", None)
        return loc

    # -------------------- VENUES (global_admin only) --------------------
    @api_router.get("/admin/venues")
    async def list_venues(location_id: Optional[str] = None, user: dict = Depends(get_current_user)):
        authz.require_staff(user)
        q = {}
        role = authz.roles.resolve_role(user)
        if role == authz.roles.ROLE_LOCATION_MANAGER:
            q["location_id"] = {"$in": authz.roles.get_role_scope(user)["location_ids"]}
        elif role == authz.roles.ROLE_VENUE_KJ:
            q["id"] = {"$in": authz.roles.get_role_scope(user)["venue_ids"]}
        if location_id:
            q["location_id"] = location_id if "location_id" not in q else q["location_id"]
        rows = await db.venues.find(q, {"_id": 0}).sort("created_at", 1).to_list(2000)
        return rows

    @api_router.post("/admin/venues")
    async def create_venue(data: VenueInput, user: dict = Depends(get_current_user)):
        loc = await db.locations.find_one({"id": data.location_id}, {"_id": 0})
        if not loc:
            raise HTTPException(status_code=404, detail="Location not found")
        authz.require_location_staff(user, data.location_id)
        venue = Venue(**data.model_dump()).to_mongo()
        try:
            await db.venues.insert_one(dict(venue))
        except DuplicateKeyError:
            raise HTTPException(status_code=400, detail="A venue with this name already exists in this location")
        venue.pop("_id", None)
        return venue

    # -------------------- EVENTS (scope-enforced) --------------------
    @api_router.get("/admin/events")
    async def list_events(user: dict = Depends(get_current_user)):
        authz.require_staff(user)
        rows = await db.events.find(authz.events_scope_query(user), {"_id": 0}).sort("event_date", -1).to_list(2000)
        return rows

    @api_router.post("/admin/events")
    async def create_event(data: EventInput, user: dict = Depends(get_current_user)):
        authz.require_staff(user)
        venue = await db.venues.find_one({"id": data.venue_id}, {"_id": 0})
        if not venue:
            raise HTTPException(status_code=404, detail="Venue not found")
        # Isolation: the creator must be in scope for this venue/location.
        probe = {"venue_id": venue["id"], "location_id": venue["location_id"]}
        authz.require_event_staff(user, probe)
        ev = Event(venue_id=venue["id"], location_id=venue["location_id"], name=data.name,
                   event_date=data.event_date, status=data.status,
                   starts_at=data.starts_at, ends_at=data.ends_at).to_mongo()
        try:
            await db.events.insert_one(dict(ev))
        except DuplicateKeyError:
            raise HTTPException(status_code=400, detail="An event with this name already exists at this venue")
        ev.pop("_id", None)
        return ev

    @api_router.get("/admin/events/{event_id}")
    async def get_event_admin(event_id: str, user: dict = Depends(get_current_user)):
        ev = await _get_event(event_id)
        authz.require_event_staff(user, ev)
        return ev

    @api_router.put("/admin/events/{event_id}/status")
    async def set_event_status(event_id: str, data: EventStatusInput, user: dict = Depends(get_current_user)):
        ev = await _get_event(event_id)
        authz.require_event_staff(user, ev)
        await db.events.update_one({"id": event_id}, {"$set": {"status": data.status, "updated_at": _iso()}})
        return {"message": "Event status updated", "event_id": event_id, "status": data.status}

    @api_router.put("/admin/locations/{location_id}")
    async def update_location(location_id: str, data: LocationInput, user: dict = Depends(get_current_user)):
        authz.require_global_admin(user)
        loc = await db.locations.find_one({"id": location_id}, {"_id": 0})
        if not loc:
            raise HTTPException(status_code=404, detail="Location not found")
        upd = {**data.model_dump(), "updated_at": _iso()}
        await db.locations.update_one({"id": location_id}, {"$set": upd})
        return {**loc, **upd}

    @api_router.put("/admin/venues/{venue_id}")
    async def update_venue(venue_id: str, data: VenueInput, user: dict = Depends(get_current_user)):
        venue = await db.venues.find_one({"id": venue_id}, {"_id": 0})
        if not venue:
            raise HTTPException(status_code=404, detail="Venue not found")
        authz.require_location_staff(user, venue["location_id"])
        upd = {"name": data.name, "address": data.address, "timezone": data.timezone, "updated_at": _iso()}
        await db.venues.update_one({"id": venue_id}, {"$set": upd})
        return {**venue, **upd}

    @api_router.put("/admin/events/{event_id}")
    async def update_event(event_id: str, data: EventInput, user: dict = Depends(get_current_user)):
        ev = await _get_event(event_id)
        authz.require_event_staff(user, ev)
        upd = {"name": data.name, "event_date": data.event_date, "status": data.status,
               "starts_at": data.starts_at, "ends_at": data.ends_at, "updated_at": _iso()}
        await db.events.update_one({"id": event_id}, {"$set": upd})
        return {**ev, **upd}

    # -------------------- EVENT QR (staff, scope-checked) --------------------
    @api_router.get("/admin/events/{event_id}/qr")
    async def get_event_qr(event_id: str, user: dict = Depends(get_current_user)):
        _flag()
        ev = await _get_event(event_id)
        authz.require_event_staff(user, ev)
        exp = (datetime.now(timezone.utc) + timedelta(hours=QR_TTL_HOURS))
        token = make_event_token(event_id, exp.isoformat())
        return {"event_id": event_id, "venue_id": ev["venue_id"], "location_id": ev.get("location_id"),
                "token": token, "checkin_path": f"/e/checkin/{token}", "expires_at": exp.isoformat()}

    # -------------------- EVENT CHECK-IN (Phase 2 route) --------------------
    @api_router.post("/e/checkin/{token}")
    async def event_checkin(token: str, user: dict = Depends(get_current_user)):
        _flag()
        event_id = parse_event_token(token)
        ev = await _get_event(event_id)
        if ev["status"] in ("ended", "cancelled", "archived"):
            raise HTTPException(status_code=400, detail=f"Event is not open for check-in (status: {ev['status']})")

        existing = await db.event_participation.find_one({"user_id": user["id"], "event_id": event_id}, {"_id": 0})
        if existing and existing.get("status") == "checked_in":
            return {"success": False, "already_checked_in": True, "event_id": event_id,
                    "list_position": existing.get("list_position"), "points_awarded": 0,
                    "message": "You're already checked in to this event."}

        now = _iso()
        if not existing:
            count = await db.event_participation.count_documents({"event_id": event_id})
            part = {
                "id": str(uuid.uuid4()), "user_id": user["id"], "event_id": event_id,
                "venue_id": ev["venue_id"], "location_id": ev.get("location_id"),
                "event_points": 0, "songs_performed": 0, "badges_earned": [],
                "list_position": count + 1, "status": "checked_in", "checked_in_at": now,
                "created_at": now, "updated_at": now,
            }
            await db.event_participation.insert_one(dict(part))
            list_position = part["list_position"]
        else:
            await db.event_participation.update_one(
                {"user_id": user["id"], "event_id": event_id},
                {"$set": {"status": "checked_in", "checked_in_at": now, "updated_at": now}})
            list_position = existing.get("list_position")

        # Audit trail + duplicate guard collection.
        try:
            await db.event_checkins.insert_one({
                "id": str(uuid.uuid4()), "user_id": user["id"], "event_id": event_id,
                "venue_id": ev["venue_id"], "location_id": ev.get("location_id"), "at": now})
        except Exception:
            pass
        await db.event_checkin_attempts.insert_one({
            "id": str(uuid.uuid4()), "user_id": user["id"], "event_id": event_id,
            "result": "checked_in", "at": now})

        # Event + season points (idempotent per event/user).
        res = await award_ledger_bound(user_id=user["id"], points=EVENT_CHECKIN_POINTS,
                                       source="event_checkin", dedupe_key=f"checkin:{event_id}:{user['id']}",
                                       event=ev)
        # Preserve legacy lifetime +10 exactly once (only while nightly is retired, to avoid double-count).
        if not LEGACY_NIGHTLY_ENABLED:
            await award_ledger_bound(user_id=user["id"], points=EVENT_CHECKIN_POINTS,
                                     source="lifetime_checkin",
                                     dedupe_key=f"lifetime_checkin:{event_id}:{user['id']}",
                                     event=ev, to_event=False, to_season=False, to_lifetime=True)

        await manager.broadcast_event(event_id, {"type": "EVENT_SINGER_CHECKED_IN", "event_id": event_id,
                                                 "user_id": user["id"], "display_name": user.get("display_name"),
                                                 "list_position": list_position})
        return {"success": True, "already_checked_in": False, "event_id": event_id,
                "venue_id": ev["venue_id"], "list_position": list_position,
                "points_awarded": EVENT_CHECKIN_POINTS, "season_points": res.get("season_points"),
                "message": f"Checked in to {ev['name']}! +{EVENT_CHECKIN_POINTS} points"}

    # -------------------- EVENT SINGER LIST --------------------
    @api_router.get("/events/{event_id}/singer-list")
    async def event_singer_list(event_id: str, limit: int = Query(500, ge=1, le=2000),
                                offset: int = Query(0, ge=0), user: dict = Depends(get_current_user)):
        _flag()
        ev = await _get_event(event_id)
        authz.require_event_view(user, ev)
        rows = await db.event_participation.find(
            {"event_id": event_id}, {"_id": 0}).sort("list_position", 1).skip(offset).limit(limit).to_list(limit)
        ids = list({r["user_id"] for r in rows})
        users = await db.users.find({"id": {"$in": ids}},
                                    {"_id": 0, "id": 1, "display_name": 1, "title_preference": 1}).to_list(100000)
        umap = {u["id"]: u for u in users}
        singers = [{"user_id": r["user_id"],
                    "display_name": umap.get(r["user_id"], {}).get("display_name", "Unknown"),
                    "list_position": r.get("list_position"), "status": r.get("status"),
                    "event_points": r.get("event_points", 0),
                    "songs_performed": r.get("songs_performed", 0)} for r in rows]
        return {"event_id": event_id, "count": len(singers), "singers": singers}

    # -------------------- Mount event + season routers --------------------
    # These routers already carry their own "/api" prefix, so mount on app (not api_router).
    app.include_router(phase2_events.build_router(
        db, manager, get_current_user, get_admin_user, EVENT_QR_ENABLED,
        get_user_rank_name, rank_perks, award_ledger=award_ledger_bound, song_points=EVENT_SONG_POINTS))
    app.include_router(phase2_seasons.build_router(
        db, manager, get_current_user, get_admin_user, EVENT_QR_ENABLED,
        get_rank, get_user_rank_name, SEASON_CFG))
    app.include_router(phase2_battles.build_router(
        db, manager, get_current_user, EVENT_QR_ENABLED, challenge_types or {},
        award_ledger=award_ledger_bound))

    # -------------------- Cron: annual season reset --------------------
    @api_router.post("/cron/season-reset")
    async def cron_season_reset(request: Request):
        # Shared-secret protected; runs the idempotent annual auto-reset.
        secret = request.headers.get("x-cron-secret") or request.query_params.get("secret")
        if WEBHOOK_CRON_SECRET and secret != WEBHOOK_CRON_SECRET:
            raise HTTPException(status_code=403, detail="Invalid cron secret")
        res = await phase2_seasons.run_auto_reset_if_due(db, SEASON_CFG)
        return {"ok": True, **res}

    # -------------------- WebSocket: per-event room + auth --------------------
    @app.websocket("/api/ws/events/{event_id}")
    async def ws_event(websocket: WebSocket, event_id: str):
        token = websocket.query_params.get("token")
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
            ev = await db.events.find_one({"id": event_id}, {"_id": 0})
            if not user or not ev:
                await websocket.close(code=4404)
                return
            authz.require_event_view(user, ev)  # raises if not authorized
        except HTTPException:
            await websocket.close(code=4403)
            return
        except Exception:
            await websocket.close(code=4401)
            return
        await manager.connect_event(event_id, websocket)
        try:
            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            manager.disconnect_event(event_id, websocket)

    # -------------------- Startup: season bootstrap --------------------
    @app.on_event("startup")
    async def _phase2_startup():
        try:
            await phase2_seasons.ensure_current_season(db, SEASON_CFG)
            await phase2_seasons.run_auto_reset_if_due(db, SEASON_CFG)
        except Exception as exc:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).warning("Phase2 season startup skipped: %s", exc)
