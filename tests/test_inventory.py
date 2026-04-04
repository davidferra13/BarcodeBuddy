"""Tests for inventory management: API routes, scan lookup, bulk operations."""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture()
def app(db_path: Path):
    from fastapi import FastAPI
    from app.database import init_db
    from app.auth_routes import router as auth_router
    from app.inventory_routes import router as inventory_router

    init_db(db_path)
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(inventory_router)
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


@pytest.fixture()
def second_user(client: TestClient):
    resp = client.post("/auth/api/signup", json={
        "email": "other@example.com",
        "password": "testpass123",
        "display_name": "Other User",
    })
    assert resp.status_code == 200
    return {"bb_session": resp.cookies.get("bb_session")}


def _create_item(client: TestClient, cookies: dict, **overrides) -> dict:
    body = {
        "name": "Test Widget",
        "sku": "WDG-001",
        "quantity": 10,
        "unit": "each",
        "location": "Shelf A1",
        "category": "Widgets",
        "barcode_type": "Code128",
    }
    body.update(overrides)
    resp = client.post("/api/inventory", json=body, cookies=cookies)
    assert resp.status_code == 201, resp.json()
    return resp.json()["item"]


# --- CRUD ---

class TestCreateItem:
    def test_create_item(self, client, auth_user):
        item = _create_item(client, auth_user)
        assert item["name"] == "Test Widget"
        assert item["sku"] == "WDG-001"
        assert item["quantity"] == 10
        assert item["barcode_value"].startswith("BB-")
        assert item["status"] == "active"

    def test_create_item_custom_barcode(self, client, auth_user):
        item = _create_item(client, auth_user, barcode_value="CUSTOM-123")
        assert item["barcode_value"] == "CUSTOM-123"

    def test_create_item_duplicate_sku(self, client, auth_user):
        _create_item(client, auth_user)
        resp = client.post("/api/inventory", json={
            "name": "Another Widget", "sku": "WDG-001",
        }, cookies=auth_user)
        assert resp.status_code == 409
        assert "SKU" in resp.json()["error"]

    def test_create_item_duplicate_barcode(self, client, auth_user):
        _create_item(client, auth_user, barcode_value="DUP-BC")
        resp = client.post("/api/inventory", json={
            "name": "Another", "sku": "WDG-002", "barcode_value": "DUP-BC",
        }, cookies=auth_user)
        assert resp.status_code == 409

    def test_create_item_unauthenticated(self, client):
        resp = client.post("/api/inventory", json={"name": "X", "sku": "X"})
        assert resp.status_code in (401, 307)

    def test_create_item_initial_transaction(self, client, auth_user):
        item = _create_item(client, auth_user, quantity=5)
        resp = client.get(f"/api/inventory/{item['id']}", cookies=auth_user)
        data = resp.json()
        assert len(data["transactions"]) == 1
        assert data["transactions"][0]["quantity_change"] == 5
        assert data["transactions"][0]["reason"] == "initial"


class TestGetItem:
    def test_get_item(self, client, auth_user):
        item = _create_item(client, auth_user)
        resp = client.get(f"/api/inventory/{item['id']}", cookies=auth_user)
        assert resp.status_code == 200
        assert resp.json()["item"]["id"] == item["id"]
        assert "transactions" in resp.json()

    def test_get_item_not_found(self, client, auth_user):
        resp = client.get("/api/inventory/nonexistent", cookies=auth_user)
        assert resp.status_code == 404

    def test_get_item_cross_user_isolation(self, client, auth_user, second_user):
        item = _create_item(client, auth_user)
        resp = client.get(f"/api/inventory/{item['id']}", cookies=second_user)
        assert resp.status_code == 404


