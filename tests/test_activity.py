"""Tests for activity logging: log entries, filtering, stats, and recent activity."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    from app.auth_routes import _reset_rate_limiter
    _reset_rate_limiter()
    yield
    _reset_rate_limiter()


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture()
def app(db_path: Path):
    from fastapi import FastAPI
    from app.auth import configure_secret_key
    from app.database import init_db
    from app.auth_routes import router as auth_router
    from app.inventory_routes import router as inventory_router
    from app.activity import router as activity_router

    init_db(db_path)
    configure_secret_key("test-secret-key-for-activity-testing")
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(inventory_router)
    app.include_router(activity_router)
    return app


@pytest.fixture()
def client(app) -> TestClient:
    return TestClient(app)


def _owner_email() -> str:
    from app.auth import OWNER_EMAIL
    return OWNER_EMAIL


@pytest.fixture()
def auth_user(client: TestClient):
    resp = client.post("/auth/api/signup", json={
        "email": _owner_email(),
        "password": "testpass123",
        "display_name": "Test User",
    })
    assert resp.status_code == 200
    return {"bb_session": resp.cookies.get("bb_session")}


# ── Activity API Tests ──────────────────────────────────────────────


def test_activity_page_requires_auth(client: TestClient):
    resp = client.get("/activity", follow_redirects=False)
    assert resp.status_code in (307, 401)


def test_activity_api_requires_auth(client: TestClient):
    resp = client.get("/api/activity")
    assert resp.status_code == 401


def test_activity_empty_on_start(client: TestClient, auth_user):
    # Signup itself logs activity, so we check structure rather than emptiness
    resp = client.get("/api/activity", cookies=auth_user)
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data
    assert "total" in data
    assert isinstance(data["entries"], list)
    assert isinstance(data["total"], int)


def test_activity_logged_on_signup(client: TestClient, auth_user):
    resp = client.get("/api/activity?category=auth", cookies=auth_user)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    found = any("Sign" in e.get("action", "") or "sign" in e.get("action", "").lower()
                 for e in data["entries"])
    assert found, "Signup should be logged as auth activity"


def test_activity_logged_on_inventory_create(client: TestClient, auth_user):
    # Create an inventory item to generate activity
    client.post("/api/inventory", cookies=auth_user, json={
        "name": "Activity Test Widget",
        "sku": "ACT-001",
    })
    resp = client.get("/api/activity?category=inventory", cookies=auth_user)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


def test_activity_filter_by_category(client: TestClient, auth_user):
    resp = client.get("/api/activity?category=nonexistent", cookies=auth_user)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert len(data["entries"]) == 0


def test_activity_search(client: TestClient, auth_user):
    resp = client.get("/api/activity?q=Sign", cookies=auth_user)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["entries"], list)


def test_activity_pagination(client: TestClient, auth_user):
    resp = client.get("/api/activity?limit=1&offset=0", cookies=auth_user)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["entries"]) <= 1


def test_activity_stats(client: TestClient, auth_user):
    resp = client.get("/api/activity/stats", cookies=auth_user)
    assert resp.status_code == 200
    data = resp.json()
    assert "today" in data
    assert "week" in data
    assert "total" in data
    assert "week_by_category" in data
    assert isinstance(data["week_by_category"], dict)


def test_activity_recent(client: TestClient, auth_user):
    resp = client.get("/api/activity/recent", cookies=auth_user)
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data
    assert isinstance(data["entries"], list)


def test_activity_recent_limit(client: TestClient, auth_user):
    resp = client.get("/api/activity/recent?limit=1", cookies=auth_user)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["entries"]) <= 1


def test_activity_days_param(client: TestClient, auth_user):
    resp = client.get("/api/activity?days=1", cookies=auth_user)
    assert resp.status_code == 200


def test_activity_page_html(client: TestClient, auth_user):
    resp = client.get("/activity", cookies=auth_user)
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
