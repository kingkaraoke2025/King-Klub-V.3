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

# Phase 2 Controlled Integration — Development Workspace (2026-06)

**Status: Integrated & verified in isolated dev workspace. NOT deployed.**

## What this workspace is
Isolated development/preview copy combining the base King Klub app (from `King-Klub-V.3-Full`)
with the Phase 2 overlay modules (from `King-Klub-V.3`). Fresh local MongoDB
(`king_klub_phase2_dev`). The live King Klub app, its production DB, and secrets were NOT touched.

## Files added
- `backend/roles.py` — Phase 2 role model (DB-based resolvers: global_admin/location_manager/venue_kj/singer).
- `backend/phase2_server.py` — integration layer: locations/venues/events admin, event QR + `/api/e/checkin/{token}`,
  singer-list, mounts event-queue/perk + season/points routers, per-event WS auth, cron season-reset, season startup.
- `backend/authz.py`, `models_phase2.py`, `phase2_events.py`, `phase2_seasons.py`, `migrations/0001-0008` — from Phase 2 overlay.
- `backend/seed_dev.py`, `backend/phase2_smoke.py` — dev seed + e2e smoke test.
- `backend/.env`, `frontend/.env` — dev-safe values, fresh secrets (git-ignored).

## Files modified
- `backend/server.py` — additive only: ConnectionManager per-event rooms + `broadcast_event`; Phase 2 feature flags;
  403 gates on legacy `/venue/qr-data`, `/checkin/{code}`, `/leaderboard/tonight`; `register_phase2(...)` before router include.
  No legacy logic rewritten.

