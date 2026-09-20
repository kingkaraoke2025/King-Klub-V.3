"""
Iteration 15 backend hardening tests for KJ permanent-delete rule +
non-disclosing 403 + event_deletion_audit endpoint role scope.
"""
import os
import uuid
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://king-v3-staging.preview.emergentagent.com").rstrip("/") + "/api"

KJ_EMAIL = "kj@kingkaraoke2025.com"
KJ_PW = "Kj!2026"
ADMIN_EMAIL = "dev-admin@kingkaraoke2025.com"
ADMIN_PW = "DevKing!2026"
SINGER_EMAIL = "singer1@kingkaraoke2025.com"
SINGER_PW = "Singer!2026"

KJ_VENUE = "c9a5f1bb-2fd1-4143-97c2-336cb327ab14"
ENDED_ID = "274d1adb-9910-4a8b-895a-dea83ce9fe66"
CANCELLED_ID = "e46bf139-8adb-41a0-b3bb-eb06c9884cd5"
ARCHIVED_ID = "6c242a7e-a92d-4487-8937-ff6f3885972a"
OTHER_VENUE_EVENT = "299a34aa-543c-4dcb-a4f7-7926718251b7"


def _login(email, pw):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def kj_tok():
    return _login(KJ_EMAIL, KJ_PW)


@pytest.fixture(scope="module")
def admin_tok():
    return _login(ADMIN_EMAIL, ADMIN_PW)


@pytest.fixture(scope="module")
def singer_tok():
    return _login(SINGER_EMAIL, SINGER_PW)


def H(t):
    return {"Authorization": f"Bearer {t}"}


# --- Non-disclosing 403 for DELETE /admin/events/{id} ---

def test_delete_random_uuid_returns_403(kj_tok):
    fake = str(uuid.uuid4())
    r = requests.delete(f"{BASE}/admin/events/{fake}", headers=H(kj_tok))
    assert r.status_code == 403, f"Expected 403 for nonexistent id, got {r.status_code} {r.text}"


def test_delete_other_venue_event_returns_403(kj_tok):
    r = requests.delete(f"{BASE}/admin/events/{OTHER_VENUE_EVENT}", headers=H(kj_tok))
    assert r.status_code == 403, f"Expected 403 for cross-venue, got {r.status_code} {r.text}"


def test_singer_delete_returns_403(singer_tok):
    r = requests.delete(f"{BASE}/admin/events/{CANCELLED_ID}", headers=H(singer_tok))
    assert r.status_code == 403


def test_cancelled_event_returns_409(kj_tok):
    r = requests.delete(f"{BASE}/admin/events/{CANCELLED_ID}", headers=H(kj_tok))
    assert r.status_code == 409, f"Cancelled should 409, got {r.status_code} {r.text}"


def test_archived_prev_ended_returns_409(kj_tok):
    r = requests.delete(f"{BASE}/admin/events/{ARCHIVED_ID}", headers=H(kj_tok))
    assert r.status_code == 409, f"Archived should 409, got {r.status_code} {r.text}"


# --- Deletion audit endpoint role scope ---

def test_singer_cannot_read_audit(singer_tok):
    r = requests.get(f"{BASE}/admin/event-deletions", headers=H(singer_tok))
    assert r.status_code == 403


def test_kj_can_read_audit_scoped(kj_tok):
    r = requests.get(f"{BASE}/admin/event-deletions", headers=H(kj_tok))
    assert r.status_code == 200, r.text
    body = r.json()
    assert "deletions" in body
    for row in body["deletions"]:
        assert row.get("venue_id") == KJ_VENUE, f"KJ saw out-of-scope row: {row}"


def test_admin_can_read_audit_all(admin_tok):
    r = requests.get(f"{BASE}/admin/event-deletions", headers=H(admin_tok))
    assert r.status_code == 200, r.text
    body = r.json()
    assert "deletions" in body


# --- Recently-deleted probing check (only meaningful if UI test ran first).
# Marked xfail if ended fixture still exists (pre-UI run).

def test_ended_id_after_deletion_is_403(kj_tok):
    """If UI test already permanently deleted ENDED_ID, this must return 403 (never 404)."""
    r = requests.delete(f"{BASE}/admin/events/{ENDED_ID}", headers=H(kj_tok))
    # If fixture still present + ended, backend would purge now → 200. Accept either 200 (first run) or 403 (already deleted).
    assert r.status_code in (200, 403), f"Expected 200 or 403, got {r.status_code} {r.text}"
    if r.status_code == 200:
        # second call must be 403 not 404
        r2 = requests.delete(f"{BASE}/admin/events/{ENDED_ID}", headers=H(kj_tok))
        assert r2.status_code == 403, f"Post-delete probing must return 403, got {r2.status_code}"
