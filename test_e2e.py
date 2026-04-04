"""End-to-end verification of all 5 critical workflows."""

import asyncio
import csv
import io
import tempfile
from pathlib import Path

import httpx

from app.auth import OWNER_EMAIL
from app.config import load_settings, ensure_runtime_directories
from app.stats import create_stats_app


async def run(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        # Setup: create admin user
        r = await c.post("/auth/api/signup", json={
            "email": OWNER_EMAIL,
            "password": "securepass123",
            "display_name": "Danpack Admin",
        })
        assert r.status_code == 200
        cookies = dict(r.cookies)
        print("SETUP: Admin user created")

        # ═══ WORKFLOW 1: Create -> Generate Barcode -> Scan -> Retrieve ═══
        print("\n=== WORKFLOW 1: Create -> Barcode -> Scan -> Retrieve ===")

        r = await c.post("/api/inventory", json={
            "name": "Corrugated Box 12x12", "sku": "BOX-1212",
            "description": "Standard corrugated shipping box",
            "quantity": 500, "unit": "each",
            "location": "Warehouse A, Row 3", "category": "Packaging",
            "tags": "corrugated,shipping", "barcode_type": "Code128",
            "min_quantity": 50, "cost": 1.25,
        }, cookies=cookies)
        assert r.status_code == 201, f"Create failed: {r.text}"
        item1 = r.json()["item"]
        print(f"  1a. Created: {item1['name']} (barcode: {item1['barcode_value']})")
        assert item1["quantity"] == 500
        assert item1["barcode_value"].startswith("BB-BOX-1212-")

        r = await c.get(f"/api/inventory/{item1['id']}/barcode.png", cookies=cookies)
        assert r.status_code == 200 and r.headers["content-type"] == "image/png"
        assert len(r.content) > 100
        print(f"  1b. Barcode PNG generated: {len(r.content)} bytes")

        r = await c.get(f"/api/scan/lookup?code={item1['barcode_value']}", cookies=cookies)
        assert r.status_code == 200
        assert r.json()["item"]["id"] == item1["id"]
        print(f"  1c. Scan by barcode: FOUND")

        r = await c.get("/api/scan/lookup?code=BOX-1212", cookies=cookies)
        assert r.status_code == 200 and r.json()["item"]["id"] == item1["id"]
        print("  1d. Scan by SKU: FOUND")
        print("  WORKFLOW 1: PASS")

        # ═══ WORKFLOW 2: Scan -> Load -> Update Quantity ═══
        print("\n=== WORKFLOW 2: Scan -> Load -> Adjust Quantity ===")

        r = await c.post(f"/api/inventory/{item1['id']}/adjust", json={
            "quantity_change": -25, "reason": "sold", "notes": "Order #1234"
        }, cookies=cookies)
        assert r.status_code == 200
        assert r.json()["item"]["quantity"] == 475
        print(f"  2a. -25 sold -> qty={r.json()['item']['quantity']}")

        r = await c.post(f"/api/inventory/{item1['id']}/adjust", json={
            "quantity_change": 100, "reason": "received", "notes": "PO #5678"
        }, cookies=cookies)
        assert r.status_code == 200
        assert r.json()["item"]["quantity"] == 575
        print(f"  2b. +100 received -> qty={r.json()['item']['quantity']}")

        r = await c.get(f"/api/inventory/{item1['id']}", cookies=cookies)
        txns = r.json()["transactions"]
        assert len(txns) == 3  # initial + sold + received
        print(f"  2c. Transaction history: {len(txns)} entries")
        print("  WORKFLOW 2: PASS")

        # ═══ WORKFLOW 3: Bulk Import -> Auto Codes -> Verify ═══
        print("\n=== WORKFLOW 3: Bulk Import -> Auto Codes -> Verify ===")

        csv_data = (
            "name,sku,description,quantity,unit,location,category,tags,notes,barcode_value,barcode_type,min_quantity,cost\n"
            "Bubble Wrap Roll,BW-100,Large bubble wrap,200,roll,Warehouse B,Packaging,wrap,,,Code128,20,3.50\n"
            "Packing Tape,TAPE-01,Clear packing tape,1000,roll,Warehouse A,Supplies,tape,,TAPE-SCAN-001,Code128,100,0.75\n"
            "Shipping Label,LBL-4X6,4x6 thermal labels,5000,sheet,Office,Labels,label printing,,LBL-4X6-001,QRCode,500,0.02\n"
        )
        files = {"file": ("import.csv", csv_data.encode(), "text/csv")}
        r = await c.post("/api/inventory/import/csv", files=files, cookies=cookies)
        assert r.status_code == 200
        imp = r.json()
        assert imp["created"] == 3 and imp["errors"] == []
        print(f"  3a. Imported: {imp['created']} items")

        r = await c.get("/api/inventory?limit=100", cookies=cookies)
        items = r.json()["items"]
        assert len(items) == 4
        print(f"  3b. Total items: {len(items)}")

        bw = next(i for i in items if i["sku"] == "BW-100")
        assert bw["barcode_value"].startswith("BB-BW-100-")
        print(f"  3c. Auto barcode: {bw['barcode_value']}")

        tape = next(i for i in items if i["sku"] == "TAPE-01")
        assert tape["barcode_value"] == "TAPE-SCAN-001"
        print(f"  3d. Manual barcode: {tape['barcode_value']}")

        r = await c.get("/api/scan/lookup?code=TAPE-SCAN-001", cookies=cookies)
        assert r.status_code == 200 and r.json()["item"]["name"] == "Packing Tape"
        print("  3e. Scan imported item: FOUND")
        print("  WORKFLOW 3: PASS")

        # ═══ WORKFLOW 4: Edit -> Re-scan -> Confirm Persistence ═══
        print("\n=== WORKFLOW 4: Edit -> Re-scan -> Confirm ===")

        r = await c.put(f"/api/inventory/{item1['id']}", json={
            "name": "Corrugated Box 12x12x8",
            "location": "Warehouse C, Row 1",
            "quantity": 600,
        }, cookies=cookies)
        assert r.status_code == 200
        edited = r.json()["item"]
        assert edited["name"] == "Corrugated Box 12x12x8"
        assert edited["quantity"] == 600
        print(f"  4a. Edited: name, location, quantity")

        r = await c.get(f"/api/scan/lookup?code={item1['barcode_value']}", cookies=cookies)
        assert r.status_code == 200
        rescanned = r.json()["item"]
        assert rescanned["name"] == "Corrugated Box 12x12x8"
        assert rescanned["quantity"] == 600
        print(f"  4b. Re-scan confirms updated data")

        r = await c.get(f"/api/inventory/{item1['id']}", cookies=cookies)
        assert len(r.json()["transactions"]) == 4
        print(f"  4c. Transaction history: {len(r.json()['transactions'])} entries")
        print("  WORKFLOW 4: PASS")

        # ═══ WORKFLOW 5: Delete/Archive -> Scan Returns Nothing ═══
        print("\n=== WORKFLOW 5: Delete/Archive -> Invalid Scan ===")

        lbl = next(i for i in items if i["sku"] == "LBL-4X6")
        r = await c.put(f"/api/inventory/{lbl['id']}", json={"status": "archived"}, cookies=cookies)
        assert r.status_code == 200 and r.json()["item"]["status"] == "archived"
        print(f"  5a. Archived: {lbl['name']}")

        r = await c.get("/api/scan/lookup?code=LBL-4X6-001", cookies=cookies)
        assert r.status_code == 404
        print("  5b. Scan archived: 404 (correct)")

        r = await c.delete(
            f"/api/inventory/{bw['id']}",
            cookies=cookies,
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 200
        print(f"  5c. Deleted: {bw['name']}")

        r = await c.get(f"/api/scan/lookup?code={bw['barcode_value']}", cookies=cookies)
        assert r.status_code == 404
        print("  5d. Scan deleted: 404 (correct)")

        r = await c.get("/api/inventory", cookies=cookies)
        active = [i for i in r.json()["items"]]
        assert len(active) == 2
        print(f"  5e. Active remaining: {len(active)}")
        print("  WORKFLOW 5: PASS")

        # ═══ ADDITIONAL CHECKS ═══
        print("\n=== ADDITIONAL CHECKS ===")

        r = await c.get("/api/inventory/categories", cookies=cookies)
        print(f"  Categories: {r.json()['categories']}")

        r = await c.get("/api/inventory/export/csv", cookies=cookies)
        assert "text/csv" in r.headers["content-type"]
        rows = list(csv.reader(io.StringIO(r.text)))
        print(f"  CSV export: {len(rows)-1} items")

        r = await c.get("/api/barcode/preview.png?value=TEST-123&format=Code128", cookies=cookies)
        assert r.status_code == 200 and len(r.content) > 100
        print(f"  Barcode preview: {len(r.content)} bytes")

        r = await c.post("/api/inventory", json={"name": "Dup", "sku": "BOX-1212"}, cookies=cookies)
        assert r.status_code == 409
        print("  Duplicate SKU rejected: correct")

        r = await c.post(f"/api/inventory/{item1['id']}/adjust", json={
            "quantity_change": -9999, "reason": "sold"
        }, cookies=cookies)
        assert r.status_code == 400
        print("  Negative qty rejected: correct")

        r = await c.get("/api/scan/lookup?code=NONEXISTENT", cookies=cookies)
        assert r.status_code == 404
        print("  Unknown code 404: correct")

        for path in ["/inventory", "/inventory/new", "/inventory/import", "/scan"]:
            r = await c.get(path, headers={"accept": "text/html"}, cookies=cookies)
            assert r.status_code == 200, f"{path} returned {r.status_code}"
        print("  All HTML pages load: OK")

        # User isolation
        r = await c.put("/admin/api/settings/signup", json={"open_signup": True}, cookies=cookies)
        assert r.status_code == 200
        r2 = await c.post("/auth/api/signup", json={
            "email": "user2@danpack.com", "password": "userpass12345",
            "display_name": "User Two"
        })
        ck2 = dict(r2.cookies)
        r = await c.get("/api/inventory", cookies=ck2)
        assert len(r.json()["items"]) == 0
        print("  User isolation: new user sees 0 items")

        r = await c.get(f"/api/scan/lookup?code={item1['barcode_value']}", cookies=ck2)
        assert r.status_code == 404
        print("  User isolation: cannot scan other user's items")

        print("\n" + "=" * 60)
        print("ALL 5 CRITICAL WORKFLOWS PASSED")
        print("ALL ADDITIONAL CHECKS PASSED")
        print("ZERO FAILURES")
        print("=" * 60)


def test_e2e_workflows():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        base_settings = load_settings(Path("config.json").resolve())
        settings = base_settings.model_copy(
            update={
                "input_path": root / "input",
                "processing_path": root / "processing",
                "output_path": root / "output",
                "rejected_path": root / "rejected",
                "log_path": root / "logs",
                "secret_key": "test-secret-key-for-e2e-0123456789abcdef",
            }
        )
        ensure_runtime_directories(settings)
        app = create_stats_app(settings)
        try:
            asyncio.run(run(app))
        finally:
            scheduler = getattr(app.state, "alert_scheduler", None)
            if scheduler is not None:
                try:
                    scheduler.shutdown(wait=False)
                except Exception:
                    pass
            from app.database import shutdown_db

            shutdown_db()
