"""Inventory management API routes: CRUD, scan lookup, bulk operations, barcode generation."""

from __future__ import annotations

import csv
import io
import json as json_mod
import uuid
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, UploadFile, File
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.activity import log_activity
from app.auth import ROLE_LEVELS, get_role_level, require_user
from app.barcode_generator import generate_barcode_bytes
from app.database import InventoryItem, InventoryTransaction, User, get_db

router = APIRouter(tags=["inventory"])


# ── RBAC helpers ───────────────────────────────────────────────────

def _resolve_target_user_id(user: User, view_user: str | None) -> str:
    """Return the user_id to query against.

    - Regular users always see their own data (view_user is ignored).
    - Manager+ can pass view_user to see another user's data.
    """
    if not view_user or view_user == user.id:
        return user.id
    if get_role_level(user) >= ROLE_LEVELS["manager"]:
        return view_user
    return user.id


def _can_write_for(user: User, target_user_id: str) -> bool:
    """Return True if user can create/edit/delete items for target_user_id."""
    if user.id == target_user_id:
        return True
    return get_role_level(user) >= ROLE_LEVELS["admin"]


def _find_item(db: Session, item_id: str, user: User, view_user: str | None = None) -> InventoryItem | None:
    """Look up an item. Manager+ can view cross-user items; admin+ can write."""
    target = _resolve_target_user_id(user, view_user)
    return db.query(InventoryItem).filter(
        InventoryItem.id == item_id, InventoryItem.user_id == target
    ).first()


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
    status: str | None = Field(default=None, pattern="^(active|archived)$")
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
    view_user: str | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    target = _resolve_target_user_id(user, view_user)
    items = db.query(InventoryItem.category).filter(
        InventoryItem.user_id == target,
        InventoryItem.status == "active",
        InventoryItem.category != "",
    ).distinct().all()
    return JSONResponse(content={"categories": sorted(set(c[0] for c in items))})


