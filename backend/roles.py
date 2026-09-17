"""
Phase 2, Step 7a — Role model (pure, non-enforcing resolvers).

Roles are resolved from the user's CURRENT database record (users.role /
users.role_scope), never from the JWT. This is the single source of truth used
by authz.py to make isolation decisions.

  - global_admin      -> unrestricted (all locations/venues/events)
  - location_manager  -> scoped to role_scope.location_ids
  - venue_kj          -> scoped to role_scope.venue_ids
  - singer            -> not staff

Legacy compatibility: a user without an explicit `role` but with is_admin==True
resolves to global_admin; everyone else resolves to singer (matches migration
0007 mapping so behaviour is identical before and after the migration runs).
"""

ROLE_GLOBAL_ADMIN = "global_admin"
ROLE_LOCATION_MANAGER = "location_manager"
ROLE_VENUE_KJ = "venue_kj"
ROLE_SINGER = "singer"

STAFF_ROLES = {ROLE_GLOBAL_ADMIN, ROLE_LOCATION_MANAGER, ROLE_VENUE_KJ}
ALL_ROLES = {ROLE_GLOBAL_ADMIN, ROLE_LOCATION_MANAGER, ROLE_VENUE_KJ, ROLE_SINGER}

DEFAULT_SCOPE = {"location_ids": [], "venue_ids": []}


def resolve_role(user: dict) -> str:
    """Resolve the caller's role from their current DB record (never the JWT)."""
    user = user or {}
    role = user.get("role")
    if role in ALL_ROLES:
        return role
    # Legacy fallback: pre-migration users only have is_admin.
    return ROLE_GLOBAL_ADMIN if user.get("is_admin") else ROLE_SINGER


def get_role_scope(user: dict) -> dict:
    """Return {'location_ids': [...], 'venue_ids': [...]} from the DB record."""
    scope = (user or {}).get("role_scope") or {}
    return {
        "location_ids": list(scope.get("location_ids", [])),
        "venue_ids": list(scope.get("venue_ids", [])),
    }