class TestUpdateItem:
    def test_update_item(self, client, auth_user):
        item = _create_item(client, auth_user)
        resp = client.put(f"/api/inventory/{item['id']}", json={
            "name": "Updated Widget", "location": "Shelf B2",
        }, cookies=auth_user)
        assert resp.status_code == 200
        assert resp.json()["item"]["name"] == "Updated Widget"
        assert resp.json()["item"]["location"] == "Shelf B2"

    def test_update_quantity_creates_transaction(self, client, auth_user):
        item = _create_item(client, auth_user, quantity=10)
        client.put(f"/api/inventory/{item['id']}", json={"quantity": 15}, cookies=auth_user)
        resp = client.get(f"/api/inventory/{item['id']}", cookies=auth_user)
        txns = resp.json()["transactions"]
        assert len(txns) == 2  # initial + adjustment
        adj = txns[0]
        assert adj["quantity_change"] == 5
        assert adj["quantity_after"] == 15

    def test_update_sku_uniqueness(self, client, auth_user):
        _create_item(client, auth_user, sku="SKU-A")
        item_b = _create_item(client, auth_user, sku="SKU-B", name="B")
        resp = client.put(f"/api/inventory/{item_b['id']}", json={"sku": "SKU-A"}, cookies=auth_user)
        assert resp.status_code == 409

    def test_archive_item(self, client, auth_user):
        item = _create_item(client, auth_user)
        resp = client.put(f"/api/inventory/{item['id']}", json={"status": "archived"}, cookies=auth_user)
        assert resp.status_code == 200
        assert resp.json()["item"]["status"] == "archived"


class TestDeleteItem:
    def test_delete_item(self, client, auth_user):
        item = _create_item(client, auth_user)
        resp = client.delete(f"/api/inventory/{item['id']}", cookies=auth_user)
        assert resp.status_code == 200
        resp = client.get(f"/api/inventory/{item['id']}", cookies=auth_user)
        assert resp.status_code == 404

    def test_delete_nonexistent(self, client, auth_user):
        resp = client.delete("/api/inventory/nonexistent", cookies=auth_user)
        assert resp.status_code == 404


# --- List & Search ---

class TestListItems:
    def test_list_empty(self, client, auth_user):
        resp = client.get("/api/inventory", cookies=auth_user)
        assert resp.status_code == 200
        assert resp.json()["items"] == []
        assert resp.json()["total"] == 0

    def test_list_items(self, client, auth_user):
        _create_item(client, auth_user, sku="A", name="Alpha")
        _create_item(client, auth_user, sku="B", name="Beta")
        resp = client.get("/api/inventory", cookies=auth_user)
        assert resp.json()["total"] == 2

    def test_search_by_name(self, client, auth_user):
        _create_item(client, auth_user, sku="A", name="Alpha Widget")
        _create_item(client, auth_user, sku="B", name="Beta Gadget")
        resp = client.get("/api/inventory?q=Alpha", cookies=auth_user)
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["name"] == "Alpha Widget"

    def test_filter_by_category(self, client, auth_user):
        _create_item(client, auth_user, sku="A", name="A", category="Electronics")
        _create_item(client, auth_user, sku="B", name="B", category="Packaging")
        resp = client.get("/api/inventory?category=Electronics", cookies=auth_user)
        assert resp.json()["total"] == 1

    def test_filter_by_status(self, client, auth_user):
        item = _create_item(client, auth_user)
        client.put(f"/api/inventory/{item['id']}", json={"status": "archived"}, cookies=auth_user)
        resp = client.get("/api/inventory?status=archived", cookies=auth_user)
        assert resp.json()["total"] == 1
        resp = client.get("/api/inventory?status=active", cookies=auth_user)
        assert resp.json()["total"] == 0

    def test_user_isolation(self, client, auth_user, second_user):
        _create_item(client, auth_user)
        resp = client.get("/api/inventory", cookies=second_user)
        assert resp.json()["total"] == 0


# --- Quantity Adjustment ---

class TestAdjustQuantity:
    def test_adjust_increase(self, client, auth_user):
        item = _create_item(client, auth_user, quantity=10)
        resp = client.post(f"/api/inventory/{item['id']}/adjust", json={
            "quantity_change": 5, "reason": "received",
        }, cookies=auth_user)
        assert resp.status_code == 200
        assert resp.json()["item"]["quantity"] == 15
        assert resp.json()["transaction"]["quantity_change"] == 5

    def test_adjust_decrease(self, client, auth_user):
        item = _create_item(client, auth_user, quantity=10)
        resp = client.post(f"/api/inventory/{item['id']}/adjust", json={
            "quantity_change": -3, "reason": "sold",
        }, cookies=auth_user)
        assert resp.status_code == 200
        assert resp.json()["item"]["quantity"] == 7

    def test_adjust_below_zero(self, client, auth_user):
        item = _create_item(client, auth_user, quantity=2)
        resp = client.post(f"/api/inventory/{item['id']}/adjust", json={
            "quantity_change": -5, "reason": "sold",
        }, cookies=auth_user)
        assert resp.status_code == 400
        assert "below zero" in resp.json()["error"]


