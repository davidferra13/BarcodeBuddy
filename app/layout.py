"""Shared navigation layout for all authenticated pages.

Provides a persistent sidebar, topbar, and page shell that every
protected page renders inside, ensuring one consistent navigation
surface across the entire application.
"""

from __future__ import annotations

import html as html_mod

_E = html_mod.escape


# ── SVG icon library (keyed by nav item id) ──────────────────────────

_ICONS: dict[str, str] = {
    "scan": (
        '<svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor"'
        ' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M2 4V2h4"/><path d="M14 2h4v2"/><path d="M2 16v2h4"/>'
        '<path d="M14 18h4v-2"/><line x1="6" y1="6" x2="6" y2="14"/>'
        '<line x1="10" y1="6" x2="10" y2="14"/><line x1="14" y1="6" x2="14" y2="14"/></svg>'
    ),
    "items": (
        '<svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor"'
        ' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M2 3h16v4H2z"/><path d="M2 9h16v8H2z"/>'
        '<line x1="8" y1="12" x2="12" y2="12"/></svg>'
    ),
    "new-item": (
        '<svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor"'
        ' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="10" cy="10" r="8"/><line x1="10" y1="6" x2="10" y2="14"/>'
        '<line x1="6" y1="10" x2="14" y2="10"/></svg>'
    ),
    "import": (
        '<svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor"'
        ' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M14 2H6a2 2 0 00-2 2v12a2 2 0 002 2h8a2 2 0 002-2V4a2 2 0 00-2-2z"/>'
        '<polyline points="7 10 10 13 13 10"/><line x1="10" y1="6" x2="10" y2="13"/></svg>'
    ),
    "export": (
        '<svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor"'
        ' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M14 2H6a2 2 0 00-2 2v12a2 2 0 002 2h8a2 2 0 002-2V4a2 2 0 00-2-2z"/>'
        '<polyline points="7 10 10 7 13 10"/><line x1="10" y1="14" x2="10" y2="7"/></svg>'
    ),
    "monitor": (
        '<svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor"'
        ' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="2" y="2" width="7" height="7" rx="1.5"/>'
        '<rect x="11" y="2" width="7" height="4" rx="1.5"/>'
        '<rect x="2" y="11" width="7" height="4" rx="1.5"/>'
        '<rect x="11" y="8" width="7" height="7" rx="1.5"/></svg>'
    ),
    "admin": (
        '<svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor"'
        ' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 14v2a2 2 0 01-2 2H4a2 2 0 01-2-2v-2"/>'
        '<path d="M16 7a4 4 0 00-8 0v3h8V7z"/><rect x="6" y="10" width="8" height="6" rx="1"/></svg>'
    ),
}


def _nav_item(icon_key: str, label: str, href: str, active: bool) -> str:
    cls = "nav-btn active" if active else "nav-btn"
    icon = _ICONS.get(icon_key, "")
    return (
        f'<a class="{cls}" href="{_E(href)}"'
        f' style="text-decoration:none;display:flex;align-items:center;gap:8px;">'
        f'{icon}{_E(label)}</a>'
    )


def _user_section(display_name: str, role: str, is_admin: bool) -> str:
    initial = _E(display_name[0].upper()) if display_name else "?"
    name = _E(display_name)
    role_e = _E(role)
    badge_bg = "#7c3aed33" if is_admin else "#3b82f633"
    badge_color = "#a78bfa" if is_admin else "#93c5fd"
    return f"""
    <div style="padding:14px 20px;border-top:1px solid rgba(255,255,255,0.06);">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
        <div style="width:28px;height:28px;border-radius:50%;background:#334155;display:flex;
          align-items:center;justify-content:center;font-size:12px;font-weight:700;color:#f8fafc;">
          {initial}
        </div>
        <div>
          <div style="font-size:13px;color:#fff;font-weight:600;">{name}</div>
          <span style="font-size:10px;padding:1px 6px;border-radius:4px;
            background:{badge_bg};color:{badge_color};font-weight:600;">
            {role_e}
          </span>
        </div>
      </div>
      <a href="#" onclick="fetch('/auth/api/logout',{{method:'POST'}}).then(()=>window.location.href='/auth/login');return false;"
        style="display:block;padding:6px 20px;color:#a0aab4;text-decoration:none;font-size:13px;
        transition:color 0.2s;"
        onmouseover="this.style.color='#f87171'" onmouseout="this.style.color='#a0aab4'">
        <svg style="width:14px;height:14px;vertical-align:-2px;margin-right:6px" viewBox="0 0 20 20"
          fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M7 17H3a1 1 0 01-1-1V4a1 1 0 011-1h4"/><path d="M14 14l4-4-4-4"/><path d="M18 10H7"/>
        </svg>Sign Out
      </a>
    </div>"""


