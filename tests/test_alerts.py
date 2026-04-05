"""Tests for alert system: API endpoints, stock checks, webhook validation, and SSRF prevention."""

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
    return tmp_path / "test_alerts.db"


@pytest.fixture()
def app(db_path: Path):
    from fastapi import FastAPI
    from app.auth import configure_secret_key
    from app.database import init_db
    from app.auth_routes import router as auth_router
    from app.inventory_routes import router as inventory_router
    from app.alerts import router as alerts_router

    init_db(db_path)
    configure_secret_key("test-secret-key-for-alerts-test!!")
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(inventory_router)
    app.include_router(alerts_router)
    return app


@pytest.fixture()
def client(app) -> TestClient:
    return TestClient(app)


def _owner_email() -> str:
    from app.auth import OWNER_EMAIL
    return OWNER_EMAIL


def _signup(client: TestClient, email: str, name: str = "User", password: str = "testpass123") -> dict:
    resp = client.post("/auth/api/signup", json={
        "email": email, "password": password, "display_name": name,
    })
    return {"response": resp, "cookies": {"bb_session": resp.cookies.get("bb_session")}}


def _create_item(client: TestClient, cookies: dict, **overrides) -> dict:
    payload = {"name": "Widget", "sku": "W-001", "quantity": 10, "unit": "pcs", **overrides}
    resp = client.post("/api/inventory", json=payload, cookies=cookies)
    return resp.json()["item"]


# ── Alert list and count ──────────────────────────────────────────

class TestAlertListAndCount:
    def test_list_alerts_empty(self, client):
        owner = _signup(client, _owner_email(), "Owner")
        resp = client.get("/api/alerts", cookies=owner["cookies"])
        assert resp.status_code == 200
        data = resp.json()
        assert data["alerts"] == []
        assert data["unread_count"] == 0

    def test_alert_count_empty(self, client):
        owner = _signup(client, _owner_email(), "Owner")
        resp = client.get("/api/alerts/count", cookies=owner["cookies"])
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 0

    def test_list_alerts_requires_auth(self, client):
        resp = client.get("/api/alerts")
        assert resp.status_code in (401, 403)

    def test_alert_count_requires_auth(self, client):
        resp = client.get("/api/alerts/count")
        assert resp.status_code in (401, 403)


# ── Alert read/dismiss ────────────────────────────────────────────

class TestAlertReadDismiss:
    def test_mark_read_empty_list(self, client):
        owner = _signup(client, _owner_email(), "Owner")
        resp = client.post("/api/alerts/read", json={"alert_ids": []}, cookies=owner["cookies"])
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_dismiss_empty_list(self, client):
        owner = _signup(client, _owner_email(), "Owner")
        resp = client.post("/api/alerts/dismiss", json={"alert_ids": []}, cookies=owner["cookies"])
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_dismiss_all(self, client):
        owner = _signup(client, _owner_email(), "Owner")
        resp = client.post("/api/alerts/dismiss-all", json={}, cookies=owner["cookies"])
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


# ── Alert config ──────────────────────────────────────────────────

class TestAlertConfig:
    def test_get_config_creates_defaults(self, client):
        owner = _signup(client, _owner_email(), "Owner")
        resp = client.get("/api/alerts/config", cookies=owner["cookies"])
        assert resp.status_code == 200
        configs = resp.json()["configs"]
        types = {c["alert_type"] for c in configs}
        assert "low_stock" in types
        assert "out_of_stock" in types
        for c in configs:
            assert c["enabled"] is True
            assert c["webhook_url"] == ""

    def test_update_config_toggle(self, client):
        owner = _signup(client, _owner_email(), "Owner")
        # First get defaults
        client.get("/api/alerts/config", cookies=owner["cookies"])
        # Disable low_stock
        resp = client.put("/api/alerts/config", json={
            "alert_type": "low_stock", "enabled": False, "webhook_url": "",
        }, cookies=owner["cookies"])
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        # Verify
        resp = client.get("/api/alerts/config", cookies=owner["cookies"])
        low = next(c for c in resp.json()["configs"] if c["alert_type"] == "low_stock")
        assert low["enabled"] is False

    def test_update_config_webhook_url(self, client):
        owner = _signup(client, _owner_email(), "Owner")
        resp = client.put("/api/alerts/config", json={
            "alert_type": "low_stock", "enabled": True,
            "webhook_url": "https://hooks.slack.com/services/test",
        }, cookies=owner["cookies"])
        assert resp.status_code == 200
        resp = client.get("/api/alerts/config", cookies=owner["cookies"])
        low = next(c for c in resp.json()["configs"] if c["alert_type"] == "low_stock")
        assert low["webhook_url"] == "https://hooks.slack.com/services/test"

    def test_config_requires_auth(self, client):
        resp = client.get("/api/alerts/config")
        assert resp.status_code in (401, 403)


# ── SSRF prevention on webhook URLs ──────────────────────────────

