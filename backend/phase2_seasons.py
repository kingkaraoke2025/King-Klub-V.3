"""
Phase 2, Step 5 — Event-scoped points, annual Season system, and leaderboards.
Additive & isolated (own router; async motor db injected by server.py). Does NOT touch
legacy users.points / nightly_points / current_night / legacy leaderboards.

Key rules (documented):
  - EVENT points live on event_participation.event_points (per singer, per event). Never shared across events.
  - SEASON points = sum of a singer's event-point awards within that season, held on
    season_participation.points (per singer, per season). Aggregation across a singer's OWN events
    in the season is intentional; different events never mix each other's totals or rankings.
  - LIFETIME/global points remain on users.points (legacy system, unchanged).
  - Awards flow ONLY through award_event_points() -> increments event_points AND season points once
    (no double counting). Event 'complete' still awards nothing (approved).
  - A new season resets season progression (points/rank/badges/accomplishments/streak) by starting
    fresh season_participation rows; historical season_participation + seasons are ARCHIVED, never deleted.
    The user account/profile is never deleted.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

import authz


def _now():
    return datetime.now(timezone.utc)


def _iso():
    return _now().isoformat()


def _current_year(cfg):
    return datetime.now(ZoneInfo(cfg["timezone"])).year


def _now_local(cfg):
    return datetime.now(ZoneInfo(cfg["timezone"]))


def is_reset_due(now_local, current_season_year, cfg):
    """A reset is due once we are at/after (reset_month, reset_day) of a calendar year
    that is newer than the current season's year."""
    boundary = datetime(now_local.year, cfg["reset_month"], cfg["reset_day"], tzinfo=now_local.tzinfo)
    return now_local >= boundary and current_season_year < now_local.year


async def ensure_current_season(db, cfg, created_by="system"):
    cur = await db.seasons.find_one({"is_current": True}, {"_id": 0})
    if cur:
        return cur
    year = _current_year(cfg)
    existing = await db.seasons.find_one({"year": year}, {"_id": 0})
    if existing:
        await db.seasons.update_one({"id": existing["id"]}, {"$set": {"is_current": True, "status": "active"}})
        return {**existing, "is_current": True, "status": "active"}
    season = {
        "id": str(uuid.uuid4()), "year": year, "name": f"{year} Season", "status": "active",
        "is_current": True, "starts_at": _iso(), "ends_at": None, "auto": False,
        "created_at": _iso(), "created_by": created_by, "closed_at": None, "closed_by": None,
        "champion_user_id": None,
    }
    try:
        await db.seasons.insert_one(dict(season))
    except DuplicateKeyError:
        season = await db.seasons.find_one({"year": year}, {"_id": 0})
    return season


async def _ensure_season_participation(db, get_rank, user, season):
    sp = await db.season_participation.find_one({"user_id": user["id"], "season_id": season["id"]}, {"_id": 0})
    if sp:
        return sp
    doc = {
        "id": str(uuid.uuid4()), "user_id": user["id"], "season_id": season["id"], "season_year": season["year"],
        "points": 0, "rank_name": get_rank(0)["name"], "badges": [], "accomplishments": [],
        "streak": 0, "placement": None, "is_champion": False,
        "created_at": _iso(), "updated_at": _iso(),
    }
    try:
        await db.season_participation.insert_one(dict(doc))
    except DuplicateKeyError:
        doc = await db.season_participation.find_one({"user_id": user["id"], "season_id": season["id"]}, {"_id": 0})
    return doc