# ── CSS ──────────────────────────────────────────────────────────────

_LAYOUT_CSS = """<style>
:root {
  --bg: #f0ebe3;
  --sidebar-bg: #1e2530;
  --sidebar-text: #a0aab4;
  --sidebar-active: #ffffff;
  --sidebar-hover: rgba(255,255,255,0.08);
  --sidebar-accent: #e8a04c;
  --paper: rgba(255, 251, 245, 0.92);
  --panel: rgba(255, 255, 255, 0.82);
  --line: rgba(44, 54, 63, 0.10);
  --text: #1a1f26;
  --muted: #68737d;
  --accent: #885529;
  --success: #1a7a54;
  --success-bg: rgba(26, 122, 84, 0.08);
  --success-border: rgba(26, 122, 84, 0.18);
  --failure: #c0392b;
  --failure-bg: rgba(192, 57, 43, 0.08);
  --failure-border: rgba(192, 57, 43, 0.18);
  --warning: #b8860b;
  --warning-bg: rgba(184, 134, 11, 0.08);
  --info: #2472a4;
  --info-bg: rgba(36, 114, 164, 0.08);
  --info-border: rgba(36, 114, 164, 0.18);
  --track: #e0dbd2;
  --radius: 16px;
  --sidebar-width: 230px;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  display: flex;
  min-height: 100vh;
  color: var(--text);
  background: var(--bg);
  font-family: "Segoe UI Variable", "Segoe UI", "Aptos", system-ui, sans-serif;
  font-size: 14px;
  line-height: 1.5;
}

/* ── Sidebar ── */
.sidebar {
  width: var(--sidebar-width);
  min-height: 100vh;
  background: var(--sidebar-bg);
  display: flex;
  flex-direction: column;
  position: fixed;
  top: 0; left: 0;
  z-index: 100;
  transition: transform 0.25s ease;
}

.sidebar-brand {
  padding: 24px 20px 20px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}

.sidebar-brand h1 {
  font-size: 18px; font-weight: 700; color: #fff;
  letter-spacing: 0.02em; line-height: 1.2;
}

.sidebar-brand .brand-sub {
  font-size: 11px; color: var(--sidebar-text);
  margin-top: 4px; letter-spacing: 0.04em; text-transform: uppercase;
}

.sidebar-nav { padding: 12px 10px; flex: 1; }

.nav-section { margin-bottom: 8px; }

.nav-section-label {
  font-size: 10px; text-transform: uppercase;
  letter-spacing: 0.14em; color: rgba(255,255,255,0.28);
  padding: 12px 12px 6px; font-weight: 600;
}

.nav-btn {
  display: flex; align-items: center; gap: 12px;
  width: 100%; padding: 10px 14px;
  border: none; border-radius: 10px;
  background: transparent; color: var(--sidebar-text);
  font-size: 13.5px; font-family: inherit;
  cursor: pointer; transition: all 0.15s ease;
  text-align: left; position: relative;
  text-decoration: none;
}

.nav-btn:hover {
  background: var(--sidebar-hover); color: #d0d6dc;
  text-decoration: none;
}

.nav-btn.active {
  background: rgba(232, 160, 76, 0.14);
  color: var(--sidebar-active);
}

.nav-btn.active::before {
  content: '';
  position: absolute; left: 0; top: 50%;
  transform: translateY(-50%);
  width: 3px; height: 20px;
  background: var(--sidebar-accent);
  border-radius: 0 4px 4px 0;
}

.nav-icon { width: 20px; height: 20px; opacity: 0.7; flex-shrink: 0; }
.nav-btn.active .nav-icon { opacity: 1; }

.sidebar-footer {
  padding: 14px 20px;
  border-top: 1px solid rgba(255,255,255,0.06);
  font-size: 11px; color: rgba(255,255,255,0.2);
}

/* ── Mobile hamburger ── */
.hamburger {
  display: none;
  position: fixed; top: 12px; left: 12px; z-index: 200;
  width: 40px; height: 40px; border: none; border-radius: 10px;
  background: var(--sidebar-bg); color: #fff;
  cursor: pointer; align-items: center; justify-content: center;
}

.sidebar-overlay {
  display: none; position: fixed; inset: 0;
  background: rgba(0,0,0,0.4); z-index: 90;
}

/* ── Main content ── */
.main {
  margin-left: var(--sidebar-width);
  flex: 1; min-height: 100vh;
}

.topbar {
  display: flex; align-items: center;
  justify-content: space-between;
  padding: 16px 28px;
  background: rgba(255,251,245,0.8);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--line);
  position: sticky; top: 0; z-index: 50;
}

.topbar-title {
  font-size: 16px; font-weight: 600; color: var(--text);
}

.topbar-meta {
  display: flex; align-items: center; gap: 16px;
  font-size: 12px; color: var(--muted);
}

.content { padding: 24px 28px; }

/* ── Cards & forms ── */
.panel {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--panel);
  padding: 20px; margin-bottom: 20px;
}

.panel-header {
  display: flex; align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.panel-title { font-size: 16px; font-weight: 600; }

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: 16px; margin-bottom: 24px;
}

.kpi {
  padding: 20px; border-radius: var(--radius);
  border: 1px solid var(--line);
  background: var(--panel);
  transition: box-shadow 0.15s ease, transform 0.15s ease;
}

.kpi:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.06); transform: translateY(-1px); }

.kpi-label {
  font-size: 11.5px; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--muted);
  margin-bottom: 8px; font-weight: 600;
}

.kpi-value {
  font-size: 32px; line-height: 1;
  font-weight: 700; letter-spacing: -0.01em;
}

.kpi-sub { font-size: 12px; color: var(--muted); margin-top: 6px; }

.kpi.accent-green { border-left: 3px solid var(--success); }
.kpi.accent-red { border-left: 3px solid var(--failure); }
.kpi.accent-amber { border-left: 3px solid var(--warning); }
.kpi.accent-blue { border-left: 3px solid var(--info); }

.color-success { color: var(--success); }
.color-failure { color: var(--failure); }
.color-warning { color: var(--warning); }

/* ── Forms ── */
.fg { margin-bottom: 14px; }
.fg label {
  display: block; font-size: 12px; font-weight: 600;
  color: var(--muted); margin-bottom: 4px;
  text-transform: uppercase; letter-spacing: .5px;
}
.fg input, .fg select, .fg textarea {
  width: 100%; padding: 8px 12px; border-radius: 8px;
  border: 1px solid var(--line); background: var(--paper);
  color: var(--text); font-size: 14px;
}
.fg input:focus, .fg select:focus, .fg textarea:focus {
  border-color: var(--info); outline: none;
}

.fr { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.fr3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; }

/* ── Buttons ── */
.btn {
  padding: 8px 16px; border-radius: 8px; border: none;
  font-size: 13px; font-weight: 600; cursor: pointer;
  transition: all .2s; display: inline-flex;
  align-items: center; gap: 6px; text-decoration: none;
  font-family: inherit;
}
.btn-primary { background: #2472a4; color: #fff; }
.btn-primary:hover { background: #1b5a80; }
.btn-success { background: var(--success); color: #fff; }
.btn-success:hover { background: #146343; }
.btn-danger { background: var(--failure); color: #fff; }
.btn-danger:hover { background: #a33025; }
.btn-secondary { background: var(--line); color: var(--text); }
.btn-secondary:hover { background: rgba(44, 54, 63, 0.18); }
.btn-sm { padding: 5px 10px; font-size: 12px; }

/* ── Tables ── */
table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
th, td { padding: 10px 12px; text-align: left; vertical-align: top; }
thead th {
  color: var(--muted); font-size: 11px;
  text-transform: uppercase; letter-spacing: 0.1em;
  font-weight: 600; border-bottom: 2px solid var(--line); padding-bottom: 8px;
}
tbody td { border-bottom: 1px solid var(--line); }
tbody tr:hover { background: rgba(0,0,0,0.015); }
tbody tr:last-child td { border-bottom: none; }

/* ── Badges ── */
.badge {
  display: inline-block; padding: 2px 8px;
  border-radius: 4px; font-size: 11px; font-weight: 600;
}
.bg { background: var(--success-bg); color: var(--success); border: 1px solid var(--success-border); }
.by { background: var(--warning-bg); color: var(--warning); }
.br { background: var(--failure-bg); color: var(--failure); border: 1px solid var(--failure-border); }
.bb { background: var(--info-bg); color: var(--info); border: 1px solid var(--info-border); }
.bgr { background: rgba(44,54,63,0.06); color: var(--muted); }

/* ── Search bar ── */
.search-bar {
  display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap;
}
.search-bar input {
  flex: 1; min-width: 200px; padding: 8px 14px;
  border-radius: 8px; border: 1px solid var(--line);
  background: var(--paper); color: var(--text); font-size: 14px;
}
.search-bar input:focus { border-color: var(--info); outline: none; }

/* ── Stat row ── */
.sr {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px; margin-bottom: 20px;
}
.sb {
  background: var(--panel); border-radius: 12px;
  padding: 14px; text-align: center;
  border: 1px solid var(--line);
}
.sb .v { font-size: 24px; font-weight: 700; color: var(--text); }
.sb .l { font-size: 11px; color: var(--muted); text-transform: uppercase; margin-top: 2px; }

/* ── Messages ── */
.err {
  background: var(--failure-bg); color: var(--failure);
  padding: 10px 14px; border-radius: 8px; font-size: 13px;
  margin-bottom: 12px; display: none;
  border: 1px solid var(--failure-border);
}
.suc {
  background: var(--success-bg); color: var(--success);
  padding: 10px 14px; border-radius: 8px; font-size: 13px;
  margin-bottom: 12px; display: none;
  border: 1px solid var(--success-border);
}

.empty { text-align: center; padding: 40px; color: var(--muted); }

/* ── Toast notifications ── */
.toast-container {
  position: fixed; bottom: 20px; right: 20px; z-index: 9999;
  display: flex; flex-direction: column-reverse; gap: 8px;
  pointer-events: none;
}
.toast {
  pointer-events: auto;
  padding: 12px 20px; border-radius: 10px;
  font-size: 13px; font-weight: 600;
  box-shadow: 0 8px 24px rgba(0,0,0,0.12);
  display: flex; align-items: center; gap: 10px;
  animation: toastIn 0.3s ease;
  max-width: 380px; backdrop-filter: blur(12px);
}
.toast.success { background: rgba(26,122,84,0.95); color: #fff; }
.toast.error { background: rgba(192,57,43,0.95); color: #fff; }
.toast.info { background: rgba(36,114,164,0.95); color: #fff; }
.toast.warning { background: rgba(184,134,11,0.95); color: #fff; }
.toast.out { animation: toastOut 0.25s ease forwards; }
@keyframes toastIn { from { opacity: 0; transform: translateY(12px) scale(0.95); } to { opacity: 1; transform: translateY(0) scale(1); } }
@keyframes toastOut { to { opacity: 0; transform: translateY(-8px) scale(0.95); } }

/* ── Form sections ── */
.form-section { margin-bottom: 24px; }
.form-section-title {
  font-size: 13px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.08em; color: var(--muted);
  padding-bottom: 8px; margin-bottom: 16px;
  border-bottom: 1px solid var(--line);
}
.form-section-desc {
  font-size: 12px; color: var(--muted); margin-bottom: 14px;
  margin-top: -8px;
}

/* ── Drop zone ── */
.dropzone {
  border: 2px dashed var(--line); border-radius: 12px;
  padding: 40px 24px; text-align: center;
  transition: all 0.2s; cursor: pointer;
  background: var(--paper);
}
.dropzone:hover, .dropzone.drag-over {
  border-color: var(--info); background: var(--info-bg);
}
.dropzone-icon { font-size: 36px; margin-bottom: 8px; color: var(--muted); }
.dropzone-text { font-size: 14px; color: var(--muted); }
.dropzone-text strong { color: var(--info); }
.dropzone-hint { font-size: 12px; color: var(--muted); margin-top: 6px; opacity: 0.7; }

/* ── Autosave indicator ── */
.autosave-badge {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 11px; color: var(--muted); padding: 3px 8px;
  border-radius: 6px; background: rgba(44,54,63,0.05);
  transition: all 0.3s;
}
.autosave-badge.saving { color: var(--info); }
.autosave-badge.saved { color: var(--success); }

/* ── Page header with actions ── */
.page-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 20px; flex-wrap: wrap; gap: 12px;
}
.page-header-left { display: flex; align-items: center; gap: 12px; }
.page-desc { font-size: 13px; color: var(--muted); margin-bottom: 20px; }

/* ── Content entrance animation ── */
.content { animation: contentIn 0.2s ease; }
@keyframes contentIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ── Quantity colors ── */
.ql { color: var(--warning); }
.qz { color: var(--failure); }

/* ── Barcode preview box ── */
.bp { background: #fff; padding: 12px; border-radius: 8px; display: inline-block; margin: 8px 0; }

/* ── Scan page ── */
.sa { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; align-items: start; }
.cb { background: #000; border-radius: 10px; overflow: hidden; position: relative; min-height: 300px; }
.cb video { width: 100%; display: block; }
.cb canvas { display: none; }
.sl {
  position: absolute; left: 10%; right: 10%;
  height: 2px; background: var(--info);
  box-shadow: 0 0 12px var(--info);
  animation: sm 2s ease-in-out infinite;
}
@keyframes sm { 0%,100% { top: 20% } 50% { top: 80% } }
.qa { display: flex; gap: 8px; align-items: center; margin-top: 12px; }
.qa button {
  width: 40px; height: 40px; border-radius: 8px;
  border: none; font-size: 18px; font-weight: 700; cursor: pointer;
}
.qa .mn { background: var(--failure); color: #fff; }
.qa .pl { background: var(--success); color: #fff; }
.qa input {
  width: 60px; text-align: center; font-size: 18px; font-weight: 700;
  background: var(--paper); border: 1px solid var(--line);
  border-radius: 8px; color: var(--text); padding: 6px;
}

/* ── Admin styles ── */
.stats-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px; margin-bottom: 24px;
}
.stat-card {
  background: var(--panel); border-radius: 12px;
  padding: 20px; text-align: center;
  border: 1px solid var(--line);
}
.stat-card .value { font-size: 32px; font-weight: 700; color: var(--text); }
.stat-card .label { font-size: 12px; color: var(--muted); margin-top: 4px; text-transform: uppercase; }

.role-badge {
  display: inline-block; padding: 3px 10px;
  border-radius: 6px; font-size: 12px; font-weight: 600;
}
.role-admin { background: rgba(124,58,237,0.12); color: #7c3aed; }
.role-user { background: var(--info-bg); color: var(--info); }
.status-active { color: var(--success); }
.status-inactive { color: var(--failure); }

.action-btn {
  padding: 5px 12px; border-radius: 6px;
  border: 1px solid var(--line); background: transparent;
  color: var(--muted); font-size: 12px;
  cursor: pointer; transition: all 0.2s; margin: 0 2px;
}
.action-btn:hover { background: rgba(44,54,63,0.08); color: var(--text); }
.action-btn.danger { border-color: var(--failure-border); color: var(--failure); }
.action-btn.danger:hover { background: var(--failure-bg); }

a { color: var(--info); text-decoration: none; }
a:hover { text-decoration: underline; }

code {
  font-family: "Cascadia Mono", "Consolas", monospace;
  font-size: 13px; word-break: break-word;
}

/* ── Responsive ── */
@media (max-width: 900px) {
  .sidebar { transform: translateX(-100%); }
  .sidebar.open { transform: translateX(0); }
  .sidebar-overlay.open { display: block; }
  .hamburger { display: flex; }
  .main { margin-left: 0; }
  .content { padding: 16px; }
  .topbar { padding: 12px 16px 12px 56px; }
  .fr, .fr3 { grid-template-columns: 1fr; }
  .sa { grid-template-columns: 1fr; }
  #mg { grid-template-columns: 1fr !important; }
}
</style>"""


