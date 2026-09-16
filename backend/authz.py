"""
Phase 2, Step 7b — Isolation enforcement (authorization decisions).

Pure, side-effect-free authorization helpers built on the Step 7a role model. The
resource (event dict) is ALWAYS loaded from the DB by the caller and passed in — we
NEVER trust a client-supplied location_id / venue_id / event_id for the decision; the
event's real venue_id / location_id come from the stored document.

Access model:
  - global_admin      -> unrestricted (all locations/venues/events).
  - location_manager  -> only events whose location_id ∈ role_scope.location_ids.
  - venue_kj          -> only events whose venue_id ∈ role_scope.venue_ids.
  - singer            -> NOT staff; denied every staff/admin action. Participatory
                         reads/self-writes on an event are allowed (require_event_view).

Denials raise HTTPException(403) with a generic message and never echo resource data.
"""
from fastapi import HTTPException

import roles


def _scope(user: dict) -> dict:
    return roles.get_role_scope(user)


def is_staff(user: dict) -> bool:
    return roles.resolve_role(user) in roles.STAFF_ROLES


def staff_can_access_event(user: dict, event: dict) -> bool:
    """True iff a STAFF user is in scope for this event. Singers are never staff -> False."""
    role = roles.resolve_role(user)
    if role == roles.ROLE_GLOBAL_ADMIN:
        return True
    sc = _scope(user)
    if role == roles.ROLE_LOCATION_MANAGER:
        return event.get("location_id") in sc["location_ids"]
    if role == roles.ROLE_VENUE_KJ:
        return event.get("venue_id") in sc["venue_ids"]
    return False


def require_event_staff(user: dict, event: dict) -> None:
    """Staff-only, scope-checked event action. Singers -> 403 (as before Step 7b)."""
    if not staff_can_access_event(user, event):
        raise HTTPException(status_code=403, detail="Not authorized for this event")


def require_event_view(user: dict, event: dict) -> None:
    """Participatory read / self-write: singers allowed; staff must be in scope."""
    if roles.resolve_role(user) == roles.ROLE_SINGER:
        return
    require_event_staff(user, event)


def require_global_admin(user: dict) -> None:
    """Platform-wide staff action (season list/reset). Only global_admin."""
    if roles.resolve_role(user) != roles.ROLE_GLOBAL_ADMIN:
        raise HTTPException(status_code=403, detail="Global admin access required")


def require_staff(user: dict) -> None:
    if not is_staff(user):
        raise HTTPException(status_code=403, detail="Staff access required")


def events_scope_query(user: dict) -> dict:
    """Mongo filter restricting an events listing to the caller's scope.
    global_admin -> {} (all). location_manager/venue_kj -> scoped. singer -> match none."""
    role = roles.resolve_role(user)
    if role == roles.ROLE_GLOBAL_ADMIN:
        return {}
    sc = _scope(user)
    if role == roles.ROLE_LOCATION_MANAGER:
        return {"location_id": {"$in": sc["location_ids"]}}
    if role == roles.ROLE_VENUE_KJ:
        return {"venue_id": {"$in": sc["venue_ids"]}}
    return {"id": {"$in": []}}
