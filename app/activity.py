"""Activity log: unified logging helper, API routes, and HTML page."""

from __future__ import annotations

import html as html_mod
import json as json_mod
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.auth import require_user
from app.database import ActivityLog, User, get_db
from app.layout import render_shell

router = APIRouter(tags=["activity"])

_E = html_mod.escape


# ── Logging helper ─────────────────────────────────────────────────

def log_activity(
    db: Session,
    *,
    user: User | None = None,
    action: str,
    category: str = "system",
    summary: str = "",
    detail: dict | None = None,
    item_id: str | None = None,
) -> None:
    """Write a single activity entry. Call from any route."""
    db.add(ActivityLog(
        user_id=user.id if user else None,
        action=action,
        category=category,
        summary=summary,
        detail=json_mod.dumps(detail or {}, default=str),
        item_id=item_id,
    ))
    db.commit()


# ── Category metadata (colour + icon label) ───────────────────────

_CAT_META = {
    "inventory": {"css_class": "cat-inventory", "label": "Inventory"},
    "auth":      {"css_class": "cat-auth", "label": "Auth"},
    "admin":     {"css_class": "cat-admin", "label": "Admin"},
    "scan":      {"css_class": "cat-scan", "label": "Scan"},
    "import":    {"css_class": "cat-import", "label": "Import"},
    "export":    {"css_class": "cat-export", "label": "Export"},
    "alert":     {"css_class": "cat-alert", "label": "Alert"},
    "system":    {"css_class": "cat-system", "label": "System"},
}


# ── API: list activity ────────────────────────────────────────────

@router.get("/api/activity")
def api_activity(
    category: str = "",
    q: str = "",
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query = db.query(ActivityLog).filter(ActivityLog.created_at >= cutoff)
    if category:
        query = query.filter(ActivityLog.category == category)
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            ActivityLog.summary.ilike(pattern)
            | ActivityLog.action.ilike(pattern)
        )
    total = query.count()
    entries = query.order_by(ActivityLog.created_at.desc()).offset(offset).limit(limit).all()

    # Resolve user names
    user_ids = {e.user_id for e in entries if e.user_id}
    users_map: dict[str, str] = {}
    if user_ids:
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        users_map = {u.id: u.display_name for u in users}

    result = []
    for e in entries:
        d = e.to_dict()
        d["user_name"] = users_map.get(e.user_id, "System")
        result.append(d)

    return JSONResponse(content={"entries": result, "total": total})


# ── API: recent activity (lightweight, for drawer) ─────────────────

