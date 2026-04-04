"""Inventory management web UI — single-page application served as HTML."""

from __future__ import annotations

import html as html_mod

from app.database import User


def render_inventory_app(user: User) -> str:
    """Render the full inventory management SPA."""
    user_name = html_mod.escape(user.display_name)
    user_role = html_mod.escape(user.role)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Barcode Buddy — Inventory</title>
<style>
:root {{
  --bg-primary: #0f172a;
  --bg-card: #1e293b;
  --bg-input: #0f172a;
  --bg-hover: #334155;
  --text-primary: #f8fafc;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --border: #334155;
  --accent: #3b82f6;
  --accent-hover: #2563eb;
  --success: #22c55e;
  --success-bg: #052e16;
  --warning: #f59e0b;
  --warning-bg: #451a03;
  --danger: #ef4444;
  --danger-bg: #450a0a;
  --purple: #7c3aed;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg-primary); color: var(--text-primary);
  min-height: 100vh;
}}
a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}

/* Layout */
.app-shell {{ display: flex; min-height: 100vh; }}
.sidebar {{
  width: 220px; background: var(--bg-card); padding: 20px 0;
  border-right: 1px solid var(--border); flex-shrink: 0;
  display: flex; flex-direction: column;
}}
.sidebar .brand {{
  padding: 0 20px 20px; font-size: 15px; font-weight: 700;
  color: var(--text-primary); border-bottom: 1px solid var(--border);
  margin-bottom: 8px; letter-spacing: 0.5px;
}}
.sidebar .brand small {{ display: block; font-size: 11px; color: var(--text-muted); font-weight: 400; margin-top: 2px; }}
.sidebar nav {{ flex: 1; }}
.sidebar nav a {{
  display: flex; align-items: center; gap: 10px;
  padding: 10px 20px; color: var(--text-secondary); font-size: 14px;
  transition: all 0.15s; text-decoration: none; border-left: 3px solid transparent;
}}
.sidebar nav a:hover {{ background: var(--bg-hover); color: var(--text-primary); }}
.sidebar nav a.active {{
  background: rgba(59,130,246,0.1); color: var(--accent);
  border-left-color: var(--accent); font-weight: 600;
}}
.sidebar .user-section {{
  padding: 16px 20px; border-top: 1px solid var(--border);
  font-size: 13px; color: var(--text-secondary);
}}
.sidebar .user-section .user-name {{ font-weight: 600; color: var(--text-primary); }}
.sidebar .user-section .user-role {{
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  font-size: 11px; font-weight: 600; margin-top: 4px;
}}
.role-admin {{ background: rgba(124,58,237,0.2); color: #a78bfa; }}
.role-user {{ background: rgba(59,130,246,0.2); color: #93c5fd; }}
.main-content {{ flex: 1; padding: 24px 32px; overflow-y: auto; max-height: 100vh; }}

/* Cards & Components */
.page-header {{
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 24px;
}}
.page-header h1 {{ font-size: 22px; font-weight: 700; }}
.card {{
  background: var(--bg-card); border-radius: 10px; padding: 20px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.2); margin-bottom: 20px;
}}
.stats-grid {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px; margin-bottom: 24px;
}}
.stat-card {{
  background: var(--bg-card); border-radius: 10px; padding: 20px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.2);
}}
.stat-card .value {{ font-size: 28px; font-weight: 700; color: var(--text-primary); }}
.stat-card .label {{ font-size: 12px; color: var(--text-muted); margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }}

/* Buttons */
.btn {{
  padding: 8px 16px; border-radius: 8px; border: none;
  font-size: 13px; font-weight: 600; cursor: pointer;
  transition: all 0.15s; display: inline-flex; align-items: center; gap: 6px;
}}
.btn-primary {{ background: var(--accent); color: #fff; }}
.btn-primary:hover {{ background: var(--accent-hover); }}
.btn-success {{ background: var(--success); color: #fff; }}
.btn-success:hover {{ opacity: 0.9; }}
.btn-danger {{ background: var(--danger); color: #fff; }}
.btn-danger:hover {{ opacity: 0.9; }}
.btn-outline {{
  background: transparent; color: var(--text-secondary);
  border: 1px solid var(--border);
}}
.btn-outline:hover {{ background: var(--bg-hover); color: var(--text-primary); }}
.btn-sm {{ padding: 5px 10px; font-size: 12px; }}
.btn-lg {{ padding: 12px 24px; font-size: 15px; }}
.btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}

/* Forms */
.form-group {{ margin-bottom: 16px; }}
.form-group label {{
  display: block; font-size: 12px; font-weight: 600;
  color: var(--text-secondary); margin-bottom: 6px;
  text-transform: uppercase; letter-spacing: 0.5px;
}}
.form-group input, .form-group select, .form-group textarea {{
  width: 100%; padding: 9px 12px; border-radius: 8px;
  border: 1px solid var(--border); background: var(--bg-input);
  color: var(--text-primary); font-size: 14px; outline: none;
  transition: border 0.2s; font-family: inherit;
}}
.form-group input:focus, .form-group select:focus, .form-group textarea:focus {{
  border-color: var(--accent);
}}
.form-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
.form-row-3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }}

/* Tables */
.table-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; }}
th {{
  text-align: left; font-size: 11px; font-weight: 600;
  color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px;
  padding: 10px 12px; border-bottom: 1px solid var(--border);
}}
td {{ padding: 10px 12px; border-bottom: 1px solid rgba(51,65,85,0.5); font-size: 13px; }}
tr:hover td {{ background: rgba(15,23,42,0.5); }}
tr {{ cursor: pointer; transition: background 0.1s; }}

/* Tags & Badges */
.badge {{
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  font-size: 11px; font-weight: 600;
}}
.badge-active {{ background: rgba(34,197,94,0.15); color: var(--success); }}
.badge-archived {{ background: rgba(148,163,184,0.15); color: var(--text-secondary); }}
.badge-low {{ background: rgba(245,158,11,0.15); color: var(--warning); }}

/* Search */
.search-bar {{
  display: flex; gap: 12px; margin-bottom: 20px; align-items: center; flex-wrap: wrap;
}}
.search-bar input {{
  flex: 1; min-width: 200px; padding: 9px 14px; border-radius: 8px;
  border: 1px solid var(--border); background: var(--bg-input);
  color: var(--text-primary); font-size: 14px; outline: none;
}}
.search-bar input:focus {{ border-color: var(--accent); }}
.search-bar select {{
  padding: 9px 12px; border-radius: 8px; border: 1px solid var(--border);
  background: var(--bg-input); color: var(--text-primary); font-size: 13px;
  outline: none;
}}

/* Scanner */
.scanner-container {{
  display: flex; flex-direction: column; align-items: center; gap: 20px;
}}
#scanner-video {{
  width: 100%; max-width: 480px; border-radius: 12px;
  border: 2px solid var(--border); background: #000;
}}
.scanner-input-row {{
  display: flex; gap: 12px; width: 100%; max-width: 480px;
}}
.scanner-input-row input {{
  flex: 1; padding: 12px 16px; border-radius: 8px;
  border: 1px solid var(--border); background: var(--bg-input);
  color: var(--text-primary); font-size: 16px; outline: none;
  font-family: 'Courier New', monospace;
}}
.scanner-input-row input:focus {{ border-color: var(--accent); }}
.scan-result {{
  width: 100%; max-width: 600px; margin-top: 12px;
}}

