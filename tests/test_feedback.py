"""Tests for the feedback widget: submission, validation, and page rendering."""

from __future__ import annotations

import json
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
    return tmp_path / "test.db"


@pytest.fixture()
def feedback_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setenv("BB_LOG_PATH", str(log_dir))
    return log_dir / "feedback.jsonl"


@pytest.fixture()
def app(db_path: Path):
    from fastapi import FastAPI
    from app.auth import configure_secret_key
    from app.database import init_db
    from app.auth_routes import router as auth_router
    from app.activity import router as activity_router
    from app.feedback import router as feedback_router

    init_db(db_path)
    configure_secret_key("test-secret-key-for-feedback-test!")
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(activity_router)
    app.include_router(feedback_router)
    return app


@pytest.fixture()
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture()
def auth_cookies(client: TestClient) -> dict:
    resp = client.post("/auth/api/signup", json={
        "email": "owner@test.com",
        "password": "testpass123",
        "display_name": "Test Owner",
    })
    assert resp.status_code == 200
    return {"bb_session": resp.cookies.get("bb_session")}


# ── Submission tests ────────────────────────────────────────────────


def test_submit_bug_report(client: TestClient, auth_cookies: dict, feedback_file: Path):
    resp = client.post("/api/feedback", json={
        "feedback_type": "bug",
        "message": "The scan page crashes when I upload a large file.",
        "page_url": "/scan",
    }, cookies=auth_cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True

    # Verify JSONL file was written
    assert feedback_file.exists()
    lines = feedback_file.read_text().strip().split("\n")
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["feedback_type"] == "bug"
    assert "large file" in entry["message"]
    assert entry["user_email"] == "owner@test.com"
    assert entry["app_version"]
    assert entry["timestamp"]


def test_submit_feature_request(client: TestClient, auth_cookies: dict, feedback_file: Path):
    resp = client.post("/api/feedback", json={
        "feedback_type": "feature",
        "message": "Add dark mode toggle.",
    }, cookies=auth_cookies)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    entry = json.loads(feedback_file.read_text().strip())
    assert entry["feedback_type"] == "feature"


def test_submit_question(client: TestClient, auth_cookies: dict, feedback_file: Path):
    resp = client.post("/api/feedback", json={
        "feedback_type": "question",
        "message": "How do I set up the AI chatbot?",
    }, cookies=auth_cookies)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_multiple_submissions_append(client: TestClient, auth_cookies: dict, feedback_file: Path):
    for ftype in ("bug", "feature", "question"):
        resp = client.post("/api/feedback", json={
            "feedback_type": ftype,
            "message": f"Test {ftype} message.",
        }, cookies=auth_cookies)
        assert resp.status_code == 200

    lines = feedback_file.read_text().strip().split("\n")
    assert len(lines) == 3


# ── Validation tests ────────────────────────────────────────────────


def test_reject_empty_message(client: TestClient, auth_cookies: dict):
    resp = client.post("/api/feedback", json={
        "feedback_type": "bug",
        "message": "",
    }, cookies=auth_cookies)
    assert resp.status_code == 422


def test_reject_invalid_type(client: TestClient, auth_cookies: dict):
    resp = client.post("/api/feedback", json={
        "feedback_type": "complaint",
        "message": "This should fail validation.",
    }, cookies=auth_cookies)
    assert resp.status_code == 422


def test_reject_unauthenticated(client: TestClient):
    resp = client.post("/api/feedback", json={
        "feedback_type": "bug",
        "message": "Should be rejected.",
    })
    assert resp.status_code in (401, 403, 307)


# ── Page rendering test ─────────────────────────────────────────────


def test_feedback_page_renders(client: TestClient, auth_cookies: dict):
    resp = client.get("/feedback", cookies=auth_cookies)
    assert resp.status_code == 200
    assert "Help &amp; Feedback" in resp.text or "Help & Feedback" in resp.text
    assert "fb-submit" in resp.text
    assert "Bug Report" in resp.text
    assert "Feature Request" in resp.text
