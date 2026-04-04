"""Tests for hivo-drop API routes."""
import pytest
from .conftest import make_token, ISSUER, SUB, HANDLE


def auth_headers(token: str | None = None) -> dict:
    return {"Authorization": f"Bearer {token or make_token()}"}


# ── Public endpoints ───────────────────────────────────────────────────────────

def test_index(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "hivo-drop" in r.text


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ── Auth checks ────────────────────────────────────────────────────────────────

def test_upload_no_auth(client):
    r = client.put("/files/test.txt", content=b"hello", headers={"Content-Type": "text/plain"})
    assert r.status_code == 401

def test_upload_wrong_audience(client):
    token = make_token(aud="other-service")
    r = client.put("/files/test.txt", content=b"hello",
                   headers={"Content-Type": "text/plain", "Authorization": f"Bearer {token}"})
    assert r.status_code == 401

def test_upload_expired_token(client):
    token = make_token(exp_delta=-1)
    r = client.put("/files/test.txt", content=b"hello",
                   headers={"Content-Type": "text/plain", "Authorization": f"Bearer {token}"})
    assert r.status_code == 401


# ── Upload ─────────────────────────────────────────────────────────────────────

def test_upload_new_file(client):
    r = client.put(
        "/files/docs/report.html",
        content=b"<h1>Hello</h1>",
        headers={**auth_headers(), "Content-Type": "text/html"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["path"] == "docs/report.html"
    assert body["size"] == len(b"<h1>Hello</h1>")
    assert "sha256" in body


def test_upload_conflict(client):
    headers = {**auth_headers(), "Content-Type": "text/plain"}
    client.put("/files/a.txt", content=b"first", headers=headers)
    r = client.put("/files/a.txt", content=b"second", headers=headers)
    assert r.status_code == 409
    assert r.json()["error"] == "conflict"


def test_upload_overwrite(client):
    headers = {**auth_headers(), "Content-Type": "text/plain"}
    client.put("/files/b.txt", content=b"v1", headers=headers)
    r = client.put("/files/b.txt", content=b"v2", headers=headers, params={"overwrite": "true"})
    assert r.status_code == 200
    assert r.json()["size"] == 2


def test_upload_too_large(client):
    big = b"x" * (1024 * 1024 + 1)
    r = client.put("/files/big.bin", content=big,
                   headers={**auth_headers(), "Content-Type": "application/octet-stream"})
    assert r.status_code == 413


# ── Upload registers ACL grants ───────────────────────────────────────────────

def test_upload_registers_acl_grants(client):
    r = client.put(
        "/files/acl-test.txt",
        content=b"hello",
        headers={**auth_headers(), "Content-Type": "text/plain"},
    )
    assert r.status_code == 201
    acl = client._fake_acl
    # Should have 4 grants for the owner
    owner_grants = [g for g in acl.grants if g[0] == SUB and g[2] in ("read", "write", "delete", "admin")]
    assert len(owner_grants) == 4


def test_overwrite_does_not_duplicate_grants(client):
    headers = {**auth_headers(), "Content-Type": "text/plain"}
    client.put("/files/ow.txt", content=b"v1", headers=headers)
    before = len(client._fake_acl.grants)
    client.put("/files/ow.txt", content=b"v2", headers=headers, params={"overwrite": "true"})
    after = len(client._fake_acl.grants)
    assert after == before  # overwrite should not add new grants


# ── Download ───────────────────────────────────────────────────────────────────

def test_download_own_file(client):
    headers = {**auth_headers(), "Content-Type": "text/plain"}
    client.put("/files/dl.txt", content=b"content", headers=headers)
    r = client.get("/files/dl.txt", headers=auth_headers())
    assert r.status_code == 200
    assert r.content == b"content"


def test_download_nonexistent(client):
    r = client.get("/files/nope.txt", headers=auth_headers())
    assert r.status_code == 404


# ── ACL cross-agent access ────────────────────────────────────────────────────

def _upload_as_owner(client, path="shared.txt", content=b"shared data"):
    """Upload a file as the default owner and return the file_id."""
    headers = {**auth_headers(), "Content-Type": "text/plain"}
    r = client.put(f"/files/{path}", content=content, headers=headers)
    assert r.status_code == 201
    # Find the file_id from ACL grants
    acl = client._fake_acl
    for sub, resource, action, effect in acl.grants:
        if sub == SUB and action == "read":
            return resource.split("drop:file:")[1]
    raise AssertionError("No ACL grant found after upload")


def test_other_agent_denied_without_grant(client):
    _upload_as_owner(client)
    token_b = make_token(sub="agt_other")
    r = client.get("/files/shared.txt", headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 404


def test_other_agent_allowed_with_grant(client):
    file_id = _upload_as_owner(client)
    other_sub = "agt_other"
    client._fake_acl.add_grant(other_sub, file_id, "read")
    token_b = make_token(sub=other_sub)
    r = client.get("/files/shared.txt", headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 200
    assert r.content == b"shared data"


def test_other_agent_head_with_grant(client):
    file_id = _upload_as_owner(client)
    other_sub = "agt_other"
    client._fake_acl.add_grant(other_sub, file_id, "read")
    token_b = make_token(sub=other_sub)
    r = client.head("/files/shared.txt", headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 200


def test_other_agent_delete_with_grant(client):
    file_id = _upload_as_owner(client)
    other_sub = "agt_other"
    client._fake_acl.add_grant(other_sub, file_id, "delete")
    token_b = make_token(sub=other_sub)
    r = client.delete("/files/shared.txt", headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 204
    # Grants should be revoked
    remaining = [g for g in client._fake_acl.grants if file_id in g[1]]
    assert len(remaining) == 0


def test_other_agent_patch_with_grant(client):
    file_id = _upload_as_owner(client)
    other_sub = "agt_other"
    client._fake_acl.add_grant(other_sub, file_id, "write")
    token_b = make_token(sub=other_sub)
    r = client.patch("/files/shared.txt",
                     json={"visibility": "public"},
                     headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 200
    assert r.json()["visibility"] == "public"


def test_other_agent_delete_denied(client):
    _upload_as_owner(client)
    token_b = make_token(sub="agt_other")
    r = client.delete("/files/shared.txt", headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 404


# ── Delete revokes ACL ────────────────────────────────────────────────────────

def test_delete_revokes_acl(client):
    file_id = _upload_as_owner(client)
    r = client.delete("/files/shared.txt", headers=auth_headers())
    assert r.status_code == 204
    remaining = [g for g in client._fake_acl.grants if file_id in g[1]]
    assert len(remaining) == 0


# ── Public share ──────────────────────────────────────────────────────────────

def test_share_public(client):
    headers = {**auth_headers(), "Content-Type": "text/html"}
    client.put("/files/page.html", content=b"<p>hi</p>", headers=headers)
    r = client.patch("/files/page.html", json={"visibility": "public"}, headers=auth_headers())
    assert r.status_code == 200
    share_id = r.json()["share_id"]
    assert share_id is not None

    # Public access without auth
    r = client.get(f"/p/{share_id}")
    assert r.status_code == 200
    assert r.content == b"<p>hi</p>"


def test_share_revoke(client):
    headers = {**auth_headers(), "Content-Type": "text/html"}
    client.put("/files/rev.html", content=b"<p>bye</p>", headers=headers)
    r = client.patch("/files/rev.html", json={"visibility": "public"}, headers=auth_headers())
    share_id = r.json()["share_id"]

    client.patch("/files/rev.html", json={"visibility": "private"}, headers=auth_headers())
    r = client.get(f"/p/{share_id}")
    assert r.status_code == 404


# ── List ──────────────────────────────────────────────────────────────────────

def test_list_files(client):
    h = {**auth_headers(), "Content-Type": "text/plain"}
    client.put("/files/x.txt", content=b"1", headers=h)
    client.put("/files/y.txt", content=b"2", headers=h)
    r = client.get("/list", headers=auth_headers())
    assert r.status_code == 200
    paths = [f["path"] for f in r.json()]
    assert "x.txt" in paths
    assert "y.txt" in paths


def test_list_with_prefix(client):
    h = {**auth_headers(), "Content-Type": "text/plain"}
    client.put("/files/a/one.txt", content=b"1", headers=h)
    client.put("/files/b/two.txt", content=b"2", headers=h)
    r = client.get("/list", params={"prefix": "a/"}, headers=auth_headers())
    assert r.status_code == 200
    paths = [f["path"] for f in r.json()]
    assert "a/one.txt" in paths
    assert "b/two.txt" not in paths


# ── Path validation ────────────────────────────────────────────────────────────

def test_path_traversal_rejected(client):
    r = client.put("/files/../etc/passwd", content=b"x",
                   headers={**auth_headers(), "Content-Type": "text/plain"})
    assert r.status_code in (404, 422)


# ── Isolation between agents ───────────────────────────────────────────────────

def test_agent_isolation(client):
    token_a = make_token(sub="agt_aaa")
    token_b = make_token(sub="agt_bbb")

    client.put("/files/secret.txt", content=b"agent A data",
               headers={"Authorization": f"Bearer {token_a}", "Content-Type": "text/plain"})

    # Agent B cannot read agent A's file (no ACL grant)
    r = client.get("/files/secret.txt",
                   headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 404
