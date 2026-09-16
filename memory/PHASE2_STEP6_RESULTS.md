# Phase 2 — Step 6 Results (Retire Legacy Nightly System)

Status: **COMPLETE — awaiting approval to proceed to Step 7.**
Controlled, flag-gated retirement. No legacy data/collections/code deleted. Verified via curl + automated suites (87 passing, incl. explicit retirement + lifetime-preservation assertions).

---

## 1. Legacy nightly components inventoried
| Component | Location | Disposition |
|---|---|---|
| `settings.current_night` | driven by legacy `get_venue_qr_data` | **Retired as source of truth** (endpoint gated off). Doc preserved. Events now come from `events` collection. |
| `users.nightly_points` | field + nightly leaderboard | **No longer used for active ranking**. Field preserved (not deleted). |
| Legacy nightly leaderboard | `GET /api/leaderboard/tonight` | **Retired** (403 when flag off). Season/event leaderboards authoritative. |
| Legacy venue QR | `GET /api/venue/qr-data` | **Retired** (403). Event QR (`/api/events/{id}/qr`) authoritative. |
| Legacy check-in | `POST /api/checkin/{venue_code}` | **Retired** (403). Event check-in (`/api/events/checkin`) authoritative. Lifetime +10 preserved via new path. |
| Nightly champion/reset | inside `get_venue_qr_data` (starts new night) | **Retired** — endpoint gated off so nightly reset/champion no longer runs. Distinct from annual season reset (Jan 2). |
| Nightly badge (Nightly Champion) | awarded during nightly reset | No longer awarded (reset retired). Historical badges on users preserved. |

## 2. What was retired (all behind a flag, code intact)
Legacy venue QR, legacy check-in, legacy nightly leaderboard, nightly reset/champion — all now return **403** when `LEGACY_NIGHTLY_ENABLED=false`, with messages pointing to the event/season replacements. The old implementations remain in `server.py` unchanged, only guarded.

## 3. What was preserved
- **Lifetime `users.points`**: fully intact. All-time leaderboard (`/api/leaderboard`) stays authoritative (200).
- **Legacy data**: `settings.current_night`, `users.nightly_points`, `checkins`, `queue`, badges, accomplishments, historical records — **untouched, not deleted**.
- **Legacy code**: retained behind the flag for rollback.

## 4. Feature flags
- `LEGACY_NIGHTLY_ENABLED` (now **false**) — master retirement switch for nightly QR/check-in/leaderboard/reset.
- `LEGACY_QR_ENABLED` (now **false**).
- `EVENT_QR_ENABLED=true`, `SEASON_AUTO_RESET_ENABLED=true`.
Flipping `LEGACY_NIGHTLY_ENABLED=true` (+ `LEGACY_QR_ENABLED=true`) instantly re-enables the legacy path — the rollback mechanism.

## 5. New authoritative paths
event QR `/api/events/{id}/qr` · event check-in `/api/events/checkin` · singer participation & list `/api/events/{id}/singer-list` · event queue `/api/events/{id}/queue*` · event points & season points (idempotent ledger) · season rank/badges/accomplishments · leaderboards `/api/events/{id}/leaderboard`, `/api/seasons/current/leaderboard`, `/api/seasons/{id}/leaderboard`.

## 6. Lifetime-point preservation (critical, no double-count)
With nightly retired, the **event check-in** now also awards the legacy **+10 lifetime** to `users.points`, via a **separate ledger key** `lifetime_checkin:{event}:{user}` (distinct from the event/season key `checkin:{event}:{user}`). Because the legacy `/checkin/{code}` is now gated off, only ONE path awards lifetime +10 → no double-count. Idempotent per (event,user). Verified: lifetime +10 once, unchanged on duplicate check-in, exactly one lifetime ledger row. Lifetime is never reset by the annual season reset.

## 7. QR transition
Legacy calendar-night QR disabled; event QR authoritative. Re-verified (test_phase2_qr / test_phase3 suites): event-specific QR, expiry (per venue/location tz), nonce/revocation, tamper rejection, duplicate-checkin prevention, participation creation, and event+season(+lifetime) awards.

