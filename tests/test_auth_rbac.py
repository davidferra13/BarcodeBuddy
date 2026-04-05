"""Tests for authentication flows, RBAC enforcement, and admin operations."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from conftest import TestClient


@pytest.fixture(autouse=True)
def _reset_globals():
    """Reset global rate limiter and owner email between every test."""
    from app.auth_routes import _reset_rate_limiter
    from app.auth import configure_owner_email, DEFAULT_OWNER_EMAIL
    _reset_rate_limiter()
    configure_owner_email(DEFAULT_OWNER_EMAIL)
    yield
    _reset_rate_limiter()
    configure_owner_email(DEFAULT_OWNER_EMAIL)


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_auth.db"


@pytest.fixture()
def app(db_path: Path):
    from app.database import init_db
    from app.auth import configure_secret_key
    from app.auth_routes import router as auth_router
    from app.admin_routes import router as admin_router
    from app.inventory_routes import router as inventory_router

    init_db(db_path)
    configure_secret_key("test-secret-key-for-testing-32plus")
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(inventory_router)
    return app


@pytest.fixture()
def client(app) -> TestClient:
    return TestClient(app)


# ── Helper ──────────────────────────────────────────────────────────

def _signup(client: TestClient, email: str, name: str = "User", password: str = "testpass123") -> dict:
    resp = client.post("/auth/api/signup", json={
        "email": email, "password": password, "display_name": name,
    })
    return {"response": resp, "cookies": {"bb_session": resp.cookies.get("bb_session")}}


def _login(client: TestClient, email: str, password: str = "testpass123") -> dict:
    resp = client.post("/auth/api/login", json={"email": email, "password": password})
    return {"response": resp, "cookies": {"bb_session": resp.cookies.get("bb_session")}}


def _owner_email() -> str:
    from app.auth import OWNER_EMAIL

    return OWNER_EMAIL


def _enable_open_signup() -> None:
    from app.database import SystemSettings, get_db

    db_gen = get_db()
    db = next(db_gen)
    try:
        settings = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
        if settings:
            settings.open_signup = True
            db.commit()
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


def _disable_open_signup() -> None:
    from app.database import SystemSettings, get_db

    db_gen = get_db()
    db = next(db_gen)
    try:
        settings = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
        if settings:
            settings.open_signup = False
            db.commit()
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


# ═══════════════════════════════════════════════════════════════════
# AUTH: Signup
# ═══════════════════════════════════════════════════════════════════

class TestSignup:
    def test_first_user_becomes_owner(self, client):
        r = _signup(client, _owner_email(), "Owner")
        assert r["response"].status_code == 200
        data = r["response"].json()
        assert data["user"]["role"] == "owner"

    def test_first_user_any_email_becomes_owner_when_env_not_set(self, client):
        """When BB_OWNER_EMAIL is not explicitly set, any email can claim owner."""
        r = _signup(client, "anyone@example.com", "Owner")
        assert r["response"].status_code == 200
        assert r["response"].json()["user"]["role"] == "owner"

    def test_second_user_becomes_regular_user(self, client):
        _signup(client, _owner_email())
        r = _signup(client, "user2@test.com")
        assert r["response"].status_code == 200
        assert r["response"].json()["user"]["role"] == "user"

    def test_duplicate_email_rejected(self, client):
        _signup(client, _owner_email())
        _enable_open_signup()
        _signup(client, "dup@test.com")
        r = _signup(client, "dup@test.com")
        assert r["response"].status_code == 409

    def test_invalid_email_rejected(self, client):
        resp = client.post("/auth/api/signup", json={
            "email": "not-an-email", "password": "testpass123", "display_name": "Bad",
        })
        assert resp.status_code == 400

    def test_short_password_rejected(self, client):
        resp = client.post("/auth/api/signup", json={
            "email": "short@test.com", "password": "short", "display_name": "Short",
        })
        assert resp.status_code == 422  # Pydantic validation

    def test_signup_open_by_default(self, client):
        """After owner creates account, signup is open by default."""
        _signup(client, _owner_email())
        r = _signup(client, "newuser@test.com")
        assert r["response"].status_code == 200
        assert r["response"].json()["user"]["role"] == "user"

    def test_signup_disabled_blocks_new_users(self, client):
        """When admin closes signup, new users are blocked."""
        _signup(client, _owner_email())
        _disable_open_signup()
        r = _signup(client, "blocked@test.com")
        assert r["response"].status_code == 403


# ═══════════════════════════════════════════════════════════════════
# AUTH: Login/Logout
# ═══════════════════════════════════════════════════════════════════

class TestLogin:
    def test_valid_login(self, client):
        _signup(client, _owner_email())
        r = _login(client, _owner_email())
        assert r["response"].status_code == 200
        assert r["cookies"]["bb_session"] is not None

    def test_wrong_password(self, client):
        _signup(client, _owner_email())
        r = _login(client, _owner_email(), password="wrongpass123")
        assert r["response"].status_code == 401

    def test_nonexistent_email(self, client):
        r = _login(client, "nobody@test.com")
        assert r["response"].status_code == 401

    def test_logout_invalidates_session(self, client):
        r = _signup(client, _owner_email())
        cookies = r["cookies"]
        assert cookies.get("bb_session"), "No session cookie set on signup"
        # Verify authenticated
        me = client.get("/auth/api/me", cookies=cookies)
        assert me.status_code == 200
        # Logout
        client.post("/auth/api/logout", cookies=cookies,
                    headers={"Content-Type": "application/json"})
        # Session should be revoked
        me2 = client.get("/auth/api/me", cookies=cookies)
        assert me2.status_code == 401

    def test_me_returns_user_info(self, client):
        r = _signup(client, _owner_email(), "Owner User")
        cookies = r["cookies"]
        assert cookies.get("bb_session"), "No session cookie set on signup"
        resp = client.get("/auth/api/me", cookies=cookies)
        assert resp.status_code == 200
        assert resp.json()["user"]["email"] == _owner_email()
        assert resp.json()["user"]["display_name"] == "Owner User"

    def test_me_unauthenticated(self, client):
        resp = client.get("/auth/api/me")
        assert resp.status_code == 401

    def test_cookie_marked_secure_when_forwarded_https(self, client):
        resp = client.post(
            "/auth/api/signup",
            json={
                "email": _owner_email(),
                "password": "testpass123",
                "display_name": "Owner",
            },
            headers={"x-forwarded-proto": "https"},
        )
        assert resp.status_code == 200
        set_cookie = resp.headers.get("set-cookie", "")
        assert "Secure" in set_cookie


# ═══════════════════════════════════════════════════════════════════
# AUTH: Password Reset
# ═══════════════════════════════════════════════════════════════════

class TestPasswordReset:
    def test_reset_request_always_succeeds(self, client):
        # Even for non-existent emails (prevent enumeration)
        resp = client.post("/auth/api/reset-request", json={"email": "nobody@test.com"})
        assert resp.status_code == 200

    def test_invalid_reset_token_rejected(self, client):
        resp = client.post("/auth/api/reset-confirm", json={
            "token": "bogus-token", "new_password": "newpass123",
        })
        assert resp.status_code == 400

    def test_reset_flow_works(self, client):
        from app.auth import create_reset_token
        from app.database import User, get_db

        _signup(client, _owner_email())
        # Get token directly (simulating email delivery)
        db_gen = get_db()
        db = next(db_gen)
        try:
            user = db.query(User).filter(User.email == _owner_email()).first()
            assert user is not None, "User should exist after signup"
            token = create_reset_token(user, db)
        finally:
            db.close()

        # Confirm reset
        resp = client.post("/auth/api/reset-confirm", json={
            "token": token, "new_password": "brandnew123",
        })
        assert resp.status_code == 200

        # Old password should no longer work
        r = _login(client, _owner_email(), "testpass123")
        assert r["response"].status_code == 401

        # New password works
        r = _login(client, _owner_email(), "brandnew123")
        assert r["response"].status_code == 200

    def test_reset_token_single_use(self, client):
        from app.auth import create_reset_token
        from app.database import User, get_db

        _signup(client, _owner_email())
        db_gen = get_db()
        db = next(db_gen)
        try:
            user = db.query(User).filter(User.email == _owner_email()).first()
            assert user is not None, "User should exist after signup"
            token = create_reset_token(user, db)
        finally:
            db.close()

        # First use
        resp = client.post("/auth/api/reset-confirm", json={
            "token": token, "new_password": "newpass123",
        })
        assert resp.status_code == 200

        # Second use should fail
        resp = client.post("/auth/api/reset-confirm", json={
            "token": token, "new_password": "anotherpass123",
        })
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════
# RBAC: Role Hierarchy
# ═════════════════════════════════════════════════════��═════════════

def _setup_multi_user(client: TestClient) -> dict:
    """Create owner + admin, manager, user. Returns cookies dict."""
    owner = _signup(client, _owner_email(), "Owner")
    owner_cookies = owner["cookies"]

    admin = _signup(client, "admin@test.com", "Admin")
    manager = _signup(client, "manager@test.com", "Manager")
    user = _signup(client, "user@test.com", "User")

    # Get user IDs via admin endpoint
    users_resp = client.get("/admin/api/users", cookies=owner_cookies)
    assert users_resp.status_code == 200, f"Failed to list users: {users_resp.json()}"
    users = {u["email"]: u for u in users_resp.json()["users"]}

    # Promote admin
    resp = client.put(f"/admin/api/users/{users['admin@test.com']['id']}/role",
                      json={"role": "admin"}, cookies=owner_cookies)
    assert resp.status_code == 200
    # Re-login admin to get updated role in token
    admin = _login(client, "admin@test.com")

    # Promote manager
    resp = client.put(f"/admin/api/users/{users['manager@test.com']['id']}/role",
                      json={"role": "manager"}, cookies=owner_cookies)
    assert resp.status_code == 200

    return {
        "owner": owner_cookies,
        "admin": admin["cookies"],
        "manager": manager["cookies"],
        "user": user["cookies"],
        "user_ids": {email: u["id"] for email, u in users.items()},
    }


class TestRBAC:
    def test_regular_user_cannot_access_admin(self, client):
        ctx = _setup_multi_user(client)
        resp = client.get("/admin/api/users", cookies=ctx["user"])
        assert resp.status_code == 403

    def test_manager_cannot_access_admin(self, client):
        ctx = _setup_multi_user(client)
        resp = client.get("/admin/api/users", cookies=ctx["manager"])
        assert resp.status_code == 403

    def test_admin_can_access_admin(self, client):
        ctx = _setup_multi_user(client)
        resp = client.get("/admin/api/users", cookies=ctx["admin"])
        assert resp.status_code == 200

    def test_owner_can_access_admin(self, client):
        ctx = _setup_multi_user(client)
        resp = client.get("/admin/api/users", cookies=ctx["owner"])
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# RBAC: Admin Operations
# ═══════════════════════════════════════════════════════════════════

class TestAdminOperations:
    def test_admin_cannot_promote_to_admin(self, client):
        """Only owner can promote to admin."""
        ctx = _setup_multi_user(client)
        user_id = ctx["user_ids"]["user@test.com"]
        resp = client.put(f"/admin/api/users/{user_id}/role",
                          json={"role": "admin"}, cookies=ctx["admin"])
        assert resp.status_code == 403

    def test_owner_can_promote_to_admin(self, client):
        ctx = _setup_multi_user(client)
        user_id = ctx["user_ids"]["user@test.com"]
        resp = client.put(f"/admin/api/users/{user_id}/role",
                          json={"role": "admin"}, cookies=ctx["owner"])
        assert resp.status_code == 200
        assert resp.json()["user"]["role"] == "admin"

    def test_cannot_change_own_role(self, client):
        ctx = _setup_multi_user(client)
        owner_id = ctx["user_ids"][_owner_email()]
        resp = client.put(f"/admin/api/users/{owner_id}/role",
                          json={"role": "user"}, cookies=ctx["owner"])
        assert resp.status_code == 400

    def test_cannot_modify_owner_role(self, client):
        ctx = _setup_multi_user(client)
        owner_id = ctx["user_ids"][_owner_email()]
        resp = client.put(f"/admin/api/users/{owner_id}/role",
                          json={"role": "admin"}, cookies=ctx["admin"])
        assert resp.status_code == 403

    def test_deactivate_user_revokes_sessions(self, client):
        ctx = _setup_multi_user(client)
        user_id = ctx["user_ids"]["user@test.com"]
        # Deactivate
        resp = client.put(f"/admin/api/users/{user_id}/active",
                          json={"is_active": False}, cookies=ctx["admin"])
        assert resp.status_code == 200
        # User's session should now be invalid
        me = client.get("/auth/api/me", cookies=ctx["user"])
        assert me.status_code == 401

    def test_cannot_deactivate_owner(self, client):
        ctx = _setup_multi_user(client)
        owner_id = ctx["user_ids"][_owner_email()]
        resp = client.put(f"/admin/api/users/{owner_id}/active",
                          json={"is_active": False}, cookies=ctx["admin"])
        assert resp.status_code == 403

    def test_cannot_delete_owner(self, client):
        ctx = _setup_multi_user(client)
        owner_id = ctx["user_ids"][_owner_email()]
        resp = client.delete(f"/admin/api/users/{owner_id}", cookies=ctx["admin"])
        assert resp.status_code == 403

    def test_delete_user(self, client):
        ctx = _setup_multi_user(client)
        user_id = ctx["user_ids"]["user@test.com"]
        resp = client.delete(f"/admin/api/users/{user_id}", cookies=ctx["admin"])
        assert resp.status_code == 200
        # Verify user is gone
        users_resp = client.get("/admin/api/users", cookies=ctx["admin"])
        emails = [u["email"] for u in users_resp.json()["users"]]
        assert "user@test.com" not in emails

    def test_non_owner_admin_cannot_delete_other_admin(self, client):
        ctx = _setup_multi_user(client)
        # Create second admin
        client.put("/admin/api/settings/signup", json={"open_signup": True}, cookies=ctx["owner"])
        r = _signup(client, "admin2@test.com", "Admin2")
        users_resp = client.get("/admin/api/users", cookies=ctx["owner"])
        admin2_id = next(u["id"] for u in users_resp.json()["users"] if u["email"] == "admin2@test.com")
        client.put(f"/admin/api/users/{admin2_id}/role", json={"role": "admin"}, cookies=ctx["owner"])
        # First admin tries to delete second admin
        resp = client.delete(f"/admin/api/users/{admin2_id}", cookies=ctx["admin"])
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════
# RBAC: Ownership Transfer
# ═══════════════════════════════════════════════════════════════════

class TestOwnershipTransfer:
    def test_transfer_ownership_to_any_active_user(self, client):
        ctx = _setup_multi_user(client)
        admin_id = ctx["user_ids"]["admin@test.com"]
        resp = client.post("/admin/api/transfer-ownership",
                           json={"target_user_id": admin_id}, cookies=ctx["owner"])
        assert resp.status_code == 200
        assert resp.json()["user"]["role"] == "owner"

    def test_non_owner_cannot_transfer(self, client):
        ctx = _setup_multi_user(client)
        user_id = ctx["user_ids"]["user@test.com"]
        resp = client.post("/admin/api/transfer-ownership",
                           json={"target_user_id": user_id}, cookies=ctx["admin"])
        assert resp.status_code == 403

    def test_cannot_transfer_to_self(self, client):
        ctx = _setup_multi_user(client)
        owner_id = ctx["user_ids"][_owner_email()]
        resp = client.post("/admin/api/transfer-ownership",
                           json={"target_user_id": owner_id}, cookies=ctx["owner"])
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════
# RBAC: System Settings
# ═══════════════════════════════════════════════════════════════════

class TestSystemSettings:
    def test_toggle_signup(self, client):
        ctx = _setup_multi_user(client)
        # Disable signup
        resp = client.put("/admin/api/settings/signup",
                          json={"open_signup": False}, cookies=ctx["admin"])
        assert resp.status_code == 200
        # Verify
        resp = client.get("/admin/api/settings", cookies=ctx["admin"])
        assert resp.json()["open_signup"] is False

    def test_user_cannot_change_settings(self, client):
        ctx = _setup_multi_user(client)
        resp = client.put("/admin/api/settings/signup",
                          json={"open_signup": True}, cookies=ctx["user"])
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════
# RBAC: Audit Log
# ═══════════════════════════════════════════════════════════════════

class TestAuditLog:
    def test_admin_actions_are_logged(self, client):
        ctx = _setup_multi_user(client)
        # The setup already performed role changes, so audit log should have entries
        resp = client.get("/admin/api/audit-log", cookies=ctx["admin"])
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        assert len(entries) > 0
        actions = [e["action"] for e in entries]
        assert "role_change" in actions

    def test_user_cannot_view_audit_log(self, client):
        ctx = _setup_multi_user(client)
        resp = client.get("/admin/api/audit-log", cookies=ctx["user"])
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════
# Rate Limiting
# ═══════════════════════════════════════════════════════════════════

class TestRateLimiting:
    def test_login_rate_limited(self, client):
        """After 10 rapid login attempts, should get 429."""
        for _ in range(10):
            client.post("/auth/api/login", json={"email": "x@x.com", "password": "wrong"})
        resp = client.post("/auth/api/login", json={"email": "x@x.com", "password": "wrong"})
        assert resp.status_code == 429