async def perform_reset(db, cfg, initiated_by, mode):
    cur = await ensure_current_season(db, cfg, created_by=initiated_by)
    # duplicate-reset protection: if the current season is itself the product of a reset and has had
    # no activity yet, block a second reset for the same boundary.
    was_reset_product = await db.season_resets.find_one({"to_season_id": cur["id"]}, {"_id": 0})
    if was_reset_product:
        activity = await db.season_participation.count_documents({"season_id": cur["id"]})
        if activity == 0:
            raise HTTPException(status_code=400,
                                detail="Season was just reset and has no activity yet — duplicate reset blocked")
    next_year = cur["year"] + 1
    existing_next = await db.seasons.find_one({"year": next_year}, {"_id": 0})
    if existing_next and existing_next.get("is_current"):
        raise HTTPException(status_code=400, detail=f"Season {next_year} already active — reset already performed")

    # rank + champion for the season being closed
    parts = await db.season_participation.find({"season_id": cur["id"]}, {"_id": 0}).sort("points", -1).to_list(100000)
    champion_id = None
    for i, p in enumerate(parts):
        is_champ = (i == 0 and p.get("points", 0) > 0)
        if is_champ:
            champion_id = p["user_id"]
        await db.season_participation.update_one(
            {"id": p["id"]}, {"$set": {"placement": i + 1, "is_champion": is_champ, "updated_at": _iso()}})

    await db.seasons.update_one({"id": cur["id"]}, {"$set": {
        "is_current": False, "status": "archived", "closed_at": _iso(), "closed_by": initiated_by,
        "ends_at": _iso(), "champion_user_id": champion_id}})

    new = {
        "id": str(uuid.uuid4()), "year": next_year, "name": f"{next_year} Season", "status": "active",
        "is_current": True, "starts_at": _iso(), "ends_at": None, "auto": (mode == "auto"),
        "created_at": _iso(), "created_by": initiated_by, "closed_at": None, "closed_by": None,
        "champion_user_id": None,
    }
    try:
        await db.seasons.insert_one(dict(new))
    except DuplicateKeyError:
        await db.seasons.update_one({"year": next_year}, {"$set": {"is_current": True, "status": "active"}})
        new = await db.seasons.find_one({"year": next_year}, {"_id": 0})

    await db.season_resets.insert_one({
        "id": str(uuid.uuid4()), "from_season_id": cur["id"], "from_year": cur["year"],
        "to_season_id": new["id"], "to_year": next_year, "mode": mode,
        "initiated_by": initiated_by, "at": _iso()})
    return {"closed_season": cur["year"], "new_season": next_year, "champion_user_id": champion_id,
            "new_season_id": new["id"]}


async def run_auto_reset_if_due(db, cfg):
    if not cfg["auto_enabled"]:
        return {"ran": False, "reason": "auto reset disabled"}
    ran = []
    cur = await ensure_current_season(db, cfg)
    now_local = _now_local(cfg)
    # catch up across any missed boundaries, guarded by unique season.year
    guard = 0
    while is_reset_due(now_local, cur["year"], cfg) and guard < 10:
        res = await perform_reset(db, cfg, "auto-scheduler", "auto")
        ran.append(res["new_season"])
        cur = await db.seasons.find_one({"is_current": True}, {"_id": 0})
        guard += 1
    return {"ran": bool(ran), "new_seasons": ran} if ran else {"ran": False, "reason": "not due"}


async def find_ledger_orphans(db, limit=100):
    """Detect (report-only) point_ledger rows whose event_id references an event that no
    longer exists. event_id=None rows (lifetime/season-only awards) are legitimate and
    excluded. Read-only: never mutates or deletes ledger records."""
    rows = await db.point_ledger.find(
        {"event_id": {"$ne": None}},
        {"_id": 0, "id": 1, "event_id": 1, "dedupe_key": 1, "source": 1, "user_id": 1},
    ).to_list(1000000)
    event_ids = list({r["event_id"] for r in rows})
    existing = set()
    if event_ids:
        cursor = db.events.find({"id": {"$in": event_ids}}, {"_id": 0, "id": 1})
        async for e in cursor:
            existing.add(e["id"])
    orphans = [r for r in rows if r["event_id"] not in existing]
    return {"scanned": len(rows), "orphan_count": len(orphans), "sample": orphans[:limit]}


class AwardPointsBody(BaseModel):
    user_id: str
    points: int = Field(gt=0, le=100000)
    action_id: Optional[str] = Field(default=None, max_length=64)
    notes: Optional[str] = Field(default=None, max_length=500)
    dedupe_key: Optional[str] = Field(default=None, max_length=128)


