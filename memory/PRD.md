# King Klub - Product Requirements Document

## Overview
King Klub is a loyalty, engagement, and entertainment platform for King Karaoke. It encourages participation, rewards customers, and enhances the karaoke experience through gamification.

## Original Problem Statement
A full-stack web app for King Karaoke featuring:
- User Accounts & Profiles with rank tracking
- Reward System with 6 ranks (Peasant → Prince/Princess)
- Song Queue & Management
- Gamification & Accomplishments with badges
- Admin Tools for staff

## User Choices
- **Theme**: Royal purple (#0F0518) and gold (#FFD700) color scheme
- **Authentication**: JWT-based email/password
- **Admin Access**: Role-based (integrated with main app)
- **Title Preference**: Users can choose male (Squire/Knight/Count/Duke/Prince) or female (Lady/Dame/Countess/Duchess/Princess) rank titles

## User Personas
1. **Karaoke Patron**: Fun-loving singer who wants to track progress and earn rewards
2. **Regular Performer**: Competitive user aiming to climb leaderboard
3. **Staff/Admin**: Venue employee managing queue and awarding points

## Core Requirements
| Requirement | Status | Priority |
|-------------|--------|----------|
| User Registration/Login | ✅ Complete | P0 |
| Dashboard with Rank Display | ✅ Complete | P0 |
| Song Queue System | ✅ Complete | P0 |
| Points & Rewards | ✅ Complete | P0 |
| Leaderboard | ✅ Complete | P0 |
| Badges/Accomplishments | ✅ Complete | P1 |
| Admin Panel | ✅ Complete | P1 |
| Title Preference (Male/Female ranks) | ✅ Complete | P1 |
| QR Code Check-in System | ✅ Complete | P1 |
| Battle/Challenge System | ✅ Complete | P1 |
| Real-time WebSocket Voting | ✅ Complete | P1 |
| Sound Effects for Voting | ✅ Complete | P1 |
| Referral System | ✅ Complete | P1 |
| Queue Jump Perks | ✅ Complete | P1 |
| 5 Songs per 30-min Window | ✅ Complete | P1 |
| Admin Queue Reordering | ✅ Complete | P1 |
| Admin Password Reset | ✅ Complete | P1 |
| Battle Notifications | ✅ Complete | P1 |
| Real-Time Updates | ✅ Complete | P1 |
| Synced Battle Timer | ✅ Complete | P1 |
| Battle Sound Effects | ✅ Complete | P1 |

## What's Been Implemented

### March 2026 - Latest Updates
- **Nightly Champion Badge**: Added new badge awarded to #1 performer on tonight's leaderboard
  - Worth 25 bonus points
  - Automatically awarded when admin generates new QR code (new night begins)
  - Recorded in accomplishments with night_date and final nightly_points

- **Nightly Leaderboard Reset**: Implemented dual leaderboard system
  - Added "Tonight" tab showing points earned during current night only
  - Added "All-Time" tab showing total accumulated points
  - Nightly points automatically reset when admin generates a new QR code
  - WebSocket `LEADERBOARD_RESET` event notifies all connected clients when reset occurs
  - All point-awarding actions now increment both `nightly_points` and `points`

- **WebSocket Battle Notifications Fix**: Fixed critical bug where battle notifications weren't being received
  - Issue: React StrictMode was causing WebSocket connections to close immediately after opening
  - Fix: Added `isConnectingRef` and `shouldReconnectRef` flags in `useVoteNotification.js` to handle double-mount/unmount cycles
  - Verified: WebSocket now connects successfully and battle notifications (BATTLE_CHALLENGE, CHALLENGE_ACCEPTED, BATTLE_ENDED) are properly received
  - Test report: `/app/test_reports/iteration_4.json`

- **Login/Register Page Cleanup**: Removed side images from login and registration pages, now centered form design

### December 2025 - Previous Updates
- **Admin Queue Reordering**: Admins can now manually move songs up/down in the queue
  - **Drag-and-drop**: Grab the grip handle (⋮⋮) and drag songs to any position
  - Up/down arrow buttons for quick single-position moves
  - Songs that used a perk to enter top 4 positions are "frozen" and cannot be moved
  - Visual indicator (lock icon + "Perk Used" badge) for protected songs
  - POST /api/admin/queue/{item_id}/reorder endpoint for drag-and-drop

- **5 Songs per 30-Minute Window**: Checked-in users can add up to 5 songs per 30-minute rolling window
  - Window resets every 30 minutes from check-in time
  - Clear feedback on songs remaining and time until reset
  - Backend validation with helpful error messages
  - GET /api/queue/my-status endpoint provides full queue eligibility info

### Previous Implementations

#### Backend (FastAPI + MongoDB)
- User authentication (register, login, JWT tokens)
- Rank system with male/female title options:
  - Peasant (both)
  - Squire / Lady
  - Knight / Dame
  - Count / Countess
  - Duke / Duchess
  - Prince / Princess
- Song queue management (add, remove, position tracking)
- Points & badges system with automatic badge unlocking (23 badges across 6 categories)
- Leaderboard API with title preference support
- Admin endpoints (queue management, user management, points adjustment)
- **QR Code Check-in System** - Daily venue check-ins with rotating QR codes
- **Battle/Challenge System** - 5 challenge types (Royal Duel, Blind Challenge, Rank Battle, Song Roulette, Harmony Duel)
- **Real-time WebSocket Voting** - Broadcast voting events to all connected clients
- **Referral System** - Users earn badges for referring friends
- **Rank-based Queue Perks** - Once-per-night queue jump based on rank

#### Frontend (React + Tailwind)
- Landing page with royal theme
- Auth pages (login, register, separate admin login)
- Dashboard with rank card, progress bar, stats, referral link sharing
- Song Queue page with add/remove functionality, perk usage
- Leaderboard with top 3 podium display
- Badges/Accomplishments page
- Admin panel (queue management, user management, battle management, delete users)
- **Battle Arena Page** - Challenge opponents, view active battles
- **Real-time Vote Popup** - WebSocket-driven popup with countdown timer
- **Sound Effects** - Web Audio API sounds for battle start, voting, warnings, and victory
- **How to Earn Points Page** - Detailed breakdown of all badges and point actions

### Design
- Dark royal theme (#0F0518 background)
- Gold accents (#FFD700)
- Cinzel font for headings
- Manrope font for body text
- Glassmorphism cards with subtle borders
- Framer Motion animations

## Prioritized Backlog

### P0 - Critical (All Completed)
- [x] User authentication
- [x] Core dashboard
- [x] Song queue
- [x] Basic points system

### P1 - Important (All Completed)
- [x] Leaderboard
- [x] Badges system (23 badges across 6 categories)
- [x] Admin panel
- [x] Rank progression display
- [x] QR code check-in system
- [x] Battle/Challenge system with 5 modes
- [x] Real-time WebSocket voting
- [x] Sound effects for voting notifications
- [x] Referral system with badges
- [x] Queue jump perks based on rank
- [x] 5 songs per 30-minute window feature

### P2 - Nice to Have (Future)
- [ ] Push notifications (mobile/browser)
- [ ] Email reminders for events
- [ ] Event management system
- [ ] Reward redemption system (free songs, merch)
- [ ] Song catalog/search integration
- [ ] Mobile app version

## Pending Issues
- ~~WebSocket battle notifications not working~~ (FIXED March 2026)
- User reported "uncaught runtime errors" after admin login (not reproduced - monitor for recurrence)

## Next Tasks
1. Monitor for any runtime errors reported by users
2. Expand notifications system (push/email)
3. Build reward redemption catalog
4. Create event management for special karaoke nights
5. Refactor server.py into modular routers (recommended for maintainability)

## Test Reports
- `/app/test_reports/iteration_1.json` - Battle system tests
- `/app/test_reports/iteration_3.json` - Queue song limit tests (33/33 passed)
- `/app/test_reports/iteration_4.json` - WebSocket notification tests (100% pass rate)

## Tech Stack
- **Frontend**: React 19, Tailwind CSS, Framer Motion, Shadcn/UI
- **Backend**: FastAPI, Motor (MongoDB async driver)
- **Database**: MongoDB
- **Auth**: JWT with bcrypt password hashing
- **Timezone**: America/Chicago (hardcoded for venue)

## Test Credentials
- **Admin**: admin@kingkaraoke2025.com / admin123
- **User**: royaltest@example.com / password123

---

## Phase 2 — Multi-Location / Multi-Venue (in progress)
Goal: support multiple King Karaoke locations → venues → events with fully isolated data (singer lists, QR, points, leaderboards) while keeping a persistent global singer profile.

- **Step 0 (COMPLETE)** — Baseline & safety: DB indexes, isolated dev sample Location→Venue→Event data, dev admin, migration/backfill strategy, existing-app verification. See `memory/PHASE2_STEP0_RESULTS.md`. Dev admin creds in `memory/test_credentials.md`.
- **Step 1 (COMPLETE)** — Data model foundation (additive): `Location`, `Venue`, `Event`, `EventParticipation` models (`backend/models_phase2.py`), migration `backend/migrations/0001_phase2_data_model.py` (idempotent/logged/reversible), 12/12 tests (`backend/test_phase2_models.py`). server.py + frontend UNCHANGED; legacy points/nightly/QR/queue/leaderboard intact. See `memory/PHASE2_STEP1_RESULTS.md`.
- **Step 2 (COMPLETE)** — Event-scoped QR (additive): opaque HMAC-signed, expiring, per-event tokens with rotation nonce; endpoints `GET /api/events/{id}/qr`, `POST /api/events/checkin`, `GET /api/admin/events`; new `event_checkins` (unique user+event dedupe) + `event_checkin_attempts` (audit) collections; per-event/venue/location timezone expiry; feature flags `EVENT_QR_ENABLED` / `LEGACY_QR_ENABLED` (legacy preserved). 23/23 tests. See `memory/PHASE2_STEP2_RESULTS.md`.
- **Step 3 (COMPLETE)** — Scope check-ins & singer lists (additive): event check-in now creates `event_participation` (per-event singer list) with deterministic `list_position` (check-in order); new `GET /api/events/{id}/singer-list` (display_name joined at read time, no PII); idempotent/reversible legacy backfill `migrations/0003_backfill_legacy_checkins.py` (dry-run default, maps legacy `checkins`→Default-Legacy event, marked is_backfill). testing_agent 30/30, no issues. Legacy check-in preserved & unmodified. See `memory/PHASE2_STEP3_RESULTS.md`.
- **Step 4 (COMPLETE)** — Scope queue & perks (additive): new `event_queue` + `event_perk_usage` collections; event-scoped queue (add/list/complete/cancel/set-current/move/reorder), per-event 5/30 limit, event-scoped rank perks (unique per user+event, no cross-event leak), KJ singer-list reorder (list_position only, timestamps preserved); WebSocket event rooms via `/api/ws/events/{id}` + `broadcast_event` (no cross-event leak); new module `phase2_events.py`; migration `0004_event_queue.py` (dry-run default, idempotent/reversible legacy-queue backfill). Event `complete` awards NO points (Step 5). Admin scope still global (venue/KJ roles = Step 7). testing_agent 28/28, no issues. See `memory/PHASE2_STEP4_RESULTS.md`.
- **Step 5 (COMPLETE)** — Event-scoped points + annual Season system + leaderboards (additive): `seasons`/`season_participation`/`season_accomplishments`/`season_resets` collections; `event_participation.event_points`; new module `phase2_seasons.py`; award via `POST /api/events/{id}/award-points` (event+season points, lifetime untouched); event & current/historical season leaderboards (paginated); manual reset (`/admin/seasons/reset`, confirm+admin, archives w/ champion & history, duplicate-guard) + auto-reset (Jan 2, toggle, `run-auto-reset`); new season = fresh Peasant/0pts, prior seasons archived not deleted; migration `0005_seasons.py`. Folded hardening (field limits, symmetric perk guard, use-perk order, pagination, bounded points). testing_agent 59/59, no issues. See `memory/PHASE2_STEP5_RESULTS.md`.
- **Step 5 CORRECTION (COMPLETE)** — season-point sources from normal activities via idempotent `point_ledger` (unique dedupe_key): event check-in (+10 event/+10 season), performed-song completion (+10/+10), manual award (dedupe_key, 409 on dup). Lifetime `users.points` unchanged; battles/referral/legacy-badge remain lifetime-only pending approval. Daily auto-reset cron `.emergent/crons.yml` → `POST /api/cron/season-reset` (Bearer WEBHOOK_CRON_SECRET, idempotent). testing_agent 69/69, no issues. Point Source Matrix in `memory/PHASE2_STEP5_CORRECTION_RESULTS.md`.
- **Step 6 (COMPLETE)** — Retire legacy nightly (flag-gated, non-destructive): `LEGACY_NIGHTLY_ENABLED=false` (+`LEGACY_QR_ENABLED=false`) → legacy venue QR, check-in, nightly leaderboard, and nightly reset/champion return 403; event/season system is authoritative. Lifetime +10 check-in preserved via event check-in (separate ledger key `lifetime_checkin:*`, no double-count). Legacy data/collections/code all preserved for rollback (flip flags true). Frontend screens still calling legacy endpoints documented (QRCheckInPage, CheckInPage, LeaderboardPage tonight-tab) — redirect deferred to a minimal UI pass. 65 local tests green. See `memory/PHASE2_STEP6_RESULTS.md`.
- **Step 7 (IN PROGRESS — split into 7c → 7a → 7b → 7d)** — venue/KJ roles & isolation, final legacy code cleanup (after acceptance), deferred hardening (cron rate-limit, ledger janitor, lifespan migration, Mongo transactions, server.py extraction). Approval-gated.
  - **Step 7c (COMPLETE — 2026-06-09)** — Surgical frontend redirects off retired legacy endpoints onto Phase 2 endpoints (no backend/data-model change):
    - `QRCheckInPage.js` (/admin/qr-checkin): now `GET /api/admin/events` (event dropdown, auto-selects most-recent **active** event, else nearest **scheduled**) → `GET /api/events/{id}/qr` (QR image from `checkin_url` = `/e/checkin/{token}`) + `GET /api/events/{id}/singer-list` (checked-in singers panel). Replaced `/venue/qr-data`.
    - `EventCheckInPage.js` (NEW, route `/e/checkin/:token`): singer check-in via `POST /api/events/checkin {token}`; states success/already/error/login-required (login redirect preserves token).
    - `CheckInPage.js` (legacy route `/checkin/:venueCode`): converted to a static friendly "QR retired" notice — **no backend call** (choice 3a).
    - `LeaderboardPage.js`: "Tonight" tab renamed **"Season"**, backed by `GET /api/seasons/current/leaderboard` (season_points, normalized shape); "All-Time" tab unchanged (`GET /api/leaderboard`). Removed `/leaderboard/tonight`.
    - Sweep: `useVoteNotification.js` champion/reset toast wording nightly→season.
    - Verified: testing_agent iteration_10.json 100% (10/10 flow assertions). Pre-existing `/api/ws` WebSocket console errors noted (out of 7c scope).
  - **Step 7a (COMPLETE — 2026-06-09)** — additive Role model, NO authz behavior change:
    - Roles: `global_admin`, `location_manager`, `venue_kj`, `singer` (defined in `backend/roles.py` with pure, non-enforcing resolvers).
    - `users` gains `role` (default `singer`) + `role_scope` `{location_ids:[], venue_ids:[]}` (scope stored for 7b, NOT enforced).
    - Legacy `is_admin` preserved untouched; `get_admin_user` still gates on `is_admin` (unchanged). Role is NOT baked into the JWT — `get_current_user` re-reads the user, so role stays fresh (avoids stale-claim authz).
    - Mapping (migration `0007_user_roles.py`, additive/idempotent/reversible): legacy admins→`global_admin`, everyone else→`singer`; never overwrites a manually-set role/scope; `down()` unsets only `role`/`role_scope` (is_admin & data intact).
    - `register` writes role+role_scope; `login`/`register`/`/auth/me` now also return `role` (additive). `step0_setup.py` dev admin seeded as global_admin.
    - Tests: `test_phase2_roles.py` 7/7 (mapping invariant, admin login/access preserved, singer default + denied admin, idempotency preserves manual role, reversibility). Full regression green: models+5b 18/18, qr/3/4/5 47/47, cron pass.
  - **Step 7b (COMPLETE — 2026-06-09)** — Isolation enforcement across every Phase 2 event/season endpoint + event WebSocket rooms. NO business-logic change (points/season/QR-token/data-model untouched); legacy flags unchanged (LEGACY_NIGHTLY_ENABLED=false, LEGACY_QR_ENABLED=false, EVENT_QR_ENABLED=true).
    - New `backend/authz.py`: pure decisions built on 7a roles. Resource (event) always loaded from DB; client-supplied location/venue/event ids are NEVER trusted for the decision. `staff_can_access_event`, `require_event_staff`, `require_event_view`, `require_global_admin`, `require_staff`, `events_scope_query`.
    - Access model: global_admin = all; location_manager = events whose `location_id ∈ role_scope.location_ids`; venue_kj = events whose `venue_id ∈ role_scope.venue_ids`; singer = no staff access, participatory reads/self-writes only. Denials are 403 with `{detail}` only (no resource data leaked).
    - Staff Phase 2 endpoints switched from `Depends(get_admin_user)` (is_admin only) → `Depends(get_current_user)` + authz, so scoped staff (lm/kj, who are NOT is_admin) work within scope while global_admin behavior is preserved and singers still 403.
    - Protected: `GET /api/admin/events` (scoped listing), `GET /api/events/{id}/qr`, `GET /api/events/{id}/singer-list`, `POST /api/events/{id}/award-points`, event queue complete/set-current/move/reorder + singer-list/reorder (staff, scoped); queue view/add/my-status/cancel, perk-status/use-perk, `GET /api/events/{id}/leaderboard` (view: singer allowed, staff scoped); `GET /api/seasons` + `/admin/seasons/reset` + `/admin/seasons/run-auto-reset` (global_admin only).
    - WebSocket `/api/ws/events/{event_id}`: now authenticates via `?token=` (JWT), loads the event, applies `require_event_view`, and closes with 4401/4404/4403 before joining; broadcasts still go only to the event room (no cross-event leak). Legacy `/api/ws` untouched.
    - Intentionally NOT scope-restricted: `POST /api/events/checkin` (singer self check-in via signed token) and season leaderboards/`seasons/current` (platform-wide, any authenticated user) — these are singer-facing and season is global.
    - Tests: `test_phase2_isolation.py` 18/18 (global_admin all; lm/kj in-scope allow + other-scope deny via forged ids; singer staff-deny + own-participation allow + cannot delete another's queue item; no-data-leak on denial; WS in-scope open, cross-venue/cross-location 4403, no-token 4401, global_admin any, and Event-A broadcast never reaches an Event-B client). Full regression green: roles/models/ledger/cron 29/29, qr/3/4/5 47/47.
  - **Step 7d (COMPLETE — 2026-06-09)** — Final hardening & cleanup. Production-safety honored: no prod deploy, no prod DB change, no data/collection/migration deletion; legacy flags unchanged.
    - **Legacy inventory (retained, NOT removed — needed for rollback):** flag-gated legacy endpoints `/api/leaderboard/tonight`, `/api/venue/qr-data`, `/api/checkin/{venue_code}`, `/api/checkin/status/today`, `/api/admin/checkins/today`, and `users.nightly_points` / `settings.current_night` writes remain in `server.py` behind `LEGACY_NIGHTLY_ENABLED`/`LEGACY_QR_ENABLED` (both false). Nothing deleted; flip flags true to restore. Frontend legacy `/checkin/:venueCode` kept as a retired-notice (7c).
    - **Cron hardening:** `/api/cron/season-reset` keeps Bearer-secret auth (401 on missing/wrong), adds in-memory replay/rate throttle (`CRON_MIN_INTERVAL_SECONDS=5` → repeat calls return 200 `{ran:false, reason:"throttled"}`), preserves Jan-2 idempotent behavior (unique season.year).
    - **Point-ledger janitor:** `phase2_seasons.find_ledger_orphans` + report-only `GET /api/admin/ledger/orphans` (global_admin) + migration `0008_ledger_orphan_janitor.py` (report by default; `--quarantine` tags `is_orphan=True` additively, never deletes; `--down` untags). Legitimate rows untouched; idempotency & lifetime/event/season separation intact.
    - **FastAPI lifecycle:** migrated `@app.on_event(startup/shutdown)` → `lifespan` context manager (low-risk); deprecation warning gone; season bootstrap + Mongo client close preserved.
    - **/api/ws:** investigated — backend endpoint accepts & works locally (logs show `[accepted]`/`connection open`); the browser console error is environmental WS routing through the preview ingress, NOT a code bug. No redesign. Phase 2 event-room isolation intact (tests pass).
    - **Security review:** auth (JWT re-read per request), role/scope authz, forged-id denial, event & location/venue isolation, QR token HMAC/expiry/nonce, ledger idempotency, season-reset authz+idempotency, WS authz+isolation, secret handling, denial no-leak — all covered by tests.
    - **Tests:** new `test_phase2_7d.py` (cron auth/throttle/idempotency, ledger-orphan endpoint authz, season-reset authz). Full suite run **serially**: **99 passed, 0 failed** (models, qr, checkin, singer-lists, queues/perks, points, seasons, roles, isolation, cron, 7d). Frontend E2E from 7c (iteration_10) 100%.
    - Files: `server.py` (lifespan, cron throttle, ledger endpoint, imports), `phase2_seasons.py` (`find_ledger_orphans`), `migrations/0008_*` (new), `test_phase2_7d.py` (new). No DB migration applied to any prod data.

Note: Phase 2 uses a per-location/venue timezone in the new model (the legacy single hardcoded America/Chicago still drives the existing system until later steps).

