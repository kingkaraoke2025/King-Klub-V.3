# Phase 2 — Step 5 Results (Event-Scoped Points & Leaderboards + Season System)

Status: **COMPLETE — awaiting approval to proceed to Step 6.**
Independent verification: testing_agent **59/59 passed, no issues** (`/app/test_reports/iteration_8.json`).
Additive & isolated. Legacy `points`/`nightly_points`/`current_night`/legacy leaderboards/queue/QR untouched. Event completion still awards NO points (approved).

---

## 1. New schema (additive collections)
- **`seasons`** — `id, year(unique), name, status(active/archived), is_current, starts_at, ends_at, auto, created_at, created_by, closed_at, closed_by, champion_user_id`.
- **`season_participation`** — `id, user_id, season_id(unique with user), season_year, points, rank_name, badges[], accomplishments[], streak, placement, is_champion, created_at, updated_at`. This is the per-season progression record.
- **`season_accomplishments`** — season-scoped accomplishment log (`user_id, season_id, season_year, event_id, action_id, notes, points, earned_at`).
- **`season_resets`** — audit (`from_season_id/from_year, to_season_id/to_year, mode(auto/manual), initiated_by, at`).
- **`event_participation`** now uses **`event_points`** (per event) and denormalized `season_id`.

## 2. Season architecture
- King Klub runs **annual seasons** (`2026 Season`, `2027 Season`, …). One `is_current` season at a time (enforced by unique `year` + lifecycle).
- **Reset = new season with historical preservation**, never destructive deletion. Closing a season archives it (status=archived, is_current=false, champion + placements computed) and opens the next year. The **user account/profile is never deleted or recreated**; only a fresh `season_participation` is created for the new season.
- New-season progression starts fresh: **points=0, rank=Peasant, badges=[], accomplishments=[], streak=0, empty annual leaderboard**. Prior season's participation rows (points/rank/badges/accomplishments/placement/champion) remain intact and queryable.

## 3. Point-source mapping (inventory + no double-count)
| Source | Awards to | Notes |
|---|---|---|
| Legacy check-in (`/checkin/{code}`) | lifetime `users.points` (+ `nightly_points`) | unchanged |
| Legacy song complete (`/admin/queue/{id}/complete`) | lifetime `users.points` | unchanged |
| Legacy `/admin/award-points`, battles, referrals, badge unlocks | lifetime `users.points` (+ nightly when active) | unchanged |
| Legacy accomplishments/badges | lifetime `users.badges` | unchanged (global) |
| **NEW `POST /api/events/{id}/award-points`** | **event_points (per event) + season points (per season)** | the ONLY event/season award path |
| **Event song complete** (`/events/{id}/queue/{item}/complete`) | **nothing** (approved) | increments `event_participation.songs_performed` only |

**No double-counting**: legacy sources write lifetime/global; the new event award writes event+season. They are distinct mechanisms/collections. Lifetime `users.points` is provably untouched by event awards (test `test_lifetime_points_untouched_by_event_awards`).

## 4. Season-points aggregation rule (documented)
`season_participation.points` = **sum of that singer's OWN event-point awards within the season**. Each award increments both the event's `event_points` and the singer's season total, once. Different events keep independent `event_points` and rankings; a singer's season total intentionally aggregates their own events — never other singers'/events' data.

## 5. Rank implementation
Starting rank each season = **Peasant** (0 pts). Current-season rank derived from `season_participation.points` using the existing 6-tier RANKS table (unchanged). Historical season ranks preserved on archived participation. Recomputed on every award.

## 6. Badge / accomplishment implementation (season-based, additive)
Season-scoped accomplishments recorded in `season_accomplishments` (+ pushed to `season_participation.accomplishments`) tagged with `season_id`/`season_year`. Same badge/accomplishment can be re-earned in a future season. Historical records stay associated with their season and are preserved across reset. The legacy global `users.badges`/`accomplishments` collections are left intact (unchanged) — the season system is additive alongside them.

## 7. Automatic reset
- Config: `SEASON_AUTO_RESET_ENABLED` (default off), `SEASON_RESET_MONTH=1`, `SEASON_RESET_DAY=2`, `SEASON_TIMEZONE` (default venue tz).
- `is_reset_due(now_local, current_season_year)` → true only on/after Jan 2 of a calendar year newer than the current season's year (verified). `run_auto_reset_if_due` catches up across missed boundaries, guarded by the unique `seasons.year` index (cannot create two seasons for one year).
- Runs on app **startup** (if enabled) and via admin `POST /api/admin/seasons/run-auto-reset`. Toggleable ON/OFF. **Production trigger recommendation:** a daily platform cron calling the run-auto-reset endpoint (documented decision below).