# --- Scan Lookup ---

class TestScanLookup:
    def test_scan_found(self, client, auth_user):
        item = _create_item(client, auth_user, barcode_value="SCAN-001")
        resp = client.get("/api/scan/lookup?code=SCAN-001", cookies=auth_user)
        assert resp.status_code == 200
        assert resp.json()["item"]["id"] == item["id"]

    def test_scan_by_sku(self, client, auth_user):
        item = _create_item(client, auth_user, sku="SCANSKU")
        resp = client.get("/api/scan/lookup?code=SCANSKU", cookies=auth_user)
        assert resp.status_code == 200
        assert resp.json()["item"]["id"] == item["id"]

    def test_scan_not_found(self, client, auth_user):
        resp = client.get("/api/scan/lookup?code=NOEXIST", cookies=auth_user)
        assert resp.status_code == 404

    def test_scan_archived_not_found(self, client, auth_user):
        item = _create_item(client, auth_user, barcode_value="ARC-001")
        client.put(f"/api/inventory/{item['id']}", json={"status": "archived"}, cookies=auth_user)
        resp = client.get("/api/scan/lookup?code=ARC-001", cookies=auth_user)
        assert resp.status_code == 404

    def test_scan_cross_user(self, client, auth_user, second_user):
        _create_item(client, auth_user, barcode_value="PRIV-001")
        resp = client.get("/api/scan/lookup?code=PRIV-001", cookies=second_user)
        assert resp.status_code == 404

    def test_scan_empty(self, client, auth_user):
        resp = client.get("/api/scan/lookup?code=", cookies=auth_user)
        assert resp.status_code == 400


# --- Barcode Generation ---

class TestBarcodeGeneration:
    def test_get_barcode_image(self, client, auth_user):
        item = _create_item(client, auth_user)
        resp = client.get(f"/api/inventory/{item['id']}/barcode.png", cookies=auth_user)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert len(resp.content) > 100

    def test_barcode_formats_endpoint(self, client, auth_user):
        resp = client.get("/api/barcode/formats", cookies=auth_user)
        assert resp.status_code == 200
        formats = resp.json()["formats"]
        assert "Code128" in formats
        assert "QRCode" in formats


# --- Bulk Operations ---

class TestBulkDelete:
    def test_bulk_delete(self, client, auth_user):
        a = _create_item(client, auth_user, sku="A", name="A")
        b = _create_item(client, auth_user, sku="B", name="B")
        resp = client.post("/api/inventory/bulk/delete", json={
            "item_ids": [a["id"], b["id"]],
        }, cookies=auth_user)
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 2
        resp = client.get("/api/inventory", cookies=auth_user)
        assert resp.json()["total"] == 0


class TestBulkUpdate:
    def test_bulk_update_location(self, client, auth_user):
        a = _create_item(client, auth_user, sku="A", name="A")
        b = _create_item(client, auth_user, sku="B", name="B")
        resp = client.post("/api/inventory/bulk/update", json={
            "item_ids": [a["id"], b["id"]],
            "location": "Warehouse 2",
        }, cookies=auth_user)
        assert resp.status_code == 200
        assert resp.json()["updated"] == 2
        r = client.get(f"/api/inventory/{a['id']}", cookies=auth_user)
        assert r.json()["item"]["location"] == "Warehouse 2"


# --- Import / Export ---

class TestImport:
    def test_import_csv(self, client, auth_user):
        csv_content = "name,sku,quantity,unit,location,category\nWidget A,IMP-A,10,each,Shelf 1,Parts\nWidget B,IMP-B,20,box,Shelf 2,Parts\n"
        files = {"file": ("import.csv", csv_content.encode(), "text/csv")}
        resp = client.post("/api/inventory/import/csv", files=files, cookies=auth_user)
        assert resp.status_code == 200
        assert resp.json()["created"] == 2

    def test_import_duplicate_sku_updates(self, client, auth_user):
        _create_item(client, auth_user, sku="EXIST", quantity=5)
        csv_content = "name,sku,quantity\nUpdated,EXIST,20\n"
        files = {"file": ("import.csv", csv_content.encode(), "text/csv")}
        resp = client.post("/api/inventory/import/csv", files=files, cookies=auth_user)
        assert resp.json()["updated"] == 1