## Verified (backend e2e, 30 checks via phase2_smoke.py)
auth; role authorization; location/venue/event creation; event QR gen; `/e/checkin/{token}` (+dup block +tamper reject);
singer-list isolation (E1↔E2); event points + isolated event/season leaderboards; season current/leaderboard;
event queue + perks; legacy nightly retired (403); singer denied staff endpoints; venue_kj scope isolation
(cannot access another venue's event by changing id); cron secret enforcement. Frontend (Phase 1 UI) compiles & loads.

## Backlog / next (pending approval)
- P1: Optional admin UI screens for locations/venues/events/event-QR (Phase 2 was backend-only; current UI is Phase 1).
- P1: Apply data-backfill migrations 0003/0004 with `--execute` if legacy data is ever imported (currently dry-run, DB is fresh).
- P0 (gated): Production cutover planning — do NOT run until explicitly approved.

---

# Phase 2 Admin UI + Staff-Login Fix (2026-06) — dev workspace

**Status: Built & verified (testing_agent: all primary flows PASS; backend smoke 30/30). NOT deployed.**

## Reported bug fixed
- "login failed" at Staff Portal: `/admin/login` previously required `is_admin=true`, rejecting `venue_kj`/`location_manager`.
  Fix: login/`/auth/me` now return `role`/`role_scope`; `AdminLoginPage` admits all staff roles and routes
  global_admin -> `/admin`, other staff -> `/admin/phase2`. Verified by testing_agent.

## Frontend files added
- `src/lib/phase2Api.js`, `src/components/Phase2Shell.jsx`
- `src/pages/phase2/LocationsPage.jsx`, `VenuesPage.jsx`, `EventsPage.jsx`, `EventManagePage.jsx`
- `src/pages/EventCheckInPage.jsx` (singer `/e/checkin/:token`)

## Frontend files modified
- `src/App.js` (staff-aware ProtectedRoute + Phase 2 routes + `/e/checkin/:token`)
- `src/pages/AdminLoginPage.js` (staff-role login), `src/pages/AdminPage.js` (Phase 2 Admin button)

## Backend files modified (small, justified)
- `server.py` — login & `/auth/me` return `role`/`role_scope`.
- `phase2_server.py` — added PUT edit endpoints (locations/venues/events) + friendly 400 on duplicate name.

## UI screens
Locations (list/create/edit, role-scoped grid) -> Venues (list/create/edit) -> Events (list/create/edit, status) ->
Event Management tabs: Overview, QR (image/copy URL/regenerate/expiry), Singers (award points), Queue (KJ controls),
Points/Leaderboard (event + current season). Royal/gold theme preserved; role-based control hiding; backend authoritative.

## Verified (testing_agent iteration_6)
staff login fix, singer rejection, full L->V->E CRUD, all event tabs, QR-token check-in, singer isolation across events,
points award + season leaderboard, venue_kj control hiding + backend cross-scope 403, Phase 1 regression. Backend 30/30 smoke.

---

# Bug fix: /admin/qr-checkin QR generation (2026-06) — dev workspace

**Root cause:** The `/admin/qr-checkin` page (`QRCheckInPage.js`) was the LEGACY nightly venue-QR page still calling the retired `GET /api/venue/qr-data` (Phase 2 disabled it -> 403), so it errored with "Failed to load QR code" and never rendered a QR. Not a backend defect.

**Fix (frontend only, smallest change):** Migrated `QRCheckInPage.js` to the existing Phase 2 event-scoped QR — added an event selector, calls `GET /api/admin/events/{id}/qr` (via `p2.eventQR`), renders the returned `/e/checkin/{token}` check-in path. Route `/admin/qr-checkin` widened `adminOnly` -> `staffOnly`. No QR backend changes; all Phase 2 protections (signed/expiring/tamper/scoping/duplicate/auth) preserved.

**Verified (testing_agent iteration_8, 6/6 + regression):** QR renders & regenerates, event switching, singer QR check-in, event scoping (singer only in selected event), duplicate protection, tampered-token rejection, staff access (venue_kj) + singer redirect. Backend smoke still 30/30.

**Known pre-existing (out of scope):** WS `/api/ws` upgrade warnings via ingress; a 429 burst on singer `/dashboard` polling — candidates for a future iteration.

---

# Bug fix: song queue not recognizing Phase 2 event check-in (2026-06) — dev workspace

**Reported:** dakota@hotmail.com checked in via Phase 2 event QR but the song queue still said "You still need to check in."

**Root cause:** Legacy queue endpoints (`/api/queue`, `/api/queue/my-status`, `/api/queue/perk-status`, `/api/queue/use-perk`) gated on the RETIRED nightly `db.checkins` record. Phase 2 stores check-ins in `event_participation` (status='checked_in'), so the legacy lookup always returned None -> "check in first".

**Fix (backend only, server.py):** Added `resolve_active_event_checkin(user)` — returns the user's current ACTIVE-event Phase 2 participation (most-recent active event) or None; does NOT fall back to nightly `checkins`. Wired into all four legacy queue endpoints. Queue items now tagged with `event_id`; 30-min song window + perk usage are per-event (Event A vs B isolation). Requirement preserved: unchecked singers still blocked (400 / can_add_songs=false).

**Verified:** testing_agent iteration_9 (100% frontend, end-to-end before->after, isolation, duplicate/tampered) + backend phase2_smoke 30/30 + final_e2e 38/38.

**Known pre-existing (out of scope):** `/api/ws` WebSocket console noise on every page (non-blocking).

---

# Venue KJ show-operation console (2026-06) — dev workspace

**Reported gap:** venue_kj had no obvious way to select/run a show, and it wasn't clear they could generate the event QR, award points, or manage the queue.

**Current Phase 1 KJ capabilities (base app):** QR check-in display, live song queue with reorder/complete/current, award points (nightly), rank perks — all gated behind is_admin (global).

**Missing in Phase 2 for venue_kj:** a scoped, discoverable entry point + explicit event selection (the per-event tools already existed in EventManagePage but were buried under Locations→Venues→Events).

**Changes (frontend only; backend authz unchanged):**
- NEW `pages/phase2/KJConsolePage.jsx` at `/admin/kj`: lists the KJ's authorized events grouped by their assigned venue (Active/Upcoming + past), each with a "Run Show" button. Single active event is marked default but still shown/selectable.
- `AdminLoginPage.js`: venue_kj now lands on `/admin/kj` (global_admin -> /admin, other staff -> /admin/phase2).
- `Phase2Shell.jsx`: role-aware header (non-admin staff get "KJ Console" + "Venues" nav instead of the admin-only "Phase 1 Admin").
- Selecting a show opens the existing per-event workflow (QR → singers+award → queue controls → leaderboard/season), event header clearly shown; everything event-scoped.

**Permission boundaries (unchanged, backend-enforced):** venue_kj is NOT is_admin; scoped to its venue only; can operate any event at its venue; cannot access other locations/venues/events, cannot award in another event, cannot reach the Phase 1 global panel (/admin -> /dashboard), cannot manage global settings/users. Award requires the target to be checked into that event.

**Event selection:** KJ Console shows "Venue: <assigned venue>" + selectable shows; selected event drives QR→check-in→singers→queue→points→perks→leaderboard.

**Verified:** testing_agent iteration_10 (KJ console + run Event A, switch to Event B, scope guards, Phase 1 compat, regression) — 100%. Backend: phase2_smoke 30/30, final_e2e 48/48 (incl. T3b venue-KJ operate-both-events + denied on other venue).


---

## Changelog — 2026-06-18 (Venue KJ: Full Show-Operation + Event-Scoped Battles)

**Context:** Isolated Phase 2 DEV env only (local Mongo `king_klub_phase2_dev`). NO production access. Preview URL is served at the job's GUID domain; `frontend/.env REACT_APP_BACKEND_URL` was corrected to the current preview origin (the old `king-v3-staging` value caused cross-origin CORS login failures).

### Delivered
- **KJ show-operation console** (`frontend/src/pages/phase2/EventManagePage.jsx`, opened via KJ Console → Run Show): full Phase-1 parity for the SELECTED event — persistent context bar (Venue · Show · Status), QR generate/regenerate/copy, Singers list, Queue with dnd-kit drag-reorder + up/down + set-current + Now-Performing card + complete + remove + singer messages + perk-protected lock, structured point awards (Phase-1 POINT_ACTIONS one-tap + custom amount), event & season leaderboards.
- **NEW event-scoped Battles module** (`backend/phase2_battles.py`, mounted via `phase2_server.register_phase2` with `CHALLENGE_TYPES`): `event_challenges` + `event_challenge_votes` collections. Endpoints under `/api/events/{event_id}/battles*` — list/battle-types (require_event_view), create/open-voting/close-voting/finalize/pick-winner/cancel (require_event_staff), vote (checked-in participant, one vote, contestants excluded). Winner/participant points via idempotent award ledger → EVENT + SEASON only (never lifetime).
- **Points attribution + audit**: manual awards go to event_points + season_participation (not legacy `users.points`); `awarded_by` (KJ id) added to `season_accomplishments` for traceability.

### Security (all backend-enforced via `authz.require_event_staff`, DB role/scope — not JWT, not is_admin)
- venue_kj can operate ONLY events in `role_scope.venue_ids`; another venue's event → 403.
- Singers → 403 on all KJ-only ops. All battle/queue/point rows carry event_id; no cross-event leakage.

### Testing
- Backend: `backend/test_kj_phase2.py` — **24/24 pass** (battles + points isolation, 403 boundaries, lifetime-untouched).
- Frontend: `test_reports/iteration_11.json` — **9/9 flows pass** incl. isolation (KJ blocked from Other Event: "Not authorized", QR 403). No bugs.

### Known non-blocking item (deferred)
- Benign WebSocket `/api/ws` console noise on Phase 2 pages (legacy Phase 1 hook). Cosmetic only.

---

## Changelog — 2026-06-18 (Staff Authorization Model)

**Context:** Isolated Phase 2 DEV only. No production.

### Delivered
- **Staff authorization layer** on top of the role model: new `users.staff_active` flag. A `venue_kj`/`location_manager` needs `staff_active=true` to access ANY staff/KJ operation — role alone grants nothing. `global_admin` always authorized.
- **Signup grants no staff**: `register` sets `role=singer, staff_active=false`. `login`/`/auth/me` now return `staff_active`.
- **Dev-Admin-only staff management**: `GET /api/admin/staff`, `PUT /api/admin/users/{id}/staff` (StaffGrant: role∈{singer,venue_kj,location_manager}, staff_active, location_ids, venue_ids). Cannot assign global_admin, cannot modify an admin, validates venue/location ids, revoke (role=singer) clears scope + forces inactive.
- **Backend gates** (`authz.py`): `staff_authorized()`; `is_staff`/`staff_can_access_event`/`can_access_location`/`events_scope_query` all require active staff auth. Deactivation is immediate (DB re-read per request; staff_active never in JWT).
- **Frontend**: Staff Portal (`/admin/login`) + `ProtectedRoute` require `staff_active` for non-admin staff; new **Staff Management** page `/admin/phase2/staff` (search users, grant/revoke Venue KJ, activate/deactivate, assign venues). Entry points: Phase-1 Admin header "Staff Access" + Phase 2 shell "Staff".

### Security verified
- No self-grant / self-promote (endpoints are is_admin-only; venue_kj → 403). Cannot escalate to global_admin. Deactivated/revoked KJ → immediate 403 + Staff Portal denial + route redirect. Singers cannot reach KJ/admin pages. Existing event isolation intact.

### Testing
- Backend: `backend/test_staff_auth.py` **29/29 pass**; `backend/test_kj_phase2.py` **24/24** (no regression).
- Frontend: `test_reports/iteration_12.json` — **18/18 UI assertions pass** (full grant→login→revoke→denied lifecycle). No UI bugs.

### Known minor (pre-existing, not introduced here)
- `/api/auth/me` can return 429 during very rapid page navigation (existing rate limiter). Non-blocking; cosmetic loading flashes only.

---

## Changelog — 2026-06-18 (KJ console rebuilt to old Admin/KJ panel parity)
- Rebuilt `frontend/src/pages/phase2/EventManagePage.jsx` to mirror the old Phase-1 Admin/KJ panel: motion header + selected-event context bar, 4 stat cards, shadcn Tabs (Queue | Singers | Award Points | Battles | Leaderboard | QR), classic DnD `SortableQueueItem` (drag handle, position, message, perk lock, move up/down, set-current, remove), Now-Performing card with Complete.
- Dedicated **Award Points** tab (singer search + select list + Point Actions Reference) and award dialog (Phase-1 one-tap actions + custom amount) → event-scoped `POST /events/{id}/award-points` (event+season, never lifetime; records awarded_by).
- Event-scoped **Battles** tab (create from checked-in singers, open/close voting, finalize, pick winner) → `phase2_battles`.
- On 403 for an out-of-scope event, KJ is redirected back to `/admin/kj`.
- Re-fixed `frontend/.env REACT_APP_BACKEND_URL` (had reverted to stale king-v3-staging → CORS login failure) to the current preview origin.
- Backend unchanged & re-verified: test_staff_auth 29/29, test_kj_phase2 24/24, focused_verify 22/22. Frontend E2E iteration_13.json 8/8 pass, no bugs.
- Restored seeded singers (singer1/2, dakota) to role=singer after earlier test drift corrupted singer1 to venue_kj.

---

## Changelog — 2026-06-18 (KJ event awards now unlock badges)
- **Bug**: KJ Award Points (Phase-2 event endpoint `POST /events/{id}/award-points`) awarded event/season points but never evaluated badges. The old `/admin/award-points` path did (special action badges + `check_and_award_badges` milestones); the Phase-2 path never called that logic.
- **Fix (server.py)**: refactored badge criteria into pure reusable helpers `_compute_milestone_badges` + `_compute_special_action_badges` (identical ids/names/thresholds/rewards preserved; `check_and_award_badges` now uses them). Added `award_event_badges(user_id, action_id, event, award_ledger)` which mirrors legacy action-stat tracking, unlocks any newly-earned badges via the EXISTING `users.badges` + `accomplishments` model (idempotent, `$addToSet`), and routes badge bonus points to the EVENT + current SEASON only (never legacy lifetime). Wired through `register_phase2` -> `phase2_seasons.build_router(award_badges=...)`; award response now returns `badges_earned`, `badge_names`, `bonus_points`.
- **Frontend**: KJ award toast surfaces unlocked badges + bonus points.
- **Note**: The KJ-reported "award failed" was the stale-domain/ingress browser issue (backend award returns 200); resolved by using the king-v3-staging preview URL.
- **Tests**: new `backend/test_kj_badges.py` 14/14 (unlock, idempotency, milestone, event/season-only attribution, isolation, singer 403, singer-facing display). Regression: test_staff_auth 29/29, test_kj_phase2 24/24, focused_verify 22/22. King kota now correctly holds `random_warrior`.

---

## Changelog — 2026-06-18 (Singer-initiated event battle requests + KJ pending notification)
- **Legacy singer-to-singer battles fully preserved** (separate `/api/challenges*`, `db.challenges`) — verified still working (create/accept/vote/list).
- Added `POST /api/events/{id}/battle-requests` (checked-in singer proposes a battle vs another checked-in singer in the SAME event; creates a pending `event_challenge` with `source=singer_request`). Shared `_create_battle` helper enforces: both contestants checked-in, event-open, no dup, event/venue immutable on the doc.
- Added `GET /api/events/{id}/battle-requests/pending` (require_event_staff) as the KJ notification source.
- KJ console (`EventManagePage`): Battles tab shows a green pending dot + "N battle(s) pending" banner + "Requested by singer" label; polls battles every 12s (existing polling pattern). KJ runs the full lifecycle pending→voting→completed with event/season points.
- Tests: `backend/test_battle_requests.py` 16/16 (request, KJ pending notify, lifecycle, cross-event/venue rejection, foreign-singer rejection, unchecked-in rejection, staff-only pending, legacy intact). Regression: staff_auth 29, kj_phase2 24, focused 22, kj_badges 14 — all pass.
