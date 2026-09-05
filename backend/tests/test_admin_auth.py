"""Tests for the single-admin login flow and the auth gate it feeds into
`app.services.auth.require_admin`, which every admin-knowledge-base route
depends on."""

from tests.conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD


def test_login_with_correct_credentials_returns_token(anonymous_client):
    resp = anonymous_client.post(
        "/api/admin/auth/login", json={"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASSWORD}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == TEST_ADMIN_EMAIL
    assert body["token"]


def test_login_is_case_insensitive_on_email(anonymous_client):
    resp = anonymous_client.post(
        "/api/admin/auth/login", json={"email": TEST_ADMIN_EMAIL.upper(), "password": TEST_ADMIN_PASSWORD}
    )
    assert resp.status_code == 200


def test_login_with_wrong_password_rejected(anonymous_client):
    resp = anonymous_client.post(
        "/api/admin/auth/login", json={"email": TEST_ADMIN_EMAIL, "password": "wrong-password"}
    )
    assert resp.status_code == 401


def test_login_with_unknown_email_rejected(anonymous_client):
    resp = anonymous_client.post(
        "/api/admin/auth/login", json={"email": "nobody@test.local", "password": TEST_ADMIN_PASSWORD}
    )
    assert resp.status_code == 401


def test_admin_kb_routes_reject_missing_token(anonymous_client):
    resp = anonymous_client.get("/api/admin/knowledge-base/documents")
    assert resp.status_code == 401


def test_admin_kb_routes_reject_garbage_token(anonymous_client):
    anonymous_client.headers["Authorization"] = "Bearer not-a-real-token"
    resp = anonymous_client.get("/api/admin/knowledge-base/documents")
    assert resp.status_code == 401


def test_admin_kb_routes_accept_valid_token(client):
    resp = client.get("/api/admin/knowledge-base/documents")
    assert resp.status_code == 200
