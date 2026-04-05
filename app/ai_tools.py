"""AI chatbot tool definitions and execution handlers.

Each tool maps to an existing database query pattern.  The chatbot model
requests a tool call, the backend executes it here, and feeds the JSON
result back so the model can formulate a natural-language answer.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import (
    ActivityLog,
    Alert,
    InventoryItem,
    InventoryTransaction,
    User,
)

# ---------------------------------------------------------------------------
# Tool definitions (generic JSON Schema — converted per-provider in ai_provider)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "query_inventory",
        "description": (
            "Search inventory items by name, SKU, category, location, or barcode. "
            "Returns matching items with quantities, costs, and locations."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "search": {"type": "string", "description": "Search term (name, SKU, barcode, tags)"},
                "category": {"type": "string", "description": "Filter by exact category"},
                "location": {"type": "string", "description": "Filter by exact location"},
                "low_stock_only": {"type": "boolean", "description": "Only return items below their min_quantity threshold"},
                "limit": {"type": "integer", "description": "Max results to return (default 10, max 50)"},
            },
        },
    },
    {
        "name": "get_inventory_stats",
        "description": (
            "Get summary statistics for the inventory: total items, total units, "
            "total value, low stock count, out-of-stock count, and breakdowns by category and location."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_processing_stats",
        "description": (
            "Get document processing statistics: total documents processed, success rate, "
            "failure count, average processing time, and recent failure reasons. "
            "Use this for questions about barcode scanning, document ingestion, or processing pipeline."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Look-back period in days (default 7, max 90)"},
            },
        },
    },
    {
        "name": "get_recent_activity",
        "description": (
            "Get recent activity log entries. Activities include inventory changes, "
            "auth events, admin actions, scans, imports, exports, and alerts."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Filter by category: inventory, auth, admin, scan, import, export, alert, system",
                },
                "search": {"type": "string", "description": "Search in action or summary text"},
                "days": {"type": "integer", "description": "Look-back period in days (default 7)"},
                "limit": {"type": "integer", "description": "Max entries (default 20, max 50)"},
            },
        },
    },
    {
        "name": "get_alerts_summary",
        "description": "Get current unread alerts: count by type, and the most recent alerts with details.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_item_history",
        "description": (
            "Get the transaction history for a specific inventory item — all quantity changes "
            "with reasons, timestamps, and notes. Search by item name or SKU."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "item_name": {"type": "string", "description": "Item name to search for"},
                "sku": {"type": "string", "description": "Exact SKU to look up"},
                "limit": {"type": "integer", "description": "Max transactions to return (default 20)"},
            },
        },
    },
    {
        "name": "get_transaction_analytics",
        "description": (
            "Get transaction analytics: breakdown by reason (received, sold, adjusted, damaged, returned), "
            "daily trends, and total volumes over a time period."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Look-back period in days (default 30, max 365)"},
            },
        },
    },
    {
        "name": "get_inventory_valuation",
        "description": (
            "Get inventory valuation breakdown by category and location. "
            "Shows total value, items with/without cost data, and value per category/location."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_top_movers",
        "description": (
            "Get the most active inventory items by transaction count (fastest movers). "
            "Shows which items have the most activity over a time period."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Look-back period in days (default 30)"},
                "limit": {"type": "integer", "description": "Number of items to return (default 10, max 20)"},
            },
        },
    },
    {
        "name": "get_stock_health",
        "description": (
            "Get stock health distribution: how many items are out-of-stock, low stock, healthy, or overstocked. "
            "Includes item details for each category."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_system_health",
        "description": (
            "Get system health including document processing queue status, service uptime, "
            "health score, and any current issues. Use this for questions about whether the system is working."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
]


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

async def execute_tool(tool_name: str, arguments: dict, db: Session, user: User, settings=None) -> str:
    """Execute a tool call and return the result as a JSON string."""
    _settings_tools = {"get_processing_stats", "get_system_health"}
    handlers = {
        "query_inventory": _tool_query_inventory,
        "get_inventory_stats": _tool_inventory_stats,
        "get_processing_stats": _tool_processing_stats,
        "get_recent_activity": _tool_recent_activity,
        "get_alerts_summary": _tool_alerts_summary,
        "get_item_history": _tool_item_history,
        "get_transaction_analytics": _tool_transaction_analytics,
        "get_inventory_valuation": _tool_inventory_valuation,
        "get_top_movers": _tool_top_movers,
        "get_stock_health": _tool_stock_health,
        "get_system_health": _tool_system_health,
    }
    handler = handlers.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    try:
        if tool_name in _settings_tools:
            return await handler(arguments, db, user, settings)
        return await handler(arguments, db, user)
    except Exception as exc:
        return json.dumps({"error": f"Tool execution failed: {exc}"})


async def _tool_query_inventory(args: dict, db: Session, user: User) -> str:
    from sqlalchemy import or_
    query = db.query(InventoryItem).filter(
        InventoryItem.user_id == user.id,
        InventoryItem.status == "active",
    )
    search = args.get("search", "")
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(
            InventoryItem.name.ilike(pattern),
            InventoryItem.sku.ilike(pattern),
            InventoryItem.barcode_value.ilike(pattern),
            InventoryItem.location.ilike(pattern),
            InventoryItem.tags.ilike(pattern),
        ))
    if args.get("category"):
        query = query.filter(InventoryItem.category == args["category"])
    if args.get("location"):
        query = query.filter(InventoryItem.location == args["location"])
    if args.get("low_stock_only"):
        query = query.filter(
            InventoryItem.min_quantity > 0,
            InventoryItem.quantity <= InventoryItem.min_quantity,
        )
    limit = min(args.get("limit", 10), 50)
    items = query.order_by(InventoryItem.updated_at.desc()).limit(limit).all()
    total = query.count()
    return json.dumps({
        "total_matching": total,
        "items": [
            {
                "name": i.name, "sku": i.sku, "quantity": i.quantity,
                "unit": i.unit, "location": i.location, "category": i.category,
                "cost": i.cost, "min_quantity": i.min_quantity,
                "barcode_value": i.barcode_value,
            }
            for i in items
        ],
    })


async def _tool_inventory_stats(args: dict, db: Session, user: User) -> str:
    items = db.query(InventoryItem).filter(
        InventoryItem.user_id == user.id,
        InventoryItem.status == "active",
    ).all()
    total_items = len(items)
    total_quantity = sum(i.quantity for i in items)
    total_value = sum((i.cost or 0) * i.quantity for i in items)
    low_stock = [i for i in items if i.min_quantity > 0 and i.quantity <= i.min_quantity]
    out_of_stock = [i for i in items if i.quantity == 0]
    categories: dict[str, int] = {}
    locations: dict[str, int] = {}
    for i in items:
        if i.category:
            categories[i.category] = categories.get(i.category, 0) + 1
        if i.location:
            locations[i.location] = locations.get(i.location, 0) + 1
    return json.dumps({
        "total_items": total_items,
        "total_quantity": total_quantity,
        "total_value": round(total_value, 2),
        "low_stock_count": len(low_stock),
        "out_of_stock_count": len(out_of_stock),
        "low_stock_items": [{"name": i.name, "sku": i.sku, "quantity": i.quantity, "min_quantity": i.min_quantity} for i in low_stock[:5]],
        "categories": categories,
        "locations": locations,
    })


async def _tool_processing_stats(args: dict, db: Session, user: User, settings=None) -> str:
    if settings is None:
        return json.dumps({"error": "Processing stats require server settings (log path). Not available."})

    try:
        from app.stats import build_stats_snapshot
        snapshot = build_stats_snapshot(settings, history_days=min(args.get("days", 7), 90))
        docs = snapshot.get("documents", {})
        last24 = snapshot.get("last_24h", {})
        failures = snapshot.get("top_failure_reasons", [])
        latency = snapshot.get("latency", {})
        return json.dumps({
            "total_documents": docs.get("total_seen", 0),
            "completed": docs.get("completed", 0),
            "succeeded": docs.get("succeeded", 0),
            "failed": docs.get("failed", 0),
            "success_rate": docs.get("success_rate", "0%"),
            "avg_completion_seconds": docs.get("avg_completion_s", 0),
            "last_24h": {
                "documents": last24.get("documents", 0),
                "completions": last24.get("completions", 0),
                "successes": last24.get("successes", 0),
                "failures": last24.get("failures", 0),
            },
            "top_failure_reasons": failures[:5],
            "latency_p50": latency.get("p50", 0),
            "latency_p90": latency.get("p90", 0),
        })
    except Exception as exc:
        return json.dumps({"error": f"Could not read processing stats: {exc}"})


async def _tool_recent_activity(args: dict, db: Session, user: User) -> str:
    days = min(args.get("days", 7), 90)
    limit = min(args.get("limit", 20), 50)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    query = db.query(ActivityLog).filter(ActivityLog.created_at >= cutoff)
    if args.get("category"):
        query = query.filter(ActivityLog.category == args["category"])
    if args.get("search"):
        pattern = f"%{args['search']}%"
        query = query.filter(
            ActivityLog.summary.ilike(pattern) | ActivityLog.action.ilike(pattern)
        )
    total = query.count()
    entries = query.order_by(ActivityLog.created_at.desc()).limit(limit).all()

    # Resolve user names
    user_ids = {e.user_id for e in entries if e.user_id}
    users_map: dict[str, str] = {}
    if user_ids:
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        users_map = {u.id: u.display_name for u in users}

    return json.dumps({
        "total_matching": total,
        "entries": [
            {
                "action": e.action,
                "category": e.category,
                "summary": e.summary,
                "user_name": users_map.get(e.user_id, "System"),
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ],
    })


async def _tool_alerts_summary(args: dict, db: Session, user: User) -> str:
    alerts = db.query(Alert).filter(
        Alert.user_id == user.id,
        Alert.is_dismissed == False,
    ).order_by(Alert.created_at.desc()).limit(20).all()

    unread = [a for a in alerts if not a.is_read]
    by_type: dict[str, int] = {}
    for a in alerts:
        by_type[a.alert_type] = by_type.get(a.alert_type, 0) + 1

    return json.dumps({
        "total_active": len(alerts),
        "unread_count": len(unread),
        "by_type": by_type,
        "recent_alerts": [
            {
                "type": a.alert_type,
                "severity": a.severity,
                "title": a.title,
                "message": a.message,
                "is_read": a.is_read,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in alerts[:10]
        ],
    })


async def _tool_item_history(args: dict, db: Session, user: User) -> str:
    from sqlalchemy import or_
    item = None
    if args.get("sku"):
        item = db.query(InventoryItem).filter(
            InventoryItem.user_id == user.id,
            InventoryItem.sku == args["sku"],
        ).first()
    elif args.get("item_name"):
        pattern = f"%{args['item_name']}%"
        item = db.query(InventoryItem).filter(
            InventoryItem.user_id == user.id,
            InventoryItem.name.ilike(pattern),
        ).first()

    if not item:
        return json.dumps({"error": "Item not found. Try a different name or SKU."})

    limit = min(args.get("limit", 20), 50)
    txns = db.query(InventoryTransaction).filter(
        InventoryTransaction.item_id == item.id,
    ).order_by(InventoryTransaction.created_at.desc()).limit(limit).all()

    return json.dumps({
        "item": {"name": item.name, "sku": item.sku, "quantity": item.quantity, "location": item.location},
        "transactions": [
            {
                "quantity_change": t.quantity_change,
                "quantity_after": t.quantity_after,
                "reason": t.reason,
                "notes": t.notes,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in txns
        ],
    })


async def _tool_transaction_analytics(args: dict, db: Session, user: User) -> str:
    days = min(args.get("days", 30), 365)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    items = db.query(InventoryItem).filter(
        InventoryItem.user_id == user.id,
    ).all()
    item_ids = [i.id for i in items]
    if not item_ids:
        return json.dumps({"error": "No inventory items found."})

    txns = db.query(InventoryTransaction).filter(
        InventoryTransaction.item_id.in_(item_ids),
        InventoryTransaction.created_at >= cutoff,
    ).all()

    by_reason: dict[str, dict] = {}
    for t in txns:
        r = t.reason or "unknown"
        if r not in by_reason:
            by_reason[r] = {"count": 0, "total_volume": 0}
        by_reason[r]["count"] += 1
        by_reason[r]["total_volume"] += abs(t.quantity_change)

    return json.dumps({
        "period_days": days,
        "total_transactions": len(txns),
        "by_reason": by_reason,
    })


async def _tool_inventory_valuation(args: dict, db: Session, user: User) -> str:
    items = db.query(InventoryItem).filter(
        InventoryItem.user_id == user.id,
        InventoryItem.status == "active",
    ).all()

    total_value = 0.0
    items_with_cost = 0
    items_without_cost = 0
    by_category: dict[str, float] = {}
    by_location: dict[str, float] = {}

    for i in items:
        if i.cost and i.cost > 0:
            val = i.cost * i.quantity
            total_value += val
            items_with_cost += 1
            if i.category:
                by_category[i.category] = by_category.get(i.category, 0) + val
            if i.location:
                by_location[i.location] = by_location.get(i.location, 0) + val
        else:
            items_without_cost += 1

    return json.dumps({
        "total_value": round(total_value, 2),
        "total_items": len(items),
        "items_with_cost": items_with_cost,
        "items_without_cost": items_without_cost,
        "value_by_category": {k: round(v, 2) for k, v in sorted(by_category.items(), key=lambda x: -x[1])},
        "value_by_location": {k: round(v, 2) for k, v in sorted(by_location.items(), key=lambda x: -x[1])},
    })


async def _tool_top_movers(args: dict, db: Session, user: User) -> str:
    days = min(args.get("days", 30), 365)
    limit = min(args.get("limit", 10), 20)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    items = db.query(InventoryItem).filter(
        InventoryItem.user_id == user.id,
    ).all()
    item_ids = [i.id for i in items]
    item_map = {i.id: i for i in items}
    if not item_ids:
        return json.dumps({"items": []})

    txns = db.query(InventoryTransaction).filter(
        InventoryTransaction.item_id.in_(item_ids),
        InventoryTransaction.created_at >= cutoff,
    ).all()

    counts: dict[str, dict] = {}
    for t in txns:
        if t.item_id not in counts:
            counts[t.item_id] = {"count": 0, "volume": 0}
        counts[t.item_id]["count"] += 1
        counts[t.item_id]["volume"] += abs(t.quantity_change)

    sorted_items = sorted(counts.items(), key=lambda x: -x[1]["count"])[:limit]

    return json.dumps({
        "period_days": days,
        "top_movers": [
            {
                "name": item_map[iid].name if iid in item_map else "Unknown",
                "sku": item_map[iid].sku if iid in item_map else "",
                "current_quantity": item_map[iid].quantity if iid in item_map else 0,
                "transaction_count": data["count"],
                "total_volume": data["volume"],
            }
            for iid, data in sorted_items
        ],
    })


async def _tool_stock_health(args: dict, db: Session, user: User) -> str:
    items = db.query(InventoryItem).filter(
        InventoryItem.user_id == user.id,
        InventoryItem.status == "active",
    ).all()

    out_of_stock = []
    low_stock = []
    healthy = []
    overstocked = []

    for i in items:
        info = {"name": i.name, "sku": i.sku, "quantity": i.quantity, "min_quantity": i.min_quantity,
                "location": i.location, "category": i.category}
        if i.quantity == 0:
            out_of_stock.append(info)
        elif i.min_quantity > 0 and i.quantity <= i.min_quantity:
            low_stock.append(info)
        elif i.min_quantity > 0 and i.quantity > i.min_quantity * 3:
            overstocked.append(info)
        else:
            healthy.append(info)

    return json.dumps({
        "total_items": len(items),
        "out_of_stock": {"count": len(out_of_stock), "items": out_of_stock[:10]},
        "low_stock": {"count": len(low_stock), "items": low_stock[:10]},
        "healthy": {"count": len(healthy)},
        "overstocked": {"count": len(overstocked), "items": overstocked[:10]},
    })


async def _tool_system_health(args: dict, db: Session, user: User, settings=None) -> str:
    if settings is None:
        return json.dumps({"error": "System health requires server settings."})

    try:
        from app.stats import build_stats_snapshot
        snapshot = build_stats_snapshot(settings, history_days=1)
        queue = snapshot.get("queue", {})
        service = snapshot.get("service", {})
        health = snapshot.get("health_score", {})
        latency = snapshot.get("latency", {})

        return json.dumps({
            "service_status": service.get("status", "unknown"),
            "last_heartbeat": service.get("last_heartbeat", ""),
            "queue": {
                "input_backlog": queue.get("input_backlog", 0),
                "processing": queue.get("processing", 0),
                "rejected": queue.get("rejected", 0),
            },
            "health_score": health.get("score", None),
            "health_grade": health.get("grade", ""),
            "latency_p50": latency.get("p50", 0),
            "latency_p95": latency.get("p95", 0),
            "latency_p99": latency.get("p99", 0),
        })
    except Exception as exc:
        return json.dumps({"error": f"Could not read system health: {exc}"})


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

def build_system_prompt(user: User) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        "You are BarcodeBuddy AI, an assistant for the Danpack packaging company's "
        "inventory and document management system.\n\n"
        "You help users understand their inventory, processing statistics, alerts, and activity. "
        "Always be concise and specific. When asked about data, use the available tools to look it up — "
        "never guess or make up numbers.\n\n"
        "If you don't have enough information, say so and suggest what the user could look up.\n"
        "Format numbers with commas for readability. Use markdown for emphasis when helpful.\n"
        "Keep answers short — a few sentences is usually enough.\n\n"
        f"Current user: {user.display_name} (role: {user.role})\n"
        f"Current date/time: {now}"
    )