# ── Shared JS utilities ──────────────────────────────────────────────

_LAYOUT_JS = """<script>
async function apiCall(m,u,b){const o={method:m,headers:{'Content-Type':'application/json'}};if(b)o.body=JSON.stringify(b);const r=await fetch(u,o);return{ok:r.ok,status:r.status,data:await r.json()}}
function showErr(m){const e=document.getElementById('err');if(e){e.textContent=m;e.style.display='block'}toast(m,'error')}
function showSuc(m){const e=document.getElementById('suc');if(e){e.textContent=m;e.style.display='block'}toast(m,'success')}
function hideMsg(){document.querySelectorAll('.err,.suc').forEach(e=>e.style.display='none')}
function esc(s){if(!s)return'';const d=document.createElement('div');d.textContent=s;return d.innerHTML}

/* Toast notification system */
(function(){const c=document.createElement('div');c.className='toast-container';c.id='toast-container';document.body.appendChild(c)})();
function toast(msg,type,duration){type=type||'info';duration=duration||3500;const c=document.getElementById('toast-container');const t=document.createElement('div');t.className='toast '+type;const icons={success:'&#10003;',error:'&#10007;',info:'&#8505;',warning:'&#9888;'};t.innerHTML='<span>'+icons[type]+'</span><span>'+esc(msg)+'</span>';c.appendChild(t);setTimeout(()=>{t.classList.add('out');setTimeout(()=>t.remove(),250)},duration)}

/* Autosave helpers */
function autosaveInit(key,fields,interval){interval=interval||2000;let timer=null;const badge=document.getElementById('autosave-badge');function save(){const data={};fields.forEach(f=>{const el=document.getElementById(f);if(el)data[f]=el.value});try{localStorage.setItem('bb_autosave_'+key,JSON.stringify(data));if(badge){badge.className='autosave-badge saved';badge.textContent='Draft saved';setTimeout(()=>{badge.className='autosave-badge';badge.textContent='Auto-saving'},2000)}}catch(e){}}fields.forEach(f=>{const el=document.getElementById(f);if(el)el.addEventListener('input',()=>{if(badge){badge.className='autosave-badge saving';badge.textContent='Saving...'}clearTimeout(timer);timer=setTimeout(save,interval)})});return{save,load:()=>autosaveLoad(key,fields),clear:()=>autosaveClear(key)}}
function autosaveLoad(key,fields){try{const raw=localStorage.getItem('bb_autosave_'+key);if(!raw)return false;const data=JSON.parse(raw);let loaded=false;fields.forEach(f=>{const el=document.getElementById(f);if(el&&data[f]!==undefined&&data[f]!==''){el.value=data[f];loaded=true}});return loaded}catch(e){return false}}
function autosaveClear(key){try{localStorage.removeItem('bb_autosave_'+key)}catch(e){}}

/* Unsaved changes guard */
function guardUnsaved(formSel){let dirty=false;const form=document.querySelector(formSel);if(!form)return;form.querySelectorAll('input,textarea,select').forEach(el=>{el.addEventListener('input',()=>{dirty=true})});window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue=''}});return{markClean:()=>{dirty=false},markDirty:()=>{dirty=true}}}
</script>"""


