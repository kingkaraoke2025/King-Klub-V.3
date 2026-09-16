# Phase 2 — Step 4 Results (Scope Queue & Perks)

Status: **COMPLETE — awaiting approval to proceed to Step 5.**
Independent verification: testing_agent **28/28 passed, no issues** (`/app/test_reports/iteration_7.json`).
Principle: additive. Legacy queue/perks preserved & untouched. Event-scoped **complete awards NO points** (points are Step 5).

---

## 1. Schema changes (new collections, additive)
- **`event_queue`** — `id, event_id, venue_id, location_id, user_id, user_name, song_title, artist, message_to_admin, status(pending/current/completed/cancelled), position (per event), estimated_wait, perk_protected, created_at, updated_at`. Backfilled rows also carry `is_backfill, source, legacy_queue_id`.
- **`event_perk_usage`** — `id, user_id, event_id, rank, perk_type, old_position, new_position, used_at`. Unique `(user_id, event_id)` → one perk per singer per event.
- `event_participation.songs_performed` is now incremented on event-song completion; `list_position` is now mutable via KJ reorder.
- Legacy `queue` and `perk_usage` collections are **separate and untouched**.

## 2. Indexes (migration 0004, idempotent)
- `event_queue`: `uniq_id`, `(event_id,status,position)`, `(event_id,user_id)`, `user_id`, `created_at`.
- `event_perk_usage`: `uniq_id`, **`(user_id,event_id)` unique**, `event_id`.

## 3. API changes (new router `phase2_events.py`, prefix `/api`, all flag-gated)
Queue: `POST /events/{id}/queue`, `GET /events/{id}/queue`, `GET /events/{id}/queue/my-status`, `DELETE /events/{id}/queue/{item}`, and admin `.../complete`, `.../set-current`, `.../move-up`, `.../move-down`, `.../reorder`.
Perks: `GET /events/{id}/perk-status`, `POST /events/{id}/use-perk`.
Singer list: admin `POST /events/{id}/singer-list/reorder`.
WebSocket: `@app.websocket("/api/ws/events/{event_id}")` (event room).

## 4. Queue architecture
- Separate `event_queue` collection → complete isolation from the legacy `queue`; every read filters by `event_id`. A song added at Event A can never surface in Event B or in the legacy queue.
- Preserved behaviors, now event-scoped: submission, ordering, positions, drag/reorder, move up/down, complete, cancel, set-current, estimated wait, perk-protected top-4, and the **5-songs/30-minute limit evaluated per (user, event)** using that event's check-in time. Verified: 5 songs at A → 6th rejected, while B still accepts.
- Admin (KJ) actions operate strictly on the target `event_id`; another event's positions are never touched.

## 5. Perk behavior
- Perk eligibility derives from the singer's **global** rank/profile (unchanged), but **usage is recorded per event** in `event_perk_usage` (unique `user_id+event_id`). Using a perk at Event A does not consume it at Event B; a second use at the same event is rejected. Perk moves only reorder that event's queue and set `perk_protected` for top‑4.

## 6. Singer-list reorder behavior
- Default order = check-in order (from Step 3). Admin `singer-list/reorder {user_id, new_position}` updates only `list_position` **within that event**, shifting neighbors in the same event; it never alters `checked_in_at` and never affects another event. Non-admin → 403. Changes persist; simultaneous events keep independent positions.

## 7. WebSocket isolation behavior
- `ConnectionManager` now has per-event rooms (`connect_event`/`disconnect_event`/`broadcast_event`). Clients subscribe via `/api/ws/events/{event_id}`. All event queue/perk/singer-list updates use `broadcast_event(event_id, …)`, delivered **only** to that event's room — verified no Event‑A update reaches an Event‑B subscriber. The legacy global `/api/ws` remains for legacy features (battles, legacy queue). **No known cross-venue data-leak path in the new event queue.**

## 8. Migration strategy (legacy queue → event model)
- `migrations/0004_event_queue.py`: ensures indexes; **dry-run by default** (needs `--execute`); maps legacy `queue` rows to `event_queue` under the **Default-Legacy event**, marked `is_backfill/source=legacy_backfill/legacy_queue_id`; **idempotent** (skips already-mapped rows); **reversible** (`--down` removes only `is_backfill` rows); the original `queue` collection is **never modified**. No production-style backfill runs without explicit `--execute`.

## 9. Tests & results
- Local pytest: `test_phase4.py` (11) + prior phases (36) = **47/47 passed**.
- testing_agent: **28/28 passed** (`iteration_7.json`) — queue add/isolation, independent queueing, per-event 5/30 limit, admin ops scoped, perks (unique per event, no leak, 2nd-use 400), singer-list reorder (list_position only, timestamps preserved, other event untouched, 403 for non-admin), authorization 403s, **WebSocket room isolation (EVENT_QUEUE_UPDATED only to matching socket)**, legacy queue intact, migration dry-run/idempotent/reversible with legacy untouched.

## 10. Regression results
Verified: register, login, legacy QR (`/venue/qr-data`, `/checkin/{code}`), legacy check-in, existing queue, points, nightly leaderboard, all-time leaderboard, badges (28), battles, admin (`/admin/users`, `/admin/events`), event QR, event check-in, event singer lists. Backend boots clean; `server.py` changes limited to ConnectionManager rooms + WS endpoint + router mount; **no frontend changes**.

## 11. Authorization limitation (as requested — documented, deferred to Step 7)
The current model has a single global `is_admin` flag: **any** admin can operate **any** event's queue/singer-list. Venue/KJ-scoped permissions are NOT implemented in Step 4 — this is deferred to **Step 7 (Roles & Isolation)**. Non-admin users are correctly rejected (403) from all admin event actions.

## 12. Risks / decisions requiring approval
1. **Admin scope is global** (above) — confirm it's acceptable until Step 7.
2. **No UI added** — Step 4 is backend-only; the existing frontend still uses the legacy queue. Confirm we defer event-queue UI (an admin event console) to a later step.
3. **Event `complete` awards no points** by design (Step 5). Confirm.
4. Non-blocking hardening noted by code review (not applied, to avoid changing just-verified code): add a Mongo transaction/session to `reorder`/`use-perk` for concurrency safety; symmetric perk-protected guard on move-down; `Field(max_length=250)` on `message_to_admin`; pagination on queue/singer-list reads. ➜ Want any of these folded into a later step?

## 13. Code organization (per your point 13)
Performed a **small, low-risk extraction**: all new event-scoped logic lives in `backend/phase2_events.py` (its own router, dependencies injected). Legacy code in `server.py` was not rewritten. `server.py` is ~2,999 lines; a larger split of legacy queue/battles/admin is recommended before Step 5/6 but intentionally NOT done now to avoid regression risk.

## 14. Files added/changed in Step 4
- `backend/phase2_events.py` — NEW event-scoped router (queue/perks/singer-list reorder).
- `backend/server.py` — ConnectionManager event rooms + `broadcast_event`; new `/api/ws/events/{event_id}`; mount event router.
- `backend/migrations/0004_event_queue.py` — NEW (indexes + legacy-queue backfill; dry-run default).
- `backend/test_phase4.py` — NEW (11 tests). `backend/tests/test_phase2_step4_event_queue.py` — added by testing_agent (28).
- `memory/PHASE2_STEP4_RESULTS.md` — this doc.
- **No frontend changes.**

## 15. Next (Step 5 — Event-Scoped Points & Leaderboards) — NOT STARTED
Awaiting your approval.
