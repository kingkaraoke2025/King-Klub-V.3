# Phase 2 — Step 1 Results (Data Model Foundation)

Status: **COMPLETE — awaiting approval to proceed to Step 2.**
Principle: purely additive. `server.py` and all frontend files are UNCHANGED. No event-scoped
QR / check-in / queue / points / leaderboard / role / WebSocket behavior implemented (those are later steps).
Existing `points`, `nightly_points`, `current_night`, QR, check-in, queue, and leaderboard systems are fully intact.

---

## 1. Exact schema / model changes
New canonical Pydantic models in `backend/models_phase2.py` (UUID-string `id` convention, matching the existing codebase — no ObjectId exposed). Each has `to_mongo()` / `from_mongo()` helpers. **No changes to the `users` model or any existing model.**

Models: `Location`, `Venue`, `Event`, `EventParticipation` + enums `EventStatus` (draft/scheduled/active/ended/archived) and `ParticipationStatus` (registered/checked_in/active/left).

## 2. New collections & fields

### `locations`
`id`(uuid) · `name` · `slug` · `city` · `state` · `country` · **`timezone`** (per-location IANA — removes the hardcoded single-tz assumption) · `active` · `is_sample` · `is_default_legacy` · `env` · `created_at` · `updated_at`

### `venues`
`id` · **`location_id`** (→ locations.id) · `name` · `slug` · `address` · `timezone` (nullable → inherits location) · `active` · `is_sample` · `is_default_legacy` · `env` · `created_at` · `updated_at`

### `events`
`id` · **`venue_id`** (→ venues.id) · **`location_id`** (denormalized) · `name` · `slug` · **`event_date`** (YYYY-MM-DD, venue-local) · **`status`** (EventStatus) · `starts_at` · `ends_at` · `qr_secret` (reserved for Step 2, unused now) · `is_sample` · `is_default_legacy` · `env` · `created_at` · `updated_at`

### `event_participation`  (singer × event join — the history record)
`id` · **`user_id`** (→ users.id) · **`event_id`** (→ events.id) · **`venue_id`** (denormalized) · **`location_id`** (denormalized) · `event_points` · `songs_performed` · `badges_earned[]` · `list_position` · `status` (ParticipationStatus) · `checked_in_at` · `created_at` · `updated_at`

## 3. Relationships between entities
```
users (persistent global singer profile — UNCHANGED)
   └─(user_id)─┐
Location 1──*  Venue 1──*  Event 1──*  EventParticipation ──(user_id)── users
   (location_id)   (venue_id)     (event_id + denormalized venue_id/location_id)
```
- A **singer/user is persistent and independent** of any venue/event; participation links them per event.
- **EventParticipation preserves per-event history** and never overwrites the global profile.
- Denormalized `venue_id`/`location_id` on events & participation allow fast, safe scoping so **Venue A and Venue B activity/leaderboards never mix**.

### Information layers (clearly separated)
| Layer | Where it lives |
|---|---|
| **Global lifetime** singer info | `users` (points, songs_performed, badges, total_checkins) — unchanged |
| **Location-specific** | `locations` + aggregates over `event_participation.location_id` |
| **Venue-specific** | `venues` + aggregates over `event_participation.venue_id` |
| **Event-specific** | `events` + `event_participation` (event_points, list_position, per-event songs/badges) |

## 4. Indexes / uniqueness constraints (owned by migration 0001)
- **locations**: `uniq_id`(unique), `uniq_slug`(unique), `uniq_name`(unique), `active`
- **venues**: `uniq_id`(unique), `location_id`, **`uniq_location_slug`(unique on location_id+slug)** → same venue slug allowed in different locations, blocked within one
- **events**: `uniq_id`(unique), `venue_id`, `location_id`, `status`, `event_date`, **`uniq_venue_date_slug`(unique on venue_id+event_date+slug)**
- **event_participation**: `uniq_id`(unique), **`uniq_user_event`(unique on user_id+event_id)** → one participation per singer per event, `user_id`, `event_id`, `venue_id`, `location_id`, `event_leaderboard`(event_id+event_points desc), `venue_user`, `location_user`

