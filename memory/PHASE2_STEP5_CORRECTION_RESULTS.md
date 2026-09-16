# Phase 2 — Step 5 CORRECTION Results (Season-Point Sources from Normal Activities)

Status: **COMPLETE — awaiting approval to proceed to Step 6.**
Independent verification: testing_agent **69/69 passed, no issues** (`/app/test_reports/iteration_9.json`).
Additive & idempotent. Lifetime `users.points` behavior unchanged. No legacy system retired.

---

## 1. POINT SOURCE MATRIX
Legacy values were inspected in `server.py` (CHECKIN_POINTS=10, legacy song complete=+10, POINT_ACTIONS, BADGES.points_reward, CHALLENGE_TYPES points_winner/participant, referral badge bonuses) and preserved — nothing guessed.

| Action | Lifetime Points (users.points) | Event Points (event_participation) | Season Points (season_participation) | Frequency / Limit | Idempotency Protection |
|---|---|---|---|---|---|
| **Event check-in** (`POST /api/events/checkin`) | unchanged (legacy `/checkin/{code}` still +10 & nightly; event path does NOT touch lifetime) | **+10** | **+10** | once per (singer, event) | unique `event_checkins (user,event)` + ledger `checkin:{event}:{user}` |
| **Performed song complete** (`POST /api/events/{id}/queue/{item}/complete`) | unchanged (legacy `/admin/queue/{id}/complete` still +10 to lifetime) | **+10** | **+10** | once per queue item | item status guard + ledger `song:{item_id}` |
| **Manual accomplishment / action award** (`POST /api/events/{id}/award-points`, uses POINT_ACTIONS values e.g. sing_song 10, bar_song 100, tiktok_post 200, blindfolded 250) | unchanged | **+points** | **+points** | admin discretion; once per `dedupe_key` when provided | ledger on caller `dedupe_key` (409 on duplicate) |
| Legacy check-in `/checkin/{code}` | +10 (+nightly) | — | — | once/day (legacy) | legacy per (user,date) |
| Legacy song complete `/admin/queue/{id}/complete` | +10 (+ badge rewards) | — | — | per completion | legacy (unchanged) |
| Badge earned (legacy milestones, points_reward 10–250) | +points_reward (existing) | — | **not auto-fed** (see decision #2) | on unlock | legacy badge-set check (unchanged) |
| Battle/challenge result (winner 50–100 / participant 25–50) | +points (existing) | — | **not auto-fed** (decision #2) | per resolved challenge | legacy (unchanged) |
| Referral (badge bonuses 10/30/50) | +points (existing) | — | **not auto-fed** (decision #2) | per referral threshold | legacy badge check (unchanged) |
| Admin adjust-points `/admin/users/{id}/points` | +points (existing) | — | — | admin | n/a |

**Selected season/event sources implemented now:** event check-in, performed-song completion, and manual event award (accomplishments/actions). These are the venue/event-bound karaoke actions. Battles/referral/legacy-badge remain lifetime-only pending decision #2 (they are not event-bound; mapping them to season is a one-line hook per source once you confirm the amounts).

**No double-counting:** legacy lifetime ledger and the new event/season ledger are distinct code paths and collections. The event/season path is guarded by a single unique `point_ledger.dedupe_key` so retries / duplicate API calls / WebSocket re-fires apply exactly once.

## 2. Idempotency strategy
- New collection **`point_ledger`** `{id, dedupe_key(unique), user_id, event_id, source, points, at}` (migration `0006_point_ledger.py`).
- Central helper `award_ledger(...)`: inserts the ledger row first; on `DuplicateKeyError` it returns `{already:True}` and applies nothing. Only on a fresh insert does it `$inc` event_points and/or season points and recompute rank.
- Dedupe keys: `checkin:{event_id}:{user_id}` (one per singer+event), `song:{item_id}` (one per queue item), and caller-supplied `dedupe_key` for manual awards (duplicate → HTTP 409).

## 3. Event / season / lifetime behavior
- **Event points**: per `event_participation.event_points`, isolated per event (A never mixes with B) — verified 10/10 across two venues.
- **Season points**: `season_participation.points` = sum of the singer's own event awards in the season (documented aggregation) — verified 20 for two check-ins.
- **Lifetime points**: `users.points` provably **unchanged** by event/season awards (asserted).
- **Rank**: current-season rank recomputed from season points on every award; new season still starts Peasant/0; historical seasons preserved.

## 4. Schema / API changes
- NEW `point_ledger` collection + unique `dedupe_key` index (migration 0006).
- `POST /api/events/checkin` now returns `points_awarded` and awards event+season.
- `POST /api/events/{id}/queue/{item}/complete` now awards event+season (+`songs_performed`), idempotent; returns `points_awarded`.
- `POST /api/events/{id}/award-points` accepts optional `dedupe_key` (409 on duplicate); routed through `award_ledger`.
- NEW `POST /api/cron/season-reset` (Bearer `WEBHOOK_CRON_SECRET`, constant-time compare) → runs `run_auto_reset_if_due` idempotently.

## 5. Auto-reset production trigger (approved decision #1)
- `.emergent/crons.yml`: daily `season-reset-check` at `0 3 * * *` `America/Chicago` → `POST {{BASE_URL}}/api/cron/season-reset`.
- Endpoint requires `WEBHOOK_CRON_SECRET`; runs the idempotent boundary check (only acts on/after Jan 2 of a newer year; unique `seasons.year` prevents double). Safe if the cron fires multiple times. Startup check retained as secondary safety.
- `SEASON_AUTO_RESET_ENABLED=true`. Verified: 401 without/with wrong token; 200 + idempotent with correct token.

## 6. Tests & results
- Local: `test_phase5b.py` (6) + `test_phase5.py` (12) + prior phases (47) = **65** (+ testing_agent's `test_phase5b_cron.py` 4) = **69/69**.
- testing_agent **69/69, no issues** (`iteration_9.json`): check-in/song event+season+lifetime-untouched, idempotent check-in & song (single ledger row), multi-event isolation with season aggregation, manual dedupe 409, rank from season points, cron 401/200 idempotent, full legacy regression.

## 7. Legacy regression
login, register, legacy QR + check-in (still lifetime+nightly), legacy queue, all-time & nightly leaderboards, badges (28), battles, admin, event QR/singer-list/queue/perks, season leaderboards — all pass. No frontend changes.

## 8. Remaining decisions requiring approval
1. **Battles / referral / legacy-badge → season points?** Currently lifetime-only (not event-bound). Confirm they stay lifetime-only, OR give the season amounts and whether they count as season-only (no event). One-line hook per source via `award_ledger(..., event=None, to_event=False)`.
2. **Legacy check-in vs event check-in coexistence:** both exist; legacy feeds lifetime+nightly, event feeds event+season. When Step 6 retires nightly, confirm legacy check-in's lifetime award stays.
3. Non-applied (documented, defer to Step 7/cleanup): cron rate-limiting/IP allowlist, ledger orphan janitor, FastAPI lifespan migration, Mongo transactions (needs replica set), further `server.py` split.

## 9. Files changed
- `backend/phase2_seasons.py` (award_ledger + refactor award_event_points, dedupe_key) · `backend/phase2_events.py` (complete awards via injected ledger) · `backend/server.py` (event_checkin awards, cron endpoint, Request import, EVENT_CHECKIN/SONG_POINTS, event_router award_ledger injection) · `backend/migrations/0006_point_ledger.py` (new) · `backend/test_phase5b.py` (new, 6) · `backend/test_phase5b_cron.py` (testing_agent, 4) · `backend/.env` (+WEBHOOK_CRON_SECRET, SEASON_AUTO_RESET_ENABLED=true) · `.emergent/crons.yml` (new) · `backend/test_phase5.py` (expectations updated for check-in points). **No frontend changes.**

## 10. Next (Step 6 — Retire Legacy Nightly) — NOT STARTED
Approval-gated.