# ── Navigation map ───────────────────────────────────────────────────

# Each entry: (section_label, [(icon_key, label, href, active_id), ...])
_NAV_SECTIONS: list[tuple[str, list[tuple[str, str, str, str]]]] = [
    ("Inventory", [
        ("scan", "Scan", "/scan", "scan"),
        ("items", "Items", "/inventory", "items"),
        ("new-item", "New Item", "/inventory/new", "new-item"),
        ("import", "Import CSV", "/inventory/import", "import"),
        ("export", "Export CSV", "/api/inventory/export/csv", "export"),
    ]),
    ("Monitor", [
        ("monitor", "Dashboard", "/", "monitor"),
    ]),
    ("System", [
        ("admin", "Admin Panel", "/admin", "admin"),
    ]),
]


def render_shell(
    *,
    title: str,
    active_nav: str,
    body_html: str,
    body_js: str = "",
    display_name: str = "User",
    role: str = "user",
    head_extra: str = "",
) -> str:
    """Return a full HTML page wrapped in the shared navigation shell.

    Parameters
    ----------
    title:       Page <title> text and topbar heading.
    active_nav:  Which nav item to highlight (e.g. "items", "scan", "admin", "monitor").
    body_html:   The page-specific HTML to insert inside `.content`.
    body_js:     Optional page-specific <script> to append after the shared JS.
    display_name: Current user's display name.
    role:        Current user's role ("admin" or "user").
    head_extra:  Optional extra content for <head> (e.g. additional styles).
    """
    is_admin = role == "admin"

    # Build sidebar nav sections
    nav_html_parts: list[str] = []
    for section_label, items in _NAV_SECTIONS:
        # Hide admin section for non-admin users
        if section_label == "System" and not is_admin:
            continue
        section_items = "\n".join(
            _nav_item(icon_key, label, href, active_id == active_nav)
            for icon_key, label, href, active_id in items
        )
        nav_html_parts.append(
            f'<div class="nav-section">'
            f'<div class="nav-section-label">{_E(section_label)}</div>'
            f'{section_items}</div>'
        )
    nav_html = "\n".join(nav_html_parts)

    user_html = _user_section(display_name, role, is_admin)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_E(title)} - Barcode Buddy</title>
  {_LAYOUT_CSS}
  {head_extra}
</head>
<body>
  <!-- Mobile hamburger -->
  <button class="hamburger" onclick="document.querySelector('.sidebar').classList.toggle('open');document.querySelector('.sidebar-overlay').classList.toggle('open')" aria-label="Menu">
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="3" y1="5" x2="17" y2="5"/><line x1="3" y1="10" x2="17" y2="10"/><line x1="3" y1="15" x2="17" y2="15"/></svg>
  </button>
  <div class="sidebar-overlay" onclick="document.querySelector('.sidebar').classList.remove('open');this.classList.remove('open')"></div>

  <nav class="sidebar">
    <div class="sidebar-brand">
      <h1>Barcode Buddy</h1>
      <div class="brand-sub">Inventory Management</div>
    </div>
    <div class="sidebar-nav">
      {nav_html}
    </div>
    {user_html}
    <div class="sidebar-footer">Barcode Buddy v3.0.0</div>
  </nav>

  <div class="main">
    <header class="topbar">
      <div class="topbar-title">{_E(title)}</div>
      <div class="topbar-meta"></div>
    </header>
    <div class="content">
      {body_html}
    </div>
  </div>
  <div class="toast-container" id="toast-container"></div>
  {_LAYOUT_JS}
  {body_js}
</body>
</html>"""