class TestWebhookSSRF:
    def test_reject_localhost(self, client):
        owner = _signup(client, _owner_email(), "Owner")
        resp = client.put("/api/alerts/config", json={
            "alert_type": "low_stock", "enabled": True,
            "webhook_url": "http://localhost:8080/admin/delete",
        }, cookies=owner["cookies"])
        assert resp.status_code == 400
        assert "localhost" in resp.json()["error"].lower()

    def test_reject_private_ip(self, client):
        owner = _signup(client, _owner_email(), "Owner")
        resp = client.put("/api/alerts/config", json={
            "alert_type": "low_stock", "enabled": True,
            "webhook_url": "http://192.168.1.1/hook",
        }, cookies=owner["cookies"])
        assert resp.status_code == 400
        assert "private" in resp.json()["error"].lower()

    def test_reject_loopback_ip(self, client):
        owner = _signup(client, _owner_email(), "Owner")
        resp = client.put("/api/alerts/config", json={
            "alert_type": "low_stock", "enabled": True,
            "webhook_url": "http://127.0.0.1:9090/hook",
        }, cookies=owner["cookies"])
        assert resp.status_code == 400
        assert "private" in resp.json()["error"].lower()

    def test_reject_link_local(self, client):
        owner = _signup(client, _owner_email(), "Owner")
        resp = client.put("/api/alerts/config", json={
            "alert_type": "low_stock", "enabled": True,
            "webhook_url": "http://169.254.169.254/latest/meta-data",
        }, cookies=owner["cookies"])
        assert resp.status_code == 400
        assert "private" in resp.json()["error"].lower()

    def test_reject_internal_10_range(self, client):
        owner = _signup(client, _owner_email(), "Owner")
        resp = client.put("/api/alerts/config", json={
            "alert_type": "low_stock", "enabled": True,
            "webhook_url": "http://10.0.0.1/hook",
        }, cookies=owner["cookies"])
        assert resp.status_code == 400

    def test_reject_ftp_scheme(self, client):
        owner = _signup(client, _owner_email(), "Owner")
        resp = client.put("/api/alerts/config", json={
            "alert_type": "low_stock", "enabled": True,
            "webhook_url": "ftp://example.com/hook",
        }, cookies=owner["cookies"])
        assert resp.status_code == 400
        assert "http" in resp.json()["error"].lower()

    def test_allow_valid_external_url(self, client):
        owner = _signup(client, _owner_email(), "Owner")
        resp = client.put("/api/alerts/config", json={
            "alert_type": "low_stock", "enabled": True,
            "webhook_url": "https://hooks.slack.com/services/T00/B00/xxx",
        }, cookies=owner["cookies"])
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_allow_empty_webhook(self, client):
        owner = _signup(client, _owner_email(), "Owner")
        resp = client.put("/api/alerts/config", json={
            "alert_type": "low_stock", "enabled": True,
            "webhook_url": "",
        }, cookies=owner["cookies"])
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


# ── Stock alert scheduler ─────────────────────────────────────────

class TestStockAlertChecker:
    def test_out_of_stock_creates_alert(self, client):
        from app.database import _SessionLocal
        from app.alerts import check_stock_alerts

        owner = _signup(client, _owner_email(), "Owner")
        _create_item(client, owner["cookies"], name="Empty Widget", sku="EW-001", quantity=0)

        db = _SessionLocal()
        try:
            created = check_stock_alerts(db)
            assert len(created) == 1
            assert created[0]["type"] == "out_of_stock"
            assert created[0]["item"] == "Empty Widget"
        finally:
            db.close()

        # Verify alert appears in API
        resp = client.get("/api/alerts", cookies=owner["cookies"])
        alerts = resp.json()["alerts"]
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "out_of_stock"
        assert alerts[0]["severity"] == "critical"
        assert "Empty Widget" in alerts[0]["title"]

    def test_low_stock_creates_alert(self, client):
        from app.database import _SessionLocal, InventoryItem
        from app.alerts import check_stock_alerts

        owner = _signup(client, _owner_email(), "Owner")
        item_data = _create_item(client, owner["cookies"], name="Low Widget", sku="LW-001", quantity=3)

        # Set min_quantity via DB (not exposed in create API for simplicity)
        db = _SessionLocal()
        try:
            item = db.query(InventoryItem).filter(InventoryItem.id == item_data["id"]).first()
            item.min_quantity = 5
            db.commit()
            created = check_stock_alerts(db)
            assert len(created) == 1
            assert created[0]["type"] == "low_stock"
        finally:
            db.close()

    def test_no_alert_for_healthy_stock(self, client):
        from app.database import _SessionLocal
        from app.alerts import check_stock_alerts

        owner = _signup(client, _owner_email(), "Owner")
        _create_item(client, owner["cookies"], name="Healthy Widget", sku="HW-001", quantity=100)

        db = _SessionLocal()
        try:
            created = check_stock_alerts(db)
            assert len(created) == 0
        finally:
            db.close()

    def test_no_duplicate_alert(self, client):
        from app.database import _SessionLocal
        from app.alerts import check_stock_alerts

        owner = _signup(client, _owner_email(), "Owner")
        _create_item(client, owner["cookies"], name="Empty Widget", sku="EW-002", quantity=0)

        db = _SessionLocal()
        try:
            first = check_stock_alerts(db)
            assert len(first) == 1
            second = check_stock_alerts(db)
            assert len(second) == 0  # Duplicate suppressed
        finally:
            db.close()

    def test_disabled_config_suppresses_alert(self, client):
        from app.database import _SessionLocal
        from app.alerts import check_stock_alerts

        owner = _signup(client, _owner_email(), "Owner")
        _create_item(client, owner["cookies"], name="Empty Widget", sku="EW-003", quantity=0)

        # Disable out_of_stock alerts
        client.put("/api/alerts/config", json={
            "alert_type": "out_of_stock", "enabled": False, "webhook_url": "",
        }, cookies=owner["cookies"])

        db = _SessionLocal()
        try:
            created = check_stock_alerts(db)
            assert len(created) == 0
        finally:
            db.close()