async def award_ledger(db, get_rank, cfg, *, user_id, points, source, dedupe_key,
                       event=None, to_event=True, to_season=True, to_lifetime=False):
    """Idempotent point award. A given dedupe_key is applied AT MOST ONCE (unique index on
    point_ledger.dedupe_key), so retries / duplicate API calls / WebSocket re-fires cannot
    double-count. Updates event_points / season points / lifetime users.points independently,
    each via its own dedupe_key so ledgers never overlap."""
    try:
        await db.point_ledger.insert_one({
            "id": str(uuid.uuid4()), "dedupe_key": dedupe_key, "user_id": user_id,
            "event_id": event["id"] if event else None, "source": source, "points": points, "at": _iso()})
    except DuplicateKeyError:
        return {"awarded": False, "already": True}
    season = await ensure_current_season(db, cfg)
    if to_event and event:
        ep_set = {"updated_at": _iso()}
        part = await db.event_participation.find_one({"user_id": user_id, "event_id": event["id"]}, {"_id": 0})
        if part is not None and not part.get("season_id"):
            ep_set["season_id"] = season["id"]
        await db.event_participation.update_one(
            {"user_id": user_id, "event_id": event["id"]},
            {"$inc": {"event_points": points}, "$set": ep_set})
    season_points = None
    if to_season:
        target = await db.users.find_one({"id": user_id}, {"_id": 0})
        sp = await _ensure_season_participation(db, get_rank, target, season)
        season_points = sp["points"] + points
        await db.season_participation.update_one(
            {"id": sp["id"]},
            {"$inc": {"points": points}, "$set": {"rank_name": get_rank(season_points)["name"], "updated_at": _iso()}})
    if to_lifetime:
        await db.users.update_one({"id": user_id}, {"$inc": {"points": points}})
    return {"awarded": True, "already": False, "points": points, "season_id": season["id"],
            "season_points": season_points}


class ResetBody(BaseModel):
    confirm: bool = False