## 5. Migration details — `backend/migrations/0001_phase2_data_model.py`
- **Additive**: only adds fields to new-collection docs, creates indexes, and creates a Default-Legacy hierarchy. Touches **no** legacy user/checkin/queue/points/settings data.
- **Idempotent**: verified — re-running `up` produces no normalize/create actions (only re-asserts indexes).
- **Logged**: every action written to `migrations_log` collection + stdout (4 log entries so far).
- **Reversible**: `--down` removes only `is_default_legacy` docs and drops the indexes it created; verified by full down→up cycle.
- **Default-Legacy hierarchy** created as the future backfill target for pre-Phase-2 records: Location "Legacy — Unassigned" → Venue "Legacy Venue" → Event "Legacy Historical Activity" (status archived, `is_default_legacy=true`, `env="system"`). No legacy data is linked to it yet (that is Step 3).

## 6. Tests performed & results
`backend/test_phase2_models.py` — **12/12 passed** (pytest, xdist). Coverage:
- slugify + auto-slug generation; `to_mongo`/`from_mongo` round-trip (strips `_id`); participation defaults
- hierarchy relationships (location→venue→event links incl. denormalized location_id)
- multiple venues per location; **multiple simultaneous active events** (no singleton)
- unique venue slug per location; **same slug allowed across different locations**
- unique event per (venue, date, slug); **unique participation per (user, event)**
- **singer isolation across venues**: same singer at Venue A (30 pts) & Venue B (70 pts) → two isolated participations, venue-scoped queries return only that venue's rows

Migration idempotency and down/up reversibility: **verified**.

## 7. Confirmation existing functionality still works
Post-Step-1 regression (live backend): health ✅ · dev-admin login ✅ · leaderboard ✅ · badges (28) ✅ · **admin QR generation** ✅ · stats ✅. No `server.py`/frontend changes; behavior identical to Step 0. (Transient night session created by the QR test was cleared afterward.)

## 8. Files added/changed in Step 1
- `backend/models_phase2.py` — NEW (models only; not yet imported by server.py)
- `backend/migrations/0001_phase2_data_model.py` — NEW (idempotent/reversible migration)
- `backend/test_phase2_models.py` — NEW (12 tests)
- `memory/PHASE2_STEP1_RESULTS.md` — this doc
- **No changes to `server.py` or any frontend file.**

## 9. Risks / design decisions needing your approval
1. **Event `slug` uniqueness key = (venue_id, event_date, slug)** with default slug derived from the event name (fallback `main`). This allows multiple events per venue per day only if they have different names/slugs. ➜ Approve, or do you want a different natural key (e.g. allow duplicate names, key on a session number/time instead)?
2. **`event_points` as an integer per participation** (mirrors current point granularity). ➜ OK, or do you foresee needing fractional/decayed points?
3. **Location/Venue/Event soft-state via `active`/`status`** rather than hard deletes. ➜ Confirm soft-deactivation is the desired lifecycle.
4. **Default-Legacy container created now** (empty, unlinked). Backfill of real legacy check-ins/queue into it is deferred to Step 3 as planned. ➜ Confirm this is the right place to draw the line.
5. **`users` collection left untouched** — no `home_location_id` or per-user default venue added yet. If singers should have a "home location", that's a small additive field I can add in a later step. ➜ Do you want a home-location concept?
6. **Unique index on `users.email`/`users.id`** (added Step 0) would reject a future production import containing duplicate emails. ➜ Flagged for the eventual prod-data import/migration step.

---

## 10. Next (Step 2 — Event-Scoped QR) — NOT STARTED
Awaiting your approval. Nothing further will be built until you approve.
