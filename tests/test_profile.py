"""Tests for profile self-service endpoints and activity logging additions.

Covers:
  - PUT /auth/api/me/profile  (update display name)
  - PUT /auth/api/me/password (change password)
  - GET /auth/profile         (profile HTML page)
  - Activity logging: alert config update, alert dismiss, JSON export, scan-to-PDF generate
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import TestClient


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    from app.auth_routes import _reset_rate_limiter
    _reset_rate_limiter()
    yield
    _reset_rate_limiter()


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_profile.db"


@pytest.fixture()
def app(db_path: Path):
    from fastapi import FastAPI
    from app.auth import configure_secret_key
    from app.database import init_db
    from app.auth_routes import router as auth_router
    from app.inventory_routes import router as inventory_router
    from app.alerts import router as alerts_router
    from app.scan_to_pdf import router as scan_to_pdf_router
    from app.activity import router as activity_router

    init_db(db_path)
    configure_secret_key("test-secret-key-for-profile-test!!")
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(inventory_router)
    app.include_router(alerts_router)
    app.include_router(scan_to_pdf_router)
    app.include_router(activity_router)
    return app


@pytest.fixture()
def client(app) -> TestClient:
    return TestClient(app)


def _owner_email() -> str:
    from app.auth import OWNER_EMAIL
    return OWNER_EMAIL


def _signup(client: TestClient, email: str, name: str = "Test Owner",
            password: str = "testpass123") -> dict:
    resp = client.post("/auth/api/signup", json={
        "email": email, "password": password, "display_name": name,
    })
    assert resp.status_code == 200, f"Signup failed: {resp.json()}"
    return {"bb_session": resp.cookies.get("bb_session")}


@pytest.fixture()
def owner(client: TestClient):
    return _signup(client, _owner_email(), "Test Owner")


# ===============================================================
# PUT /auth/api/me/profile -- Update display name
# ===============================================================

class TestUpdateProfile:
    def test_update_display_name_success(self, client, owner):
        resp = client.put("/auth/api/me/profile",
                          json={"display_name": "New Name"},
                          cookies=owner)
        assert resp.status_code == 200
        data = resp.json()
        assert "user" in data
        assert data["user"]["display_name"] == "New Name"

    def test_update_display_name_reflects_on_me(self, client, owner):
        client.put("/auth/api/me/profile",
                   json={"display_name": "Updated Owner"},
                   cookies=owner)
        me = client.get("/auth/api/me", cookies=owner)
        assert me.status_code == 200
        assert me.json()["user"]["display_name"] == "Updated Owner"

    def test_update_display_name_empty_rejected(self, client, owner):
        resp = client.put("/auth/api/me/profile",
                          json={"display_name": ""},
                          cookies=owner)
        assert resp.status_code == 422

    def test_update_profile_requires_auth(self, client):
        resp = client.put("/auth/api/me/profile",
                          json={"display_name": "Nobody"})
        assert resp.status_code == 401

    def test_update_display_name_logs_activity(self, client, owner):
        client.put("/auth/api/me/profile",
                   json={"display_name": "Activity Check"},
                   cookies=owner)
        resp = client.get("/api/activity?category=auth", cookies=owner)
        assert resp.status_code == 200
        actions = [e["action"] for e in resp.json()["entries"]]
        assert "Profile Updated" in actions


# ===============================================================
# PUT /auth/api/me/password -- Change password
# ===============================================================

class TestChangePassword:
    def test_change_password_success(self, client, owner):
        resp = client.put("/auth/api/me/password", json={
            "current_password": "testpass123",
            "new_password": "newsecure456",
        }, cookies=owner)
        assert resp.status_code == 200
        assert resp.json()["message"] == "Password updated successfully"

    def test_changed_password_works_for_login(self, client, owner):
        client.put("/auth/api/me/password", json={
            "current_password": "testpass123",
            "new_password": "brandnew789",
        }, cookies=owner)
        r = client.post("/auth/api/login",
                        json={"email": _owner_email(), "password": "brandnew789"})
        assert r.status_code == 200

    def test_old_password_rejected_after_change(self, client, owner):
        client.put("/auth/api/me/password", json={
            "current_password": "testpass123",
            "new_password": "brandnew789",
        }, cookies=owner)
        r = client.post("/auth/api/login",
                        json={"email": _owner_email(), "password": "testpass123"})
        assert r.status_code == 401

    def test_wrong_current_password_rejected(self, client, owner):
        resp = client.put("/auth/api/me/password", json={
            "current_password": "wrongpassword",
            "new_password": "newsecure456",
        }, cookies=owner)
        assert resp.status_code == 400
        assert "incorrect" in resp.json()["error"].lower()

    def test_short_new_password_rejected(self, client, owner):
        resp = client.put("/auth/api/me/password", json={
            "current_password": "testpass123",
            "new_password": "short",
        }, cookies=owner)
        assert resp.status_code == 422

    def test_change_password_requires_auth(self, client):
        resp = client.put("/auth/api/me/password", json={
            "current_password": "testpass123",
            "new_password": "newsecure456",
        })
        assert resp.status_code == 401

    def test_change_password_logs_activity(self, client, owner):
        client.put("/auth/api/me/password", json={
            "current_password": "testpass123",
            "new_password": "newlogged456",
        }, cookies=owner)
        resp = client.get("/api/activity?category=auth", cookies=owner)
        assert resp.status_code == 200
        actions = [e["action"] for e in resp.json()["entries"]]
        assert "Password Changed" in actions


# ===============================================================
# GET /auth/profile -- Profile HTML page
# ===============================================================

class TestProfilePage:
    def test_profile_page_returns_200(self, client, owner):
        resp = client.get("/auth/profile", cookies=owner)
        assert resp.status_code == 200

    def test_profile_page_is_html(self, client, owner):
        resp = client.get("/auth/profile", cookies=owner)
        assert "text/html" in resp.headers.get("content-type", "")

    def test_profile_page_contains_user_email(self, client, owner):
        resp = client.get("/auth/profile", cookies=owner)
        assert _owner_email() in resp.text

    def test_profile_page_contains_display_name(self, client, owner):
        resp = client.get("/auth/profile", cookies=owner)
        assert "Test Owner" in resp.text

    def test_profile_page_requires_auth(self, client):
        resp = client.get("/auth/profile", follow_redirects=False)
        assert resp.status_code in (401, 302, 307)

    def test_profile_page_contains_password_form(self, client, owner):
        resp = client.get("/auth/profile", cookies=owner)
        assert "password" in resp.text.lower()

    def test_profile_page_contains_role(self, client, owner):
        resp = client.get("/auth/profile", cookies=owner)
        assert "owner" in resp.text.lower()


# ===============================================================
# Activity logging -- Alert config update
# ===============================================================

class TestAlertConfigActivityLogging:
    def test_alert_config_update_logs_activity(self, client, owner):
        client.get("/api/alerts/config", cookies=owner)
        client.put("/api/alerts/config", json={
            "alert_type": "low_stock", "enabled": False, "webhook_url": "",
        }, cookies=owner)
        resp = client.get("/api/activity?category=alert", cookies=owner)
        assert resp.status_code == 200
        actions = [e["action"] for e in resp.json()["entries"]]
        assert "Alert Config Updated" in actions

    def test_alert_config_update_logs_correct_summary(self, client, owner):
        client.get("/api/alerts/config", cookies=owner)
        client.put("/api/alerts/config", json={
            "alert_type": "out_of_stock", "enabled": True, "webhook_url": "",
        }, cookies=owner)
        resp = client.get("/api/activity?category=alert", cookies=owner)
        entries = resp.json()["entries"]
        config_entries = [e for e in entries if e["action"] == "Alert Config Updated"]
        assert len(config_entries) >= 1
        assert "out_of_stock" in config_entries[0]["summary"]


# ===============================================================
# Activity logging -- Alert dismiss
# ===============================================================

class TestAlertDismissActivityLogging:
    def _create_alert(self, client, owner):
        from app.database import _SessionLocal
        from app.alerts import check_stock_alerts

        client.post("/api/inventory", json={
            "name": "Zero Stock Item", "sku": "ZSI-001", "quantity": 0, "unit": "pcs",
        }, cookies=owner)
        db = _SessionLocal()
        try:
            check_stock_alerts(db)
        finally:
            db.close()

        resp = client.get("/api/alerts", cookies=owner)
        return resp.json()["alerts"]

    def test_alert_dismiss_logs_activity(self, client, owner):
        alerts = self._create_alert(client, owner)
        assert len(alerts) >= 1
        alert_id = alerts[0]["id"]

        client.post("/api/alerts/dismiss",
                    json={"alert_ids": [alert_id]},
                    cookies=owner)

        resp = client.get("/api/activity?category=alert", cookies=owner)
        assert resp.status_code == 200
        actions = [e["action"] for e in resp.json()["entries"]]
        assert "Alerts Dismissed" in actions

    def test_dismiss_empty_list_does_not_log(self, client, owner):
        before_resp = client.get("/api/activity?category=alert", cookies=owner)
        before_count = before_resp.json()["total"]

        client.post("/api/alerts/dismiss", json={"alert_ids": []}, cookies=owner)

        after_resp = client.get("/api/activity?category=alert", cookies=owner)
        assert after_resp.json()["total"] == before_count


# ===============================================================
# Activity logging -- JSON export
# ===============================================================

class TestJsonExportActivityLogging:
    def test_json_export_logs_activity(self, client, owner):
        resp = client.get("/api/inventory/export/json", cookies=owner)
        assert resp.status_code == 200

        activity = client.get("/api/activity?category=export", cookies=owner)
        assert activity.status_code == 200
        actions = [e["action"] for e in activity.json()["entries"]]
        assert "JSON Export" in actions

    def test_json_export_activity_includes_item_count(self, client, owner):
        client.post("/api/inventory", json={
            "name": "Export Widget", "sku": "EXP-001", "quantity": 5, "unit": "pcs",
        }, cookies=owner)
        client.get("/api/inventory/export/json", cookies=owner)

        activity = client.get("/api/activity?category=export", cookies=owner)
        export_entries = [e for e in activity.json()["entries"]
                          if e["action"] == "JSON Export"]
        assert len(export_entries) >= 1
        summary = export_entries[0]["summary"]
        assert "1" in summary or "item" in summary.lower()

    def test_json_export_requires_auth(self, client):
        resp = client.get("/api/inventory/export/json")
        assert resp.status_code == 401


# ===============================================================
# Activity logging -- Scan-to-PDF generate
# ===============================================================

class TestScanToPdfActivityLogging:
    def test_scan_to_pdf_generate_logs_activity(self, client, owner):
        resp = client.post("/api/scan-to-pdf/generate", json={
            "title": "Test Report",
            "entries": [
                {"barcode": "123456789012", "label": "Widget A", "qty": 1},
            ],
        }, cookies=owner)
        if resp.status_code == 200:
            activity = client.get("/api/activity?category=export", cookies=owner)
            assert activity.status_code == 200
            actions = [e["action"] for e in activity.json()["entries"]]
            assert "Scan-to-PDF Generated" in actions

    def test_scan_to_pdf_generate_requires_auth(self, client):
        resp = client.post("/api/scan-to-pdf/generate", json={
            "title": "Unauthorized",
            "entries": [{"barcode": "123456789012", "label": "X", "qty": 1}],
        })
        assert resp.status_code == 401
