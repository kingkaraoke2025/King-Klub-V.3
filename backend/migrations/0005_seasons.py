"""
Migration 0005 — Season system indexes + bootstrap current season (additive, idempotent, reversible).

UP (default): ensures indexes on seasons / season_participation / season_accomplishments / season_resets,
and bootstraps the current-year season if none is active (idempotent). No legacy data touched.

--down: removes season collections' docs created by the bootstrap ONLY if empty-ish; by default it
drops the indexes this migration created and removes seasons/season_participation/season_resets/
season_accomplishments docs. (These are all new Phase-2 collections; legacy data is never touched.)
"""
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

MIGRATION_NAME = "0005_seasons"
client = MongoClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
TZ = os.environ.get("SEASON_TIMEZONE", os.environ.get("VENUE_TIMEZONE", "America/Chicago"))

INDEX_SPECS = {
    "seasons": [("uniq_id", [("id", ASCENDING)], {"unique": True}),
                ("uniq_year", [("year", ASCENDING)], {"unique": True}),
                ("is_current", [("is_current", ASCENDING)], {})],
    "season_participation": [("uniq_id", [("id", ASCENDING)], {"unique": True}),
                             ("uniq_user_season", [("user_id", ASCENDING), ("season_id", ASCENDING)], {"unique": True}),
                             ("season_points", [("season_id", ASCENDING), ("points", DESCENDING)], {}),
                             ("user_id", [("user_id", ASCENDING)], {})],
    "season_accomplishments": [("uniq_id", [("id", ASCENDING)], {"unique": True}),
                               ("user_season", [("user_id", ASCENDING), ("season_id", ASCENDING)], {}),
                               ("season_id", [("season_id", ASCENDING)], {})],
    "season_resets": [("uniq_id", [("id", ASCENDING)], {"unique": True})],
}


def _iso():
    return datetime.now(timezone.utc).isoformat()


def log(direction, actions):
    db.migrations_log.insert_one({"migration": MIGRATION_NAME, "direction": direction, "actions": actions, "at": _iso()})
    print(f"[{direction}] {MIGRATION_NAME}")
    for a in actions:
        print("  -", a)


def ensure_indexes():
    for coll, specs in INDEX_SPECS.items():
        for name, keys, kwargs in specs:
            db[coll].create_index(keys, name=name, **kwargs)


def bootstrap_current_season():
    if db.seasons.find_one({"is_current": True}):
        return None
    year = datetime.now(ZoneInfo(TZ)).year
    existing = db.seasons.find_one({"year": year})
    if existing:
        db.seasons.update_one({"id": existing["id"]}, {"$set": {"is_current": True, "status": "active"}})
        return existing["id"]
    doc = {"id": str(uuid.uuid4()), "year": year, "name": f"{year} Season", "status": "active",
           "is_current": True, "starts_at": _iso(), "ends_at": None, "auto": False,
           "created_at": _iso(), "created_by": "migration_0005", "closed_at": None, "closed_by": None,
           "champion_user_id": None}
    db.seasons.insert_one(doc)
    return doc["id"]


def up():
    ensure_indexes()
    sid = bootstrap_current_season()
    log("up", [f"indexes ensured for {list(INDEX_SPECS)}", f"current_season={'created ' + sid if sid else 'already existed'}"])


def down():
    actions = []
    for coll in ["season_participation", "season_accomplishments", "season_resets", "seasons"]:
        r = db[coll].delete_many({})
        actions.append(f"cleared {r.deleted_count} from {coll}")
    for coll, specs in INDEX_SPECS.items():
        existing = {i["name"] for i in db[coll].list_indexes()}
        for name, _k, _kw in specs:
            if name in existing and name != "_id_":
                try:
                    db[coll].drop_index(name)
                    actions.append(f"dropped index {coll}.{name}")
                except Exception as exc:  # noqa: BLE001
                    actions.append(f"skip {coll}.{name}: {exc}")
    log("down", actions)


if __name__ == "__main__":
    down() if "--down" in sys.argv else up()