/* Modal */
.modal-overlay {{
  position: fixed; inset: 0; background: rgba(0,0,0,0.6);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000; padding: 20px;
}}
.modal {{
  background: var(--bg-card); border-radius: 12px; padding: 28px;
  width: 100%; max-width: 600px; max-height: 80vh; overflow-y: auto;
  box-shadow: 0 8px 32px rgba(0,0,0,0.4);
}}
.modal h2 {{ font-size: 18px; margin-bottom: 20px; }}
.modal-actions {{ display: flex; gap: 12px; justify-content: flex-end; margin-top: 20px; }}

/* Toast */
.toast-container {{
  position: fixed; top: 20px; right: 20px; z-index: 2000;
  display: flex; flex-direction: column; gap: 8px;
}}
.toast {{
  padding: 12px 20px; border-radius: 8px; font-size: 13px; font-weight: 500;
  animation: slideIn 0.3s ease; min-width: 280px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.3);
}}
.toast-success {{ background: var(--success-bg); color: #86efac; border: 1px solid #166534; }}
.toast-error {{ background: var(--danger-bg); color: #fca5a5; border: 1px solid #7f1d1d; }}
.toast-warning {{ background: var(--warning-bg); color: #fcd34d; border: 1px solid #78350f; }}
@keyframes slideIn {{ from {{ transform: translateX(100%); opacity: 0; }} to {{ transform: translateX(0); opacity: 1; }} }}

/* Empty state */
.empty-state {{
  text-align: center; padding: 60px 20px; color: var(--text-muted);
}}
.empty-state h3 {{ font-size: 18px; color: var(--text-secondary); margin-bottom: 8px; }}
.empty-state p {{ font-size: 14px; margin-bottom: 20px; }}

/* Loading */
.loading {{ text-align: center; padding: 40px; color: var(--text-muted); }}

/* Item detail */
.detail-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }}
.detail-header h1 {{ font-size: 22px; }}
.detail-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
.detail-field {{ padding: 12px; background: var(--bg-primary); border-radius: 8px; }}
.detail-field .field-label {{ font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }}
.detail-field .field-value {{ font-size: 15px; color: var(--text-primary); }}
.barcode-preview {{ text-align: center; padding: 20px; background: #fff; border-radius: 8px; margin: 16px 0; }}
.barcode-preview img {{ max-width: 100%; height: auto; }}

/* Transaction history */
.txn-table td {{ font-size: 12px; padding: 8px 10px; }}
.txn-positive {{ color: var(--success); font-weight: 600; }}
.txn-negative {{ color: var(--danger); font-weight: 600; }}

/* Quantity adjuster */
.qty-adjuster {{
  display: flex; align-items: center; gap: 8px;
}}
.qty-adjuster button {{
  width: 36px; height: 36px; border-radius: 8px; border: 1px solid var(--border);
  background: var(--bg-input); color: var(--text-primary); font-size: 18px;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
}}
.qty-adjuster button:hover {{ background: var(--bg-hover); }}
.qty-adjuster .qty-display {{
  font-size: 20px; font-weight: 700; min-width: 60px; text-align: center;
}}

/* Responsive */
@media (max-width: 768px) {{
  .sidebar {{ display: none; }}
  .main-content {{ padding: 16px; }}
  .form-row, .form-row-3 {{ grid-template-columns: 1fr; }}
  .detail-grid {{ grid-template-columns: 1fr; }}
  .stats-grid {{ grid-template-columns: 1fr 1fr; }}
  .page-header {{ flex-direction: column; gap: 12px; align-items: flex-start; }}
}}
/* Mobile nav */
.mobile-nav {{
  display: none; position: fixed; bottom: 0; left: 0; right: 0;
  background: var(--bg-card); border-top: 1px solid var(--border);
  padding: 8px 0; z-index: 100;
}}
.mobile-nav .nav-items {{
  display: flex; justify-content: space-around;
}}
.mobile-nav a {{
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  padding: 6px 12px; color: var(--text-muted); font-size: 10px;
  text-decoration: none; font-weight: 600;
}}
.mobile-nav a.active {{ color: var(--accent); }}
.mobile-nav a .nav-icon {{ font-size: 18px; }}
@media (max-width: 768px) {{
  .mobile-nav {{ display: block; }}
  .main-content {{ padding-bottom: 80px; }}
}}
</style>
</head>
<body>
<div class="app-shell">
  <!-- Sidebar -->
  <aside class="sidebar">
    <div class="brand">Barcode Buddy<small>Inventory System</small></div>
    <nav>
      <a href="#" data-page="dashboard" class="active" onclick="navigateTo('dashboard')">
        <span>&#9632;</span> Dashboard
      </a>
      <a href="#" data-page="inventory" onclick="navigateTo('inventory')">
        <span>&#9776;</span> Inventory
      </a>
      <a href="#" data-page="scanner" onclick="navigateTo('scanner')">
        <span>&#9212;</span> Scanner
      </a>
      <a href="#" data-page="add-item" onclick="navigateTo('add-item')">
        <span>&#43;</span> Add Item
      </a>
      <a href="#" data-page="import" onclick="navigateTo('import')">
        <span>&#8593;</span> Import / Export
      </a>
      <a href="/" data-page="stats">
        <span>&#9881;</span> Processing Stats
      </a>
      <a href="/admin" data-page="admin">
        <span>&#9881;</span> Admin
      </a>
    </nav>
    <div class="user-section">
      <div class="user-name">{user_name}</div>
      <div class="user-role role-{user_role}">{user_role}</div>
      <div style="margin-top:10px"><a href="#" onclick="logout()" style="font-size:12px;color:var(--text-muted)">Sign out</a></div>
    </div>
  </aside>

  <!-- Main Content -->
  <main class="main-content" id="main-content">
    <div class="loading">Loading...</div>
  </main>
</div>

<!-- Mobile Nav -->
<div class="mobile-nav">
  <div class="nav-items">
    <a href="#" data-page="dashboard" class="active" onclick="navigateTo('dashboard')">
      <span class="nav-icon">&#9632;</span>Home
    </a>
    <a href="#" data-page="inventory" onclick="navigateTo('inventory')">
      <span class="nav-icon">&#9776;</span>Items
    </a>
    <a href="#" data-page="scanner" onclick="navigateTo('scanner')">
      <span class="nav-icon">&#9212;</span>Scan
    </a>
    <a href="#" data-page="add-item" onclick="navigateTo('add-item')">
      <span class="nav-icon">&#43;</span>Add
    </a>
  </div>
</div>

<!-- Toast container -->
<div class="toast-container" id="toast-container"></div>

<!-- Modal container -->
<div id="modal-root"></div>

<script>
// --- State ---
let currentPage = 'dashboard';
let inventoryCache = [];
let summaryCache = null;
let categoriesCache = [];
let locationsCache = [];
let selectedItems = new Set();
let cameraStream = null;

// --- API helpers ---
async function api(path, options = {{}}) {{
  const resp = await fetch(path, {{
    headers: {{'Content-Type': 'application/json', ...options.headers}},
    ...options,
  }});
  if (resp.status === 307) {{
    window.location.href = '/auth/login';
    return null;
  }}
  const data = await resp.json();
  if (!resp.ok) {{
    throw new Error(data.error || `Request failed (${{resp.status}})`);
  }}
  return data;
}}

async function apiUpload(path, formData) {{
  const resp = await fetch(path, {{ method: 'POST', body: formData }});
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.error || 'Upload failed');
  return data;
}}

// --- Toast ---
function toast(message, type = 'success') {{
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast toast-${{type}}`;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}}

// --- Navigation ---
function navigateTo(page, params = {{}}) {{
  currentPage = page;
  document.querySelectorAll('[data-page]').forEach(a => {{
    a.classList.toggle('active', a.dataset.page === page);
  }});
  renderPage(page, params);
  stopCamera();
}}

function renderPage(page, params = {{}}) {{
  const main = document.getElementById('main-content');
  switch(page) {{
    case 'dashboard': renderDashboard(main); break;
    case 'inventory': renderInventory(main); break;
    case 'scanner': renderScanner(main); break;
    case 'add-item': renderAddItem(main); break;
    case 'import': renderImportExport(main); break;
    case 'item-detail': renderItemDetail(main, params.id); break;
    case 'edit-item': renderEditItem(main, params.id); break;
    default: renderDashboard(main);
  }}
}}

// --- Dashboard ---
async function renderDashboard(el) {{
  el.innerHTML = '<div class="loading">Loading dashboard...</div>';
  try {{
    const summary = await api('/api/inventory/summary');
    summaryCache = summary;
    const lowStockRows = (summary.low_stock_items || []).map(i => `
      <tr onclick="navigateTo('item-detail', {{id:'${{i.id}}'}})">
        <td>${{esc(i.name)}}</td><td>${{esc(i.sku)}}</td>
        <td><span class="badge badge-low">${{i.quantity}} / ${{i.min_quantity}}</span></td>
        <td>${{esc(i.location)}}</td>
      </tr>
    `).join('');

    const catEntries = Object.entries(summary.categories || {{}}).sort((a,b) => b[1]-a[1]);
    const locEntries = Object.entries(summary.locations || {{}}).sort((a,b) => b[1]-a[1]);

    el.innerHTML = `
      <div class="page-header">
        <h1>Dashboard</h1>
        <div style="display:flex;gap:8px">
          <button class="btn btn-primary" onclick="navigateTo('add-item')">+ New Item</button>
          <button class="btn btn-outline" onclick="navigateTo('scanner')">Scan</button>
        </div>
      </div>
      <div class="stats-grid">
        <div class="stat-card"><div class="value">${{summary.total_items}}</div><div class="label">Total Items</div></div>
        <div class="stat-card"><div class="value">${{summary.total_quantity.toLocaleString()}}</div><div class="label">Total Units</div></div>
        <div class="stat-card"><div class="value">${{summary.total_value > 0 ? '$' + summary.total_value.toLocaleString(undefined, {{minimumFractionDigits:2}}) : '-'}}</div><div class="label">Total Value</div></div>
        <div class="stat-card"><div class="value" style="color:${{summary.low_stock_count > 0 ? 'var(--warning)' : 'var(--success)'}}">${{summary.low_stock_count}}</div><div class="label">Low Stock Alerts</div></div>
      </div>
      ${{summary.low_stock_count > 0 ? `
      <div class="card">
        <h3 style="font-size:14px;color:var(--warning);margin-bottom:12px">Low Stock Items</h3>
        <div class="table-wrap"><table>
          <thead><tr><th>Name</th><th>SKU</th><th>Qty / Min</th><th>Location</th></tr></thead>
          <tbody>${{lowStockRows}}</tbody>
        </table></div>
      </div>` : ''}}
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
        <div class="card">
          <h3 style="font-size:14px;color:var(--text-secondary);margin-bottom:12px">By Category</h3>
          ${{catEntries.length ? catEntries.map(([cat,cnt]) => `
            <div style="display:flex;justify-content:space-between;padding:6px 0;font-size:13px;border-bottom:1px solid var(--border)">
              <span>${{esc(cat)}}</span><span style="color:var(--text-muted)">${{cnt}}</span>
            </div>`).join('') : '<div class="empty-state" style="padding:20px"><p>No categories yet</p></div>'}}
        </div>
        <div class="card">
          <h3 style="font-size:14px;color:var(--text-secondary);margin-bottom:12px">By Location</h3>
          ${{locEntries.length ? locEntries.map(([loc,cnt]) => `
            <div style="display:flex;justify-content:space-between;padding:6px 0;font-size:13px;border-bottom:1px solid var(--border)">
              <span>${{esc(loc)}}</span><span style="color:var(--text-muted)">${{cnt}}</span>
            </div>`).join('') : '<div class="empty-state" style="padding:20px"><p>No locations yet</p></div>'}}
        </div>
      </div>
    `;
  }} catch (e) {{
    el.innerHTML = `<div class="empty-state"><h3>Error</h3><p>${{esc(e.message)}}</p></div>`;
  }}
}}

// --- Inventory List ---
async function renderInventory(el, opts = {{}}) {{
  el.innerHTML = '<div class="loading">Loading inventory...</div>';
  try {{
    const [cats, locs] = await Promise.all([
      api('/api/inventory/categories'),
      api('/api/inventory/locations'),
    ]);
    categoriesCache = cats.categories || [];
    locationsCache = locs.locations || [];

    el.innerHTML = `
      <div class="page-header">
        <h1>Inventory</h1>
        <div style="display:flex;gap:8px">
          <button class="btn btn-sm btn-outline" id="bulk-actions-btn" style="display:none" onclick="showBulkActions()">Bulk Actions</button>
          <button class="btn btn-primary" onclick="navigateTo('add-item')">+ New Item</button>
        </div>
      </div>
      <div class="search-bar">
        <input type="text" id="search-input" placeholder="Search items by name, SKU, barcode..." value="${{esc(opts.q || '')}}" onkeyup="if(event.key==='Enter')searchInventory()">
        <select id="filter-category" onchange="searchInventory()">
          <option value="">All Categories</option>
          ${{categoriesCache.map(c => `<option value="${{esc(c)}}">${{esc(c)}}</option>`).join('')}}
        </select>
        <select id="filter-location" onchange="searchInventory()">
          <option value="">All Locations</option>
          ${{locationsCache.map(l => `<option value="${{esc(l)}}">${{esc(l)}}</option>`).join('')}}
        </select>
        <select id="filter-status" onchange="searchInventory()">
          <option value="active">Active</option>
          <option value="archived">Archived</option>
          <option value="">All</option>
        </select>
        <button class="btn btn-outline btn-sm" onclick="searchInventory()">Search</button>
      </div>
      <div class="card">
        <div class="table-wrap">
          <table>
            <thead><tr>
              <th style="width:30px"><input type="checkbox" id="select-all" onchange="toggleSelectAll(this)"></th>
              <th>Name</th><th>SKU</th><th>Qty</th><th>Location</th><th>Category</th><th>Status</th><th>Updated</th>
            </tr></thead>
            <tbody id="inventory-body"><tr><td colspan="8" class="loading">Loading...</td></tr></tbody>
          </table>
        </div>
        <div id="pagination" style="display:flex;justify-content:center;gap:8px;margin-top:16px"></div>
      </div>
    `;
    searchInventory();
  }} catch (e) {{
    el.innerHTML = `<div class="empty-state"><h3>Error</h3><p>${{esc(e.message)}}</p></div>`;
  }}
}}

let currentInventoryPage = 1;
async function searchInventory(page = 1) {{
  currentInventoryPage = page;
  const q = document.getElementById('search-input')?.value || '';
  const category = document.getElementById('filter-category')?.value || '';
  const location = document.getElementById('filter-location')?.value || '';
  const status = document.getElementById('filter-status')?.value || 'active';
  selectedItems.clear();
  updateBulkButton();

  try {{
    const data = await api(`/api/inventory?q=${{encodeURIComponent(q)}}&category=${{encodeURIComponent(category)}}&status=${{encodeURIComponent(status)}}&limit=50&offset=${{(page-1)*50}}`);
    inventoryCache = data.items;
    const tbody = document.getElementById('inventory-body');

    if (data.items.length === 0) {{
      tbody.innerHTML = '<tr><td colspan="8" class="empty-state"><p>No items found</p></td></tr>';
    }} else {{
      tbody.innerHTML = data.items.map(item => `
        <tr onclick="navigateTo('item-detail', {{id:'${{item.id}}'}})">
          <td onclick="event.stopPropagation()"><input type="checkbox" data-id="${{item.id}}" onchange="toggleItemSelect(this)"></td>
          <td style="font-weight:600">${{esc(item.name)}}</td>
          <td style="font-family:monospace;font-size:12px;color:var(--text-muted)">${{esc(item.sku)}}</td>
          <td>
            <span style="font-weight:600;${{item.min_quantity > 0 && item.quantity <= item.min_quantity ? 'color:var(--warning)' : ''}}">${{item.quantity}}</span>
            <span style="color:var(--text-muted);font-size:11px"> ${{esc(item.unit)}}</span>
          </td>
          <td>${{esc(item.location) || '-'}}</td>
          <td>${{esc(item.category) || '-'}}</td>
          <td><span class="badge badge-${{item.status}}">${{item.status}}</span></td>
          <td style="color:var(--text-muted);font-size:12px">${{formatDate(item.updated_at)}}</td>
        </tr>
      `).join('');
    }}

    // Pagination
    const pag = document.getElementById('pagination');
    if (data.pages > 1) {{
      let html = '';
      for (let p = 1; p <= data.pages; p++) {{
        html += `<button class="btn btn-sm ${{p === page ? 'btn-primary' : 'btn-outline'}}" onclick="searchInventory(${{p}})">${{p}}</button>`;
      }}
      pag.innerHTML = html;
    }} else {{
      pag.innerHTML = '';
    }}
  }} catch (e) {{
    document.getElementById('inventory-body').innerHTML = `<tr><td colspan="8">${{esc(e.message)}}</td></tr>`;
  }}
}}

function toggleSelectAll(cb) {{
  document.querySelectorAll('#inventory-body input[type=checkbox]').forEach(el => {{
    el.checked = cb.checked;
    if (cb.checked) selectedItems.add(el.dataset.id);
    else selectedItems.delete(el.dataset.id);
  }});
  updateBulkButton();
}}

function toggleItemSelect(cb) {{
  if (cb.checked) selectedItems.add(cb.dataset.id);
  else selectedItems.delete(cb.dataset.id);
  updateBulkButton();
}}

function updateBulkButton() {{
  const btn = document.getElementById('bulk-actions-btn');
  if (btn) btn.style.display = selectedItems.size > 0 ? 'inline-flex' : 'none';
}}

function showBulkActions() {{
  const ids = Array.from(selectedItems);
  showModal(`
    <h2>Bulk Actions (${{ids.length}} items)</h2>
    <div class="form-group">
      <label>Update Location</label>
      <input type="text" id="bulk-location" placeholder="Leave blank to skip">
    </div>
    <div class="form-group">
      <label>Update Category</label>
      <input type="text" id="bulk-category" placeholder="Leave blank to skip">
    </div>
    <div class="form-group">
      <label>Update Status</label>
      <select id="bulk-status"><option value="">No change</option><option value="active">Active</option><option value="archived">Archived</option></select>
    </div>
    <div class="modal-actions">
      <button class="btn btn-danger" onclick="bulkDelete()">Delete All</button>
      <button class="btn btn-outline" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="bulkUpdate()">Update</button>
    </div>
  `);
}}

async function bulkUpdate() {{
  const ids = Array.from(selectedItems);
  const body = {{ item_ids: ids }};
  const loc = document.getElementById('bulk-location').value.trim();
  const cat = document.getElementById('bulk-category').value.trim();
  const stat = document.getElementById('bulk-status').value;
  if (loc) body.location = loc;
  if (cat) body.category = cat;
  if (stat) body.status = stat;
  try {{
    const r = await api('/api/inventory/bulk/update', {{ method: 'POST', body: JSON.stringify(body) }});
    toast(`Updated ${{r.updated}} items`);
    closeModal();
    searchInventory(currentInventoryPage);
  }} catch (e) {{ toast(e.message, 'error'); }}
}}

async function bulkDelete() {{
  if (!confirm(`Delete ${{selectedItems.size}} items? This cannot be undone.`)) return;
  try {{
    const r = await api('/api/inventory/bulk/delete', {{ method: 'POST', body: JSON.stringify({{ item_ids: Array.from(selectedItems) }}) }});
    toast(`Deleted ${{r.deleted}} items`);
    closeModal();
    searchInventory(currentInventoryPage);
  }} catch (e) {{ toast(e.message, 'error'); }}
}}

// --- Scanner ---
function renderScanner(el) {{
  el.innerHTML = `
    <div class="page-header"><h1>Barcode Scanner</h1></div>
    <div class="scanner-container">
      <video id="scanner-video" autoplay playsinline style="display:none"></video>
      <div style="display:flex;gap:8px;margin-bottom:8px">
        <button class="btn btn-primary" id="camera-btn" onclick="toggleCamera()">Start Camera</button>
        <button class="btn btn-outline" id="stop-camera-btn" style="display:none" onclick="stopCamera()">Stop Camera</button>
      </div>
      <div class="scanner-input-row">
        <input type="text" id="barcode-input" placeholder="Type or scan barcode..." autofocus
               onkeyup="if(event.key==='Enter')scanBarcode()">
        <button class="btn btn-success" onclick="scanBarcode()">Lookup</button>
      </div>
      <div class="scan-result" id="scan-result"></div>
    </div>
  `;
  setTimeout(() => document.getElementById('barcode-input')?.focus(), 100);
}}

async function scanBarcode() {{
  const input = document.getElementById('barcode-input');
  const value = input.value.trim();
  if (!value) return;
  const resultEl = document.getElementById('scan-result');
  resultEl.innerHTML = '<div class="loading">Looking up...</div>';
  try {{
    const data = await api(`/api/scan/lookup?code=${{encodeURIComponent(value)}}`);
    const item = data.item;
    resultEl.innerHTML = `
      <div class="card" style="border-left:4px solid var(--success)">
        <div style="display:flex;justify-content:space-between;align-items:flex-start">
          <div>
            <h3 style="font-size:18px;margin-bottom:4px">${{esc(item.name)}}</h3>
            <div style="font-size:12px;color:var(--text-muted)">SKU: ${{esc(item.sku)}} | Barcode: ${{esc(item.barcode_value)}}</div>
          </div>
          <button class="btn btn-sm btn-outline" onclick="navigateTo('item-detail', {{id:'${{item.id}}'}})">View Details</button>
        </div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:16px">
          <div><div style="font-size:11px;color:var(--text-muted);text-transform:uppercase">Quantity</div><div style="font-size:20px;font-weight:700">${{item.quantity}} <span style="font-size:12px;color:var(--text-muted)">${{esc(item.unit)}}</span></div></div>
          <div><div style="font-size:11px;color:var(--text-muted);text-transform:uppercase">Location</div><div style="font-size:14px">${{esc(item.location) || '-'}}</div></div>
          <div><div style="font-size:11px;color:var(--text-muted);text-transform:uppercase">Category</div><div style="font-size:14px">${{esc(item.category) || '-'}}</div></div>
          <div><div style="font-size:11px;color:var(--text-muted);text-transform:uppercase">Status</div><div><span class="badge badge-${{item.status}}">${{item.status}}</span></div></div>
        </div>
        <div style="display:flex;gap:8px;margin-top:16px">
          <button class="btn btn-sm btn-success" onclick="quickAdjust('${{item.id}}', 1)">+ Receive</button>
          <button class="btn btn-sm btn-danger" onclick="quickAdjust('${{item.id}}', -1)">- Issue</button>
          <button class="btn btn-sm btn-outline" onclick="navigateTo('edit-item', {{id:'${{item.id}}'}})">Edit</button>
        </div>
      </div>
    `;
    input.value = '';
    input.focus();
  }} catch (e) {{
    resultEl.innerHTML = `
      <div class="card" style="border-left:4px solid var(--danger)">
        <h3 style="color:var(--danger);margin-bottom:4px">Not Found</h3>
        <p style="font-size:13px;color:var(--text-secondary)">No active item matches barcode: <strong>${{esc(value)}}</strong></p>
        <button class="btn btn-sm btn-primary" style="margin-top:12px" onclick="navigateTo('add-item')">Create New Item</button>
      </div>
    `;
    input.select();
  }}
}}

async function quickAdjust(itemId, change) {{
  const reason = change > 0 ? 'received' : 'sold';
  try {{
    const data = await api(`/api/inventory/${{itemId}}/adjust`, {{
      method: 'POST',
      body: JSON.stringify({{ quantity_change: change, reason: reason, notes: 'Quick scan adjustment' }})
    }});
    toast(`${{data.item.name}}: qty now ${{data.item.quantity}}`);
    scanBarcode.__lastItem = data.item;
    // Re-render the scan result
    const resultEl = document.getElementById('scan-result');
    const item = data.item;
    resultEl.querySelector('.stat-card .value, div[style*="font-size:20px"]').textContent = item.quantity + ' ';
  }} catch (e) {{
    toast(e.message, 'error');
  }}
}}

// Camera support via MediaDevices API
async function toggleCamera() {{
  const video = document.getElementById('scanner-video');
  const camBtn = document.getElementById('camera-btn');
  const stopBtn = document.getElementById('stop-camera-btn');
  try {{
    cameraStream = await navigator.mediaDevices.getUserMedia({{
      video: {{ facingMode: 'environment', width: {{ ideal: 1280 }}, height: {{ ideal: 720 }} }}
    }});
    video.srcObject = cameraStream;
    video.style.display = 'block';
    camBtn.style.display = 'none';
    stopBtn.style.display = 'inline-flex';
    // Use BarcodeDetector API if available
    if ('BarcodeDetector' in window) {{
      const detector = new BarcodeDetector({{ formats: ['qr_code', 'ean_13', 'ean_8', 'code_128', 'code_39', 'upc_a', 'upc_e', 'codabar', 'data_matrix', 'itf'] }});
      const scanLoop = async () => {{
        if (!cameraStream) return;
        try {{
          const barcodes = await detector.detect(video);
          if (barcodes.length > 0) {{
            const value = barcodes[0].rawValue;
            document.getElementById('barcode-input').value = value;
            scanBarcode();
            stopCamera();
            return;
          }}
        }} catch(_) {{}}
        if (cameraStream) requestAnimationFrame(scanLoop);
      }};
      scanLoop();
    }}
  }} catch (e) {{
    toast('Camera access denied or not available', 'error');
  }}
}}

function stopCamera() {{
  if (cameraStream) {{
    cameraStream.getTracks().forEach(t => t.stop());
    cameraStream = null;
  }}
  const video = document.getElementById('scanner-video');
  if (video) {{ video.style.display = 'none'; video.srcObject = null; }}
  const camBtn = document.getElementById('camera-btn');
  const stopBtn = document.getElementById('stop-camera-btn');
  if (camBtn) camBtn.style.display = 'inline-flex';
  if (stopBtn) stopBtn.style.display = 'none';
}}

// --- Add Item ---
async function renderAddItem(el) {{
  const [cats, locs, formats] = await Promise.all([
    api('/api/inventory/categories').catch(() => ({{ categories: [] }})),
    api('/api/inventory/locations').catch(() => ({{ locations: [] }})),
    api('/api/barcode/formats').catch(() => ({{ formats: ['Code128', 'QRCode'] }})),
  ]);

  el.innerHTML = `
    <div class="page-header"><h1>Add New Item</h1></div>
    <div class="card">
      <form onsubmit="event.preventDefault(); createItem()">
        <div class="form-row">
          <div class="form-group"><label>Item Name *</label><input type="text" id="item-name" required></div>
          <div class="form-group"><label>SKU *</label><input type="text" id="item-sku" required></div>
        </div>
        <div class="form-group"><label>Description</label><textarea id="item-description" rows="2"></textarea></div>
        <div class="form-row-3">
          <div class="form-group"><label>Quantity</label><input type="number" id="item-quantity" value="0" min="0"></div>
          <div class="form-group"><label>Unit</label><input type="text" id="item-unit" value="each" list="unit-list">
            <datalist id="unit-list"><option value="each"><option value="box"><option value="case"><option value="pallet"><option value="kg"><option value="lb"><option value="roll"><option value="sheet"></datalist>
          </div>
          <div class="form-group"><label>Min Quantity (Alert)</label><input type="number" id="item-min-qty" value="0" min="0"></div>
        </div>
        <div class="form-row">
          <div class="form-group"><label>Location</label><input type="text" id="item-location" list="loc-list">
            <datalist id="loc-list">${{locs.locations.map(l => `<option value="${{esc(l)}}">`).join('')}}</datalist>
          </div>
          <div class="form-group"><label>Category</label><input type="text" id="item-category" list="cat-list">
            <datalist id="cat-list">${{cats.categories.map(c => `<option value="${{esc(c)}}">`).join('')}}</datalist>
          </div>
        </div>
        <div class="form-row">
          <div class="form-group"><label>Barcode Type</label>
            <select id="item-barcode-type">
              ${{formats.formats.map(f => `<option value="${{f}}" ${{f==='Code128'?'selected':''}}>${{f}}</option>`).join('')}}
            </select>
          </div>
          <div class="form-group"><label>Barcode Value (auto-generated if blank)</label><input type="text" id="item-barcode-value" placeholder="Leave blank for auto-generated"></div>
        </div>
        <div class="form-row">
          <div class="form-group"><label>Cost per Unit ($)</label><input type="number" id="item-cost" step="0.01" min="0"></div>
          <div class="form-group"><label>Tags (comma-separated)</label><input type="text" id="item-tags" placeholder="tag1, tag2"></div>
        </div>
        <div class="form-group"><label>Notes</label><textarea id="item-notes" rows="2"></textarea></div>
        <div style="display:flex;gap:12px;margin-top:8px">
          <button type="submit" class="btn btn-primary btn-lg">Create Item</button>
          <button type="button" class="btn btn-outline btn-lg" onclick="navigateTo('inventory')">Cancel</button>
        </div>
      </form>
    </div>
  `;
}}

async function createItem() {{
  const body = {{
    name: document.getElementById('item-name').value.trim(),
    sku: document.getElementById('item-sku').value.trim(),
    description: document.getElementById('item-description').value.trim(),
    quantity: parseInt(document.getElementById('item-quantity').value) || 0,
    unit: document.getElementById('item-unit').value.trim() || 'each',
    min_quantity: parseInt(document.getElementById('item-min-qty').value) || 0,
    location: document.getElementById('item-location').value.trim(),
    category: document.getElementById('item-category').value.trim(),
    barcode_type: document.getElementById('item-barcode-type').value,
    barcode_value: document.getElementById('item-barcode-value').value.trim(),
    cost: parseFloat(document.getElementById('item-cost').value) || null,
    tags: document.getElementById('item-tags').value.trim(),
    notes: document.getElementById('item-notes').value.trim(),
  }};
  try {{
    const data = await api('/api/inventory', {{ method: 'POST', body: JSON.stringify(body) }});
    toast(`Created: ${{data.item.name}}`);
    navigateTo('item-detail', {{ id: data.item.id }});
  }} catch (e) {{
    toast(e.message, 'error');
  }}
}}

// --- Item Detail ---
async function renderItemDetail(el, itemId) {{
  el.innerHTML = '<div class="loading">Loading item...</div>';
  try {{
    const data = await api(`/api/inventory/${{itemId}}`);
    const item = data.item;
    const txns = data.transactions || [];
    const isLow = item.min_quantity > 0 && item.quantity <= item.min_quantity;

    const txnRows = txns.map(t => `
      <tr>
        <td style="color:var(--text-muted)">${{formatDateTime(t.created_at)}}</td>
        <td class="${{t.quantity_change >= 0 ? 'txn-positive' : 'txn-negative'}}">${{t.quantity_change >= 0 ? '+' : ''}}${{t.quantity_change}}</td>
        <td>${{t.quantity_after}}</td>
        <td>${{esc(t.reason)}}</td>
        <td style="color:var(--text-muted)">${{esc(t.notes)}}</td>
      </tr>
    `).join('');

    el.innerHTML = `
      <div class="detail-header">
        <div>
          <div style="display:flex;align-items:center;gap:12px">
            <h1>${{esc(item.name)}}</h1>
            <span class="badge badge-${{item.status}}">${{item.status}}</span>
            ${{isLow ? '<span class="badge badge-low">LOW STOCK</span>' : ''}}
          </div>
          <div style="font-size:13px;color:var(--text-muted);margin-top:4px">SKU: ${{esc(item.sku)}} | Created: ${{formatDate(item.created_at)}}</div>
        </div>
        <div style="display:flex;gap:8px">
          <button class="btn btn-outline btn-sm" onclick="navigateTo('edit-item', {{id:'${{item.id}}'}})">Edit</button>
          <button class="btn btn-danger btn-sm" onclick="deleteItem('${{item.id}}','${{esc(item.name)}}')">Delete</button>
          <button class="btn btn-outline btn-sm" onclick="navigateTo('inventory')">Back</button>
        </div>
      </div>

      <div class="detail-grid">
        <div class="detail-field"><div class="field-label">Quantity</div>
          <div style="display:flex;align-items:center;gap:16px">
            <div class="field-value" style="font-size:28px;font-weight:700;${{isLow?'color:var(--warning)':''}}">${{item.quantity}} <span style="font-size:14px;color:var(--text-muted)">${{esc(item.unit)}}</span></div>
            <div class="qty-adjuster">
              <button onclick="adjustAndRefresh('${{item.id}}',-1,'sold')">-</button>
              <button onclick="adjustAndRefresh('${{item.id}}',1,'received')">+</button>
            </div>
          </div>
          ${{item.min_quantity > 0 ? `<div style="font-size:11px;color:var(--text-muted);margin-top:4px">Min: ${{item.min_quantity}}</div>` : ''}}
        </div>
        <div class="detail-field"><div class="field-label">Location</div><div class="field-value">${{esc(item.location) || '-'}}</div></div>
        <div class="detail-field"><div class="field-label">Category</div><div class="field-value">${{esc(item.category) || '-'}}</div></div>
        <div class="detail-field"><div class="field-label">Cost</div><div class="field-value">${{item.cost != null ? '$' + item.cost.toFixed(2) : '-'}}</div></div>
        <div class="detail-field" style="grid-column:span 2"><div class="field-label">Description</div><div class="field-value">${{esc(item.description) || '-'}}</div></div>
        <div class="detail-field"><div class="field-label">Tags</div><div class="field-value">${{esc(item.tags) || '-'}}</div></div>
        <div class="detail-field"><div class="field-label">Notes</div><div class="field-value">${{esc(item.notes) || '-'}}</div></div>
      </div>

      <div class="card" style="margin-top:20px">
        <h3 style="font-size:14px;color:var(--text-secondary);margin-bottom:12px">Barcode</h3>
        <div style="display:flex;align-items:center;gap:20px;flex-wrap:wrap">
          <div class="barcode-preview">
            <img src="/api/inventory/${{item.id}}/barcode.png?scale=5" alt="Barcode" onerror="this.parentElement.innerHTML='<p style=color:#666>Could not render barcode</p>'">
          </div>
          <div>
            <div style="font-family:monospace;font-size:16px;margin-bottom:4px">${{esc(item.barcode_value)}}</div>
            <div style="font-size:12px;color:var(--text-muted)">Type: ${{esc(item.barcode_type)}}</div>
            <a href="/api/inventory/${{item.id}}/barcode.png?scale=8" download="${{esc(item.sku)}}_barcode.png" class="btn btn-sm btn-outline" style="margin-top:8px">Download PNG</a>
          </div>
        </div>
      </div>

      <div class="card" style="margin-top:20px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <h3 style="font-size:14px;color:var(--text-secondary)">Quantity History</h3>
          <button class="btn btn-sm btn-outline" onclick="showAdjustModal('${{item.id}}')">Adjust Quantity</button>
        </div>
        <div class="table-wrap">
          <table class="txn-table">
            <thead><tr><th>Date</th><th>Change</th><th>After</th><th>Reason</th><th>Notes</th></tr></thead>
            <tbody>${{txnRows || '<tr><td colspan="5" style="color:var(--text-muted);text-align:center;padding:20px">No transactions yet</td></tr>'}}</tbody>
          </table>
        </div>
      </div>
    `;
  }} catch (e) {{
    el.innerHTML = `<div class="empty-state"><h3>Item not found</h3><p>${{esc(e.message)}}</p><button class="btn btn-primary" onclick="navigateTo('inventory')">Back to Inventory</button></div>`;
  }}
}}

async function adjustAndRefresh(itemId, change, reason) {{
  try {{
    await api(`/api/inventory/${{itemId}}/adjust`, {{
      method: 'POST',
      body: JSON.stringify({{ quantity_change: change, reason: reason, notes: '' }})
    }});
    renderItemDetail(document.getElementById('main-content'), itemId);
  }} catch (e) {{ toast(e.message, 'error'); }}
}}

function showAdjustModal(itemId) {{
  showModal(`
    <h2>Adjust Quantity</h2>
    <div class="form-row">
      <div class="form-group"><label>Change (+/-)</label><input type="number" id="adj-change" value="1"></div>
      <div class="form-group"><label>Reason</label>
        <select id="adj-reason">
          <option value="received">Received</option>
          <option value="sold">Sold/Issued</option>
          <option value="adjusted">Adjustment</option>
          <option value="damaged">Damaged</option>
          <option value="returned">Returned</option>
        </select>
      </div>
    </div>
    <div class="form-group"><label>Notes</label><input type="text" id="adj-notes" placeholder="Optional"></div>
    <div class="modal-actions">
      <button class="btn btn-outline" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="submitAdjust('${{itemId}}')">Apply</button>
    </div>
  `);
}}

async function submitAdjust(itemId) {{
  const change = parseInt(document.getElementById('adj-change').value);
  const reason = document.getElementById('adj-reason').value;
  const notes = document.getElementById('adj-notes').value;
  if (isNaN(change) || change === 0) {{ toast('Enter a non-zero quantity', 'warning'); return; }}
  try {{
    await api(`/api/inventory/${{itemId}}/adjust`, {{
      method: 'POST',
      body: JSON.stringify({{ quantity_change: change, reason: reason, notes: notes }})
    }});
    toast('Quantity updated');
    closeModal();
    renderItemDetail(document.getElementById('main-content'), itemId);
  }} catch (e) {{ toast(e.message, 'error'); }}
}}

async function deleteItem(itemId, name) {{
  if (!confirm(`Delete "${{name}}"? This cannot be undone.`)) return;
  try {{
    await api(`/api/inventory/${{itemId}}`, {{ method: 'DELETE' }});
    toast('Item deleted');
    navigateTo('inventory');
  }} catch (e) {{ toast(e.message, 'error'); }}
}}

// --- Edit Item ---
async function renderEditItem(el, itemId) {{
  el.innerHTML = '<div class="loading">Loading...</div>';
  try {{
    const data = await api(`/api/inventory/${{itemId}}`);
    const item = data.item;
    const [cats, locs] = await Promise.all([
      api('/api/inventory/categories').catch(() => ({{ categories: [] }})),
      api('/api/inventory/locations').catch(() => ({{ locations: [] }})),
    ]);

    el.innerHTML = `
      <div class="page-header"><h1>Edit: ${{esc(item.name)}}</h1></div>
      <div class="card">
        <form onsubmit="event.preventDefault(); updateItem('${{item.id}}')">
          <div class="form-row">
            <div class="form-group"><label>Item Name *</label><input type="text" id="edit-name" value="${{esc(item.name)}}" required></div>
            <div class="form-group"><label>SKU *</label><input type="text" id="edit-sku" value="${{esc(item.sku)}}" required></div>
          </div>
          <div class="form-group"><label>Description</label><textarea id="edit-description" rows="2">${{esc(item.description)}}</textarea></div>
          <div class="form-row-3">
            <div class="form-group"><label>Quantity</label><input type="number" id="edit-quantity" value="${{item.quantity}}" min="0"></div>
            <div class="form-group"><label>Unit</label><input type="text" id="edit-unit" value="${{esc(item.unit)}}"></div>
            <div class="form-group"><label>Min Quantity</label><input type="number" id="edit-min-qty" value="${{item.min_quantity}}" min="0"></div>
          </div>
          <div class="form-row">
            <div class="form-group"><label>Location</label><input type="text" id="edit-location" value="${{esc(item.location)}}" list="edit-loc-list">
              <datalist id="edit-loc-list">${{locs.locations.map(l => `<option value="${{esc(l)}}">`).join('')}}</datalist>
            </div>
            <div class="form-group"><label>Category</label><input type="text" id="edit-category" value="${{esc(item.category)}}" list="edit-cat-list">
              <datalist id="edit-cat-list">${{cats.categories.map(c => `<option value="${{esc(c)}}">`).join('')}}</datalist>
            </div>
          </div>
          <div class="form-row">
            <div class="form-group"><label>Cost per Unit ($)</label><input type="number" id="edit-cost" value="${{item.cost != null ? item.cost : ''}}" step="0.01" min="0"></div>
            <div class="form-group"><label>Status</label>
              <select id="edit-status">
                <option value="active" ${{item.status==='active'?'selected':''}}>Active</option>
                <option value="archived" ${{item.status==='archived'?'selected':''}}>Archived</option>
              </select>
            </div>
          </div>
          <div class="form-group"><label>Tags</label><input type="text" id="edit-tags" value="${{esc(item.tags)}}"></div>
          <div class="form-group"><label>Notes</label><textarea id="edit-notes" rows="2">${{esc(item.notes)}}</textarea></div>
          <div style="display:flex;gap:12px;margin-top:8px">
            <button type="submit" class="btn btn-primary btn-lg">Save Changes</button>
            <button type="button" class="btn btn-outline btn-lg" onclick="navigateTo('item-detail', {{id:'${{item.id}}'}})">Cancel</button>
          </div>
        </form>
      </div>
    `;
  }} catch (e) {{
    el.innerHTML = `<div class="empty-state"><h3>Error</h3><p>${{esc(e.message)}}</p></div>`;
  }}
}}

async function updateItem(itemId) {{
  const body = {{
    name: document.getElementById('edit-name').value.trim(),
    sku: document.getElementById('edit-sku').value.trim(),
    description: document.getElementById('edit-description').value.trim(),
    quantity: parseInt(document.getElementById('edit-quantity').value) || 0,
    unit: document.getElementById('edit-unit').value.trim(),
    min_quantity: parseInt(document.getElementById('edit-min-qty').value) || 0,
    location: document.getElementById('edit-location').value.trim(),
    category: document.getElementById('edit-category').value.trim(),
    cost: parseFloat(document.getElementById('edit-cost').value) || null,
    status: document.getElementById('edit-status').value,
    tags: document.getElementById('edit-tags').value.trim(),
    notes: document.getElementById('edit-notes').value.trim(),
  }};
  try {{
    const data = await api(`/api/inventory/${{itemId}}`, {{ method: 'PUT', body: JSON.stringify(body) }});
    toast('Item updated');
    navigateTo('item-detail', {{ id: itemId }});
  }} catch (e) {{ toast(e.message, 'error'); }}
}}

// --- Import/Export ---
function renderImportExport(el) {{
  el.innerHTML = `
    <div class="page-header"><h1>Import & Export</h1></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
      <div class="card">
        <h3 style="font-size:16px;margin-bottom:16px">Import from CSV</h3>
        <p style="font-size:13px;color:var(--text-secondary);margin-bottom:16px">
          Upload a CSV file with columns: <strong>name</strong>, <strong>sku</strong>, quantity, unit, location, category, tags, notes, barcode_type, barcode_value, cost
        </p>
        <form id="import-form" onsubmit="event.preventDefault(); importCSV()">
          <div class="form-group">
            <input type="file" id="import-file" accept=".csv" required style="padding:8px">
          </div>
          <button type="submit" class="btn btn-primary">Import</button>
        </form>
        <div id="import-result" style="margin-top:16px"></div>
      </div>
      <div class="card">
        <h3 style="font-size:16px;margin-bottom:16px">Export to CSV</h3>
        <p style="font-size:13px;color:var(--text-secondary);margin-bottom:16px">
          Download all inventory items as a CSV file for backup or editing.
        </p>
        <a href="/api/inventory/export/csv" class="btn btn-primary" download>Download CSV</a>
        <div style="margin-top:24px;padding-top:20px;border-top:1px solid var(--border)">
          <h3 style="font-size:16px;margin-bottom:16px">CSV Template</h3>
          <p style="font-size:13px;color:var(--text-secondary);margin-bottom:12px">Download a blank template to get started.</p>
          <button class="btn btn-outline" onclick="downloadTemplate()">Download Template</button>
        </div>
      </div>
    </div>
  `;
}}

async function importCSV() {{
  const file = document.getElementById('import-file').files[0];
  if (!file) return;
  const formData = new FormData();
  formData.append('file', file);
  const resultEl = document.getElementById('import-result');
  resultEl.innerHTML = '<div class="loading">Importing...</div>';
  try {{
    const data = await apiUpload('/api/inventory/import/csv', formData);
    let html = `<div style="padding:12px;background:var(--success-bg);border-radius:8px;border:1px solid #166534">
      <strong style="color:#86efac">${{data.created}} items imported</strong>`;
    if (data.skipped > 0) {{
      html += `<br><span style="color:#fcd34d">${{data.skipped}} skipped</span>`;
    }}
    if (data.errors && data.errors.length > 0) {{
      html += '<div style="margin-top:8px;font-size:12px;color:var(--text-muted)">' +
        data.errors.map(e => esc(e)).join('<br>') + '</div>';
    }}
    html += '</div>';
    resultEl.innerHTML = html;
  }} catch (e) {{
    resultEl.innerHTML = `<div style="padding:12px;background:var(--danger-bg);border-radius:8px;border:1px solid #7f1d1d;color:#fca5a5">${{esc(e.message)}}</div>`;
  }}
}}

function downloadTemplate() {{
  const csv = 'name,sku,quantity,unit,location,category,tags,notes,barcode_type,barcode_value,cost,min_quantity\\n';
  const blob = new Blob([csv], {{ type: 'text/csv' }});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'inventory_template.csv';
  a.click();
}}

// --- Modal ---
function showModal(html) {{
  document.getElementById('modal-root').innerHTML = `
    <div class="modal-overlay" onclick="if(event.target===this)closeModal()">
      <div class="modal">${{html}}</div>
    </div>`;
}}
function closeModal() {{
  document.getElementById('modal-root').innerHTML = '';
}}

// --- Utilities ---
function esc(s) {{
  if (s == null) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}}

function formatDate(iso) {{
  if (!iso) return '-';
  return new Date(iso).toLocaleDateString();
}}

function formatDateTime(iso) {{
  if (!iso) return '-';
  const d = new Date(iso);
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], {{hour:'2-digit',minute:'2-digit'}});
}}

async function logout() {{
  await fetch('/auth/api/logout', {{ method: 'POST' }});
  window.location.href = '/auth/login';
}}

// --- Init ---
navigateTo('dashboard');
</script>
</body>
</html>"""