@router.get("/api/activity/recent")
def api_activity_recent(
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    entries = db.query(ActivityLog).order_by(
        ActivityLog.created_at.desc()
    ).limit(limit).all()

    user_ids = {e.user_id for e in entries if e.user_id}
    users_map: dict[str, str] = {}
    if user_ids:
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        users_map = {u.id: u.display_name for u in users}

    result = []
    for e in entries:
        d = e.to_dict()
        d["user_name"] = users_map.get(e.user_id, "System")
        result.append(d)

    return JSONResponse(content={"entries": result})


# ── API: activity stats summary ────────────────────────────────────

@router.get("/api/activity/stats")
def api_activity_stats(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)

    today_count = db.query(ActivityLog).filter(ActivityLog.created_at >= today_start).count()
    week_count = db.query(ActivityLog).filter(ActivityLog.created_at >= week_start).count()
    total_count = db.query(ActivityLog).count()

    # Category breakdown for the week
    week_entries = db.query(ActivityLog).filter(ActivityLog.created_at >= week_start).all()
    cat_counts: dict[str, int] = {}
    for e in week_entries:
        cat_counts[e.category] = cat_counts.get(e.category, 0) + 1

    return JSONResponse(content={
        "today": today_count,
        "week": week_count,
        "total": total_count,
        "week_by_category": cat_counts,
    })


# ── HTML: Activity Log page ───────────────────────────────────────

@router.get("/activity", response_class=HTMLResponse)
def activity_page(user: User = Depends(require_user)) -> HTMLResponse:
    # Build category filter options
    cat_options = "".join(
        f'<option value="{k}">{v["label"]}</option>'
        for k, v in _CAT_META.items()
    )

    # Category badges now use .cat-badge classes from layout.py
    cat_badge_css = ""  # No longer needed — layout.py provides .cat-badge.cat-*

    body = f"""
<style>
  .activity-stats {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(140px,1fr)); gap:12px; margin-bottom:20px; }}
  .astat {{ background:var(--paper); border:1px solid var(--line); border-radius:10px; padding:16px 18px; text-align:center; }}
  .astat .av {{ font-size:28px; font-weight:700; color:var(--text); }}
  .astat .al {{ font-size:12px; color:var(--muted); margin-top:4px; text-transform:uppercase; letter-spacing:.5px; }}
  .activity-filters {{ display:flex; gap:10px; margin-bottom:16px; flex-wrap:wrap; align-items:center; }}
  .activity-filters input, .activity-filters select {{
    padding:9px 14px; border-radius:8px; border:1px solid var(--line);
    background:var(--paper); color:var(--text); font-size:14px;
  }}
  .activity-filters input {{ flex:1; min-width:200px; }}
  .act-list {{ display:flex; flex-direction:column; gap:0; }}
  .act-row {{
    display:grid; grid-template-columns:140px 90px 1fr auto;
    gap:12px; padding:12px 16px; border-bottom:1px solid var(--line);
    align-items:center; transition: background .15s;
  }}
  .act-row:hover {{ background:rgba(255,255,255,.03); }}
  .act-time {{ font-size:12px; color:var(--muted); white-space:nowrap; }}
  .act-cat {{
    display:inline-block; padding:3px 10px; border-radius:20px;
    font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:.5px;
    text-align:center;
  }}
  {cat_badge_css}
  .act-body {{ display:flex; flex-direction:column; gap:2px; }}
  .act-action {{ font-weight:600; font-size:14px; color:var(--text); }}
  .act-summary {{ font-size:13px; color:var(--muted); }}
  .act-user {{ font-size:12px; color:var(--muted); white-space:nowrap; }}
  .act-empty {{ text-align:center; padding:40px; color:var(--muted); }}
  .load-more {{
    display:block; margin:16px auto 0; padding:10px 32px; border-radius:8px;
    border:1px solid var(--line); background:var(--paper); color:var(--text);
    cursor:pointer; font-size:14px;
  }}
  .load-more:hover {{ background:rgba(255,255,255,.05); }}
  .week-chart {{ display:flex; gap:4px; align-items:flex-end; height:60px; margin-top:8px; }}
  .week-bar {{ flex:1; border-radius:4px 4px 0 0; min-width:20px; transition: height .3s; }}
  @media(max-width:700px) {{
    .act-row {{ grid-template-columns:1fr; gap:6px; }}
    .act-time {{ order:2; }}
  }}
</style>

<div class="page-header">
  <div>
    <p class="page-desc" style="margin-bottom:0">Everything that has happened across the system.</p>
  </div>
</div>

<div class="activity-stats" id="act-stats">
  <div class="astat"><div class="av" id="stat-today">-</div><div class="al">Today</div></div>
  <div class="astat"><div class="av" id="stat-week">-</div><div class="al">This Week</div></div>
  <div class="astat"><div class="av" id="stat-total">-</div><div class="al">All Time</div></div>
  <div class="astat" style="padding-bottom:8px">
    <div class="al" style="margin-bottom:6px">Week by Category</div>
    <div class="week-chart" id="week-chart"></div>
  </div>
</div>

<div class="activity-filters">
  <input type="text" id="act-q" placeholder="Search actions and summaries..." autofocus>
  <select id="act-cat">
    <option value="">All Categories</option>
    {cat_options}
  </select>
  <select id="act-days">
    <option value="7">Last 7 days</option>
    <option value="30" selected>Last 30 days</option>
    <option value="90">Last 90 days</option>
    <option value="365">Last year</option>
  </select>
</div>

<div class="panel" style="padding:0;">
  <div class="act-list" id="act-list">
    <div style="padding:16px;display:flex;flex-direction:column;gap:8px"><div class="skeleton skeleton-row"></div><div class="skeleton skeleton-row"></div><div class="skeleton skeleton-row"></div><div class="skeleton skeleton-row"></div><div class="skeleton skeleton-row"></div></div>
  </div>
</div>
<button class="load-more" id="load-more" style="display:none" onclick="loadMore()">Load More</button>
"""

    cat_meta_json = json_mod.dumps(_CAT_META)

    js = f"""<script>
const CAT_META = {cat_meta_json};
/* Resolve bar chart colors from CSS variables for theme support */
const _cv = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const CAT_COLORS = {{inventory:_cv('--info'),auth:'#a78bfa',admin:_cv('--warning'),scan:_cv('--success'),'import':'#06b6d4','export':'#8b5cf6',alert:_cv('--failure'),system:_cv('--muted')}};
let actOffset = 0;
const PAGE = 100;
let actTotal = 0;

async function loadStats() {{
  let d;try{{const r = await fetch('/api/activity/stats');d = await r.json()}}catch(e){{toast('Failed to load stats','error');return}}
  document.getElementById('stat-today').textContent = d.today.toLocaleString();
  document.getElementById('stat-week').textContent = d.week.toLocaleString();
  document.getElementById('stat-total').textContent = d.total.toLocaleString();
  // Mini bar chart
  const chart = document.getElementById('week-chart');
  const cats = Object.entries(d.week_by_category || {{}});
  if (cats.length === 0) {{
    chart.innerHTML = '<span style="font-size:12px;color:var(--muted)">No activity</span>';
    return;
  }}
  const maxVal = Math.max(...cats.map(c => c[1]));
  chart.innerHTML = cats.map(([k, v]) => {{
    const meta = CAT_META[k] || CAT_META.system;
    const h = Math.max(8, (v / maxVal) * 52);
    return `<div class="week-bar" style="height:${{h}}px;background:${{CAT_COLORS[k]||CAT_COLORS.system}}" title="${{meta.label}}: ${{v}}"></div>`;
  }}).join('');
}}

async function loadActivity(append) {{
  if (!append) actOffset = 0;
  const cat = document.getElementById('act-cat').value;
  const q = document.getElementById('act-q').value;
  const days = document.getElementById('act-days').value;
  const params = new URLSearchParams({{days, limit: PAGE, offset: actOffset}});
  if (cat) params.set('category', cat);
  if (q) params.set('q', q);
  let d;try{{const r = await fetch('/api/activity?' + params);d = await r.json()}}catch(e){{toast('Failed to load activity','error');return}}
  actTotal = d.total;
  const list = document.getElementById('act-list');
  if (!append) list.innerHTML = '';
  if (d.entries.length === 0 && !append) {{
    list.innerHTML = '<div class="empty-state"><svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1"><path d="M10 2a8 8 0 100 16 8 8 0 000-16z"/><path d="M10 6v4l3 3"/></svg><h3>No activity found</h3><p>Try adjusting your filters or check back later.</p></div>';
    document.getElementById('load-more').style.display = 'none';
    return;
  }}
  list.innerHTML += d.entries.map(e => {{
    const meta = CAT_META[e.category] || CAT_META.system;
    const time = new Date(e.created_at);
    const timeStr = time.toLocaleDateString(undefined, {{month:'short',day:'numeric'}}) + ' ' + time.toLocaleTimeString(undefined, {{hour:'2-digit',minute:'2-digit'}});
    let detailHtml = '';
    try {{
      const det = JSON.parse(e.detail || '{{}}');
      const keys = Object.keys(det);
      if (keys.length) detailHtml = ' <span style="color:var(--muted);font-size:11px">(' + keys.slice(0,3).map(k => k+'='+det[k]).join(', ') + ')</span>';
    }} catch(_) {{}}
    return `<div class="act-row">
      <div class="act-time">${{timeStr}}</div>
      <div><span class="cat-badge cat-${{e.category}}">${{meta.label}}</span></div>
      <div class="act-body">
        <div class="act-action">${{esc(e.action)}}${{detailHtml}}</div>
        <div class="act-summary">${{esc(e.summary)}}</div>
      </div>
      <div class="act-user">${{esc(e.user_name)}}</div>
    </div>`;
  }}).join('');
  actOffset += d.entries.length;
  document.getElementById('load-more').style.display = actOffset < actTotal ? 'block' : 'none';
}}

function loadMore() {{ loadActivity(true); }}
function esc(s) {{ if (!s) return ''; const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }}

let debounce;
document.getElementById('act-q').addEventListener('input', () => {{ clearTimeout(debounce); debounce = setTimeout(() => loadActivity(false), 300); }});
document.getElementById('act-cat').addEventListener('change', () => loadActivity(false));
document.getElementById('act-days').addEventListener('change', () => loadActivity(false));

loadStats();
loadActivity(false);
</script>"""

    return HTMLResponse(content=render_shell(
        title="Activity Log",
        active_nav="activity",
        body_html=body,
        body_js=js,
        display_name=user.display_name,
        role=user.role,
    ))
