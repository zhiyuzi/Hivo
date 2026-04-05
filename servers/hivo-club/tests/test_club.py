"""Tests for hivo-club API routes."""
from .conftest import make_token, ISSUER, SUB


def auth(token: str | None = None) -> dict:
    return {"Authorization": f"Bearer {token or make_token()}"}


# ── Public endpoints ───────────────────────────────────────────────────────────

def test_index(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "hivo-club" in r.text


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ── Auth ───────────────────────────────────────────────────────────────────────

def test_create_club_no_auth(client):
    r = client.post("/clubs", json={"name": "Test"})
    assert r.status_code == 401


def test_create_club_expired_token(client):
    token = make_token(exp_delta=-1)
    r = client.post("/clubs", json={"name": "Test"}, headers=auth(token))
    assert r.status_code == 401


# ── Create Club ────────────────────────────────────────────────────────────────

def _create_club(client, name="Test Club", token=None):
    r = client.post("/clubs", json={"name": name, "description": "A test club"}, headers=auth(token))
    assert r.status_code == 201
    return r.json()


def test_create_club(client):
    body = _create_club(client)
    assert body["name"] == "Test Club"
    assert body["owner_sub"] == SUB
    assert body["club_id"].startswith("club_")


def test_create_club_owner_is_member(client):
    body = _create_club(client)
    r = client.get(f"/clubs/{body['club_id']}/members", headers=auth())
    assert r.status_code == 200
    members = r.json()["members"]
    assert len(members) == 1
    assert members[0]["sub"] == SUB
    assert members[0]["role"] == "owner"


# ── Get Club Info ──────────────────────────────────────────────────────────────

def test_get_club(client):
    body = _create_club(client)
    r = client.get(f"/clubs/{body['club_id']}", headers=auth())
    assert r.status_code == 200
    assert r.json()["name"] == "Test Club"


def test_get_club_not_found(client):
    r = client.get("/clubs/club_nonexistent", headers=auth())
    assert r.status_code == 404


# ── List Members ───────────────────────────────────────────────────────────────

def test_list_members_non_member_forbidden(client):
    body = _create_club(client)
    other_token = make_token(sub="agt_outsider")
    r = client.get(f"/clubs/{body['club_id']}/members", headers=auth(other_token))
    assert r.status_code == 403


# ── Direct Invite ──────────────────────────────────────────────────────────────

def test_invite_member(client):
    body = _create_club(client)
    club_id = body["club_id"]
    r = client.post(f"/clubs/{club_id}/members", json={"sub": "agt_new", "role": "member"}, headers=auth())
    assert r.status_code == 201
    assert r.json()["sub"] == "agt_new"

    # Verify member appears in list
    r = client.get(f"/clubs/{club_id}/members", headers=auth())
    subs = [m["sub"] for m in r.json()["members"]]
    assert "agt_new" in subs


def test_invite_duplicate(client):
    body = _create_club(client)
    club_id = body["club_id"]
    client.post(f"/clubs/{club_id}/members", json={"sub": "agt_dup", "role": "member"}, headers=auth())
    r = client.post(f"/clubs/{club_id}/members", json={"sub": "agt_dup", "role": "member"}, headers=auth())
    assert r.status_code == 409


def test_invite_by_non_admin_forbidden(client):
    body = _create_club(client)
    club_id = body["club_id"]
    # Add a regular member
    client.post(f"/clubs/{club_id}/members", json={"sub": "agt_regular", "role": "member"}, headers=auth())
    # Regular member tries to invite
    regular_token = make_token(sub="agt_regular")
    r = client.post(f"/clubs/{club_id}/members", json={"sub": "agt_x", "role": "member"}, headers=auth(regular_token))
    assert r.status_code == 403


def test_invite_invalid_role(client):
    body = _create_club(client)
    r = client.post(f"/clubs/{body['club_id']}/members", json={"sub": "agt_x", "role": "owner"}, headers=auth())
    assert r.status_code == 422


# ── Invite Link ────────────────────────────────────────────────────────────────

def test_create_invite_link(client):
    body = _create_club(client)
    club_id = body["club_id"]
    r = client.post(f"/clubs/{club_id}/invite-links", json={"max_uses": 5}, headers=auth())
    assert r.status_code == 201
    link = r.json()
    assert "token" in link
    assert link["max_uses"] == 5


def test_join_via_link(client):
    body = _create_club(client)
    club_id = body["club_id"]
    link = client.post(f"/clubs/{club_id}/invite-links", json={}, headers=auth()).json()

    joiner_token = make_token(sub="agt_joiner")
    r = client.post(f"/join/{link['token']}", headers=auth(joiner_token))
    assert r.status_code == 201
    assert r.json()["club_id"] == club_id
    assert r.json()["sub"] == "agt_joiner"


def test_join_via_link_already_member(client):
    body = _create_club(client)
    club_id = body["club_id"]
    link = client.post(f"/clubs/{club_id}/invite-links", json={}, headers=auth()).json()

    joiner_token = make_token(sub="agt_joiner2")
    client.post(f"/join/{link['token']}", headers=auth(joiner_token))
    r = client.post(f"/join/{link['token']}", headers=auth(joiner_token))
    assert r.status_code == 409


def test_join_via_link_expired(client):
    body = _create_club(client)
    club_id = body["club_id"]
    r = client.post(
        f"/clubs/{club_id}/invite-links",
        json={"expires_at": "2020-01-01T00:00:00Z"},
        headers=auth(),
    )
    link = r.json()

    joiner_token = make_token(sub="agt_late")
    r = client.post(f"/join/{link['token']}", headers=auth(joiner_token))
    assert r.status_code == 410


def test_join_via_link_max_uses(client):
    body = _create_club(client)
    club_id = body["club_id"]
    link = client.post(f"/clubs/{club_id}/invite-links", json={"max_uses": 1}, headers=auth()).json()

    j1 = make_token(sub="agt_j1")
    client.post(f"/join/{link['token']}", headers=auth(j1))

    j2 = make_token(sub="agt_j2")
    r = client.post(f"/join/{link['token']}", headers=auth(j2))
    assert r.status_code == 410


def test_join_invalid_token(client):
    joiner_token = make_token(sub="agt_lost")
    r = client.post("/join/nonexistent-token", headers=auth(joiner_token))
    assert r.status_code == 404


# ── List Invite Links ─────────────────────────────────────────────────────────

def test_list_invite_links(client):
    body = _create_club(client)
    club_id = body["club_id"]
    client.post(f"/clubs/{club_id}/invite-links", json={"max_uses": 3}, headers=auth())
    client.post(f"/clubs/{club_id}/invite-links", json={"max_uses": 10}, headers=auth())

    r = client.get(f"/clubs/{club_id}/invite-links", headers=auth())
    assert r.status_code == 200
    links = r.json()["invite_links"]
    assert len(links) == 2


def test_list_invite_links_empty(client):
    body = _create_club(client)
    club_id = body["club_id"]
    r = client.get(f"/clubs/{club_id}/invite-links", headers=auth())
    assert r.status_code == 200
    assert r.json()["invite_links"] == []


def test_list_invite_links_member_forbidden(client):
    body = _create_club(client)
    club_id = body["club_id"]
    client.post(f"/clubs/{club_id}/members", json={"sub": "agt_peeker", "role": "member"}, headers=auth())
    peeker_token = make_token(sub="agt_peeker")
    r = client.get(f"/clubs/{club_id}/invite-links", headers=auth(peeker_token))
    assert r.status_code == 403


# ── Revoke Invite Link ────────────────────────────────────────────────────────

def test_revoke_invite_link(client):
    body = _create_club(client)
    club_id = body["club_id"]
    link = client.post(f"/clubs/{club_id}/invite-links", json={}, headers=auth()).json()

    r = client.delete(f"/clubs/{club_id}/invite-links/{link['token']}", headers=auth())
    assert r.status_code == 204

    # Verify link is gone
    r = client.get(f"/clubs/{club_id}/invite-links", headers=auth())
    assert len(r.json()["invite_links"]) == 0


def test_revoke_invite_link_not_found(client):
    body = _create_club(client)
    club_id = body["club_id"]
    r = client.delete(f"/clubs/{club_id}/invite-links/nonexistent", headers=auth())
    assert r.status_code == 404


def test_revoke_invite_link_member_forbidden(client):
    body = _create_club(client)
    club_id = body["club_id"]
    link = client.post(f"/clubs/{club_id}/invite-links", json={}, headers=auth()).json()
    client.post(f"/clubs/{club_id}/members", json={"sub": "agt_revoker", "role": "member"}, headers=auth())

    revoker_token = make_token(sub="agt_revoker")
    r = client.delete(f"/clubs/{club_id}/invite-links/{link['token']}", headers=auth(revoker_token))
    assert r.status_code == 403


def test_revoked_link_cannot_be_used(client):
    body = _create_club(client)
    club_id = body["club_id"]
    link = client.post(f"/clubs/{club_id}/invite-links", json={}, headers=auth()).json()

    client.delete(f"/clubs/{club_id}/invite-links/{link['token']}", headers=auth())

    joiner_token = make_token(sub="agt_too_late")
    r = client.post(f"/join/{link['token']}", headers=auth(joiner_token))
    assert r.status_code == 404


# ── Leave / Remove Member ─────────────────────────────────────────────────────

def test_leave_club(client):
    body = _create_club(client)
    club_id = body["club_id"]
    client.post(f"/clubs/{club_id}/members", json={"sub": "agt_leaver", "role": "member"}, headers=auth())

    leaver_token = make_token(sub="agt_leaver")
    r = client.delete(f"/clubs/{club_id}/members/agt_leaver", headers=auth(leaver_token))
    assert r.status_code == 204

    # Verify gone
    r = client.get(f"/clubs/{club_id}/members", headers=auth())
    subs = [m["sub"] for m in r.json()["members"]]
    assert "agt_leaver" not in subs


def test_owner_cannot_leave(client):
    body = _create_club(client)
    r = client.delete(f"/clubs/{body['club_id']}/members/{SUB}", headers=auth())
    assert r.status_code == 403


def test_admin_remove_member(client):
    body = _create_club(client)
    club_id = body["club_id"]
    # Add admin
    client.post(f"/clubs/{club_id}/members", json={"sub": "agt_admin", "role": "admin"}, headers=auth())
    # Add member
    client.post(f"/clubs/{club_id}/members", json={"sub": "agt_target", "role": "member"}, headers=auth())

    admin_token = make_token(sub="agt_admin")
    r = client.delete(f"/clubs/{club_id}/members/agt_target", headers=auth(admin_token))
    assert r.status_code == 204


def test_admin_cannot_remove_owner(client):
    body = _create_club(client)
    club_id = body["club_id"]
    client.post(f"/clubs/{club_id}/members", json={"sub": "agt_admin2", "role": "admin"}, headers=auth())

    admin_token = make_token(sub="agt_admin2")
    r = client.delete(f"/clubs/{club_id}/members/{SUB}", headers=auth(admin_token))
    assert r.status_code == 403


def test_member_cannot_remove_other(client):
    body = _create_club(client)
    club_id = body["club_id"]
    client.post(f"/clubs/{club_id}/members", json={"sub": "agt_m1", "role": "member"}, headers=auth())
    client.post(f"/clubs/{club_id}/members", json={"sub": "agt_m2", "role": "member"}, headers=auth())

    m1_token = make_token(sub="agt_m1")
    r = client.delete(f"/clubs/{club_id}/members/agt_m2", headers=auth(m1_token))
    assert r.status_code == 403


# ── Update Role ────────────────────────────────────────────────────────────────

def test_owner_update_role(client):
    body = _create_club(client)
    club_id = body["club_id"]
    client.post(f"/clubs/{club_id}/members", json={"sub": "agt_promote", "role": "member"}, headers=auth())

    r = client.patch(f"/clubs/{club_id}/members/agt_promote", json={"role": "admin"}, headers=auth())
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_admin_update_member_role(client):
    body = _create_club(client)
    club_id = body["club_id"]
    client.post(f"/clubs/{club_id}/members", json={"sub": "agt_adm", "role": "admin"}, headers=auth())
    client.post(f"/clubs/{club_id}/members", json={"sub": "agt_mem", "role": "member"}, headers=auth())

    adm_token = make_token(sub="agt_adm")
    r = client.patch(f"/clubs/{club_id}/members/agt_mem", json={"role": "admin"}, headers=auth(adm_token))
    assert r.status_code == 200


def test_admin_cannot_change_owner_role(client):
    body = _create_club(client)
    club_id = body["club_id"]
    client.post(f"/clubs/{club_id}/members", json={"sub": "agt_adm3", "role": "admin"}, headers=auth())

    adm_token = make_token(sub="agt_adm3")
    r = client.patch(f"/clubs/{club_id}/members/{SUB}", json={"role": "member"}, headers=auth(adm_token))
    assert r.status_code == 403


def test_cannot_set_role_to_owner(client):
    body = _create_club(client)
    club_id = body["club_id"]
    client.post(f"/clubs/{club_id}/members", json={"sub": "agt_sneaky", "role": "member"}, headers=auth())

    r = client.patch(f"/clubs/{club_id}/members/agt_sneaky", json={"role": "owner"}, headers=auth())
    assert r.status_code == 422


# ── Dissolve Club ──────────────────────────────────────────────────────────────

def test_dissolve_club(client):
    body = _create_club(client)
    club_id = body["club_id"]
    r = client.delete(f"/clubs/{club_id}", headers=auth())
    assert r.status_code == 204

    # Club gone
    r = client.get(f"/clubs/{club_id}", headers=auth())
    assert r.status_code == 404


def test_non_owner_cannot_dissolve(client):
    body = _create_club(client)
    club_id = body["club_id"]
    client.post(f"/clubs/{club_id}/members", json={"sub": "agt_adm4", "role": "admin"}, headers=auth())

    adm_token = make_token(sub="agt_adm4")
    r = client.delete(f"/clubs/{club_id}", headers=auth(adm_token))
    assert r.status_code == 403


# ── Update Club ───────────────────────────────────────────────────────────────

def test_update_club_name(client):
    body = _create_club(client)
    club_id = body["club_id"]
    r = client.patch(f"/clubs/{club_id}", json={"name": "New Name"}, headers=auth())
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"


def test_update_club_description(client):
    body = _create_club(client)
    club_id = body["club_id"]
    r = client.patch(f"/clubs/{club_id}", json={"description": "New desc"}, headers=auth())
    assert r.status_code == 200
    assert r.json()["description"] == "New desc"


def test_update_club_multiple_fields(client):
    body = _create_club(client)
    club_id = body["club_id"]
    r = client.patch(f"/clubs/{club_id}", json={"name": "Updated", "description": "Updated desc"}, headers=auth())
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Updated"
    assert data["description"] == "Updated desc"


def test_update_club_empty_body(client):
    body = _create_club(client)
    club_id = body["club_id"]
    r = client.patch(f"/clubs/{club_id}", json={}, headers=auth())
    assert r.status_code == 422


def test_update_club_admin_allowed(client):
    body = _create_club(client)
    club_id = body["club_id"]
    client.post(f"/clubs/{club_id}/members", json={"sub": "agt_adm5", "role": "admin"}, headers=auth())

    adm_token = make_token(sub="agt_adm5")
    r = client.patch(f"/clubs/{club_id}", json={"name": "Admin Updated"}, headers=auth(adm_token))
    assert r.status_code == 200
    assert r.json()["name"] == "Admin Updated"


def test_update_club_member_forbidden(client):
    body = _create_club(client)
    club_id = body["club_id"]
    client.post(f"/clubs/{club_id}/members", json={"sub": "agt_mem5", "role": "member"}, headers=auth())

    mem_token = make_token(sub="agt_mem5")
    r = client.patch(f"/clubs/{club_id}", json={"name": "Nope"}, headers=auth(mem_token))
    assert r.status_code == 403


def test_update_club_non_member_forbidden(client):
    body = _create_club(client)
    club_id = body["club_id"]
    outsider = make_token(sub="agt_outsider")
    r = client.patch(f"/clubs/{club_id}", json={"name": "Nope"}, headers=auth(outsider))
    assert r.status_code == 403


# ── Update My Membership ─────────────────────────────────────────────────────

def test_update_my_membership_display_name(client):
    body = _create_club(client)
    club_id = body["club_id"]
    r = client.patch(f"/clubs/{club_id}/me", json={"display_name": "Boss"}, headers=auth())
    assert r.status_code == 200
    assert r.json()["display_name"] == "Boss"


def test_update_my_membership_bio(client):
    body = _create_club(client)
    club_id = body["club_id"]
    r = client.patch(f"/clubs/{club_id}/me", json={"bio": "I run this club"}, headers=auth())
    assert r.status_code == 200
    assert r.json()["bio"] == "I run this club"


def test_update_my_membership_multiple(client):
    body = _create_club(client)
    club_id = body["club_id"]
    r = client.patch(f"/clubs/{club_id}/me", json={"display_name": "Nick", "bio": "Hello"}, headers=auth())
    assert r.status_code == 200
    data = r.json()
    assert data["display_name"] == "Nick"
    assert data["bio"] == "Hello"


def test_update_my_membership_empty_body(client):
    body = _create_club(client)
    club_id = body["club_id"]
    r = client.patch(f"/clubs/{club_id}/me", json={}, headers=auth())
    assert r.status_code == 422


def test_update_my_membership_non_member(client):
    body = _create_club(client)
    club_id = body["club_id"]
    outsider = make_token(sub="agt_outsider2")
    r = client.patch(f"/clubs/{club_id}/me", json={"display_name": "Nope"}, headers=auth(outsider))
    assert r.status_code == 403


def test_update_my_membership_visible_in_members_list(client):
    body = _create_club(client)
    club_id = body["club_id"]
    client.patch(f"/clubs/{club_id}/me", json={"display_name": "Custom Nick", "bio": "My intro"}, headers=auth())

    r = client.get(f"/clubs/{club_id}/members", headers=auth())
    assert r.status_code == 200
    member = r.json()["members"][0]
    assert member["display_name"] == "Custom Nick"
    assert member["bio"] == "My intro"


# ── My Clubs ───────────────────────────────────────────────────────────────────

def test_my_clubs(client):
    _create_club(client, "Club A")
    _create_club(client, "Club B")
    r = client.get("/me/clubs", headers=auth())
    assert r.status_code == 200
    names = [c["name"] for c in r.json()["clubs"]]
    assert "Club A" in names
    assert "Club B" in names


def test_my_clubs_empty(client):
    other_token = make_token(sub="agt_lonely")
    r = client.get("/me/clubs", headers=auth(other_token))
    assert r.status_code == 200
    assert r.json()["clubs"] == []