# ── Alert read/dismiss with real alerts ───────────────────────────

class TestAlertLifecycle:
    def test_mark_read_and_dismiss_lifecycle(self, client):
        from app.database import _SessionLocal
        from app.alerts import check_stock_alerts

        owner = _signup(client, _owner_email(), "Owner")
        _create_item(client, owner["cookies"], name="Empty", sku="LC-001", quantity=0)

        db = _SessionLocal()
        try:
            check_stock_alerts(db)
        finally:
            db.close()

        # Get alerts
        resp = client.get("/api/alerts", cookies=owner["cookies"])
        alerts = resp.json()["alerts"]
        assert len(alerts) == 1
        alert_id = alerts[0]["id"]
        assert alerts[0]["is_read"] is False

        # Count should be 1
        resp = client.get("/api/alerts/count", cookies=owner["cookies"])
        assert resp.json()["unread_count"] == 1

        # Mark read
        resp = client.post("/api/alerts/read", json={"alert_ids": [alert_id]}, cookies=owner["cookies"])
        assert resp.status_code == 200

        # Count should be 0
        resp = client.get("/api/alerts/count", cookies=owner["cookies"])
        assert resp.json()["unread_count"] == 0

        # Dismiss
        resp = client.post("/api/alerts/dismiss", json={"alert_ids": [alert_id]}, cookies=owner["cookies"])
        assert resp.status_code == 200

        # Alert should be gone from default list
        resp = client.get("/api/alerts", cookies=owner["cookies"])
        assert resp.json()["alerts"] == []


# ── Alerts page (HTML) ────────────────────────────────────────────

class TestAlertsPage:
    def test_alerts_page_loads(self, client):
        owner = _signup(client, _owner_email(), "Owner")
        resp = client.get("/alerts", cookies=owner["cookies"])
        assert resp.status_code == 200
        assert "Alerts" in resp.text

    def test_alerts_page_requires_auth(self, client):
        resp = client.get("/alerts")
        assert resp.status_code in (401, 403)


# ── URL validation unit tests ─────────────────────────────────────

class TestValidateWebhookUrl:
    def test_empty_string_valid(self):
        from app.alerts import validate_webhook_url
        assert validate_webhook_url("") is None

    def test_https_valid(self):
        from app.alerts import validate_webhook_url
        assert validate_webhook_url("https://example.com/webhook") is None

    def test_http_valid(self):
        from app.alerts import validate_webhook_url
        assert validate_webhook_url("http://example.com/webhook") is None

    def test_ftp_rejected(self):
        from app.alerts import validate_webhook_url
        err = validate_webhook_url("ftp://example.com")
        assert err is not None
        assert "http" in err.lower()

    def test_localhost_rejected(self):
        from app.alerts import validate_webhook_url
        err = validate_webhook_url("http://localhost/hook")
        assert err is not None

    def test_private_10_rejected(self):
        from app.alerts import validate_webhook_url
        err = validate_webhook_url("http://10.0.0.1/hook")
        assert err is not None

    def test_private_172_rejected(self):
        from app.alerts import validate_webhook_url
        err = validate_webhook_url("http://172.16.0.1/hook")
        assert err is not None

    def test_private_192_rejected(self):
        from app.alerts import validate_webhook_url
        err = validate_webhook_url("http://192.168.0.1/hook")
        assert err is not None

    def test_link_local_rejected(self):
        from app.alerts import validate_webhook_url
        err = validate_webhook_url("http://169.254.169.254/latest")
        assert err is not None

    def test_loopback_rejected(self):
        from app.alerts import validate_webhook_url
        err = validate_webhook_url("http://127.0.0.1/hook")
        assert err is not None

    def test_zero_rejected(self):
        from app.alerts import validate_webhook_url
        err = validate_webhook_url("http://0.0.0.0/hook")
        assert err is not None

    def test_no_hostname_rejected(self):
        from app.alerts import validate_webhook_url
        err = validate_webhook_url("http:///no-host")
        assert err is not None
