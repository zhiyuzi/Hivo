"""Tests for hivo-drop API routes."""
import pytest
from .conftest import make_token, ISSUER, SUB, HANDLE


def auth_headers(token: str | None = None) -> dict:
    return {"Authorization": f"Bearer {token or make_token()}"}


# ── Public endpoints ───────────────────────────────────────────────────────────

def test_index(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Agent Drop" in r.text


def test_readme(client):
    r = client.get("/README.md")
    assert r.status_code == 200
    assert "Authentication" in r.text


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
    headers = {**auth_headers(), "Content-Type": "text/plain"}
    data = b"x" * (1024 * 1024 + 1)
    r = client.put("/files/big.txt", content=data, headers=headers)
    assert r.status_code == 413
    assert r.json()["error"] == "file_too_large"


# ── Download ───────────────────────────────────────────────────────────────────

def test_get_file(client):
    headers = {**auth_headers(), "Content-Type": "text/plain"}
    client.put("/files/hello.txt", content=b"world", headers=headers)
    r = client.get("/files/hello.txt", headers=auth_headers())
    assert r.status_code == 200
    assert r.content == b"world"


def test_get_file_not_found(client):
    r = client.get("/files/nope.txt", headers=auth_headers())
    assert r.status_code == 404
    assert r.json()["error"] == "not_found"


# ── HEAD ───────────────────────────────────────────────────────────────────────

def test_head_file(client):
    headers = {**auth_headers(), "Content-Type": "text/markdown"}
    client.put("/files/doc.md", content=b"# hi", headers=headers)
    r = client.head("/files/doc.md", headers=auth_headers())
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/markdown")
    assert r.headers["content-length"] == "4"
    assert r.headers["x-visibility"] == "private"


def test_head_file_not_found(client):
    r = client.head("/files/ghost.md", headers=auth_headers())
    assert r.status_code == 404


# ── Delete ─────────────────────────────────────────────────────────────────────

def test_delete_file(client):
    headers = {**auth_headers(), "Content-Type": "text/plain"}
    client.put("/files/del.txt", content=b"bye", headers=headers)
    r = client.delete("/files/del.txt", headers=auth_headers())
    assert r.status_code == 204
    r2 = client.get("/files/del.txt", headers=auth_headers())
    assert r2.status_code == 404


def test_delete_not_found(client):
    r = client.delete("/files/ghost.txt", headers=auth_headers())
    assert r.status_code == 404


# ── PATCH (visibility) ─────────────────────────────────────────────────────────

def test_make_public(client):
    headers = {**auth_headers(), "Content-Type": "text/html"}
    client.put("/files/page.html", content=b"<p>hi</p>", headers=headers)

    r = client.patch("/files/page.html",
                     json={"visibility": "public"},
                     headers=auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["visibility"] == "public"
    assert body["share_id"] is not None


def test_make_private_revokes_share(client):
    headers = {**auth_headers(), "Content-Type": "text/plain"}
    client.put("/files/priv.txt", content=b"secret", headers=headers)

    patch_r = client.patch("/files/priv.txt",
                           json={"visibility": "public"},
                           headers=auth_headers())
    share_id = patch_r.json()["share_id"]

    # Public access works
    r1 = client.get(f"/p/{share_id}")
    assert r1.status_code == 200

    # Revoke
    client.patch("/files/priv.txt", json={"visibility": "private"}, headers=auth_headers())

    # Public access gone
    r2 = client.get(f"/p/{share_id}")
    assert r2.status_code == 404


# ── Public share access ────────────────────────────────────────────────────────

def test_public_access_html(client):
    headers = {**auth_headers(), "Content-Type": "text/html"}
    client.put("/files/pub.html", content=b"<b>hi</b>", headers=headers)
    patch_r = client.patch("/files/pub.html",
                           json={"visibility": "public"},
                           headers=auth_headers())
    share_id = patch_r.json()["share_id"]

    r = client.get(f"/p/{share_id}")
    assert r.status_code == 200
    assert r.content == b"<b>hi</b>"
    assert "default-src 'none'" in r.headers.get("content-security-policy", "")
    assert r.headers.get("x-frame-options") == "DENY"


def test_public_access_not_found(client):
    r = client.get("/p/nonexistent-share-id")
    assert r.status_code == 404


# ── List ───────────────────────────────────────────────────────────────────────

def test_list_files(client):
    h = {**auth_headers(), "Content-Type": "text/plain"}
    client.put("/files/x.txt", content=b"a", headers=h)
    client.put("/files/y.txt", content=b"b", headers=h)
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

    # Agent B cannot read agent A's file
    r = client.get("/files/secret.txt",
                   headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 404