## 8. Nightly reset/champion transition
Nightly auto-reset/champion no longer runs (its host endpoint is gated off). The **annual season reset** (Jan 2, via cron `/api/cron/season-reset`) is the only reset: rank→Peasant, season points→0, season badges/accomplishments/streak reset, previous season archived, champion recorded. Lifetime points are NOT reset. (Distinct mechanisms — verified in test_phase5.)

## 9. Migration
No destructive migration. All Step-2..6 migrations are additive/idempotent/reversible/dry-run-by-default. Legacy historical records remain for audit/rollback. (No new migration required for Step 6 — it is pure flag gating + one additive lifetime award path.)

## 10. Rollback mechanism
Set `LEGACY_NIGHTLY_ENABLED=true` and `LEGACY_QR_ENABLED=true` in `backend/.env` and restart backend → legacy nightly QR/check-in/leaderboard/reset immediately active again (code never removed). The event check-in's extra lifetime award auto-disables when nightly is re-enabled (guarded by the flag) so lifetime is never double-awarded during rollback.

## 11. Test results
Full suite green after updating the (now-intentional) legacy assertions to expect 403:
- `test_phase2_models` 12, `test_phase2_qr` 11, `test_phase3` 13, `test_phase4` 11, `test_phase5` 12, `test_phase5b` 6 → **65** local, all passing (plus testing_agent suites from prior steps).
- Explicit Step 6 checks (curl): legacy `venue/qr-data`, `checkin/{code}`, `leaderboard/tonight` → **403**; `/leaderboard`, `/seasons/current/leaderboard`, `/admin/events` → **200**. Event check-in awards event+season+lifetime once; duplicate awards nothing.

## 12. Full regression
Login, register, all-time leaderboard, badges (28), battles, admin, event QR/check-in/singer-list/queue/perks, season points/leaderboards, season reset, cron — all pass. Legacy `checkins`/`queue` collections intact and unmodified.

## 13. Frontend impact (identified — NOT silently broken; minimal-change policy honored)
These existing screens call now-retired endpoints and will show errors until redirected (deferred UI task — no redesign in Step 6):
- `pages/QRCheckInPage.js` → `GET /venue/qr-data` (403). Redirect to admin event-QR flow (`GET /api/admin/events` + `/api/events/{id}/qr`).
- `pages/CheckInPage.js` (`/checkin/:venueCode`) → `POST /checkin/{code}` (403). Redirect to event check-in (`POST /api/events/checkin`).
- `pages/LeaderboardPage.js` → `GET /leaderboard/tonight` (403) for the "Tonight" tab. Point it at `/api/seasons/current/leaderboard` (or an event leaderboard).
- `hooks/useVoteNotification.js` → cosmetic `nightly_points` reference in a toast.
The all-time leaderboard tab and lifetime-points UI continue to work unchanged.

## 14. Remaining risks / decisions requiring approval
1. **Frontend redirect**: approve a minimal, surgical UI pass to point the 3 screens above at the event/season endpoints (no redesign), or keep `LEGACY_NIGHTLY_ENABLED=true` in the current deployment until that UI pass lands? (Retirement is flag-controlled, so this is a rollout choice.)
2. **Nightly Champion history**: past nightly champion badges remain on `users.badges`; confirm no migration needed.
3. Confirm Step 7 will handle final code cleanup (remove legacy code paths only after acceptance) + venue/KJ roles + the deferred items (cron rate-limit, ledger janitor, lifespan migration, transactions, server.py extraction).

## 15. Files changed
`backend/server.py` (LEGACY_NIGHTLY_ENABLED flag + 403 gates on venue/qr-data, checkin/{code}, leaderboard/tonight; event check-in lifetime award) · `backend/phase2_seasons.py` (award_ledger `to_lifetime`) · `backend/.env` (LEGACY_QR_ENABLED=false, LEGACY_NIGHTLY_ENABLED=false) · updated legacy-assertion tests in `test_phase5.py`/`test_phase3.py`/`test_phase2_qr.py` · `backend/test_phase5b.py` (lifetime-on-checkin assertion). **No frontend changes (impact documented above).**

## 16. Next (Step 7 — Roles, Isolation & Hardening + final cleanup) — NOT STARTED
Approval-gated.