@router.get("/api/inventory/locations")
def api_locations(
    view_user: str | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    target = _resolve_target_user_id(user, view_user)
    rows = db.query(InventoryItem.location).filter(
        InventoryItem.user_id == target,
        InventoryItem.status == "active",
        InventoryItem.location != "",
    ).distinct().all()
    return JSONResponse(content={"locations": sorted(set(r[0] for r in rows))})


@router.get("/api/inventory/summary")
def api_summary(
    view_user: str | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    target = _resolve_target_user_id(user, view_user)
    items = db.query(InventoryItem).filter(
        InventoryItem.user_id == target, InventoryItem.status == "active",
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


# ── Calendar ──────────────────────────────────────────────────────

@router.get("/api/calendar")
def api_calendar_month(
    year: int = Query(default=0, ge=0),
    month: int = Query(default=0, ge=0, le=12),
    view_user: str | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    today = date.today()
    if year == 0:
        year = today.year
    if month == 0:
        month = today.month
    _, days_in_month = monthrange(year, month)
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    end = datetime(year, month, days_in_month, 23, 59, 59, tzinfo=timezone.utc)

    target = _resolve_target_user_id(user, view_user)

    txns = db.query(InventoryTransaction).join(
        InventoryItem, InventoryTransaction.item_id == InventoryItem.id
    ).filter(
        InventoryItem.user_id == target,
        InventoryTransaction.created_at >= start,
        InventoryTransaction.created_at <= end,
    ).all()

    # Build per-day buckets
    days: dict[str, dict] = {}
    for d in range(1, days_in_month + 1):
        key = date(year, month, d).isoformat()
        days[key] = {"transactions": 0, "received": 0, "sold": 0, "adjusted": 0,
                     "damaged": 0, "returned": 0, "net_change": 0, "items": []}
    seen_items: dict[str, set] = defaultdict(set)
    for t in txns:
        key = t.created_at.strftime("%Y-%m-%d") if t.created_at else None
        if key and key in days:
            bucket = days[key]
            bucket["transactions"] += 1
            reason = t.reason or "adjusted"
            if reason in bucket:
                bucket[reason] += 1
            bucket["net_change"] += t.quantity_change
            if t.item_id not in seen_items[key]:
                seen_items[key].add(t.item_id)
                bucket["items"].append(t.item_id)

    # Items created this month
    new_items = db.query(InventoryItem).filter(
        InventoryItem.user_id == target,
        InventoryItem.created_at >= start,
        InventoryItem.created_at <= end,
    ).all()
    items_created: dict[str, int] = defaultdict(int)
    for item in new_items:
        if item.created_at:
            key = item.created_at.strftime("%Y-%m-%d")
            if key in days:
                items_created[key] += 1

    for key, count in items_created.items():
        days[key]["items_created"] = count

    return JSONResponse(content={
        "year": year,
        "month": month,
        "days_in_month": days_in_month,
        "today": today.isoformat(),
        "days": days,
    })


@router.get("/api/calendar/day")
def api_calendar_day(
    d: str = Query(..., alias="date"),
    view_user: str | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    try:
        target_date = date.fromisoformat(d)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid date format. Use YYYY-MM-DD."})

    start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    target = _resolve_target_user_id(user, view_user)

    txns = db.query(InventoryTransaction).join(
        InventoryItem, InventoryTransaction.item_id == InventoryItem.id
    ).filter(
        InventoryItem.user_id == target,
        InventoryTransaction.created_at >= start,
        InventoryTransaction.created_at < end,
    ).order_by(InventoryTransaction.created_at.desc()).all()

    # Resolve item names
    item_ids = list({t.item_id for t in txns})
    items_map: dict[str, dict] = {}
    if item_ids:
        items = db.query(InventoryItem).filter(InventoryItem.id.in_(item_ids)).all()
        items_map = {i.id: {"name": i.name, "sku": i.sku} for i in items}

    transactions = []
    for t in txns:
        item_info = items_map.get(t.item_id, {"name": "(deleted)", "sku": ""})
        transactions.append({
            **t.to_dict(),
            "item_name": item_info["name"],
            "item_sku": item_info["sku"],
        })

    # Items created on this day
    new_items = db.query(InventoryItem).filter(
        InventoryItem.user_id == target,
        InventoryItem.created_at >= start,
        InventoryItem.created_at < end,
    ).all()

    return JSONResponse(content={
        "date": target_date.isoformat(),
        "transactions": transactions,
        "items_created": [i.to_dict() for i in new_items],
    })


# ── Export CSV ──────────────────────────────────────────────────────

@router.get("/api/inventory/export/csv")
def api_export_csv(
    view_user: str | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    target = _resolve_target_user_id(user, view_user)
    items = db.query(InventoryItem).filter(
        InventoryItem.user_id == target, InventoryItem.status == "active"
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
    log_activity(db, user=user, action="CSV Export", category="export",
                 summary=f"Exported {len(items)} items",
                 detail={"count": len(items)})
    return StreamingResponse(
        iter([output.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory_export.csv"},
    )


# ── Export JSON ─────────────────────────────────────────────────────

@router.get("/api/inventory/export/json")
def api_export_json(
    category: str = "",
    location: str = "",
    status: str = "active",
    view_user: str | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> Response:
    target = _resolve_target_user_id(user, view_user)
    query = db.query(InventoryItem).filter(InventoryItem.user_id == target)
    if status:
        query = query.filter(InventoryItem.status == status)
    if category:
        query = query.filter(InventoryItem.category == category)
    if location:
        query = query.filter(InventoryItem.location == location)
    items = query.order_by(InventoryItem.name).all()
    payload = {
        "export_date": datetime.now(timezone.utc).isoformat(),
        "total_items": len(items),
        "items": [
            {
                "name": i.name, "sku": i.sku, "description": i.description,
                "quantity": i.quantity, "unit": i.unit, "location": i.location,
                "category": i.category, "tags": i.tags, "notes": i.notes,
                "barcode_value": i.barcode_value, "barcode_type": i.barcode_type,
                "min_quantity": i.min_quantity, "cost": i.cost,
                "status": i.status,
            }
            for i in items
        ],
    }
    return Response(
        content=json_mod.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=inventory_export.json"},
    )


# ── Export CSV (filtered) ──────────────────────────────────────────

@router.get("/api/inventory/export/csv/filtered")
def api_export_csv_filtered(
    category: str = "",
    location: str = "",
    status: str = "active",
    view_user: str | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    target = _resolve_target_user_id(user, view_user)
    query = db.query(InventoryItem).filter(InventoryItem.user_id == target)
    if status:
        query = query.filter(InventoryItem.status == status)
    if category:
        query = query.filter(InventoryItem.category == category)
    if location:
        query = query.filter(InventoryItem.location == location)
    items = query.order_by(InventoryItem.name).all()
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


# ── Import JSON ─────────────────────────────────────────────────────

_JSON_IMPORT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/api/inventory/import/json")
async def api_import_json(
    file: UploadFile = File(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    content = await file.read(_JSON_IMPORT_MAX_BYTES + 1)
    if len(content) > _JSON_IMPORT_MAX_BYTES:
        return JSONResponse(status_code=400, content={"error": "JSON file too large. Maximum size is 10 MB."})
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")
    try:
        data = json_mod.loads(text)
    except json_mod.JSONDecodeError as exc:
        return JSONResponse(status_code=400, content={"error": f"Invalid JSON: {exc}"})

    # Accept either a list of items or an object with an "items" key
    if isinstance(data, dict):
        rows = data.get("items", [])
    elif isinstance(data, list):
        rows = data
    else:
        return JSONResponse(status_code=400, content={"error": "JSON must be an array or an object with an 'items' key."})

    created = 0
    updated = 0
    errors: list[str] = []
    for idx, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"Item {idx}: not an object")
            continue
        name = str(row.get("name", "")).strip()
        sku = str(row.get("sku", "")).strip()
        if not name or not sku:
            errors.append(f"Item {idx}: missing name or sku")
            continue
        existing = db.query(InventoryItem).filter(
            InventoryItem.user_id == user.id, InventoryItem.sku == sku,
        ).first()
        try:
            qty = int(row.get("quantity", 0) or 0)
        except (ValueError, TypeError):
            qty = 0
        cost_val = row.get("cost")
        cost = float(cost_val) if cost_val not in (None, "", "null") else None
        barcode_value = str(row.get("barcode_value", "")).strip()
        if not barcode_value:
            barcode_value = f"BB-{sku.upper()}-{uuid.uuid4().hex[:6].upper()}"
        if existing:
            existing.name = name
            existing.description = str(row.get("description", "")).strip()
            old_qty = existing.quantity
            existing.quantity = qty
            existing.unit = str(row.get("unit", "each")).strip() or "each"
            existing.location = str(row.get("location", "")).strip()
            existing.category = str(row.get("category", "")).strip()
            existing.tags = str(row.get("tags", "")).strip()
            existing.notes = str(row.get("notes", "")).strip()
            existing.barcode_type = str(row.get("barcode_type", "Code128")).strip() or "Code128"
            existing.min_quantity = int(row.get("min_quantity", 0) or 0)
            existing.cost = cost
            existing.updated_at = datetime.now(timezone.utc)
            if qty != old_qty:
                db.add(InventoryTransaction(
                    item_id=existing.id, user_id=user.id,
                    quantity_change=qty - old_qty, quantity_after=qty,
                    reason="adjusted", notes="JSON import update",
                ))
            updated += 1
        else:
            item = InventoryItem(
                user_id=user.id, name=name, sku=sku,
                description=str(row.get("description", "")).strip(),
                quantity=qty, unit=str(row.get("unit", "each")).strip() or "each",
                location=str(row.get("location", "")).strip(),
                category=str(row.get("category", "")).strip(),
                tags=str(row.get("tags", "")).strip(),
                notes=str(row.get("notes", "")).strip(),
                barcode_value=barcode_value,
                barcode_type=str(row.get("barcode_type", "Code128")).strip() or "Code128",
                min_quantity=int(row.get("min_quantity", 0) or 0),
                cost=cost,
            )
            db.add(item)
            db.flush()
            if qty > 0:
                db.add(InventoryTransaction(
                    item_id=item.id, user_id=user.id,
                    quantity_change=qty, quantity_after=qty,
                    reason="initial", notes="JSON import",
                ))
            created += 1
    db.commit()
    log_activity(db, user=user, action="JSON Import", category="import",
                 summary=f"{created} created, {updated} updated, {len(errors)} errors",
                 detail={"created": created, "updated": updated, "errors": len(errors)})
    return JSONResponse(content={
        "created": created, "updated": updated, "errors": errors,
        "message": f"Import complete: {created} created, {updated} updated, {len(errors)} errors",
    })


# ── Import CSV ──────────────────────────────────────────────────────

_CSV_IMPORT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/api/inventory/import/csv")
async def api_import_csv(
    file: UploadFile = File(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    content = await file.read(_CSV_IMPORT_MAX_BYTES + 1)
    if len(content) > _CSV_IMPORT_MAX_BYTES:
        return JSONResponse(status_code=400, content={"error": "CSV file too large. Maximum size is 10 MB."})
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
    log_activity(db, user=user, action="CSV Import", category="import",
                 summary=f"{created} created, {updated} updated, {len(errors)} errors",
                 detail={"created": created, "updated": updated, "errors": len(errors)})
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
    view_user: str | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    target = _resolve_target_user_id(user, view_user)
    query = db.query(InventoryItem).filter(InventoryItem.user_id == target)
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
    log_activity(db, user=user, action="Item Created", category="inventory",
                 summary=f"{item.name} (SKU: {item.sku}) — qty {item.quantity}",
                 detail={"sku": item.sku, "quantity": item.quantity}, item_id=item.id)
    return JSONResponse(status_code=201, content={"item": item.to_dict()})


# ── Get Item ────────────────────────────────────────────────────────

@router.get("/api/inventory/{item_id}")
def api_get_item(
    item_id: str,
    view_user: str | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    item = _find_item(db, item_id, user, view_user)
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
    view_user: str | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    target = _resolve_target_user_id(user, view_user)
    if not _can_write_for(user, target):
        return JSONResponse(status_code=403, content={"error": "Admin access required to edit other users' items"})
    item = db.query(InventoryItem).filter(
        InventoryItem.id == item_id, InventoryItem.user_id == target
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
            InventoryItem.user_id == target, InventoryItem.sku == update_data["sku"],
            InventoryItem.id != item_id, InventoryItem.status != "archived",
        ).first()
        if dup:
            return JSONResponse(status_code=409, content={"error": f"SKU '{update_data['sku']}' already exists"})
    for key, value in update_data.items():
        setattr(item, key, value.strip() if isinstance(value, str) else value)
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    log_activity(db, user=user, action="Item Updated", category="inventory",
                 summary=f"{item.name} — fields: {', '.join(update_data.keys())}",
                 detail={"fields": list(update_data.keys())}, item_id=item.id)
    return JSONResponse(content={"item": item.to_dict()})


# ── Delete Item ─────────────────────────────────────────────────────

@router.delete("/api/inventory/{item_id}")
def api_delete_item(
    item_id: str,
    view_user: str | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    target = _resolve_target_user_id(user, view_user)
    if not _can_write_for(user, target):
        return JSONResponse(status_code=403, content={"error": "Admin access required to delete other users' items"})
    item = db.query(InventoryItem).filter(
        InventoryItem.id == item_id, InventoryItem.user_id == target
    ).first()
    if not item:
        return JSONResponse(status_code=404, content={"error": "Item not found"})
    item_name, item_sku = item.name, item.sku
    db.delete(item)
    db.commit()
    log_activity(db, user=user, action="Item Deleted", category="inventory",
                 summary=f"{item_name} (SKU: {item_sku})",
                 detail={"sku": item_sku, "name": item_name})
    return JSONResponse(content={"message": "Item deleted"})


# ── Adjust Quantity ─────────────────────────────────────────────────

@router.post("/api/inventory/{item_id}/adjust")
def api_adjust_quantity(
    item_id: str, body: QuantityAdjust,
    view_user: str | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    target = _resolve_target_user_id(user, view_user)
    if not _can_write_for(user, target):
        return JSONResponse(status_code=403, content={"error": "Admin access required to adjust other users' items"})
    item = db.query(InventoryItem).filter(
        InventoryItem.id == item_id, InventoryItem.user_id == target
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
    sign = "+" if body.quantity_change > 0 else ""
    log_activity(db, user=user, action="Quantity Adjusted", category="inventory",
                 summary=f"{item.name} — {sign}{body.quantity_change} ({body.reason}) → {new_qty}",
                 detail={"change": body.quantity_change, "reason": body.reason, "after": new_qty},
                 item_id=item.id)
    return JSONResponse(content={"item": item.to_dict(), "transaction": txn.to_dict()})


# ── Scan Lookup ─────────────────────────────────────────────────────

@router.get("/api/scan/lookup")
def api_scan_lookup(
    code: str = "",
    view_user: str | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    code = code.strip()
    if not code:
        return JSONResponse(status_code=400, content={"error": "No barcode value provided"})
    target = _resolve_target_user_id(user, view_user)
    item = db.query(InventoryItem).filter(
        InventoryItem.user_id == target, InventoryItem.barcode_value == code,
        InventoryItem.status == "active",
    ).first()
    if not item:
        item = db.query(InventoryItem).filter(
            InventoryItem.user_id == target, InventoryItem.sku == code,
            InventoryItem.status == "active",
        ).first()
    if not item:
        log_activity(db, user=user, action="Scan — No Match", category="scan",
                     summary=f"Barcode '{code}' not found in inventory",
                     detail={"code": code})
        return JSONResponse(status_code=404, content={"error": "No item found for this code", "code": code})
    log_activity(db, user=user, action="Scan Lookup", category="scan",
                 summary=f"Matched {item.name} (SKU: {item.sku})",
                 detail={"code": code, "item_name": item.name}, item_id=item.id)
    return JSONResponse(content={"item": item.to_dict()})


# ── Barcode Image ───────────────────────────────────────────────────

@router.get("/api/inventory/{item_id}/barcode.png")
def api_barcode_image(
    item_id: str,
    scale: int = Query(default=4, ge=1, le=20),
    view_user: str | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> Response:
    item = _find_item(db, item_id, user, view_user)
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
    item_ids: list[str] = Field(min_length=1, max_length=500)


class BulkUpdateRequest(BaseModel):
    item_ids: list[str] = Field(min_length=1, max_length=500)
    location: str | None = None
    category: str | None = None
    status: str | None = Field(default=None, pattern="^(active|archived)$")
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
    log_activity(db, user=user, action="Bulk Delete", category="inventory",
                 summary=f"Deleted {deleted} items",
                 detail={"deleted": deleted, "requested": len(body.item_ids)})
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
    changes = [k for k in ("location", "category", "status", "tags") if getattr(body, k) is not None]
    log_activity(db, user=user, action="Bulk Update", category="inventory",
                 summary=f"Updated {updated} items — fields: {', '.join(changes)}",
                 detail={"updated": updated, "fields": changes})
    return JSONResponse(content={"updated": updated})


# ── Analytics ──────────────────────────────────────────────────────

@router.get("/api/analytics/transactions")
def api_analytics_transactions(
    days: int = Query(default=30, ge=1, le=365),
    view_user: str | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Transaction breakdown by reason over time."""
    target = _resolve_target_user_id(user, view_user)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    txns = db.query(InventoryTransaction).join(
        InventoryItem, InventoryTransaction.item_id == InventoryItem.id
    ).filter(
        InventoryItem.user_id == target,
        InventoryTransaction.created_at >= cutoff,
    ).all()

    # Aggregate by reason
    by_reason: dict[str, int] = defaultdict(int)
    by_reason_qty: dict[str, int] = defaultdict(int)
    for t in txns:
        reason = t.reason or "adjusted"
        by_reason[reason] += 1
        by_reason_qty[reason] += abs(t.quantity_change)

    # Daily trend by reason
    daily: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for t in txns:
        day_key = t.created_at.strftime("%Y-%m-%d") if t.created_at else None
        if day_key:
            daily[day_key][t.reason or "adjusted"] += 1

    daily_sorted = [
        {"date": k, **v}
        for k, v in sorted(daily.items())
    ]

    return JSONResponse(content={
        "period_days": days,
        "total_transactions": len(txns),
        "by_reason": dict(by_reason),
        "by_reason_quantity": dict(by_reason_qty),
        "daily_trend": daily_sorted,
    })


@router.get("/api/analytics/valuation")
def api_analytics_valuation(
    view_user: str | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Inventory valuation breakdown by category and location."""
    target = _resolve_target_user_id(user, view_user)
    items = db.query(InventoryItem).filter(
        InventoryItem.user_id == target, InventoryItem.status == "active",
    ).all()

    total_value = 0.0
    by_category: dict[str, dict] = {}
    by_location: dict[str, dict] = {}
    by_barcode_type: dict[str, int] = defaultdict(int)
    items_with_cost = 0
    items_without_cost = 0

    for i in items:
        val = (i.cost or 0) * i.quantity
        total_value += val
        if i.cost:
            items_with_cost += 1
        else:
            items_without_cost += 1

        cat = i.category or "(uncategorized)"
        if cat not in by_category:
            by_category[cat] = {"items": 0, "quantity": 0, "value": 0.0}
        by_category[cat]["items"] += 1
        by_category[cat]["quantity"] += i.quantity
        by_category[cat]["value"] += val

        loc = i.location or "(no location)"
        if loc not in by_location:
            by_location[loc] = {"items": 0, "quantity": 0, "value": 0.0}
        by_location[loc]["items"] += 1
        by_location[loc]["quantity"] += i.quantity
        by_location[loc]["value"] += val

        by_barcode_type[i.barcode_type] += 1

    # Round values
    for v in by_category.values():
        v["value"] = round(v["value"], 2)
    for v in by_location.values():
        v["value"] = round(v["value"], 2)

    return JSONResponse(content={
        "total_items": len(items),
        "total_value": round(total_value, 2),
        "items_with_cost": items_with_cost,
        "items_without_cost": items_without_cost,
        "by_category": by_category,
        "by_location": by_location,
        "by_barcode_type": dict(by_barcode_type),
    })


@router.get("/api/analytics/velocity")
def api_analytics_velocity(
    days: int = Query(default=30, ge=1, le=365),
    view_user: str | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Item velocity — most active items by transaction count."""
    target = _resolve_target_user_id(user, view_user)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    txns = db.query(
        InventoryTransaction.item_id,
        func.count(InventoryTransaction.id).label("txn_count"),
        func.sum(func.abs(InventoryTransaction.quantity_change)).label("volume"),
    ).join(
        InventoryItem, InventoryTransaction.item_id == InventoryItem.id
    ).filter(
        InventoryItem.user_id == target,
        InventoryTransaction.created_at >= cutoff,
    ).group_by(InventoryTransaction.item_id).order_by(
        func.count(InventoryTransaction.id).desc()
    ).limit(20).all()

    item_ids = [t[0] for t in txns]
    items_map: dict[str, dict] = {}
    if item_ids:
        items = db.query(InventoryItem).filter(InventoryItem.id.in_(item_ids)).all()
        items_map = {i.id: {"name": i.name, "sku": i.sku, "quantity": i.quantity, "category": i.category} for i in items}

    velocity = []
    for item_id, txn_count, volume in txns:
        info = items_map.get(item_id, {"name": "(deleted)", "sku": "", "quantity": 0, "category": ""})
        velocity.append({
            "item_id": item_id,
            "name": info["name"],
            "sku": info["sku"],
            "category": info["category"],
            "current_quantity": info["quantity"],
            "transaction_count": txn_count,
            "total_volume": int(volume or 0),
        })

    return JSONResponse(content={
        "period_days": days,
        "top_items": velocity,
    })


@router.get("/api/analytics/stock-health")
def api_analytics_stock_health(
    view_user: str | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Stock health overview — distribution of stock levels."""
    target = _resolve_target_user_id(user, view_user)
    items = db.query(InventoryItem).filter(
        InventoryItem.user_id == target, InventoryItem.status == "active",
    ).all()

    out_of_stock = []
    low_stock = []
    healthy = []
    overstocked = []  # qty > 10x min_quantity (if min_quantity set)

    for i in items:
        entry = {"id": i.id, "name": i.name, "sku": i.sku, "quantity": i.quantity,
                 "min_quantity": i.min_quantity, "location": i.location, "category": i.category}
        if i.quantity == 0:
            out_of_stock.append(entry)
        elif i.min_quantity > 0 and i.quantity <= i.min_quantity:
            low_stock.append(entry)
        elif i.min_quantity > 0 and i.quantity > i.min_quantity * 10:
            overstocked.append(entry)
        else:
            healthy.append(entry)

    return JSONResponse(content={
        "total": len(items),
        "out_of_stock": {"count": len(out_of_stock), "items": out_of_stock[:20]},
        "low_stock": {"count": len(low_stock), "items": low_stock[:20]},
        "healthy": {"count": len(healthy)},
        "overstocked": {"count": len(overstocked), "items": overstocked[:20]},
    })
