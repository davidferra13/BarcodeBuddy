"""Tests for scan-to-pdf: enrich, generate PDF, decode upload, and page route."""

from __future__ import annotations

import io
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
    from app.database import init_db
    from app.auth_routes import router as auth_router
    from app.inventory_routes import router as inventory_router
    from app.scan_to_pdf import router as scan_to_pdf_router

    init_db(db_path)
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(inventory_router)
    app.include_router(scan_to_pdf_router)
    return app


@pytest.fixture()
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture()
def auth_user(client: TestClient):
    resp = client.post("/auth/api/signup", json={
        "email": "test@example.com",
        "password": "testpass123",
        "display_name": "Test User",
    })
    assert resp.status_code == 200
    return {"bb_session": resp.cookies.get("bb_session")}


def _create_item(client: TestClient, cookies: dict, **overrides) -> dict:
    body = {
        "name": overrides.get("name", "Test Widget"),
        "sku": overrides.get("sku", "WDG-001"),
        "quantity": overrides.get("quantity", 10),
        "barcode_value": overrides.get("barcode_value", "BC-WIDGET-001"),
        "barcode_type": overrides.get("barcode_type", "Code128"),
        "location": overrides.get("location", "Shelf A"),
        "category": overrides.get("category", "Parts"),
    }
    resp = client.post("/api/inventory", json=body, cookies=cookies)
    assert resp.status_code == 201
    return resp.json()["item"]


class TestEnrichEndpoint:
    """Tests for POST /api/scan-to-pdf/enrich."""

    def test_enrich_found_by_barcode(self, client, auth_user):
        item = _create_item(client, auth_user, barcode_value="ENRICH-001", name="Enriched Item", location="Bay 3")
        resp = client.post("/api/scan-to-pdf/enrich", json={"codes": ["ENRICH-001"]}, cookies=auth_user)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["found"] is True
        assert data["items"][0]["name"] == "Enriched Item"
        assert data["items"][0]["location"] == "Bay 3"

    def test_enrich_found_by_sku(self, client, auth_user):
        _create_item(client, auth_user, sku="SKU-LOOKUP", barcode_value="BC-SKU-123", name="SKU Item")
        resp = client.post("/api/scan-to-pdf/enrich", json={"codes": ["SKU-LOOKUP"]}, cookies=auth_user)
        assert resp.status_code == 200
        assert resp.json()["items"][0]["found"] is True
        assert resp.json()["items"][0]["name"] == "SKU Item"

    def test_enrich_not_found(self, client, auth_user):
        resp = client.post("/api/scan-to-pdf/enrich", json={"codes": ["NONEXISTENT"]}, cookies=auth_user)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"][0]["found"] is False
        assert data["items"][0]["name"] is None

    def test_enrich_multiple_codes(self, client, auth_user):
        _create_item(client, auth_user, barcode_value="MULTI-001", name="First", sku="M1")
        _create_item(client, auth_user, barcode_value="MULTI-002", name="Second", sku="M2")
        resp = client.post("/api/scan-to-pdf/enrich", json={"codes": ["MULTI-001", "MULTI-002", "MISSING"]}, cookies=auth_user)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 3
        assert items[0]["found"] is True
        assert items[1]["found"] is True
        assert items[2]["found"] is False

    def test_enrich_empty_codes_rejected(self, client, auth_user):
        resp = client.post("/api/scan-to-pdf/enrich", json={"codes": []}, cookies=auth_user)
        assert resp.status_code == 422

    def test_enrich_requires_auth(self, client):
        resp = client.post("/api/scan-to-pdf/enrich", json={"codes": ["ABC"]})
        assert resp.status_code in (401, 403)


