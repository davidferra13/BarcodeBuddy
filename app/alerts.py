"""Alert system: routes, scheduler jobs, and webhook dispatch."""

from __future__ import annotations

import html as html_mod
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_user
from app.database import Alert, AlertConfig, InventoryItem, User, get_db
from app.layout import render_shell

router = APIRouter(tags=["alerts"])
_E = html_mod.escape
_log = logging.getLogger(__name__)


# ── Request models ─────────────────────────────────────────────────

class AlertConfigUpdate(BaseModel):
    alert_type: str
    enabled: bool
    webhook_url: str = ""


class DismissRequest(BaseModel):
    alert_ids: list[str]


# ── API endpoints ──────────────────────────────────────────────────

@router.get("/api/alerts")
def list_alerts(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    q = db.query(Alert).filter(
        Alert.user_id == user.id,
        Alert.is_dismissed == False,
    )
    if unread_only:
        q = q.filter(Alert.is_read == False)
    alerts = q.order_by(Alert.created_at.desc()).limit(limit).all()
    unread_count = db.query(Alert).filter(
        Alert.user_id == user.id, Alert.is_read == False, Alert.is_dismissed == False,
    ).count()
    return JSONResponse(content={
        "alerts": [_alert_to_dict(a) for a in alerts],
        "unread_count": unread_count,
    })


@router.get("/api/alerts/count")
def alert_count(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    count = db.query(Alert).filter(
        Alert.user_id == user.id, Alert.is_read == False, Alert.is_dismissed == False,
    ).count()
    return JSONResponse(content={"unread_count": count})


@router.post("/api/alerts/read")
def mark_alerts_read(
    body: DismissRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    if body.alert_ids:
        db.query(Alert).filter(
            Alert.id.in_(body.alert_ids), Alert.user_id == user.id,
        ).update({"is_read": True}, synchronize_session=False)
        db.commit()
    return JSONResponse(content={"ok": True})


@router.post("/api/alerts/dismiss")
def dismiss_alerts(
    body: DismissRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    if body.alert_ids:
        db.query(Alert).filter(
            Alert.id.in_(body.alert_ids), Alert.user_id == user.id,
        ).update({"is_dismissed": True}, synchronize_session=False)
        db.commit()
    return JSONResponse(content={"ok": True})


@router.post("/api/alerts/dismiss-all")
def dismiss_all_alerts(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    db.query(Alert).filter(
        Alert.user_id == user.id, Alert.is_dismissed == False,
    ).update({"is_dismissed": True}, synchronize_session=False)
    db.commit()
    return JSONResponse(content={"ok": True})


# ── Alert config endpoints ─────────────────────────────────────────

@router.get("/api/alerts/config")
def get_alert_configs(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    configs = db.query(AlertConfig).filter(AlertConfig.user_id == user.id).all()
    # Ensure default configs exist
    existing_types = {c.alert_type for c in configs}
    for atype in ("low_stock", "out_of_stock"):
        if atype not in existing_types:
            cfg = AlertConfig(user_id=user.id, alert_type=atype, enabled=True)
            db.add(cfg)
            configs.append(cfg)
    db.commit()
    return JSONResponse(content={
        "configs": [
            {
                "id": c.id,
                "alert_type": c.alert_type,
                "enabled": c.enabled,
                "webhook_url": c.webhook_url,
            }
            for c in configs
        ]
    })


@router.put("/api/alerts/config")
def update_alert_config(
    body: AlertConfigUpdate,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    cfg = db.query(AlertConfig).filter(
        AlertConfig.user_id == user.id, AlertConfig.alert_type == body.alert_type,
    ).first()
    if not cfg:
        cfg = AlertConfig(user_id=user.id, alert_type=body.alert_type)
        db.add(cfg)
    cfg.enabled = body.enabled
    cfg.webhook_url = body.webhook_url.strip()
    db.commit()
    return JSONResponse(content={"ok": True})


# ── Scheduler job ──────────────────────────────────────────────────

def check_stock_alerts(db: Session) -> list[dict[str, Any]]:
    """Check all users' inventory for low/out-of-stock items and create alerts.

    Called by APScheduler. Returns list of alerts created (for logging).
    """
    created: list[dict[str, Any]] = []
    users = db.query(User).filter(User.is_active == True).all()

    for user in users:
        # Check configs
        configs = {
            c.alert_type: c
            for c in db.query(AlertConfig).filter(AlertConfig.user_id == user.id).all()
        }

        items = db.query(InventoryItem).filter(
            InventoryItem.user_id == user.id,
            InventoryItem.status == "active",
        ).all()

        for item in items:
            # Out of stock
            if item.quantity == 0:
                alert_type = "out_of_stock"
                cfg = configs.get(alert_type)
                if cfg and not cfg.enabled:
                    continue
                # Avoid duplicate: check if unread alert exists for this item
                existing = db.query(Alert).filter(
                    Alert.user_id == user.id,
                    Alert.item_id == item.id,
                    Alert.alert_type == alert_type,
                    Alert.is_dismissed == False,
                ).first()
                if existing:
                    continue
                alert = Alert(
                    user_id=user.id,
                    alert_type=alert_type,
                    severity="critical",
                    title=f"Out of stock: {item.name}",
                    message=f"{item.name} ({item.sku}) has 0 {item.unit} remaining.",
                    item_id=item.id,
                )
                db.add(alert)
                created.append({"type": alert_type, "item": item.name, "user": user.email})
                _fire_webhook(cfg, alert) if cfg else None

            # Low stock
            elif item.min_quantity > 0 and item.quantity <= item.min_quantity:
                alert_type = "low_stock"
                cfg = configs.get(alert_type)
                if cfg and not cfg.enabled:
                    continue
                existing = db.query(Alert).filter(
                    Alert.user_id == user.id,
                    Alert.item_id == item.id,
                    Alert.alert_type == alert_type,
                    Alert.is_dismissed == False,
                ).first()
                if existing:
                    continue
                alert = Alert(
                    user_id=user.id,
                    alert_type=alert_type,
                    severity="warning",
                    title=f"Low stock: {item.name}",
                    message=f"{item.name} ({item.sku}) has {item.quantity} {item.unit} remaining (min: {item.min_quantity}).",
                    item_id=item.id,
                )
                db.add(alert)
                created.append({"type": alert_type, "item": item.name, "user": user.email})
                _fire_webhook(cfg, alert) if cfg else None

    db.commit()
    return created


# ── Webhook dispatch ───────────────────────────────────────────────

def _fire_webhook(cfg: AlertConfig | None, alert: Alert) -> None:
    """Fire webhook if configured. Non-blocking best-effort."""
    if not cfg or not cfg.webhook_url:
        return
    try:
        payload = {
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "title": alert.title,
            "message": alert.message,
            "item_id": alert.item_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with httpx.Client(timeout=10) as client:
            resp = client.post(cfg.webhook_url, json=payload)
            if resp.status_code >= 400:
                _log.warning("Webhook returned %d for %s", resp.status_code, cfg.webhook_url)
    except Exception as e:
        _log.warning("Webhook failed for %s: %s", cfg.webhook_url, e)


# ── Alerts HTML page ───────────────────────────────────────────────

@router.get("/alerts", response_class=HTMLResponse)
def alerts_page(user: User = Depends(require_user)) -> HTMLResponse:
    css = """<style>
    .alert-tabs{display:flex;gap:4px;margin-bottom:24px;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:4px}
    .alert-tab{padding:8px 16px;border-radius:8px;border:none;background:transparent;color:var(--muted);font-size:13px;font-weight:600;cursor:pointer;transition:all .15s;font-family:inherit}
    .alert-tab:hover{background:rgba(44,54,63,.06);color:var(--text)}
    .alert-tab.active{background:var(--sidebar-bg);color:#fff}
    .alert-sec{display:none;animation:alertIn .2s ease}
    .alert-sec.active{display:block}
    @keyframes alertIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
    .alert-item{display:grid;grid-template-columns:40px 1fr auto;gap:12px;align-items:start;padding:14px 16px;border-bottom:1px solid var(--line);transition:background .15s}
    .alert-item:hover{background:rgba(44,54,63,.03)}
    .alert-item.unread{background:rgba(36,114,164,.04)}
    .alert-icon{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:16px}
    .alert-icon.critical{background:var(--failure-bg);color:var(--failure);border:1px solid var(--failure-border)}
    .alert-icon.warning{background:var(--warning-bg);color:var(--warning);border:1px solid rgba(184,134,11,.18)}
    .alert-icon.info{background:var(--info-bg);color:var(--info);border:1px solid var(--info-border)}
    .alert-title{font-weight:600;font-size:14px;line-height:1.3}
    .alert-msg{font-size:12px;color:var(--muted);margin-top:2px}
    .alert-time{font-size:11px;color:var(--muted);white-space:nowrap}
    .alert-actions{display:flex;gap:6px;margin-top:6px}
    .alert-actions button{padding:4px 10px;border-radius:6px;border:1px solid var(--line);background:var(--panel);color:var(--muted);font-size:11px;cursor:pointer;font-family:inherit;transition:all .15s}
    .alert-actions button:hover{color:var(--text);border-color:var(--text)}
    .cfg-row{display:grid;grid-template-columns:1fr 80px 1fr;gap:16px;align-items:center;padding:14px 0;border-bottom:1px solid var(--line)}
    .cfg-row:last-child{border-bottom:none}
    .toggle{position:relative;width:44px;height:24px;cursor:pointer}
    .toggle input{opacity:0;width:0;height:0}
    .toggle .slider{position:absolute;inset:0;background:var(--track);border-radius:24px;transition:.2s}
    .toggle input:checked+.slider{background:var(--success)}
    .toggle .slider:before{content:'';position:absolute;height:18px;width:18px;left:3px;bottom:3px;background:#fff;border-radius:50%;transition:.2s}
    .toggle input:checked+.slider:before{transform:translateX(20px)}
    .webhook-input{padding:6px 10px;border-radius:6px;border:1px solid var(--line);background:var(--paper);color:var(--text);font-size:12px;font-family:inherit;width:100%}
    </style>"""

    body = """
    <div class="page-header">
      <div class="page-header-left">
        <p class="page-desc" style="margin-bottom:0">Stock alerts and notification settings.</p>
      </div>
      <div style="display:flex;gap:8px">
        <button class="btn btn-secondary" onclick="markAllRead()" style="padding:8px 16px;font-size:13px">Mark All Read</button>
        <button class="btn btn-secondary" onclick="dismissAll()" style="padding:8px 16px;font-size:13px">Dismiss All</button>
      </div>
    </div>

    <div class="alert-tabs">
      <button class="alert-tab active" onclick="switchAlertTab('list',this)">Alerts <span id="badge-count" style="background:var(--failure);color:#fff;border-radius:999px;padding:1px 7px;font-size:11px;margin-left:4px;display:none"></span></button>
      <button class="alert-tab" onclick="switchAlertTab('config',this)">Settings</button>
    </div>

    <div class="alert-sec active" id="sec-list">
      <div class="panel" style="padding:0" id="alert-list">
        <div style="padding:40px;text-align:center;color:var(--muted)">Loading alerts...</div>
      </div>
    </div>

    <div class="alert-sec" id="sec-config">
      <div class="panel" style="padding:20px">
        <h3 style="font-size:14px;margin-bottom:16px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em">Alert Types & Webhooks</h3>
        <p style="font-size:12px;color:var(--muted);margin-bottom:16px">Configure which alerts trigger and optional webhook URLs for external notifications (Slack, Teams, etc).</p>
        <div id="config-rows"></div>
      </div>
    </div>"""

    js = """<script>
const SEVERITY_ICONS={critical:'&#10007;',warning:'&#9888;',info:'&#8505;'};
const TYPE_LABELS={low_stock:'Low Stock',out_of_stock:'Out of Stock',processing_failure:'Processing Failure'};
function switchAlertTab(id,btn){document.querySelectorAll('.alert-sec').forEach(s=>s.classList.remove('active'));document.getElementById('sec-'+id).classList.add('active');document.querySelectorAll('.alert-tab').forEach(t=>t.classList.remove('active'));btn.classList.add('active')}

async function loadAlerts(){
  const r=await fetch('/api/alerts');const d=await r.json();
  const badge=document.getElementById('badge-count');
  if(d.unread_count>0){badge.textContent=d.unread_count;badge.style.display='inline'}else{badge.style.display='none'}
  const list=document.getElementById('alert-list');
  if(!d.alerts.length){list.innerHTML='<div style="padding:40px;text-align:center;color:var(--muted)"><svg width="48" height="48" viewBox="0 0 20 20" fill="none" stroke="var(--muted)" stroke-width="1" style="margin-bottom:12px;opacity:.4"><path d="M10 2a6 6 0 00-6 6c0 3-1.5 5-2 6h16c-.5-1-2-3-2-6a6 6 0 00-6-6z"/><path d="M8 16a2 2 0 004 0"/></svg><div style="font-size:15px;margin-bottom:6px;color:var(--text)">No alerts</div><div>Your inventory is looking good. Alerts will appear here when stock levels need attention.</div></div>';return}
  list.innerHTML=d.alerts.map(a=>{
    const icon=SEVERITY_ICONS[a.severity]||'&#8505;';
    const cls=a.is_read?'':'unread';
    const ago=timeAgo(a.created_at);
    return `<div class="alert-item ${cls}" data-id="${a.id}">
      <div class="alert-icon ${a.severity}">${icon}</div>
      <div>
        <div class="alert-title">${esc(a.title)}</div>
        <div class="alert-msg">${esc(a.message)}</div>
        <div class="alert-actions">
          ${a.item_id?`<button onclick="location='/inventory/${a.item_id}'">View Item</button>`:''}
          ${!a.is_read?`<button onclick="markRead('${a.id}')">Mark Read</button>`:''}
          <button onclick="dismiss('${a.id}')">Dismiss</button>
        </div>
      </div>
      <div class="alert-time">${ago}</div>
    </div>`;
  }).join('');
}

function timeAgo(iso){
  const d=new Date(iso+'Z');const now=new Date();const s=Math.floor((now-d)/1000);
  if(s<60)return 'just now';if(s<3600)return Math.floor(s/60)+'m ago';
  if(s<86400)return Math.floor(s/3600)+'h ago';return Math.floor(s/86400)+'d ago';
}

async function markRead(id){await apiCall('POST','/api/alerts/read',{alert_ids:[id]});loadAlerts()}
async function dismiss(id){await apiCall('POST','/api/alerts/dismiss',{alert_ids:[id]});loadAlerts()}
async function markAllRead(){
  const r=await fetch('/api/alerts?unread_only=true');const d=await r.json();
  if(d.alerts.length){await apiCall('POST','/api/alerts/read',{alert_ids:d.alerts.map(a=>a.id)});loadAlerts();toast('All marked as read','success')}
}
async function dismissAll(){await apiCall('POST','/api/alerts/dismiss-all',{});loadAlerts();toast('All alerts dismissed','success')}

// Config
async function loadConfig(){
  const r=await fetch('/api/alerts/config');const d=await r.json();
  const rows=document.getElementById('config-rows');
  rows.innerHTML=d.configs.map(c=>`<div class="cfg-row">
    <div><div style="font-weight:600">${esc(TYPE_LABELS[c.alert_type]||c.alert_type)}</div><div style="font-size:11px;color:var(--muted)">Get notified when items ${c.alert_type==='out_of_stock'?'reach zero stock':'fall below minimum quantity'}</div></div>
    <label class="toggle"><input type="checkbox" ${c.enabled?'checked':''} onchange="saveConfig('${c.alert_type}',this.checked,this.closest('.cfg-row').querySelector('.webhook-input').value)"><span class="slider"></span></label>
    <input type="text" class="webhook-input" value="${esc(c.webhook_url)}" placeholder="Webhook URL (optional)" onblur="saveConfig('${c.alert_type}',this.closest('.cfg-row').querySelector('input[type=checkbox]').checked,this.value)">
  </div>`).join('');
}

async function saveConfig(type,enabled,url){
  await apiCall('PUT','/api/alerts/config',{alert_type:type,enabled:enabled,webhook_url:url});
  toast('Settings saved','success');
}

loadAlerts();loadConfig();
</script>"""

    return HTMLResponse(content=render_shell(
        title="Alerts",
        active_nav="alerts",
        body_html=body,
        body_js=js,
        display_name=user.display_name,
        role=user.role,
        head_extra=css,
    ))


def _alert_to_dict(a: Alert) -> dict[str, Any]:
    return {
        "id": a.id,
        "alert_type": a.alert_type,
        "severity": a.severity,
        "title": a.title,
        "message": a.message,
        "item_id": a.item_id,
        "is_read": a.is_read,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }
