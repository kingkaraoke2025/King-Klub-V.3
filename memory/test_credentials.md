# Test Credentials — King Klub Phase 2 (isolated DEV workspace)

> Isolated development workspace. Fresh local MongoDB (`king_klub_phase2_dev`). NOT production.
> Re-seed users + named scenario with: `python /app/backend/setup_final_scenario.py` (idempotent)
> Basic user seed only: `python /app/backend/seed_dev.py`

## Staff login page: `/admin/login`  ·  Singer login: `/login`

| Role | Email | Password | Scope |
|---|---|---|---|
| global_admin | `dev-admin@kingkaraoke2025.com` | `DevKing!2026` | all |
| location_manager | `lm@kingkaraoke2025.com` | `Manager!2026` | "Test Location" |
| venue_kj | `kj@kingkaraoke2025.com` | `Kj!2026` | "Test Venue" |
| singer | `singer1@kingkaraoke2025.com` | `Singer!2026` | — |
| singer | `singer2@kingkaraoke2025.com` | `Singer!2026` | — |
| singer | `dakota@hotmail.com` | `Dakota!2026` | — |

## Staff authorization model (added 2026-06-18)
- Staff access = **role (venue_kj/location_manager) + `users.staff_active=true`**. Role alone grants nothing.
- Signup always creates `role=singer, staff_active=false`. Only global_admin grants/revokes via Staff Management (`/admin/phase2/staff` → `PUT /api/admin/users/{id}/staff`).
- global_admin is always staff (is_admin). Deactivation/revocation takes effect immediately (DB re-read each request; staff_active is NOT in the JWT).
- Backend enforces everything (403); frontend gating is cosmetic. Seeded `kj@`/`lm@` are pre-activated (`staff_active=true`).
- Staff Portal = `/admin/login`. Singer login = `/login` (no KJ controls).

Routing: global_admin → `/admin` (has "Phase 2 Admin" button → `/admin/phase2`); other staff → `/admin/phase2`.

## Named verification scenario (created by setup_final_scenario.py)
- Test Location → Test Venue → Event A "Test Karaoke Night", Event B "Second Night"
- Out-of-scope (negative tests): Other Location → Other Venue → Other Event

Notes:
- Roles resolved from DB record (users.role / users.role_scope), not the JWT.
- Legacy nightly QR/check-in/leaderboard retired via flags (LEGACY_NIGHTLY_ENABLED=false, LEGACY_QR_ENABLED=false).
