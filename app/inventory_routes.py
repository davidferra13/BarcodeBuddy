"""Inventory management API routes: CRUD, scan lookup, bulk operations, barcode generation."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, UploadFile, File
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import require_user
from app.barcode_generator import generate_barcode_bytes
from app.database import InventoryItem, InventoryTransaction, User, get_db

router = APIRouter(tags=["inventory"])


# ── Request Models ──────────────────────────────────────────────────

class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    sku: str = Field(min_length=1, max_length=100)
    description: str = ""
    quantity: int = Field(default=0, ge=0)
    unit: str = "each"
    location: str = ""
    category: str = ""
    tags: str = ""
    notes: str = ""
    barcode_type: str = "Code128"
    barcode_value: str = ""
    min_quantity: int = 0
    cost: float | None = None


class ItemUpdate(BaseModel):
    name: str | None = None
    sku: str | None = None
    description: str | None = None
    quantity: int | None = None
    unit: str | None = None
    location: str | None = None
    category: str | None = None
    tags: str | None = None
    notes: str | None = None
    status: str | None = None
    barcode_type: str | None = None
    min_quantity: int | None = None
    cost: float | None = None


class QuantityAdjust(BaseModel):
    quantity_change: int
    reason: str = Field(min_length=1, max_length=50)
    notes: str = ""


# ── Static paths (must be before parameterized {item_id} routes) ───

@router.get("/api/inventory/categories")
def api_categories(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    items = db.query(InventoryItem.category).filter(
        InventoryItem.user_id == user.id,
        InventoryItem.status == "active",
        InventoryItem.category != "",
    ).distinct().all()
    return JSONResponse(content={"categories": sorted(set(c[0] for c in items))})


@router.get("/api/inventory/locations")
def api_locations(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    rows = db.query(InventoryItem.location).filter(
        InventoryItem.user_id == user.id,
        InventoryItem.status == "active",
        InventoryItem.location != "",
    ).distinct().all()
    return JSONResponse(content={"locations": sorted(set(r[0] for r in rows))})


@router.get("/api/inventory/summary")
def api_summary(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    items = db.query(InventoryItem).filter(
        InventoryItem.user_id == user.id, InventoryItem.status == "active",
    ).all()
    total_items = len(items)
    total_quantity = sum(i.quantity for i in items)
    total_value = sum((i.cost or 0) * i.quantity for i in items)
    low_stock = [i.to_dict() for i in items if i.min_quantity > 0 and i.quantity <= i.min_quantity]
    categories: dict[str, int] = {}
    locations: dict[str, int] = {}
    for i in items:
        if i.category:
            categories[i.category] = categories.get(i.category, 0) + 1
        if i.location:
            locations[i.location] = locations.get(i.location, 0) + 1
    return JSONResponse(content={
        "total_items": total_items,
        "total_quantity": total_quantity,
        "total_value": round(total_value, 2),
        "low_stock_count": len(low_stock),
        "low_stock_items": low_stock[:10],
        "categories": categories,
        "locations": locations,
    })


# ── Export CSV ──────────────────────────────────────────────────────

@router.get("/api/inventory/export/csv")
def api_export_csv(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    items = db.query(InventoryItem).filter(
        InventoryItem.user_id == user.id, InventoryItem.status == "active"
    ).order_by(InventoryItem.name).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "sku", "description", "quantity", "unit", "location",
                     "category", "tags", "notes", "barcode_value", "barcode_type",
                     "min_quantity", "cost"])
    for item in items:
        writer.writerow([item.name, item.sku, item.description, item.quantity,
                         item.unit, item.location, item.category, item.tags,
                         item.notes, item.barcode_value, item.barcode_type,
                         item.min_quantity, item.cost or ""])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory_export.csv"},
    )


# ── Import CSV ──────────────────────────────────────────────────────

@router.post("/api/inventory/import/csv")
async def api_import_csv(
    file: UploadFile = File(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")
    reader = csv.DictReader(io.StringIO(text))
    created = 0
    updated = 0
    errors: list[str] = []
    for row_num, row in enumerate(reader, start=2):
        name = row.get("name", "").strip()
        sku = row.get("sku", "").strip()
        if not name or not sku:
            errors.append(f"Row {row_num}: missing name or sku")
            continue
        existing = db.query(InventoryItem).filter(
            InventoryItem.user_id == user.id, InventoryItem.sku == sku,
        ).first()
        qty = int(row.get("quantity", "0") or "0")
        cost_str = row.get("cost", "").strip()
        cost = float(cost_str) if cost_str else None
        barcode_value = row.get("barcode_value", "").strip()
        if not barcode_value:
            barcode_value = f"BB-{sku.upper()}-{uuid.uuid4().hex[:6].upper()}"
        if existing:
            existing.name = name
            existing.description = row.get("description", "").strip()
            old_qty = existing.quantity
            existing.quantity = qty
            existing.unit = row.get("unit", "each").strip() or "each"
            existing.location = row.get("location", "").strip()
            existing.category = row.get("category", "").strip()
            existing.tags = row.get("tags", "").strip()
            existing.notes = row.get("notes", "").strip()
            existing.barcode_type = row.get("barcode_type", "Code128").strip() or "Code128"
            existing.min_quantity = int(row.get("min_quantity", "0") or "0")
            existing.cost = cost
            existing.updated_at = datetime.now(timezone.utc)
            if qty != old_qty:
                db.add(InventoryTransaction(
                    item_id=existing.id, user_id=user.id,
                    quantity_change=qty - old_qty, quantity_after=qty,
                    reason="adjusted", notes="CSV import update",
                ))
            updated += 1
        else:
            item = InventoryItem(
                user_id=user.id, name=name, sku=sku,
                description=row.get("description", "").strip(),
                quantity=qty, unit=row.get("unit", "each").strip() or "each",
                location=row.get("location", "").strip(),
                category=row.get("category", "").strip(),
                tags=row.get("tags", "").strip(),
                notes=row.get("notes", "").strip(),
                barcode_value=barcode_value,
                barcode_type=row.get("barcode_type", "Code128").strip() or "Code128",
                min_quantity=int(row.get("min_quantity", "0") or "0"),
                cost=cost,
            )
            db.add(item)
            db.flush()
            if qty > 0:
                db.add(InventoryTransaction(
                    item_id=item.id, user_id=user.id,
                    quantity_change=qty, quantity_after=qty,
                    reason="initial", notes="CSV import",
                ))
            created += 1
    db.commit()
    return JSONResponse(content={
        "created": created, "updated": updated, "errors": errors,
        "message": f"Import complete: {created} created, {updated} updated, {len(errors)} errors",
    })


# ── List Items ──────────────────────────────────────────────────────

@router.get("/api/inventory")
def api_list_items(
    q: str = "", category: str = "", location: str = "", status: str = "active",
    sort: str = "updated_at", order: str = "desc",
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    query = db.query(InventoryItem).filter(InventoryItem.user_id == user.id)
    if status:
        query = query.filter(InventoryItem.status == status)
    if category:
        query = query.filter(InventoryItem.category == category)
    if location:
        query = query.filter(InventoryItem.location == location)
    if q:
        pattern = f"%{q}%"
        query = query.filter(or_(
            InventoryItem.name.ilike(pattern), InventoryItem.sku.ilike(pattern),
            InventoryItem.barcode_value.ilike(pattern), InventoryItem.location.ilike(pattern),
            InventoryItem.tags.ilike(pattern),
        ))
    sort_col = getattr(InventoryItem, sort, InventoryItem.updated_at)
    query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return JSONResponse(content={"items": [i.to_dict() for i in items], "total": total})


# ── Create Item ─────────────────────────────────────────────────────

@router.post("/api/inventory")
def api_create_item(
    body: ItemCreate,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    barcode_value = body.barcode_value.strip()
    if not barcode_value:
        barcode_value = f"BB-{body.sku.strip().upper()}-{uuid.uuid4().hex[:6].upper()}"
    existing = db.query(InventoryItem).filter(
        InventoryItem.user_id == user.id, InventoryItem.sku == body.sku.strip(),
        InventoryItem.status != "archived",
    ).first()
    if existing:
        return JSONResponse(status_code=409, content={"error": f"SKU '{body.sku}' already exists"})
    bc_existing = db.query(InventoryItem).filter(
        InventoryItem.user_id == user.id, InventoryItem.barcode_value == barcode_value,
    ).first()
    if bc_existing:
        return JSONResponse(status_code=409, content={"error": f"Barcode '{barcode_value}' already in use"})
    item = InventoryItem(
        user_id=user.id, name=body.name.strip(), sku=body.sku.strip(),
        description=body.description.strip(), quantity=body.quantity,
        unit=body.unit.strip() or "each", location=body.location.strip(),
        category=body.category.strip(), tags=body.tags.strip(),
        notes=body.notes.strip(), barcode_value=barcode_value,
        barcode_type=body.barcode_type, min_quantity=body.min_quantity, cost=body.cost,
    )
    db.add(item)
    db.flush()
    if body.quantity > 0:
        db.add(InventoryTransaction(
            item_id=item.id, user_id=user.id,
            quantity_change=body.quantity, quantity_after=body.quantity,
            reason="initial", notes="Initial stock on item creation",
        ))
    db.commit()
    db.refresh(item)
    return JSONResponse(status_code=201, content={"item": item.to_dict()})


# ── Get Item ────────────────────────────────────────────────────────

@router.get("/api/inventory/{item_id}")
def api_get_item(
    item_id: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    item = db.query(InventoryItem).filter(
        InventoryItem.id == item_id, InventoryItem.user_id == user.id
    ).first()
    if not item:
        return JSONResponse(status_code=404, content={"error": "Item not found"})
    txns = db.query(InventoryTransaction).filter(
        InventoryTransaction.item_id == item_id
    ).order_by(InventoryTransaction.created_at.desc()).limit(50).all()
    return JSONResponse(content={"item": item.to_dict(), "transactions": [t.to_dict() for t in txns]})


# ── Update Item ─────────────────────────────────────────────────────

@router.put("/api/inventory/{item_id}")
def api_update_item(
    item_id: str, body: ItemUpdate,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    item = db.query(InventoryItem).filter(
        InventoryItem.id == item_id, InventoryItem.user_id == user.id
    ).first()
    if not item:
        return JSONResponse(status_code=404, content={"error": "Item not found"})
    update_data = body.model_dump(exclude_none=True)
    if "quantity" in update_data and update_data["quantity"] != item.quantity:
        change = update_data["quantity"] - item.quantity
        db.add(InventoryTransaction(
            item_id=item.id, user_id=user.id,
            quantity_change=change, quantity_after=update_data["quantity"],
            reason="adjusted", notes="Manual quantity update",
        ))
    if "sku" in update_data and update_data["sku"] != item.sku:
        dup = db.query(InventoryItem).filter(
            InventoryItem.user_id == user.id, InventoryItem.sku == update_data["sku"],
            InventoryItem.id != item_id, InventoryItem.status != "archived",
        ).first()
        if dup:
            return JSONResponse(status_code=409, content={"error": f"SKU '{update_data['sku']}' already exists"})
    for key, value in update_data.items():
        setattr(item, key, value.strip() if isinstance(value, str) else value)
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return JSONResponse(content={"item": item.to_dict()})


# ── Delete Item ─────────────────────────────────────────────────────

@router.delete("/api/inventory/{item_id}")
def api_delete_item(
    item_id: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    item = db.query(InventoryItem).filter(
        InventoryItem.id == item_id, InventoryItem.user_id == user.id
    ).first()
    if not item:
        return JSONResponse(status_code=404, content={"error": "Item not found"})
    db.delete(item)
    db.commit()
    return JSONResponse(content={"message": "Item deleted"})


# ── Adjust Quantity ─────────────────────────────────────────────────

@router.post("/api/inventory/{item_id}/adjust")
def api_adjust_quantity(
    item_id: str, body: QuantityAdjust,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    item = db.query(InventoryItem).filter(
        InventoryItem.id == item_id, InventoryItem.user_id == user.id
    ).first()
    if not item:
        return JSONResponse(status_code=404, content={"error": "Item not found"})
    new_qty = item.quantity + body.quantity_change
    if new_qty < 0:
        return JSONResponse(status_code=400, content={"error": "Quantity cannot go below zero"})
    txn = InventoryTransaction(
        item_id=item.id, user_id=user.id,
        quantity_change=body.quantity_change, quantity_after=new_qty,
        reason=body.reason, notes=body.notes.strip(),
    )
    db.add(txn)
    item.quantity = new_qty
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return JSONResponse(content={"item": item.to_dict(), "transaction": txn.to_dict()})


# ── Scan Lookup ─────────────────────────────────────────────────────

@router.get("/api/scan/lookup")
def api_scan_lookup(
    code: str = "",
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    code = code.strip()
    if not code:
        return JSONResponse(status_code=400, content={"error": "No barcode value provided"})
    item = db.query(InventoryItem).filter(
        InventoryItem.user_id == user.id, InventoryItem.barcode_value == code,
        InventoryItem.status == "active",
    ).first()
    if not item:
        item = db.query(InventoryItem).filter(
            InventoryItem.user_id == user.id, InventoryItem.sku == code,
            InventoryItem.status == "active",
        ).first()
    if not item:
        return JSONResponse(status_code=404, content={"error": "No item found for this code", "code": code})
    return JSONResponse(content={"item": item.to_dict()})


# ── Barcode Image ───────────────────────────────────────────────────

@router.get("/api/inventory/{item_id}/barcode.png")
def api_barcode_image(
    item_id: str,
    scale: int = Query(default=4, ge=1, le=20),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> Response:
    item = db.query(InventoryItem).filter(
        InventoryItem.id == item_id, InventoryItem.user_id == user.id
    ).first()
    if not item:
        return JSONResponse(status_code=404, content={"error": "Item not found"})
    try:
        img_bytes = generate_barcode_bytes(item.barcode_value, format=item.barcode_type, scale=scale)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"Barcode generation failed: {exc}"})
    return Response(content=img_bytes, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=3600"})


@router.get("/api/barcode/preview.png")
def api_barcode_preview(
    value: str = "",
    format: str = "Code128",
    scale: int = Query(default=4, ge=1, le=20),
    user: User = Depends(require_user),
) -> Response:
    if not value.strip():
        return JSONResponse(status_code=400, content={"error": "No value"})
    try:
        img_bytes = generate_barcode_bytes(value.strip(), format=format, scale=scale)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"Generation failed: {exc}"})
    return Response(content=img_bytes, media_type="image/png")


# ── Barcode Formats ──────────────────────────────────────────────────

@router.get("/api/barcode/formats")
def api_barcode_formats(
    user: User = Depends(require_user),
) -> JSONResponse:
    from app.barcode_generator import list_supported_formats
    return JSONResponse(content={"formats": list_supported_formats()})


# ── Bulk Operations ──────────────────────────────────────────────────

class BulkDeleteRequest(BaseModel):
    item_ids: list[str]


class BulkUpdateRequest(BaseModel):
    item_ids: list[str]
    location: str | None = None
    category: str | None = None
    status: str | None = None
    tags: str | None = None


@router.post("/api/inventory/bulk/delete")
def api_bulk_delete(
    body: BulkDeleteRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    deleted = 0
    for item_id in body.item_ids:
        item = db.query(InventoryItem).filter(
            InventoryItem.id == item_id, InventoryItem.user_id == user.id,
        ).first()
        if item:
            db.delete(item)
            deleted += 1
    db.commit()
    return JSONResponse(content={"deleted": deleted})


@router.post("/api/inventory/bulk/update")
def api_bulk_update(
    body: BulkUpdateRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    updated = 0
    for item_id in body.item_ids:
        item = db.query(InventoryItem).filter(
            InventoryItem.id == item_id, InventoryItem.user_id == user.id,
        ).first()
        if item:
            if body.location is not None:
                item.location = body.location.strip()
            if body.category is not None:
                item.category = body.category.strip()
            if body.status is not None:
                item.status = body.status
            if body.tags is not None:
                item.tags = body.tags.strip()
            item.updated_at = datetime.now(timezone.utc)
            updated += 1
    db.commit()
    return JSONResponse(content={"updated": updated})
