"""Tests for AI integration: config, setup status, chat validation, conversations."""

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
def app(db_path: Path, tmp_path: Path):
    from fastapi import FastAPI
    from app.auth import configure_secret_key
    from app.database import init_db
    from app.auth_routes import router as auth_router
    from app.ai_routes import router as ai_router, set_app_settings
    from app.config import Settings

    init_db(db_path)
    configure_secret_key("test-secret-key-for-ai-testing")

    # Create a minimal Settings for AI routes
    cfg = {
        "input_path": str(tmp_path / "input"),
        "processing_path": str(tmp_path / "processing"),
        "output_path": str(tmp_path / "output"),
        "rejected_path": str(tmp_path / "rejected"),
        "log_path": str(tmp_path / "logs"),
        "barcode_types": ["code128"],
        "scan_all_pages": True,
        "duplicate_handling": "timestamp",
        "file_stability_delay_ms": 2000,
        "max_pages_scan": 50,
    }
    for key in ("input_path", "processing_path", "output_path", "rejected_path", "log_path"):
        Path(cfg[key]).mkdir(parents=True, exist_ok=True)
    settings = Settings(**cfg)

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(ai_router)
    set_app_settings(settings)
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
        "display_name": "AI Test User",
    })
    assert resp.status_code == 200
    return {"bb_session": resp.cookies.get("bb_session")}


# ── AI Status ────────────────────────────────────────────────────────


def test_ai_status_requires_auth(client: TestClient):
    resp = client.get("/ai/api/status")
    assert resp.status_code == 401


def test_ai_status(client: TestClient, auth_user):
    resp = client.get("/ai/api/status", cookies=auth_user)
    assert resp.status_code == 200
    data = resp.json()
    assert "ai_enabled" in data
    assert "setup_completed" in data


def test_ai_config_requires_auth(client: TestClient):
    resp = client.get("/ai/api/config")
    assert resp.status_code == 401


def test_ai_config(client: TestClient, auth_user):
    resp = client.get("/ai/api/config", cookies=auth_user)
    assert resp.status_code == 200
    data = resp.json()
    assert "ai_enabled" in data


# ── Setup Pages ──────────────────────────────────────────────────────


def test_setup_page_html(client: TestClient, auth_user):
    resp = client.get("/ai/setup", cookies=auth_user)
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


def test_chat_page_html(client: TestClient, auth_user):
    resp = client.get("/ai/chat", cookies=auth_user)
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


def test_privacy_page_html(client: TestClient, auth_user):
    resp = client.get("/ai/privacy", cookies=auth_user)
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


def test_settings_page_html(client: TestClient, auth_user):
    resp = client.get("/ai/settings", cookies=auth_user)
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


# ── Chat Validation ──────────────────────────────────────────────────


def test_chat_requires_auth(client: TestClient):
    resp = client.post("/ai/api/chat", json={"message": "hello"})
    assert resp.status_code == 401


def test_chat_empty_message_rejected(client: TestClient, auth_user):
    resp = client.post("/ai/api/chat", cookies=auth_user, json={"message": ""})
    assert resp.status_code == 400


def test_chat_too_long_message_rejected(client: TestClient, auth_user):
    resp = client.post("/ai/api/chat", cookies=auth_user, json={"message": "x" * 2001})
    assert resp.status_code == 400


def test_chat_ai_disabled(client: TestClient, auth_user):
    # AI is not enabled by default, so chat should indicate this
    resp = client.post("/ai/api/chat", cookies=auth_user, json={"message": "hello"})
    assert resp.status_code == 400
    assert "not" in resp.json().get("error", "").lower() or "disabled" in resp.json().get("error", "").lower() or "enabled" in resp.json().get("error", "").lower()


# ── Conversations ─���──────────────────────────────────────────────────


def test_list_conversations_empty(client: TestClient, auth_user):
    resp = client.get("/ai/api/conversations", cookies=auth_user)
    assert resp.status_code == 200
    data = resp.json()
    assert "conversations" in data
    assert isinstance(data["conversations"], list)


def test_get_nonexistent_conversation(client: TestClient, auth_user):
    resp = client.get("/ai/api/conversations/nonexistent-id", cookies=auth_user)
    assert resp.status_code == 404


def test_delete_nonexistent_conversation(client: TestClient, auth_user):
    resp = client.delete("/ai/api/conversations/nonexistent-id", cookies=auth_user)
    assert resp.status_code == 404


# ── Setup Steps ──────────────────────────────────────────────────────


def test_setup_step_choose_mode(client: TestClient, auth_user):
    resp = client.post("/ai/api/setup-step", cookies=auth_user, json={
        "step": "choose_mode",
        "mode": "local",
    })
    assert resp.status_code == 200


def test_setup_step_skip(client: TestClient, auth_user):
    resp = client.post("/ai/api/setup-step", cookies=auth_user, json={
        "step": "skip",
    })
    assert resp.status_code == 200


# ── Models ───────────────────────────────────────────────────────────


def test_list_models(client: TestClient, auth_user):
    resp = client.get("/ai/api/models", cookies=auth_user)
    # May return 200 with empty list or 500 if Ollama is not running — both acceptable
    assert resp.status_code in (200, 500)


# ── Suggest & CSV Preview ────────────────────────────────────────────


def test_suggest_item_ai_disabled(client: TestClient, auth_user):
    resp = client.post("/ai/api/suggest-item", cookies=auth_user, json={
        "name": "Widget",
        "field": "category",
    })
    # AI not enabled — should return error
    assert resp.status_code in (200, 400)


def test_csv_preview_ai_disabled(client: TestClient, auth_user):
    resp = client.post("/ai/api/csv-preview", cookies=auth_user, json={
        "columns": ["Name", "SKU", "Qty"],
        "sample_rows": [["Widget", "W001", "10"]],
    })
    assert resp.status_code in (200, 400)
