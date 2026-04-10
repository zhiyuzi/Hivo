"""Tests for hivo-salon."""
import json
from tests.conftest import auth, CLUB_ID, SUB, SUB2, SUB3


# ── Helpers ───────────────────────────────────────────────────────────────────

def _create_salon(client, club_id=CLUB_ID, name="Test Salon", bulletin=None, sub=SUB):
    body = {"name": name, "club_id": club_id}
    if bulletin:
        body["bulletin"] = bulletin
    r = client.post("/salons", json=body, headers=auth(sub))
    assert r.status_code == 201
    return r.json()


def _add_member(client, salon_id, target_sub=SUB2, role="member", sub=SUB):
    r = client.post(
        f"/salons/{salon_id}/members",
        json={"sub": target_sub, "role": role},
        headers=auth(sub),
    )
    assert r.status_code == 201
    return r.json()


def _send_message(client, salon_id, content, sub=SUB):
    r = client.post(
        f"/salons/{salon_id}/messages",
        json={"content": content},
        headers=auth(sub),
    )
    assert r.status_code == 201
    return r.json()


# ── Static ────────────────────────────────────────────────────────────────────

def test_index(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "hivo-salon" in r.text


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ── Create Salon ──────────────────────────────────────────────────────────────

def test_create_salon(client):
    data = _create_salon(client, bulletin="Welcome!")
    assert data["id"].startswith("sln_")
    assert data["name"] == "Test Salon"
    assert data["bulletin"] == "Welcome!"
    assert data["club_id"] == CLUB_ID
    assert data["owner_sub"] == SUB
    assert data["owner_handle"] == "alice@test"


def test_create_salon_not_club_member(client):
    r = client.post(
        "/salons",
        json={"name": "Bad", "club_id": "club_nonexistent"},
        headers=auth(SUB),
    )
    assert r.status_code == 403


# ── Get Salon ─────────────────────────────────────────────────────────────────

def test_get_salon(client):
    salon = _create_salon(client, bulletin="Hello")
    r = client.get(f"/salons/{salon['id']}", headers=auth(SUB))
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Test Salon"
    assert data["bulletin"] == "Hello"
    assert data["owner_handle"] == "alice@test"


def test_get_salon_not_member(client):
    salon = _create_salon(client)
    r = client.get(f"/salons/{salon['id']}", headers=auth(SUB2))
    assert r.status_code == 403


def test_get_salon_not_found(client):
    r = client.get("/salons/sln_nonexistent", headers=auth(SUB))
    assert r.status_code == 404


# ── List Salons ───────────────────────────────────────────────────────────────

def test_list_salons(client):
    _create_salon(client, name="Salon A")
    _create_salon(client, name="Salon B")
    r = client.get("/salons", params={"club_id": CLUB_ID}, headers=auth(SUB))
    assert r.status_code == 200
    data = r.json()
    assert len(data["salons"]) == 2


def test_list_salons_not_club_member(client):
    r = client.get("/salons", params={"club_id": "club_nonexistent"}, headers=auth(SUB))
    assert r.status_code == 403


# ── Update Salon ──────────────────────────────────────────────────────────────

def test_update_salon(client):
    salon = _create_salon(client)
    r = client.patch(
        f"/salons/{salon['id']}",
        json={"name": "Updated", "bulletin": "New bulletin"},
        headers=auth(SUB),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Updated"
    assert data["bulletin"] == "New bulletin"


def test_update_salon_member_forbidden(client):
    salon = _create_salon(client)
    _add_member(client, salon["id"], SUB2)
    r = client.patch(
        f"/salons/{salon['id']}",
        json={"name": "Nope"},
        headers=auth(SUB2),
    )
    assert r.status_code == 403


# ── Delete Salon ──────────────────────────────────────────────────────────────

def test_delete_salon(client):
    salon = _create_salon(client)
    r = client.delete(f"/salons/{salon['id']}", headers=auth(SUB))
    assert r.status_code == 204
    # Verify gone
    r = client.get(f"/salons/{salon['id']}", headers=auth(SUB))
    assert r.status_code == 404


def test_delete_salon_not_owner(client):
    salon = _create_salon(client)
    _add_member(client, salon["id"], SUB2, role="admin")
    r = client.delete(f"/salons/{salon['id']}", headers=auth(SUB2))
    assert r.status_code == 403


# ── Members ───────────────────────────────────────────────────────────────────

def test_add_member(client):
    salon = _create_salon(client)
    data = _add_member(client, salon["id"], SUB2)
    assert data["sub"] == SUB2
    assert data["role"] == "member"
    assert data["handle"] == "bob@test"


def test_add_member_not_club_member(client):
    salon = _create_salon(client)
    r = client.post(
        f"/salons/{salon['id']}/members",
        json={"sub": "agt_outsider", "role": "member"},
        headers=auth(SUB),
    )
    assert r.status_code == 403


def test_add_member_already_exists(client):
    salon = _create_salon(client)
    _add_member(client, salon["id"], SUB2)
    r = client.post(
        f"/salons/{salon['id']}/members",
        json={"sub": SUB2, "role": "member"},
        headers=auth(SUB),
    )
    assert r.status_code == 409


def test_list_members(client):
    salon = _create_salon(client)
    _add_member(client, salon["id"], SUB2)
    r = client.get(f"/salons/{salon['id']}/members", headers=auth(SUB))
    assert r.status_code == 200
    data = r.json()
    assert len(data["members"]) == 2


def test_remove_member(client):
    salon = _create_salon(client)
    _add_member(client, salon["id"], SUB2)
    r = client.delete(f"/salons/{salon['id']}/members/{SUB2}", headers=auth(SUB))
    assert r.status_code == 204


def test_remove_member_not_privileged(client):
    salon = _create_salon(client)
    _add_member(client, salon["id"], SUB2)
    _add_member(client, salon["id"], SUB3)
    r = client.delete(f"/salons/{salon['id']}/members/{SUB3}", headers=auth(SUB2))
    assert r.status_code == 403


def test_update_member_me(client):
    salon = _create_salon(client)
    _add_member(client, salon["id"], SUB2)
    r = client.patch(
        f"/salons/{salon['id']}/members/me",
        json={"display_name": "Bob Display", "bio": "Hello"},
        headers=auth(SUB2),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["display_name"] == "Bob Display"
    assert data["bio"] == "Hello"


def test_update_member_role_by_owner(client):
    salon = _create_salon(client)
    _add_member(client, salon["id"], SUB2)
    r = client.patch(
        f"/salons/{salon['id']}/members/{SUB2}",
        json={"role": "admin"},
        headers=auth(SUB),
    )
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_update_member_role_by_member_forbidden(client):
    salon = _create_salon(client)
    _add_member(client, salon["id"], SUB2)
    _add_member(client, salon["id"], SUB3)
    r = client.patch(
        f"/salons/{salon['id']}/members/{SUB3}",
        json={"role": "admin"},
        headers=auth(SUB2),
    )
    assert r.status_code == 403


# ── Messages ──────────────────────────────────────────────────────────────────

def test_send_message(client):
    salon = _create_salon(client)
    content = [{"type": "text", "text": "Hello world"}]
    data = _send_message(client, salon["id"], content)
    assert data["id"].startswith("msg_")
    assert data["sender_sub"] == SUB
    assert data["sender_handle"] == "alice@test"
    assert data["content"] == content


def test_send_message_not_member(client):
    salon = _create_salon(client)
    r = client.post(
        f"/salons/{salon['id']}/messages",
        json={"content": [{"type": "text", "text": "Hi"}]},
        headers=auth(SUB2),
    )
    assert r.status_code == 403


def test_list_messages(client):
    salon = _create_salon(client)
    _send_message(client, salon["id"], [{"type": "text", "text": "msg1"}])
    _send_message(client, salon["id"], [{"type": "text", "text": "msg2"}])
    r = client.get(f"/salons/{salon['id']}/messages", headers=auth(SUB))
    assert r.status_code == 200
    data = r.json()
    assert len(data["messages"]) == 2


def test_list_messages_with_mention_filter(client):
    salon = _create_salon(client)
    _add_member(client, salon["id"], SUB2)
    _send_message(client, salon["id"], [
        {"type": "text", "text": "Hey"},
        {"type": "mention", "sub": SUB2, "handle": "bob@test"},
    ])
    _send_message(client, salon["id"], [{"type": "text", "text": "No mention"}])

    # SUB2 filters mention_me
    r = client.get(
        f"/salons/{salon['id']}/messages",
        params={"mention_me": "true"},
        headers=auth(SUB2),
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["messages"]) == 1


def test_list_messages_with_sender_filter(client):
    salon = _create_salon(client)
    _add_member(client, salon["id"], SUB2)
    _send_message(client, salon["id"], [{"type": "text", "text": "from alice"}], sub=SUB)
    _send_message(client, salon["id"], [{"type": "text", "text": "from bob"}], sub=SUB2)

    r = client.get(
        f"/salons/{salon['id']}/messages",
        params={"sender": SUB2},
        headers=auth(SUB),
    )
    assert r.status_code == 200
    assert len(r.json()["messages"]) == 1
    assert r.json()["messages"][0]["sender_sub"] == SUB2


def test_list_messages_with_sender_handle_filter(client):
    salon = _create_salon(client)
    _add_member(client, salon["id"], SUB2)
    _send_message(client, salon["id"], [{"type": "text", "text": "from bob"}], sub=SUB2)

    r = client.get(
        f"/salons/{salon['id']}/messages",
        params={"sender": "bob@test"},
        headers=auth(SUB),
    )
    assert r.status_code == 200
    assert len(r.json()["messages"]) == 1


def test_get_message(client):
    salon = _create_salon(client)
    msg = _send_message(client, salon["id"], [{"type": "text", "text": "Hello"}])
    r = client.get(f"/messages/{msg['id']}", headers=auth(SUB))
    assert r.status_code == 200
    assert r.json()["content"] == [{"type": "text", "text": "Hello"}]


def test_get_message_not_member(client):
    salon = _create_salon(client)
    msg = _send_message(client, salon["id"], [{"type": "text", "text": "Hello"}])
    r = client.get(f"/messages/{msg['id']}", headers=auth(SUB2))
    assert r.status_code == 403


def test_delete_message_by_sender(client):
    salon = _create_salon(client)
    msg = _send_message(client, salon["id"], [{"type": "text", "text": "Delete me"}])
    r = client.delete(f"/messages/{msg['id']}", headers=auth(SUB))
    assert r.status_code == 204


def test_delete_message_by_admin(client):
    salon = _create_salon(client)
    _add_member(client, salon["id"], SUB2, role="admin")
    msg = _send_message(client, salon["id"], [{"type": "text", "text": "Delete me"}])
    r = client.delete(f"/messages/{msg['id']}", headers=auth(SUB2))
    assert r.status_code == 204


def test_delete_message_by_member_forbidden(client):
    salon = _create_salon(client)
    _add_member(client, salon["id"], SUB2)
    msg = _send_message(client, salon["id"], [{"type": "text", "text": "Nope"}])
    r = client.delete(f"/messages/{msg['id']}", headers=auth(SUB2))
    assert r.status_code == 403


# ── Files ─────────────────────────────────────────────────────────────────────

def test_add_file(client):
    salon = _create_salon(client)
    client._fake_acl.add_grant(SUB, "file_001", "admin")
    r = client.post(
        f"/salons/{salon['id']}/files",
        json={"file_id": "file_001", "alias": "report.pdf", "permissions": "read"},
        headers=auth(SUB),
    )
    assert r.status_code == 201
    data = r.json()
    assert data["file_id"] == "file_001"
    assert data["alias"] == "report.pdf"
    assert data["owner_handle"] == "alice@test"


def test_add_file_duplicate_alias(client):
    salon = _create_salon(client)
    client._fake_acl.add_grant(SUB, "file_001", "admin")
    client._fake_acl.add_grant(SUB, "file_002", "admin")
    client.post(
        f"/salons/{salon['id']}/files",
        json={"file_id": "file_001", "alias": "report.pdf"},
        headers=auth(SUB),
    )
    r = client.post(
        f"/salons/{salon['id']}/files",
        json={"file_id": "file_002", "alias": "report.pdf"},
        headers=auth(SUB),
    )
    assert r.status_code == 409


def test_list_files(client):
    salon = _create_salon(client)
    client._fake_acl.add_grant(SUB, "file_001", "admin")
    client._fake_acl.add_grant(SUB, "file_002", "admin")
    client.post(
        f"/salons/{salon['id']}/files",
        json={"file_id": "file_001", "alias": "a.pdf"},
        headers=auth(SUB),
    )
    client.post(
        f"/salons/{salon['id']}/files",
        json={"file_id": "file_002", "alias": "b.pdf"},
        headers=auth(SUB),
    )
    r = client.get(f"/salons/{salon['id']}/files", headers=auth(SUB))
    assert r.status_code == 200
    assert len(r.json()["files"]) == 2


def test_remove_file_by_owner(client):
    salon = _create_salon(client)
    client._fake_acl.add_grant(SUB, "file_001", "admin")
    client.post(
        f"/salons/{salon['id']}/files",
        json={"file_id": "file_001", "alias": "a.pdf"},
        headers=auth(SUB),
    )
    r = client.delete(f"/salons/{salon['id']}/files/file_001", headers=auth(SUB))
    assert r.status_code == 204


def test_remove_file_by_member_forbidden(client):
    salon = _create_salon(client)
    _add_member(client, salon["id"], SUB2)
    client._fake_acl.add_grant(SUB, "file_001", "admin")
    client.post(
        f"/salons/{salon['id']}/files",
        json={"file_id": "file_001", "alias": "a.pdf"},
        headers=auth(SUB),
    )
    r = client.delete(f"/salons/{salon['id']}/files/file_001", headers=auth(SUB2))
    assert r.status_code == 403


# ── Inbox ─────────────────────────────────────────────────────────────────────

def test_inbox_empty(client):
    r = client.get("/inbox", headers=auth(SUB))
    assert r.status_code == 200
    assert r.json()["inbox"] == []


def test_inbox_with_unread(client):
    salon = _create_salon(client)
    _send_message(client, salon["id"], [{"type": "text", "text": "msg1"}])
    r = client.get("/inbox", headers=auth(SUB))
    assert r.status_code == 200
    entries = r.json()["inbox"]
    assert len(entries) == 1
    assert entries[0]["unread_count"] == 1


def test_inbox_after_read(client):
    salon = _create_salon(client)
    _send_message(client, salon["id"], [{"type": "text", "text": "msg1"}])
    # Mark as read
    client.post(f"/salons/{salon['id']}/read", headers=auth(SUB))
    r = client.get("/inbox", headers=auth(SUB))
    entries = r.json()["inbox"]
    assert entries[0]["unread_count"] == 0


def test_inbox_with_mention(client):
    salon = _create_salon(client)
    _add_member(client, salon["id"], SUB2)
    _send_message(client, salon["id"], [
        {"type": "mention", "sub": SUB2, "handle": "bob@test"},
    ])
    r = client.get("/inbox", headers=auth(SUB2))
    entries = r.json()["inbox"]
    assert len(entries) == 1
    assert entries[0]["has_mention"] is True


# ── Read Cursor ───────────────────────────────────────────────────────────────

def test_mark_read(client):
    salon = _create_salon(client)
    r = client.post(f"/salons/{salon['id']}/read", headers=auth(SUB))
    assert r.status_code == 200
    assert "last_read_at" in r.json()


def test_mark_read_twice(client):
    salon = _create_salon(client)
    r1 = client.post(f"/salons/{salon['id']}/read", headers=auth(SUB))
    r2 = client.post(f"/salons/{salon['id']}/read", headers=auth(SUB))
    assert r2.status_code == 200
    assert r2.json()["last_read_at"] >= r1.json()["last_read_at"]


def test_mark_read_not_member(client):
    salon = _create_salon(client)
    r = client.post(f"/salons/{salon['id']}/read", headers=auth(SUB2))
    assert r.status_code == 403


# ── Delete Salon Cascade ─────────────────────────────────────────────────────

def test_delete_salon_cascades(client):
    salon = _create_salon(client)
    _add_member(client, salon["id"], SUB2)
    _send_message(client, salon["id"], [{"type": "text", "text": "msg"}])
    client._fake_acl.add_grant(SUB, "file_001", "admin")
    client.post(
        f"/salons/{salon['id']}/files",
        json={"file_id": "file_001", "alias": "a.pdf"},
        headers=auth(SUB),
    )
    client.post(f"/salons/{salon['id']}/read", headers=auth(SUB))

    # Delete
    r = client.delete(f"/salons/{salon['id']}", headers=auth(SUB))
    assert r.status_code == 204

    # All related data should be gone
    r = client.get(f"/salons/{salon['id']}", headers=auth(SUB))
    assert r.status_code == 404
