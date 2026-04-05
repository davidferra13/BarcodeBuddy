"""Tests for team management: CRUD, membership, tasks, permissions."""

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
    from app.admin_routes import router as admin_router
    from app.team_routes import router as team_router

    init_db(db_path)
    configure_secret_key("test-secret-key-for-team-testing")
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(team_router)
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
        "display_name": "Owner User",
    })
    assert resp.status_code == 200
    return {"bb_session": resp.cookies.get("bb_session")}


@pytest.fixture()
def second_user(client: TestClient, auth_user):
    from app.database import SystemSettings, get_db
    db_gen = get_db()
    db = next(db_gen)
    try:
        settings = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
        if settings:
            settings.open_signup = True
            db.commit()
    finally:
        db.close()
    resp = client.post("/auth/api/signup", json={
        "email": "member@example.com",
        "password": "testpass123",
        "display_name": "Team Member",
    })
    assert resp.status_code == 200
    return {"bb_session": resp.cookies.get("bb_session")}


def _create_team(client, auth_user, name="Alpha Team", description="First team"):
    resp = client.post("/team/api/teams", cookies=auth_user, json={
        "name": name,
        "description": description,
    })
    assert resp.status_code == 201
    return resp.json()["team"]


# ── Team CRUD ────────────────────────────────────────────────────────


def test_create_team(client: TestClient, auth_user):
    team = _create_team(client, auth_user)
    assert team["name"] == "Alpha Team"
    assert "id" in team


def test_list_teams(client: TestClient, auth_user):
    _create_team(client, auth_user, name="Team A")
    resp = client.get("/team/api/teams", cookies=auth_user)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["teams"], list)
    assert len(data["teams"]) >= 1


def test_get_team(client: TestClient, auth_user):
    team = _create_team(client, auth_user, name="Team Detail")
    resp = client.get(f"/team/api/teams/{team['id']}", cookies=auth_user)
    assert resp.status_code == 200
    data = resp.json()
    assert data["team"]["name"] == "Team Detail"


def test_update_team(client: TestClient, auth_user):
    team = _create_team(client, auth_user, name="Old Name")
    resp = client.put(f"/team/api/teams/{team['id']}", cookies=auth_user, json={
        "name": "New Name",
        "description": "",
    })
    assert resp.status_code == 200
    assert resp.json()["team"]["name"] == "New Name"


def test_delete_team(client: TestClient, auth_user):
    team = _create_team(client, auth_user, name="Delete Me")
    resp = client.delete(f"/team/api/teams/{team['id']}", cookies=auth_user)
    assert resp.status_code == 200
    # Verify deleted
    resp = client.get(f"/team/api/teams/{team['id']}", cookies=auth_user)
    assert resp.status_code == 404


def test_create_team_requires_auth(client: TestClient):
    resp = client.post("/team/api/teams", json={"name": "No Auth"})
    assert resp.status_code == 401


def test_create_team_empty_name_rejected(client: TestClient, auth_user):
    resp = client.post("/team/api/teams", cookies=auth_user, json={"name": ""})
    assert resp.status_code == 422


# ── Membership ───────────────────────────────────────────────────────


def test_add_member(client: TestClient, auth_user, second_user):
    team = _create_team(client, auth_user, name="Member Team")
    me_resp = client.get("/auth/api/me", cookies=second_user)
    user_id = me_resp.json()["user"]["id"]

    resp = client.post(f"/team/api/teams/{team['id']}/members", cookies=auth_user, json={
        "user_id": user_id,
        "team_role": "member",
    })
    assert resp.status_code in (200, 201)


def test_remove_member(client: TestClient, auth_user, second_user):
    team = _create_team(client, auth_user, name="Remove Test")
    me_resp = client.get("/auth/api/me", cookies=second_user)
    user_id = me_resp.json()["user"]["id"]

    client.post(f"/team/api/teams/{team['id']}/members", cookies=auth_user, json={
        "user_id": user_id,
        "team_role": "member",
    })

    detail = client.get(f"/team/api/teams/{team['id']}", cookies=auth_user).json()
    member = next(m for m in detail["team"]["members"] if m["user_id"] == user_id)

    resp = client.delete(f"/team/api/teams/{team['id']}/members/{member['id']}", cookies=auth_user)
    assert resp.status_code == 200


def test_creator_is_lead(client: TestClient, auth_user):
    team = _create_team(client, auth_user, name="Lead Test")
    detail = client.get(f"/team/api/teams/{team['id']}", cookies=auth_user).json()
    assert len(detail["team"]["members"]) >= 1
    creator_member = detail["team"]["members"][0]
    assert creator_member["team_role"] == "lead"


# ── Tasks ────────────────────────────────────────────────────────────


def test_create_task(client: TestClient, auth_user):
    team = _create_team(client, auth_user, name="Task Team")
    resp = client.post(f"/team/api/teams/{team['id']}/tasks", cookies=auth_user, json={
        "title": "Fix the widget",
        "priority": "high",
    })
    assert resp.status_code in (200, 201)
    data = resp.json()["task"]
    assert data["title"] == "Fix the widget"
    assert data["priority"] == "high"
    assert data["status"] == "todo"


def test_update_task(client: TestClient, auth_user):
    team = _create_team(client, auth_user, name="Update Task Team")
    task_resp = client.post(f"/team/api/teams/{team['id']}/tasks", cookies=auth_user, json={
        "title": "Original Title",
    })
    task_id = task_resp.json()["task"]["id"]
    resp = client.put(f"/team/api/teams/{team['id']}/tasks/{task_id}", cookies=auth_user, json={
        "status": "in_progress",
        "title": "Updated Title",
    })
    assert resp.status_code == 200
    assert resp.json()["task"]["status"] == "in_progress"


def test_delete_task(client: TestClient, auth_user):
    team = _create_team(client, auth_user, name="Delete Task Team")
    task_resp = client.post(f"/team/api/teams/{team['id']}/tasks", cookies=auth_user, json={
        "title": "Delete me",
    })
    task_id = task_resp.json()["task"]["id"]
    resp = client.delete(f"/team/api/teams/{team['id']}/tasks/{task_id}", cookies=auth_user)
    assert resp.status_code == 200


# ── Teams Page ───────────────────────────────────────────────────────


def test_teams_page_html(client: TestClient, auth_user):
    resp = client.get("/team", cookies=auth_user)
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


def test_available_users(client: TestClient, auth_user):
    resp = client.get("/team/api/available-users", cookies=auth_user)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["users"], list)
    assert len(data["users"]) >= 1


# ── Permissions ──────────────────────────────────────────────────────


def test_regular_user_cannot_delete_team(client: TestClient, auth_user, second_user):
    """Only owner/admin can delete teams, not regular users."""
    team = _create_team(client, auth_user, name="Protected Team")
    resp = client.delete(f"/team/api/teams/{team['id']}", cookies=second_user)
    assert resp.status_code in (403, 404)