class TestExport:
    def test_export_csv(self, client, auth_user):
        _create_item(client, auth_user, sku="EXP-1", name="Export Item")
        resp = client.get("/api/inventory/export/csv", cookies=auth_user)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        assert rows[0][0] == "name"
        assert rows[1][0] == "Export Item"


# --- Summary ---

class TestSummary:
    def test_summary(self, client, auth_user):
        _create_item(client, auth_user, quantity=10, cost=5.0, min_quantity=20)
        _create_item(client, auth_user, sku="B", name="B", quantity=50, cost=2.0)
        resp = client.get("/api/inventory/summary", cookies=auth_user)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_items"] == 2
        assert data["total_quantity"] == 60
        assert data["total_value"] == 150.0
        assert data["low_stock_count"] == 1

    def test_categories_and_locations(self, client, auth_user):
        _create_item(client, auth_user, category="Parts", location="Zone A")
        resp = client.get("/api/inventory/categories", cookies=auth_user)
        assert "Parts" in resp.json()["categories"]
        resp = client.get("/api/inventory/locations", cookies=auth_user)
        assert "Zone A" in resp.json()["locations"]


# --- End-to-End Workflows ---

class TestEndToEndWorkflows:
    def test_create_scan_update_verify(self, client, auth_user):
        """Create item -> scan -> update qty -> re-scan -> verify."""
        item = _create_item(client, auth_user, barcode_value="E2E-001", quantity=100)
        resp = client.get("/api/scan/lookup?code=E2E-001", cookies=auth_user)
        assert resp.json()["item"]["quantity"] == 100

        client.post(f"/api/inventory/{item['id']}/adjust", json={
            "quantity_change": -25, "reason": "sold",
        }, cookies=auth_user)

        resp = client.get("/api/scan/lookup?code=E2E-001", cookies=auth_user)
        assert resp.json()["item"]["quantity"] == 75

    def test_edit_rescan_persists(self, client, auth_user):
        """Edit item -> re-scan -> confirm updated data."""
        item = _create_item(client, auth_user, barcode_value="E2E-002", location="Old Spot")
        client.put(f"/api/inventory/{item['id']}", json={"location": "New Location"}, cookies=auth_user)
        resp = client.get("/api/scan/lookup?code=E2E-002", cookies=auth_user)
        assert resp.json()["item"]["location"] == "New Location"

    def test_delete_scan_returns_not_found(self, client, auth_user):
        """Delete item -> scan no longer returns it."""
        item = _create_item(client, auth_user, barcode_value="E2E-003")
        client.delete(f"/api/inventory/{item['id']}", cookies=auth_user)
        resp = client.get("/api/scan/lookup?code=E2E-003", cookies=auth_user)
        assert resp.status_code == 404

    def test_archive_scan_returns_not_found(self, client, auth_user):
        """Archived items should not appear in scan results."""
        item = _create_item(client, auth_user, barcode_value="E2E-004")
        client.put(f"/api/inventory/{item['id']}", json={"status": "archived"}, cookies=auth_user)
        resp = client.get("/api/scan/lookup?code=E2E-004", cookies=auth_user)
        assert resp.status_code == 404

    def test_bulk_import_then_scan_all(self, client, auth_user):
        """Bulk import -> auto-generate codes -> scan each by barcode."""
        csv_content = "name,sku,quantity\nItem X,BULK-X,100\nItem Y,BULK-Y,200\n"
        files = {"file": ("import.csv", csv_content.encode(), "text/csv")}
        resp = client.post("/api/inventory/import/csv", files=files, cookies=auth_user)
        assert resp.json()["created"] == 2

        resp = client.get("/api/inventory?status=active", cookies=auth_user)
        items = resp.json()["items"]
        for item in items:
            scan_resp = client.get(f"/api/scan/lookup?code={item['barcode_value']}", cookies=auth_user)
            assert scan_resp.status_code == 200
            assert scan_resp.json()["item"]["id"] == item["id"]
