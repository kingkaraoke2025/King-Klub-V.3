# Test Credentials — King Klub Phase 2 (isolated DEV workspace)

> Isolated development workspace. Fresh local MongoDB (`king_klub_phase2_dev`). NOT production.
> Seed/reseed with: `python /app/backend/seed_dev.py`

## Global Admin (role: global_admin)
- Email: `dev-admin@kingkaraoke2025.com`
- Password: `DevKing!2026`  (from backend/.env `DEV_ADMIN_PASSWORD`)

## Singers (role: singer)
- `singer1@kingkaraoke2025.com` / `Singer!2026`  (id: dev-singer-0001)
- `singer2@kingkaraoke2025.com` / `Singer!2026`  (id: dev-singer-0002)

## Venue KJ (role: venue_kj) — created by phase2_smoke.py test run
- `kj@kingkaraoke2025.com` / `Kj!2026`  (scoped to the "Royal Stage" venue only)

Notes:
- Roles are resolved from the DB record (users.role / users.role_scope), not the JWT.
- Legacy nightly QR/check-in/leaderboard are retired via flags (LEGACY_NIGHTLY_ENABLED=false, LEGACY_QR_ENABLED=false).
