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
