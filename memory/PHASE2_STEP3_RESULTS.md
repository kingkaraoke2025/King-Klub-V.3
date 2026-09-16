# Phase 2 — Step 3 Results (Scope Check-ins & Singer Lists)

Status: **COMPLETE — awaiting approval to proceed to Step 4.**
Independent verification: testing_agent **30/30 passed, no issues** (`/app/test_reports/iteration_6.json`).
Principle: additive. Legacy date-based check-in preserved & unchanged. No event-scoped points / queue / leaderboard / WebSocket behavior (later steps).

---

## 1. Schema changes
No new collections. The existing `event_participation` (from Step 1) is now populated by event check-ins and serves as the **per-event singer list**. Fields written per check-in:
`id, user_id, event_id, venue_id (denorm), location_id (denorm), checked_in_at, status="checked_in", list_position, songs_performed(0), event_points(0), badges_earned([]), created_at, updated_at`.
- **The user profile is NOT duplicated** — only `user_id` is stored; `display_name` is joined at read time.
- New index (migration 0003): `event_participation (event_id, list_position)` for deterministic ordered reads.
- Uniqueness `event_participation (user_id, event_id)` (from Step 1) enforces one participation per singer per event.
- Backfilled records are tagged `is_backfill=true, source="legacy_backfill", legacy_checkin_count, legacy_dates`.

## 2. API changes
- **`POST /api/events/checkin`** (user, flag-gated) — now, on success, also creates the singer's `event_participation` (via idempotent `_ensure_event_participation`) and returns `list_position` + `participation_id`. Flow: **QR → token validation → event resolution → EventParticipation → singer list**. No points awarded (Step 5).
- **`GET /api/events/{event_id}/singer-list`** (admin, flag-gated) — NEW. Returns singers ordered by `list_position`, with `display_name` joined at read time; includes `status`, `songs_performed`, `event_points`, `checked_in_at`, `is_backfill`, plus `venue_id`/`location_id` for isolation checks.
- Legacy `POST /api/checkin/{venue_code}` and `GET /api/venue/qr-data` unchanged in behavior (still write only to legacy `checkins`).

## 3. Singer-list design
- The singer list **is** `event_participation` filtered by `event_id`.
- **Independent per event**: keyed by `event_id`; a singer only appears in an event's list if they actually checked into that event. Verified: John in A&B, Mary in A only → A={John,Mary}, B={John}.
- **Venue/location isolation**: each row carries denormalized `venue_id`/`location_id`; Venue A activity never surfaces in a Venue B list.
- **Deterministic ordering**: default `list_position` = check-in order (`count+1` at insert). `list_position` is a first-class field reserved for future manual KJ reordering (Step 4+). The `(event_id, list_position)` index keeps reads stable.
- **Minimum fields supported** (per requirements): singer/user id, event id, check-in time, list position, participation status, songs performed, event-specific info (event_points, badges_earned).

## 4. Migration / backfill behavior — `migrations/0003_backfill_legacy_checkins.py`
- Maps every legacy `checkins` record to the **Default-Legacy Location→Venue→Event** (from 0001), creating **one participation + one event_checkin per legacy singer**, marked `is_backfill/source=legacy_backfill`.
- **Writing OFF by default** (dry-run reports counts). Requires `--execute` to write. → No production-style backfill runs without explicit action/approval.
- **Idempotent**: skips singers who already have a participation for the legacy event (re-run creates nothing).
- **Reversible**: `--down` deletes only `is_backfill` participations/checkins.
- **Non-destructive**: the original `checkins` collection is **never modified** (verified by testing_agent).
- Also idempotently ensures the `(event_id, list_position)` index.

## 5. Security
- The event is derived **solely from the signed QR token** — the request body has no trusted `event_id`. Verified: sending an extra `event_id` in the body is ignored (token wins).
- All Step 2 protections still apply (HMAC signature, nonce, expiry). Rejected check-ins (cancelled/expired/not-started/tampered/malformed) create **no** participation.
- Duplicate prevention via unique `(user_id, event_id)` index + pre-check.

## 6. Timezones
- Unchanged from Step 2: expiry honors event → venue → location timezone; participation `checked_in_at` stored in UTC ISO.

## 7. Tests & results
- Local pytest: `test_phase3.py` (13) + `test_phase2_qr.py` (11) + `test_phase2_models.py` (12) = **36/36 passed**.
- Independent testing_agent: **30/30 passed** (`iteration_6.json`), covering: event QR gen (admin-only, 404 unknown), successful check-in + participation, duplicate prevention (single row), singer list ordering + PII-free join, simultaneous-events independence, Mary-not-in-B isolation, venue isolation, cancelled/expired/not-started/tampered/malformed rejected without participation, event-id spoof ignored, legacy check-in writes only to `checkins`, backfill dry-run/idempotent/reversible with legacy untouched.

## 8. Regression results (existing app)
Verified working (testing_agent + local): register, login, legacy QR (`/venue/qr-data` + `/checkin/{code}`), queue, points, nightly leaderboard, all-time leaderboard, badges (28), battles (`/challenges/voting-open`), admin (`/admin/users`, `/admin/events`), stats. Backend boots clean; only additive `server.py` changes; **no frontend changes**; legacy `points`/`nightly_points`/`current_night`/queue/leaderboard untouched. Legacy `checkins` collection unmodified by the new system.

## 9. Files added/changed in Step 3
- `backend/server.py` — event_checkin now creates participation + returns list_position; added `_ensure_event_participation` + `GET /events/{id}/singer-list`; import of `EventParticipation`.
- `backend/migrations/0003_backfill_legacy_checkins.py` — NEW (dry-run default, `--execute`, `--down`).
- `backend/test_phase3.py` — NEW (13 tests).
- `backend/tests/test_phase2_step3_singer_lists.py` — added by testing_agent (30 tests).
- `memory/PHASE2_STEP3_RESULTS.md` — this doc.
- **No frontend changes.**

## 10. Noted recommendations (non-blocking, from code review)
- `server.py` is ~2.95k lines; recommend extracting event/QR/participation logic into a module before Step 4/5.
- Add pagination params to `singer-list` before scale.
- (Optional) return a discriminated result from `parse_event_qr_token` instead of raising inside a helper.

## 11. Next (Step 4 — Scope Queue & Perks) — NOT STARTED
Awaiting your approval. Note: singer-list manual KJ reordering (`list_position`) is a natural fit to fold into Step 4.