def build_router(db, manager, get_current_user, get_admin_user, event_qr_enabled, get_rank, get_user_rank_name, cfg, award_badges=None):
    router = APIRouter(prefix="/api")

    def _flag():
        if not event_qr_enabled:
            raise HTTPException(status_code=403, detail="Event QR system is disabled")

    async def _join_names(rows, key="user_id"):
        ids = list({r[key] for r in rows})
        users = await db.users.find({"id": {"$in": ids}},
                                    {"_id": 0, "id": 1, "display_name": 1, "title_preference": 1}).to_list(100000)
        return {u["id"]: u for u in users}

    # -------------------- EVENT POINTS --------------------
    @router.post("/events/{event_id}/award-points")
    async def award_event_points(event_id: str, body: AwardPointsBody, user: dict = Depends(get_current_user)):
        """Award EVENT points to a checked-in singer. Increments event_points AND season points once."""
        _flag()
        ev = await db.events.find_one({"id": event_id}, {"_id": 0})
        if not ev:
            raise HTTPException(status_code=404, detail="Event not found")
        authz.require_event_staff(user, ev)
        part = await db.event_participation.find_one({"user_id": body.user_id, "event_id": event_id}, {"_id": 0})
        if not part:
            raise HTTPException(status_code=400, detail="Singer is not checked into this event")
        target = await db.users.find_one({"id": body.user_id}, {"_id": 0})
        if not target:
            raise HTTPException(status_code=404, detail="User not found")

        season = await ensure_current_season(db, cfg)
        sp = await _ensure_season_participation(db, get_rank, target, season)

        dedupe = body.dedupe_key or f"manual:{event_id}:{body.user_id}:{uuid.uuid4().hex}"
        res = await award_ledger(db, get_rank, cfg, user_id=body.user_id, points=body.points,
                                 source="manual_award", dedupe_key=dedupe, event=ev)
        if res.get("already"):
            raise HTTPException(status_code=409, detail="This award was already applied (duplicate dedupe_key)")

        if body.action_id:
            await db.season_accomplishments.insert_one({
                "id": str(uuid.uuid4()), "user_id": body.user_id, "season_id": season["id"],
                "season_year": season["year"], "event_id": event_id, "action_id": body.action_id,
                "notes": body.notes, "points": body.points, "awarded_by": user["id"], "earned_at": _iso()})
            await db.season_participation.update_one(
                {"id": sp["id"]}, {"$push": {"accomplishments": body.action_id}})

        # Evaluate/unlock badges using the EXISTING badge system (event + season scoped).
        badge_result = {"badges_earned": [], "badge_names": [], "bonus_points": 0}
        if award_badges is not None and body.action_id:
            badge_result = await award_badges(body.user_id, body.action_id, ev)

        part2 = await db.event_participation.find_one({"user_id": body.user_id, "event_id": event_id}, {"_id": 0})
        await manager.broadcast_event(event_id, {"type": "EVENT_POINTS_AWARDED", "event_id": event_id,
                                                  "user_id": body.user_id,
                                                  "event_points": part2.get("event_points", 0)})
        # Recompute season points to include any badge bonus.
        sp_final = await db.season_participation.find_one({"id": sp["id"]}, {"_id": 0})
        season_points_final = sp_final.get("points") if sp_final else res.get("season_points")
        return {"event_id": event_id, "user_id": body.user_id, "awarded": body.points,
                "event_points": part2.get("event_points", 0), "season_id": season["id"],
                "season_points": season_points_final, "season_rank": get_rank(season_points_final or 0)["name"],
                "badges_earned": badge_result["badges_earned"], "badge_names": badge_result["badge_names"],
                "bonus_points": badge_result["bonus_points"]}

    # -------------------- LEADERBOARDS --------------------
    @router.get("/events/{event_id}/leaderboard")
    async def event_leaderboard(event_id: str, limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0),
                                user: dict = Depends(get_current_user)):
        _flag()
        ev = await db.events.find_one({"id": event_id}, {"_id": 0})
        if not ev:
            raise HTTPException(status_code=404, detail="Event not found")
        authz.require_event_view(user, ev)
        rows = await db.event_participation.find(
            {"event_id": event_id}, {"_id": 0}).sort("event_points", -1).skip(offset).limit(limit).to_list(limit)
        umap = await _join_names(rows)
        board = [{"position": offset + i + 1, "user_id": r["user_id"],
                  "display_name": umap.get(r["user_id"], {}).get("display_name", "Unknown"),
                  "event_points": r.get("event_points", 0), "list_position": r.get("list_position")}
                 for i, r in enumerate(rows)]
        return {"event_id": event_id, "count": len(board), "limit": limit, "offset": offset, "leaderboard": board}

    @router.get("/seasons/current/leaderboard")
    async def current_season_leaderboard(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0),
                                         user: dict = Depends(get_current_user)):
        _flag()
        season = await ensure_current_season(db, cfg)
        return await _season_board(season, limit, offset)

    @router.get("/seasons/{season_id}/leaderboard")
    async def historical_season_leaderboard(season_id: str, limit: int = Query(50, ge=1, le=500),
                                            offset: int = Query(0, ge=0), user: dict = Depends(get_current_user)):
        _flag()
        season = await db.seasons.find_one({"id": season_id}, {"_id": 0})
        if not season:
            raise HTTPException(status_code=404, detail="Season not found")
        return await _season_board(season, limit, offset)

    async def _season_board(season, limit, offset):
        rows = await db.season_participation.find(
            {"season_id": season["id"]}, {"_id": 0}).sort("points", -1).skip(offset).limit(limit).to_list(limit)
        umap = await _join_names(rows)
        board = [{"position": offset + i + 1, "user_id": r["user_id"],
                  "display_name": umap.get(r["user_id"], {}).get("display_name", "Unknown"),
                  "season_points": r.get("points", 0), "rank": r.get("rank_name"),
                  "placement": r.get("placement"), "is_champion": r.get("is_champion", False)}
                 for i, r in enumerate(rows)]
        return {"season_id": season["id"], "season_year": season["year"], "status": season["status"],
                "is_current": season.get("is_current", False), "count": len(board),
                "limit": limit, "offset": offset, "leaderboard": board}

    # -------------------- SEASONS --------------------
    @router.get("/seasons/current")
    async def get_current_season(user: dict = Depends(get_current_user)):
        _flag()
        season = await ensure_current_season(db, cfg)
        sp = await db.season_participation.find_one(
            {"user_id": user["id"], "season_id": season["id"]}, {"_id": 0})
        return {"season": season, "my_participation": sp}

    @router.get("/seasons")
    async def list_seasons(user: dict = Depends(get_current_user),
                           limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
        _flag()
        authz.require_global_admin(user)
        rows = await db.seasons.find({}, {"_id": 0}).sort("year", -1).skip(offset).limit(limit).to_list(limit)
        return {"count": len(rows), "limit": limit, "offset": offset, "seasons": rows}

    @router.post("/admin/seasons/reset")
    async def manual_reset(body: ResetBody, user: dict = Depends(get_current_user)):
        _flag()
        authz.require_global_admin(user)
        if not body.confirm:
            raise HTTPException(status_code=400, detail="Reset requires explicit confirmation (confirm=true)")
        res = await perform_reset(db, cfg, initiated_by=user["id"], mode="manual")
        return {"message": f"Season {res['closed_season']} closed; {res['new_season']} started", **res}

    @router.post("/admin/seasons/run-auto-reset")
    async def trigger_auto_reset(user: dict = Depends(get_current_user)):
        _flag()
        authz.require_global_admin(user)
        return await run_auto_reset_if_due(db, cfg)

    return router
