"""Core ACL check logic: wildcard matching, club expansion, DENY-priority ruling."""
from datetime import datetime, timezone

import httpx

from .config import settings
from .db import get_conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wildcard_resource(resource: str) -> str | None:
    """Return the wildcard form of a resource, e.g. drop:file:abc -> drop:file:*"""
    parts = resource.split(":")
    if len(parts) == 3 and parts[2] != "*":
        return f"{parts[0]}:{parts[1]}:*"
    return None


def _get_clubs_for_subject(subject: str) -> list[str]:
    """Query hivo-club for all clubs the subject belongs to."""
    if not subject.startswith("agt_"):
        return []
    try:
        # We call club service with the subject's identity — but ACL has no token for the subject.
        # The club service exposes GET /me/clubs which requires Bearer.
        # For internal service-to-service calls, we use a special internal query:
        # GET /internal/members/{sub}/clubs — defined in hivo-club for ACL use.
        url = f"{settings.club_url}/internal/members/{subject}/clubs"
        resp = httpx.get(url, timeout=3)
        if resp.status_code == 200:
            return [c["club_id"] for c in resp.json()]
    except Exception:
        pass
    return []


def _collect_rules(conn, subject: str, resource: str, action: str) -> list[dict]:
    """Collect all matching grant rows for (subject, resource, action)."""
    wildcard = _wildcard_resource(resource)
    rows = []

    # Exact match
    cur = conn.execute(
        "SELECT effect FROM grants WHERE subject=? AND resource=? AND action=?",
        (subject, resource, action),
    )
    rows.extend(dict(r) for r in cur.fetchall())

    # Wildcard match
    if wildcard:
        cur = conn.execute(
            "SELECT effect FROM grants WHERE subject=? AND resource=? AND action=?",
            (subject, wildcard, action),
        )
        rows.extend(dict(r) for r in cur.fetchall())

    return rows


def check_permission(subject: str, resource: str, action: str) -> bool:
    """Return True if subject is allowed to perform action on resource."""
    with get_conn() as conn:
        rules = _collect_rules(conn, subject, resource, action)

        # Expand clubs
        clubs = _get_clubs_for_subject(subject)
        for club_id in clubs:
            rules.extend(_collect_rules(conn, club_id, resource, action))

        if not rules:
            return False

        # DENY wins
        if any(r["effect"] == "deny" for r in rules):
            return False

        return any(r["effect"] == "allow" for r in rules)


def has_admin_on_resource(conn, caller_sub: str, resource: str) -> bool:
    """Check if caller has admin grant on the resource (for grant management)."""
    rows = _collect_rules(conn, caller_sub, resource, "admin")
    clubs = _get_clubs_for_subject(caller_sub)
    for club_id in clubs:
        rows.extend(_collect_rules(conn, club_id, resource, "admin"))
    if any(r["effect"] == "deny" for r in rows):
        return False
    return any(r["effect"] == "allow" for r in rows)


def write_audit(conn, event: str, subject: str, resource: str, action: str, actor: str):
    conn.execute(
        "INSERT INTO audit_log (event, subject, resource, action, actor, created_at) VALUES (?,?,?,?,?,?)",
        (event, subject, resource, action, actor, _now_iso()),
    )
