"""API-level acceptance tests for KJ delete-ended-event rule (iteration 14)."""
import os
import requests
import pytest

BASE = os.environ.get('REACT_APP_BACKEND_URL', 'https://king-v3-staging.preview.emergentagent.com').rstrip('/')

VENUE_ID = 'c9a5f1bb-2fd1-4143-97c2-336cb327ab14'
ENDED_ID = '7047ceb4-107e-4fb8-bf4a-92dc94d26f8e'
CANCELLED_ID = '61529bf5-d2a7-452e-a4a9-df9eb68e5220'
ARCHIVED_ID = '2243af01-fe06-4d14-b128-8a8d376742a5'
OTHER_VENUE_EVENT = '299a34aa-543c-4dcb-a4f7-7926718251b7'

KJ = ('kj@kingkaraoke2025.com', 'Kj!2026')
ADMIN = ('dev-admin@kingkaraoke2025.com', 'DevKing!2026')
SINGER = ('singer1@kingkaraoke2025.com', 'Singer!2026')


def login(email, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    return r.json().get('access_token') or r.json().get('token')


@pytest.fixture(scope='module')
def kj_token():
    return login(*KJ)


@pytest.fixture(scope='module')
def admin_token():
    return login(*ADMIN)


@pytest.fixture(scope='module')
def singer_token():
    return login(*SINGER)


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


def get_event(admin_token, event_id):
    """Return event dict via admin list or None."""
    r = requests.get(f"{BASE}/api/admin/events", headers=hdr(admin_token))
    if r.status_code != 200:
        return None
    for ev in r.json():
        if ev.get('id') == event_id:
            return ev
    return None


def test_seeded_events_present(admin_token):
    assert get_event(admin_token, ENDED_ID) is not None, "Ended seed missing - reseed needed"
    assert get_event(admin_token, CANCELLED_ID) is not None, "Cancelled seed missing"
    assert get_event(admin_token, ARCHIVED_ID) is not None, "Archived seed missing"
    assert get_event(admin_token, OTHER_VENUE_EVENT) is not None, "Other venue event missing"


def test_singer_cannot_delete_ended(singer_token, admin_token):
    r = requests.delete(f"{BASE}/api/admin/events/{ENDED_ID}", headers=hdr(singer_token))
    assert r.status_code == 403, f"singer got {r.status_code}"
    assert get_event(admin_token, ENDED_ID) is not None


def test_kj_cannot_delete_other_venue_ended(kj_token, admin_token):
    r = requests.delete(f"{BASE}/api/admin/events/{OTHER_VENUE_EVENT}", headers=hdr(kj_token))
    assert r.status_code == 403, f"cross-venue got {r.status_code}"
    assert get_event(admin_token, OTHER_VENUE_EVENT) is not None


def test_kj_cannot_delete_cancelled_returns_409(kj_token, admin_token):
    r = requests.delete(f"{BASE}/api/admin/events/{CANCELLED_ID}", headers=hdr(kj_token))
    # Cancelled has history => 409 archive fallback
    assert r.status_code in (409, 400), f"cancelled got {r.status_code} {r.text}"
    assert get_event(admin_token, CANCELLED_ID) is not None


def test_kj_cannot_delete_archived(kj_token, admin_token):
    r = requests.delete(f"{BASE}/api/admin/events/{ARCHIVED_ID}", headers=hdr(kj_token))
    assert r.status_code in (409, 400), f"archived got {r.status_code} {r.text}"
    assert get_event(admin_token, ARCHIVED_ID) is not None


def test_inactive_kj_cannot_delete_ended(admin_token, kj_token):
    """Revoke KJ staff, verify 403, then re-grant."""
    # find kj user id
    r = requests.get(f"{BASE}/api/admin/users", headers=hdr(admin_token))
    assert r.status_code == 200
    kj_user = next((u for u in r.json() if u.get('email') == KJ[0]), None)
    assert kj_user, "kj user not found"
    uid = kj_user['id']
    # revoke
    rr = requests.put(f"{BASE}/api/admin/users/{uid}/staff", headers=hdr(admin_token),
                     json={"staff_active": False, "role": "venue_kj",
                           "role_scope": {"venue_id": VENUE_ID}})
    assert rr.status_code == 200, rr.text
    try:
        r2 = requests.delete(f"{BASE}/api/admin/events/{ENDED_ID}", headers=hdr(kj_token))
        assert r2.status_code == 403, f"inactive KJ got {r2.status_code}"
        assert get_event(admin_token, ENDED_ID) is not None
    finally:
        # re-grant
        requests.put(f"{BASE}/api/admin/users/{uid}/staff", headers=hdr(admin_token),
                    json={"staff_active": True, "role": "venue_kj",
                          "role_scope": {"venue_id": VENUE_ID}})


# NOTE: intentionally NOT deleting the ended event here — the frontend E2E does it.