class TestGeneratePdfEndpoint:
    """Tests for POST /api/scan-to-pdf/generate."""

    def test_generate_basic_pdf(self, client, auth_user):
        resp = client.post("/api/scan-to-pdf/generate", json={
            "title": "Test Report",
            "entries": [
                {"code": "BC-001", "format": "Code128", "name": "Widget", "location": "Shelf A", "scanned_at": "2026-04-04T12:00:00Z"},
                {"code": "BC-002", "format": "QRCode", "name": "", "location": "", "scanned_at": "2026-04-04T12:01:00Z"},
            ],
        }, cookies=auth_user)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "content-disposition" in resp.headers
        assert "Test Report" in resp.headers["content-disposition"]
        # Verify it's a valid PDF (starts with %PDF)
        assert resp.content[:5] == b"%PDF-"

    def test_generate_pdf_default_title(self, client, auth_user):
        resp = client.post("/api/scan-to-pdf/generate", json={
            "entries": [{"code": "SINGLE-001"}],
        }, cookies=auth_user)
        assert resp.status_code == 200
        assert resp.content[:5] == b"%PDF-"
        assert "Barcode Scan Report" in resp.headers["content-disposition"]

    def test_generate_pdf_many_entries(self, client, auth_user):
        """Generate PDF with enough entries to span multiple pages."""
        entries = [{"code": f"BATCH-{i:04d}", "format": "Code128"} for i in range(60)]
        resp = client.post("/api/scan-to-pdf/generate", json={
            "title": "Batch Report",
            "entries": entries,
        }, cookies=auth_user)
        assert resp.status_code == 200
        assert resp.content[:5] == b"%PDF-"
        # Multi-page PDF should be larger
        assert len(resp.content) > 1000

    def test_generate_pdf_empty_entries_rejected(self, client, auth_user):
        resp = client.post("/api/scan-to-pdf/generate", json={
            "entries": [],
        }, cookies=auth_user)
        assert resp.status_code == 422

    def test_generate_pdf_requires_auth(self, client):
        resp = client.post("/api/scan-to-pdf/generate", json={
            "entries": [{"code": "X"}],
        })
        assert resp.status_code in (401, 403)

    def test_generate_pdf_special_characters_in_title(self, client, auth_user):
        """Title with special chars should be sanitized in filename."""
        resp = client.post("/api/scan-to-pdf/generate", json={
            "title": "Report <with> special/chars!",
            "entries": [{"code": "SC-001"}],
        }, cookies=auth_user)
        assert resp.status_code == 200
        disposition = resp.headers["content-disposition"]
        # No angle brackets or slashes in filename
        assert "<" not in disposition
        assert ">" not in disposition


class TestDecodeUploadEndpoint:
    """Tests for POST /api/scan-to-pdf/decode."""

    def test_decode_barcode_image(self, client, auth_user):
        """Upload a programmatically generated barcode image and verify decoding."""
        from app.barcode_generator import generate_barcode_bytes
        img_bytes = generate_barcode_bytes("DECODE-TEST-123", format="Code128", scale=4)
        resp = client.post(
            "/api/scan-to-pdf/decode",
            files={"file": ("barcode.png", io.BytesIO(img_bytes), "image/png")},
            cookies=auth_user,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        values = [b["value"] for b in data["barcodes"]]
        assert "DECODE-TEST-123" in values

    def test_decode_qr_code(self, client, auth_user):
        from app.barcode_generator import generate_barcode_bytes
        img_bytes = generate_barcode_bytes("QR-HELLO-456", format="QRCode", scale=8)
        resp = client.post(
            "/api/scan-to-pdf/decode",
            files={"file": ("qr.png", io.BytesIO(img_bytes), "image/png")},
            cookies=auth_user,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        values = [b["value"] for b in data["barcodes"]]
        assert "QR-HELLO-456" in values

    def test_decode_no_barcode_image(self, client, auth_user):
        """Upload a plain white image — should return zero barcodes."""
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (200, 200), "white").save(buf, format="PNG")
        buf.seek(0)
        resp = client.post(
            "/api/scan-to-pdf/decode",
            files={"file": ("blank.png", buf, "image/png")},
            cookies=auth_user,
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_decode_invalid_file(self, client, auth_user):
        """Upload garbage data — should return 400."""
        resp = client.post(
            "/api/scan-to-pdf/decode",
            files={"file": ("bad.png", io.BytesIO(b"not an image"), "image/png")},
            cookies=auth_user,
        )
        assert resp.status_code == 400

    def test_decode_requires_auth(self, client):
        resp = client.post(
            "/api/scan-to-pdf/decode",
            files={"file": ("test.png", io.BytesIO(b""), "image/png")},
        )
        assert resp.status_code in (401, 403)

    def test_decode_pdf_with_barcode(self, client, auth_user):
        """Create a PDF containing a barcode image, upload it, verify decoding."""
        import fitz
        from app.barcode_generator import generate_barcode_bytes

        # Generate a barcode image
        img_bytes = generate_barcode_bytes("PDF-BC-789", format="Code128", scale=6)

        # Create a PDF with the barcode embedded
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        img_rect = fitz.Rect(50, 50, 400, 200)
        page.insert_image(img_rect, stream=img_bytes)
        pdf_bytes = doc.tobytes()
        doc.close()

        resp = client.post(
            "/api/scan-to-pdf/decode",
            files={"file": ("doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            cookies=auth_user,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        values = [b["value"] for b in data["barcodes"]]
        assert "PDF-BC-789" in values
        # PDF results should include page number
        assert data["barcodes"][0].get("page") == 1


class TestScanToPdfPage:
    """Tests for GET /scan-to-pdf HTML page."""

    def test_page_loads(self, client, auth_user):
        resp = client.get("/scan-to-pdf", cookies=auth_user)
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Scan to PDF" in resp.text
        assert "Manual Entry" in resp.text
        assert "Camera" in resp.text
        assert "Upload File" in resp.text
        assert "Export PDF" in resp.text

    def test_page_requires_auth(self, client):
        resp = client.get("/scan-to-pdf")
        assert resp.status_code in (401, 403)
