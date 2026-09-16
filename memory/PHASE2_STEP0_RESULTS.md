# Phase 2 — Step 0 Results (Baseline & Safety)

Status: **COMPLETE — awaiting approval to proceed to Step 1.**
Date: 2026-09 (America/Chicago)
Principle: additive & non-destructive. No legacy data altered or removed. No app behavior changed.

---

## 1. What was done

### a) Database indexes (idempotent)
Added via `/app/backend/step0_setup.py`. 26 indexes ensured (safe to re-run):
- **users**: `uniq_id` (unique), `uniq_email` (unique), `points_desc`, `nightly_points_desc`, `referred_by`
- **queue**: `status_position`, `user_id`, `created_at`
- **checkins**: `user_date` (user_id+date), `date`, `venue_code`
- **accomplishments**: `user_id`
- **perk_usage**: `user_date`
- **challenges**: `challenger_id`, `opponent_id`, `status`
- **votes**: `challenge_id`, `user_id`
- **settings**: `uniq_key` (unique)
- **locations** (new): `uniq_id`
- **venues** (new): `uniq_id`, `location_id`
- **events** (new): `uniq_id`, `venue_id`, `status`, `event_date`

### b) Isolated development sample data
Two full Location → Venue → Event chains (to demonstrate multi-location isolation). Every doc tagged `is_sample=true`, `env="development"` for clean rollback.

| Location | Venue | Event | Date |
|---|---|---|---|
| King Karaoke - Downtown (Chicago, IL) | The Royal Stage | Friday Karaoke Night | 2026-09-09 |
| King Karaoke - Riverside (St. Louis, MO) | Crown Lounge | Saturday Karaoke Night | 2026-09-10 |

These are NEW collections (`locations`, `venues`, `events`) — the existing app does not read them yet, so behavior is unchanged.

### c) Development admin account
- Email: `dev-admin@kingkaraoke2025.com`
- Password: set via `DEV_ADMIN_PASSWORD` env var in `backend/.env` (temporary, secure; NOT admin123; value not committed)
- `is_admin=true`, `is_dev_account=true`
- Stored in `/app/memory/test_credentials.md`.

---

## 2. Verification — existing application still works (unchanged)

Tests run against the live backend (`REACT_APP_BACKEND_URL/api`):

| # | Check | Result |
|---|---|---|
| 1 | `GET /api/` health | ✅ `King Klub API v1.0.0` |
| 2 | Register new user | ✅ token issued, rank=Peasant |
| 3 | Dev admin login | ✅ token, is_admin=true |
| 4 | `GET /api/leaderboard` | ✅ returns list |
| 5 | `GET /api/badges` | ✅ 28 badges |
| 6 | `GET /api/queue` | ✅ list |
| 7 | `GET /api/stats` | ✅ totals |
| 8 | Admin `GET /api/venue/qr-data` (generates daily QR) | ✅ venue_code + expiry (4 AM cutoff) |
| 9 | User `POST /api/checkin/{code}` | ✅ +10 pts |
| 10 | Add song after check-in | ✅ position 1, 4 remaining (5/30min limit intact) |
| 11 | Duplicate check-in | ✅ blocked (`already_checked_in`) |
| 12 | `GET /api/leaderboard/tonight` | ✅ active session logic intact |
| 13 | Frontend landing page | ✅ renders (royal theme) |

All temporary test artifacts (test user, its check-in/queue, the test night session) were removed afterward. Final DB state: 1 user (dev admin), 0 queue items, no active night session, sample hierarchy intact.

---

## 3. Assumptions documented

1. **Env/secrets**: Original prod `JWT_SECRET`/`VENUE_SECRET` were unavailable, so newly generated values are used. Consequence: any historical JWTs/QR hashes would differ — irrelevant here since the DB is fresh.
2. **Fresh dev DB**: `test_database` contains no legacy/production data. "Non-destructive" here means the *code path* and *legacy schema* are untouched; there is no prod data in this environment to migrate.
3. **Singer == User**: A "singer" is the existing `users` record. Phase 2 keeps this as the persistent global profile; per-event participation will be a separate additive record (Step 1).
4. **Event model shape (draft, finalized in Step 1)**: `event = venue_id + location_id + event_date + status`. Multiple events may be `status="active"` simultaneously.
5. **Legacy points untouched**: `users.points` (lifetime) and `users.nightly_points` (global nightly) remain and keep working. The event-scoped points system will run in parallel and only replace nightly after full verification (Step 6, with explicit approval).
6. **Sample data isolation**: all sample docs carry `is_sample=true`; nothing links them to legacy check-ins/queue yet.
7. **Indexes**: `users.email` and `users.id` made unique (app already enforced uniqueness; DB was empty so no conflict). If a future prod import contains duplicates, the unique index would reject them — flagged for the migration step.

---

## 4. Rollback / migration strategy

### Rollback of Step 0 (fully reversible)
- Sample data + dev admin: `python /app/backend/step0_setup.py --rollback-samples`
  - Deletes ONLY `is_sample=true` docs and `is_dev_account=true` users. Never touches legacy data.
- Indexes: additive and safe; can be dropped individually if ever needed (`db.<coll>.drop_index("<name>")`). No behavioral dependency exists yet.

### Migration/backfill strategy for legacy records (spec — NOT executed in Step 0)
When Step 3+ introduces scoping keys:
1. Create a real (non-sample) **Default Location → Default Venue → Default Event** representing "historical / pre-Phase-2 activity."
2. Backfill legacy `checkins`, `queue`, `perk_usage`, participation to that default `event_id`/`venue_id`/`location_id` using a **dated migration script** that is idempotent and logs every change.
3. Each migration ships with a paired down-migration (or a pre-migration snapshot) so it can be reversed.
4. Legacy fields (`nightly_points`, `settings.current_night`) are retained until the event-scoped replacement passes acceptance — only then retired, with approval.

---

## 5. Files added/changed in Step 0
- `backend/step0_setup.py` — NEW idempotent setup/rollback script.
- `backend/.env` — added `JWT_SECRET`, `VENUE_SECRET`, `VENUE_TIMEZONE` (required to boot; protected vars preserved).
- `memory/test_credentials.md` — dev admin credentials.
- `memory/PHASE2_STEP0_RESULTS.md` — this document.
- **No changes to `server.py` or any frontend file.**

---

## 6. Next (Step 1 — Data Model Foundation) — NOT STARTED
Awaiting your approval. Step 1 will additively define Location/Venue/Event/EventParticipation models + read-only admin APIs, keeping all legacy fields and behavior intact.