## 8. Manual reset
- `POST /api/admin/seasons/reset` — admin-only (403 for non-admin), requires `{confirm:true}` (400 otherwise). Archives current (records champion = top season_participation by points, sets placements), opens next season, writes a `season_resets` audit (who/when/from/to). **Duplicate-reset protection:** re-resetting a freshly-created season that has no activity yet is blocked (400); the unique `seasons.year` index is the backstop.

## 9. Leaderboards
- `GET /api/events/{id}/leaderboard` — event-scoped (by `event_points`).
- `GET /api/seasons/current/leaderboard` and `GET /api/seasons/{season_id}/leaderboard` — current & historical season (by season points), with placement/champion.
- All paginated (`limit`/`offset`). **Event A never includes Event B points**; season/event rankings independent. Legacy `/api/leaderboard` and `/api/leaderboard/tonight` remain live (not retired — Step 6).

## 10. Migration
`migrations/0005_seasons.py` — ensures indexes + bootstraps the current-year season (idempotent, reversible `--down`). No legacy backfill executed. Prior migrations (0003 checkins, 0004 queue) remain dry-run-by-default for legacy backfill.

## 11. Folded hardening (from Step 4 review + Step 5 review)
- **Field limits**: queue `message_to_admin`/`song_title`/`artist` (`Field(max_length)`) → 422 instead of silent truncation; award `notes` ≤500; **`award-points.points` bounded `>0, ≤100000`**.
- **Symmetric perk-protection** guard on queue move (both directions).
- **use-perk records usage before shifting** positions (unique index guard) — no reorder-without-consume window.
- **Pagination** on event queue, singer-list, and all new leaderboards.
- **Atomic protection note:** the environment's MongoDB is standalone (no multi-doc transactions); position/points writes use atomic `$inc`/`$set`, and queue positions self-heal via `_recalc_positions`. Transactions are deferred (would require a replica set) — documented, not applied.
- **season_id stamping** on event_participation only when absent (no retro-restamp of historical events).

## 12. Tests & results
Local: **test_phase5.py 12/12** (run `-n 0`) + prior phases **47/47**. testing_agent: **59/59, no issues** (`iteration_8.json`) — multi-event & multi-venue isolation, season aggregation, lifetime-points-untouched, rank-from-season-points, manual reset archive+champion+history, duplicate-reset block, fresh-Peasant new season, auto-reset due logic, message 422, admin-only authorization, legacy leaderboards. Post-run DB verified: exactly one current season (2026, active).

## 13. Legacy regression
register, login, legacy QR + check-in, legacy queue, points, nightly leaderboard, all-time leaderboard, badges (28), battles, admin, event QR/check-in/singer-list/queue/perks — all pass. No frontend changes.

## 14. Remaining decisions requiring approval
1. **Auto-reset production trigger**: wire a daily platform cron to `POST /api/admin/seasons/run-auto-reset` (startup-only isn't sufficient for a 24/7 boundary). Approve adding a cron in a later step?
2. **Leaderboard visibility**: currently any logged-in user can read any event/season leaderboard. Keep public, or restrict to participants/venue (ties into Step 7 roles)?
3. **Season rollup of NON-event awards**: Step 5 only awards season points via event awards. If you want legacy/global actions to ALSO feed season points, that's an explicit mapping change (currently they do NOT, to avoid double-count). Confirm.
4. Non-applied review items (documented): FastAPI lifespan migration, Mongo transactions (needs replica set), further `server.py` extraction. Fold into Step 7/cleanup?

## 15. Files added/changed
- `backend/phase2_seasons.py` (NEW) · `backend/migrations/0005_seasons.py` (NEW) · `backend/test_phase5.py` (NEW, 12) · `backend/server.py` (SEASON_CONFIG, mount season_router, startup ensure/auto-reset, paginated singer-list) · `backend/phase2_events.py` (field limits, symmetric perk guard, use-perk order, queue pagination) · `backend/.env` (season vars) · `memory/PHASE2_STEP5_RESULTS.md` (this doc).
- **No frontend changes.**

## 16. Next (Step 6 — Retire Legacy Nightly) — NOT STARTED
Approval-gated; nothing will be retired without explicit go-ahead after full verification.
