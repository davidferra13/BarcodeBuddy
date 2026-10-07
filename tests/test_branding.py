"""Branding reaches page display without changing authentication behavior."""
from __future__ import annotations

import html
import pytest
from fastapi import FastAPI
from conftest import TestClient
from app.branding import load_branding
from app.layout import render_shell
from app.auth_routes import router, login_page, signup_page, reset_request_page, reset_page


def test_default_product_identity():
    branding = load_branding({})
    assert branding.product_name == "Barcode Buddy"
    assert branding.organization_name is None
    assert branding.display_name == "Barcode Buddy"
    assert load_branding({"BB_ORGANIZATION_NAME": " \t\n"}).organization_name is None


def test_environment_is_read_on_each_call(monkeypatch):
    monkeypatch.setenv("BB_ORGANIZATION_NAME", "  Reference Packaging Co  ")
    assert load_branding().organization_name == "Reference Packaging Co"
    monkeypatch.delenv("BB_ORGANIZATION_NAME")
    assert load_branding().organization_name is None


def test_shared_shell_escapes_organization_and_keeps_product(monkeypatch):
    name = '<script>alert("buyer")</script> & Co'
    monkeypatch.setenv("BB_ORGANIZATION_NAME", name)
    page = render_shell(title="Documents", active_nav="scan", body_html="<p>Ready</p>")
    assert html.escape(name) in page
    assert name not in page
    assert "<h1>Barcode Buddy</h1>" in page
    assert 'href="/scan"' in page
    assert "/auth/api/logout" in page


@pytest.mark.parametrize("render", [login_page, signup_page, reset_request_page, reset_page])
def test_auth_page_display_uses_same_safe_branding(monkeypatch, render):
    monkeypatch.setenv("BB_ORGANIZATION_NAME", 'Reference <Co> & "Buyer"')
    page = render().body.decode()
    assert html.escape(load_branding().display_name) in page
    assert "Reference <Co>" not in page
    assert "Barcode Buddy" in page


def test_branded_auth_routes_still_reject_missing_credentials(monkeypatch, tmp_path):
    from app.database import init_db, shutdown_db
    monkeypatch.setenv("BB_ORGANIZATION_NAME", "Reference Packaging Co")
    app = FastAPI()
    app.include_router(router)
    init_db(tmp_path / "auth.db")
    try:
        with TestClient(app) as client:
            assert client.get("/auth/login").status_code == 200
            assert client.get("/auth/signup").status_code == 200
            assert client.post("/auth/api/login", json={}).status_code == 422
            assert client.post("/auth/api/signup", json={}).status_code == 422
            assert client.get("/auth/api/me").status_code == 401
    finally:
        shutdown_db()
