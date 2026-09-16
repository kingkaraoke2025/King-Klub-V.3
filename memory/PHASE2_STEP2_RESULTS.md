# Phase 2 — Step 2 Results (Event-Scoped QR)

Status: **COMPLETE — awaiting approval to proceed to Step 3.**
Principle: additive. Legacy date-based QR preserved behind a feature flag. No event-scoped
points / queue / leaderboard / WebSocket behavior implemented (later steps).

---

## 1. QR / token design
- **Opaque, HMAC-signed, expiring token.** Format: `base64url(payload).base64url(HMAC_SHA256(payload))`.
- **Payload carries only non-sensitive data**: `{ eid: <event_id>, n: <rotation nonce>, exp: <unix ts UTC> }`. No venue/location details, no user data, no secrets.
- **Signature** uses server-side `EVENT_QR_SECRET` (48-byte urlsafe). Tokens are non-guessable and tamper-evident (`hmac.compare_digest`).
- **Rotation-ready**: each event has a server-only `qr_nonce`; a token is valid only while its `n` matches the event's current nonce. Rotating the nonce instantly invalidates old QRs (wired for Step 7's optional periodic refresh).
- **Event-binding = venue/location-binding**: the token resolves to exactly one `event_id`, and an event is immutably tied to its `venue_id` + `location_id`. So a Venue A token can never resolve to Venue B.

## 2. API changes (all under `/api`, additive)
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/events/{event_id}/qr` | admin | Generate the signed event QR token (sets nonce if absent); returns token, `checkin_url`, `expires_at_utc`, `expires_at_local`, tz, venue/location names. Gated by `EVENT_QR_ENABLED`. |
| POST | `/events/checkin` | user | Validate token + record event-scoped check-in. Body `{ "token": "..." }`. Gated by `EVENT_QR_ENABLED`. |
| GET | `/admin/events` | admin | Read-only list of events with venue/location names (supports the future QR UI). |

Legacy endpoints unchanged in contract, now flag-guarded:
- `GET /api/venue/qr-data` and `POST /api/checkin/{venue_code}` → return **403** only if `LEGACY_QR_ENABLED=false`; otherwise behave exactly as before.

## 3. Database changes (additive)
- New collection **`event_checkins`**: `id, user_id, event_id, venue_id, location_id, checked_in_at`.
  Indexes (migration 0002): `uniq_id`, **`uniq_user_event` (unique user_id+event_id → duplicate guard)**, `event_id`, `venue_id`, `location_id`.
- New collection **`event_checkin_attempts`** (audit trail): `id, user_id, event_id, token_prefix, result(success|duplicate|rejected), reason, at`.
  Indexes: `uniq_id`, `event_id`, `user_id`, `at`.
- `events` gains a lazily-set server-only field **`qr_nonce`** (never returned by `/admin/events`).
- Enum `EventStatus` gains **`cancelled`** (models_phase2.py).
- Migration `backend/migrations/0002_event_qr.py`: additive · idempotent (verified) · logged (`migrations_log`) · reversible (`--down` drops only its indexes, never data — verified down→up).

## 4. Security considerations
- HMAC-SHA256 signature over the payload; constant-time comparison; tampered/malformed tokens → 400.
- Secret stored in env (`EVENT_QR_SECRET`), never in the QR.
- QR contains no PII and no venue/location strings — only an opaque event id + nonce + expiry.
- Nonce enables instant server-side revocation/rotation without redeploying.
- Duplicate check-ins prevented by a unique DB index (authoritative) plus a pre-check.
- Every check-in attempt (success/duplicate/rejected + reason) is logged for audit.
- Defense-in-depth: expiry enforced both from the signed token AND recomputed server-side from the event.

## 5. Expiration / timezone behavior
- Expiry respects the **event's own timezone** (`venue.timezone` → else `location.timezone` → else global `VENUE_TIMEZONE`). No reliance on the global America/Chicago.
- If `event.ends_at` is set, that is the expiry. Otherwise the window closes at **04:00 local, the day after `event_date`** (mirrors legacy cutoff but per-venue).
- Verified: same `event_date` with no `ends_at` yields a **3-hour UTC gap** between an America/New_York event and an America/Los_Angeles event (EDT vs PDT).

### Event lifecycle at check-in (clearly defined)
| Event status / state | Check-in result |
|---|---|
| `active` | ✅ allowed |
| `scheduled` with `starts_at` in future | ❌ 400 "has not started yet" |
| `scheduled` (started) | ✅ allowed |
| `draft` | ❌ 400 "not open for check-in yet" |
| `cancelled` | ❌ 403 "event has been cancelled" |
| `ended` / `archived` | ❌ 400 "event has ended" |
| past expiry (token or server-computed) | ❌ 400 "QR code has expired" |
| nonce rotated / mismatch | ❌ 400 "QR code is no longer valid" |
| QR generation for cancelled/ended event | ❌ blocked at `/events/{id}/qr` |

## 6. Feature flag behavior
- `EVENT_QR_ENABLED` (default `false`; set `true` here): gates the new `/events/{id}/qr` and `/events/checkin` endpoints (403 when off).
- `LEGACY_QR_ENABLED` (default `true`): keeps the legacy date-QR fully working; set `false` later (after new system verified) to retire it without code removal.
- Both systems currently run **in parallel** — nothing removed or broken.

## 7. Tests & results
`backend/test_phase2_qr.py` (live backend) + `backend/test_phase2_models.py` → **23/23 passed**.
QR coverage: correct-event routing · Venue A token can't hit Venue B · expired rejected · cancelled rejected · ended rejected · not-started rejected · duplicate rejected · two simultaneous events → independent tokens & check-ins · NY vs LA timezone gap · tampered/malformed token rejected · legacy QR still works while flag enabled.
Migration 0002 idempotency + reversibility: verified.

## 8. Regression results (existing app)
Live checks pass: health · dev-admin login · **legacy QR (`/venue/qr-data`)** · leaderboard · badges (28) · `/admin/events`. Backend boots clean. Only additive changes to `server.py` (new endpoints, flags, one pre-existing bare-`except` lint fix); **no frontend changes**; legacy `points`/`nightly_points`/`current_night`/queue/leaderboard untouched.

## 9. Files added/changed in Step 2
- `backend/server.py` — added event-QR config/flags, helper fns, 3 endpoints, legacy flag guards; fixed 1 pre-existing bare-except.
- `backend/models_phase2.py` — added `EventStatus.cancelled`.
- `backend/migrations/0002_event_qr.py` — NEW.
- `backend/test_phase2_qr.py` — NEW (11 QR tests).
- `backend/.env` — added `EVENT_QR_SECRET`, `EVENT_QR_ENABLED=true`, `LEGACY_QR_ENABLED=true`.
- `memory/PHASE2_STEP2_RESULTS.md` — this doc.
- **No frontend changes.**

## 10. Notes / for your awareness
- `/events/checkin` deliberately does **not** award points, add to a singer list, touch the queue, or emit WebSocket events yet — that is Step 3+ per your sequencing.
- No frontend QR-scan UI was added (backend-only step); the existing QR pages continue to use the legacy flow.

## 11. Next (Step 3 — Scope Check-ins & Singer Lists) — NOT STARTED
Awaiting your approval.
