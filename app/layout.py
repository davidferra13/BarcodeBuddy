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
    "calendar": (
        '<svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor"'
        ' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="2" y="4" width="16" height="14" rx="2"/>'
        '<line x1="2" y1="8" x2="18" y2="8"/>'
        '<line x1="6" y1="2" x2="6" y2="6"/><line x1="14" y1="2" x2="14" y2="6"/>'
        '<line x1="6" y1="8" x2="6" y2="18"/><line x1="10" y1="8" x2="10" y2="18"/>'
        '<line x1="14" y1="8" x2="14" y2="18"/>'
        '<line x1="2" y1="12" x2="18" y2="12"/><line x1="2" y1="16" x2="18" y2="16"/></svg>'
    ),
    "analytics": (
        '<svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor"'
        ' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="2 16 6 10 10 13 14 6 18 2"/>'
        '<polyline points="14 2 18 2 18 6"/>'
        '<line x1="2" y1="18" x2="18" y2="18"/></svg>'
    ),
    "alerts": (
        '<svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor"'
        ' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M10 2a6 6 0 00-6 6c0 3-1.5 5-2 6h16c-.5-1-2-3-2-6a6 6 0 00-6-6z"/>'
        '<path d="M8 16a2 2 0 004 0"/></svg>'
    ),
    "admin": (
        '<svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor"'
        ' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 14v2a2 2 0 01-2 2H4a2 2 0 01-2-2v-2"/>'
        '<path d="M16 7a4 4 0 00-8 0v3h8V7z"/><rect x="6" y="10" width="8" height="6" rx="1"/></svg>'
    ),
    "bulk-io": (
        '<svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor"'
        ' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M3 2h10l4 4v12a2 2 0 01-2 2H5a2 2 0 01-2-2V4a2 2 0 012-2z"/>'
        '<polyline points="6 12 10 8 14 12"/><polyline points="6 16 10 12 14 16"/></svg>'
    ),
    "scan-to-pdf": (
        '<svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor"'
        ' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M14 2H6a2 2 0 00-2 2v12a2 2 0 002 2h8a2 2 0 002-2V4a2 2 0 00-2-2z"/>'
        '<line x1="7" y1="7" x2="7" y2="13"/><line x1="10" y1="7" x2="10" y2="13"/>'
        '<line x1="13" y1="7" x2="13" y2="13"/><polyline points="7 15 10 13 13 15"/></svg>'
    ),
    "activity": (
        '<svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor"'
        ' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M10 2a8 8 0 100 16 8 8 0 000-16z"/>'
        '<path d="M10 6v4l3 3"/></svg>'
    ),
    "team": (
        '<svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor"'
        ' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="7" cy="6" r="3"/><circle cx="14" cy="7" r="2.5"/>'
        '<path d="M1 17v-1a4 4 0 018 0v1"/><path d="M11 17v-1a3 3 0 016 0v1"/></svg>'
    ),
    "feedback": (
        '<svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor"'
        ' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M2 4a2 2 0 012-2h12a2 2 0 012 2v9a2 2 0 01-2 2H7l-4 3v-3a1 1 0 01-1-1V4z"/>'
        '<line x1="7" y1="7" x2="13" y2="7"/><line x1="7" y1="10" x2="11" y2="10"/></svg>'
    ),
}


def _nav_item(icon_key: str, label: str, href: str, active: bool) -> str:
    cls = "nav-btn active" if active else "nav-btn"
    icon = _ICONS.get(icon_key, "")
    aria = ' aria-current="page"' if active else ""
    badge = '<span class="nav-alert-badge" id="sidebar-alert-badge" style="display:none"></span>' if icon_key == "alerts" else ""
    return (
        f'<a class="{cls}" href="{_E(href)}" role="menuitem"{aria}'
        f' data-tooltip="{_E(label)}" tabindex="0">'
        f'{icon}<span class="nav-label">{_E(label)}</span>{badge}</a>'
    )


_ROLE_BADGE_COLORS: dict[str, tuple[str, str]] = {
    "owner": ("#dc262633", "#fca5a5"),
    "admin": ("#7c3aed33", "#a78bfa"),
    "manager": ("#d9770633", "#fcd34d"),
    "user": ("#3b82f633", "#93c5fd"),
}


def _user_section(display_name: str, role: str, is_admin: bool) -> str:
    initial = _E(display_name[0].upper()) if display_name else "?"
    name = _E(display_name)
    role_e = _E(role)
    badge_bg, badge_color = _ROLE_BADGE_COLORS.get(role, _ROLE_BADGE_COLORS["user"])
    return f"""
    <div class="sidebar-user" style="padding:14px 20px;border-top:1px solid rgba(255,255,255,0.06);overflow:hidden;">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
        <div class="user-avatar" style="width:28px;height:28px;border-radius:50%;background:#334155;display:flex;
          align-items:center;justify-content:center;font-size:12px;font-weight:700;color:#f8fafc;flex-shrink:0;">
          {initial}
        </div>
        <div class="user-info" style="min-width:0;overflow:hidden;">
          <div style="font-size:13px;color:#fff;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{name}</div>
          <span style="font-size:10px;padding:1px 6px;border-radius:4px;
            background:{badge_bg};color:{badge_color};font-weight:600;white-space:nowrap;">
            {role_e}
          </span>
        </div>
      </div>
      <a href="/auth/profile"
        class="signout-link"
        style="display:flex;align-items:center;gap:6px;padding:6px 0;color:#a0aab4;text-decoration:none;font-size:13px;
        transition:color 0.2s;white-space:nowrap;overflow:hidden;"
        onmouseover="this.style.color='#60a5fa'" onmouseout="this.style.color='#a0aab4'">
        <svg style="width:14px;height:14px;flex-shrink:0;" viewBox="0 0 20 20"
          fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M10 12a4 4 0 100-8 4 4 0 000 8z"/><path d="M16 18a6 6 0 00-12 0"/>
        </svg><span class="signout-text">Profile</span>
      </a>
      <a href="#" onclick="fetch('/auth/api/logout',{{method:'POST'}}).catch(()=>{{}}).finally(()=>window.location.href='/auth/login');return false;"
        class="signout-link"
        style="display:flex;align-items:center;gap:6px;padding:6px 0;color:#a0aab4;text-decoration:none;font-size:13px;
        transition:color 0.2s;white-space:nowrap;overflow:hidden;"
        onmouseover="this.style.color='#f87171'" onmouseout="this.style.color='#a0aab4'">
        <svg style="width:14px;height:14px;flex-shrink:0;" viewBox="0 0 20 20"
          fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M7 17H3a1 1 0 01-1-1V4a1 1 0 011-1h4"/><path d="M14 14l4-4-4-4"/><path d="M18 10H7"/>
        </svg><span class="signout-text">Sign Out</span>
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
  --sidebar-collapsed-width: 64px;
}

/* ── Dark mode ── */
[data-theme="dark"] {
  --bg: #0f1419;
  --sidebar-bg: #0a0e13;
  --sidebar-text: #8b95a1;
  --sidebar-active: #f0f4f8;
  --sidebar-hover: rgba(255,255,255,0.06);
  --sidebar-accent: #e8a04c;
  --paper: rgba(22, 28, 36, 0.92);
  --panel: rgba(30, 37, 48, 0.82);
  --line: rgba(148, 163, 184, 0.10);
  --text: #e2e8f0;
  --muted: #8b95a1;
  --accent: #e8a04c;
  --success: #34d399;
  --success-bg: rgba(52, 211, 153, 0.10);
  --success-border: rgba(52, 211, 153, 0.20);
  --failure: #f87171;
  --failure-bg: rgba(248, 113, 113, 0.10);
  --failure-border: rgba(248, 113, 113, 0.20);
  --warning: #fbbf24;
  --warning-bg: rgba(251, 191, 36, 0.10);
  --info: #60a5fa;
  --info-bg: rgba(96, 165, 250, 0.10);
  --info-border: rgba(96, 165, 250, 0.20);
  --track: #1e293b;
}
[data-theme="dark"] .topbar {
  background: rgba(15, 20, 25, 0.85);
}
[data-theme="dark"] .sidebar {
  border-right: 1px solid rgba(148, 163, 184, 0.06);
}
[data-theme="dark"] .btn-primary { background: #3b82f6; }
[data-theme="dark"] .btn-primary:hover { background: #2563eb; }
[data-theme="dark"] .btn-secondary { background: rgba(148,163,184,0.12); color: var(--text); }
[data-theme="dark"] .btn-secondary:hover { background: rgba(148,163,184,0.2); }
[data-theme="dark"] .fg input, [data-theme="dark"] .fg select, [data-theme="dark"] .fg textarea {
  background: rgba(15, 20, 25, 0.6); border-color: rgba(148,163,184,0.15);
}
[data-theme="dark"] .search-bar input {
  background: rgba(15, 20, 25, 0.6); border-color: rgba(148,163,184,0.15);
}
[data-theme="dark"] tbody tr:hover { background: rgba(255,255,255,0.02); }
[data-theme="dark"] .cmd-dialog { background: #1e293b; }
[data-theme="dark"] .cmd-item:hover, [data-theme="dark"] .cmd-item.selected { background: rgba(96,165,250,0.12); }
[data-theme="dark"] .ra-drawer { background: #111827; }
[data-theme="dark"] .ra-item:hover { background: rgba(255,255,255,0.02); }
[data-theme="dark"] .dropzone { background: rgba(15,20,25,0.6); border-color: rgba(148,163,184,0.2); }
[data-theme="dark"] .stat-card { background: var(--panel); }
[data-theme="dark"] code { color: #93c5fd; }
[data-theme="dark"] .nav-btn[data-tooltip]::after { background: #334155; }

/* ── Theme toggle button ── */
.theme-toggle {
  background: none; border: none; cursor: pointer; color: var(--muted);
  display: flex; align-items: center; justify-content: center;
  padding: 0; transition: color 0.2s, transform 0.3s;
  width: 20px; height: 20px;
}
.theme-toggle:hover { color: var(--text); transform: rotate(30deg); }
.theme-toggle svg { width: 18px; height: 18px; }

* { box-sizing: border-box; margin: 0; padding: 0; }

/* ── Skip to content (accessibility) ── */
.skip-link {
  position: absolute; top: -100%; left: 16px;
  padding: 8px 16px; background: var(--info); color: #fff;
  border-radius: 0 0 8px 8px; font-size: 13px; font-weight: 600;
  z-index: 999; text-decoration: none; transition: top 0.2s;
}
.skip-link:focus { top: 0; }

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
  transition: width 0.25s cubic-bezier(.4,0,.2,1), transform 0.25s cubic-bezier(.4,0,.2,1);
  overflow: hidden;
}

.sidebar-brand {
  padding: 24px 20px 20px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  display: flex; align-items: center; justify-content: space-between;
  min-height: 70px;
}

.sidebar-brand-text { min-width: 0; overflow: hidden; }

.sidebar-brand h1 {
  font-size: 18px; font-weight: 700; color: #fff;
  letter-spacing: 0.02em; line-height: 1.2;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

.sidebar-brand .brand-sub {
  font-size: 11px; color: var(--sidebar-text);
  margin-top: 4px; letter-spacing: 0.04em; text-transform: uppercase;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

/* Sidebar collapse toggle */
.sidebar-toggle {
  width: 28px; height: 28px; border: none; border-radius: 8px;
  background: rgba(255,255,255,0.06); color: var(--sidebar-text);
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; transition: all 0.2s;
}
.sidebar-toggle:hover { background: rgba(255,255,255,0.12); color: #fff; }
.sidebar-toggle svg { transition: transform 0.25s; }

.sidebar-nav {
  padding: 12px 10px; flex: 1;
  overflow-y: auto; overflow-x: hidden;
  scrollbar-width: thin; scrollbar-color: rgba(255,255,255,0.1) transparent;
  /* Scroll fade indicators */
  mask-image: linear-gradient(to bottom, transparent 0%, black 8px, black calc(100% - 8px), transparent 100%);
  -webkit-mask-image: linear-gradient(to bottom, transparent 0%, black 8px, black calc(100% - 8px), transparent 100%);
}
.sidebar-nav::-webkit-scrollbar { width: 4px; }
.sidebar-nav::-webkit-scrollbar-track { background: transparent; }
.sidebar-nav::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }

.nav-section { margin-bottom: 8px; }

.nav-section-label {
  font-size: 10px; text-transform: uppercase;
  letter-spacing: 0.14em; color: rgba(255,255,255,0.28);
  padding: 12px 12px 6px; font-weight: 600;
  white-space: nowrap; overflow: hidden;
  display: flex; align-items: center; justify-content: space-between;
  cursor: pointer; user-select: none;
  transition: color 0.15s;
}
.nav-section-label:hover { color: rgba(255,255,255,0.45); }

.nav-section-label .section-chevron {
  width: 14px; height: 14px; opacity: 0.4;
  transition: transform 0.2s, opacity 0.15s; flex-shrink: 0;
}
.nav-section-label:hover .section-chevron { opacity: 0.7; }
.nav-section.collapsed .section-chevron { transform: rotate(-90deg); }
.nav-section.collapsed .nav-section-items { display: none; }

.nav-btn {
  display: flex; align-items: center; gap: 12px;
  width: 100%; padding: 10px 14px;
  border: none; border-radius: 10px;
  background: transparent; color: var(--sidebar-text);
  font-size: 13.5px; font-family: inherit;
  cursor: pointer; transition: all 0.15s ease;
  text-align: left; position: relative;
  text-decoration: none; white-space: nowrap;
  outline: none;
}

.nav-btn:hover {
  background: var(--sidebar-hover); color: #d0d6dc;
  text-decoration: none;
}

.nav-btn:focus-visible {
  outline: 2px solid var(--sidebar-accent);
  outline-offset: -2px;
}

.nav-btn.active {
  background: rgba(232, 160, 76, 0.14);
  color: var(--sidebar-active);
  box-shadow: -2px 0 12px rgba(232, 160, 76, 0.15);
}

.nav-btn.active::before {
  content: '';
  position: absolute; left: 0; top: 50%;
  transform: translateY(-50%);
  width: 3px; height: 20px;
  background: var(--sidebar-accent);
  border-radius: 0 4px 4px 0;
  box-shadow: 0 0 8px rgba(232, 160, 76, 0.4);
}

.nav-icon { width: 20px; height: 20px; opacity: 0.7; flex-shrink: 0; }
.nav-btn.active .nav-icon { opacity: 1; }
.nav-label { overflow: hidden; text-overflow: ellipsis; transition: opacity 0.2s; }

/* Sidebar alert badge */
.nav-alert-badge {
  font-size: 10px; font-weight: 700; min-width: 18px; height: 18px;
  border-radius: 999px; text-align: center; line-height: 18px;
  padding: 0 5px; background: var(--failure); color: #fff;
  margin-left: auto; flex-shrink: 0;
  animation: badgePop 0.3s cubic-bezier(.4,0,.2,1);
}
@keyframes badgePop { from { transform: scale(0); } to { transform: scale(1); } }

/* Tooltip for collapsed sidebar */
.nav-btn[data-tooltip] { position: relative; }
.nav-btn[data-tooltip]::after {
  content: attr(data-tooltip);
  position: absolute; left: calc(100% + 12px); top: 50%;
  transform: translateY(-50%); white-space: nowrap;
  background: #1a1f26; color: #fff; padding: 6px 12px;
  border-radius: 8px; font-size: 12px; font-weight: 600;
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
  pointer-events: none; opacity: 0;
  transition: opacity 0.15s, transform 0.15s;
  transform: translateY(-50%) translateX(-4px);
  z-index: 200;
}
/* Tooltips only show when sidebar is collapsed */
.sidebar.collapsed .nav-btn[data-tooltip]:hover::after {
  opacity: 1; transform: translateY(-50%) translateX(0);
}

/* ── Collapsed sidebar state ── */
.sidebar.collapsed { width: var(--sidebar-collapsed-width); }
.sidebar.collapsed .sidebar-brand-text { opacity: 0; width: 0; }
.sidebar.collapsed .sidebar-brand { padding: 24px 0 20px; justify-content: center; }
.sidebar.collapsed .sidebar-toggle svg { transform: rotate(180deg); }
.sidebar.collapsed .nav-section-label span:first-child { opacity: 0; width: 0; overflow: hidden; }
.sidebar.collapsed .section-chevron { display: none; }
.sidebar.collapsed .nav-section-label { justify-content: center; padding: 12px 0 6px; }
.sidebar.collapsed .nav-btn { justify-content: center; padding: 10px 0; }
.sidebar.collapsed .nav-label { opacity: 0; width: 0; position: absolute; }
.sidebar.collapsed .nav-alert-badge {
  position: absolute; top: 4px; right: 8px;
  min-width: 14px; height: 14px; font-size: 9px; line-height: 14px;
}
.sidebar.collapsed .sidebar-nav { padding: 12px 6px; }
.sidebar.collapsed + .sidebar-overlay + .main,
body:has(.sidebar.collapsed) .main { margin-left: var(--sidebar-collapsed-width); }
.sidebar.collapsed .sidebar-footer { padding: 14px 8px; font-size: 0; }
.sidebar.collapsed .sidebar-footer::after { content: "v3"; font-size: 10px; }
.sidebar.collapsed .sidebar-user { padding: 14px 8px; display: flex; flex-direction: column; align-items: center; }
.sidebar.collapsed .user-info { display: none; }
.sidebar.collapsed .signout-text { display: none; }
.sidebar.collapsed .signout-link { justify-content: center; padding: 6px 0; }

.sidebar-footer {
  padding: 14px 20px;
  border-top: 1px solid rgba(255,255,255,0.06);
  font-size: 11px; color: rgba(255,255,255,0.2);
  white-space: nowrap; overflow: hidden;
}

/* ── Mobile hamburger ── */
.hamburger {
  display: none;
  position: fixed; top: 12px; left: 12px; z-index: 200;
  width: 40px; height: 40px; border: none; border-radius: 10px;
  background: var(--sidebar-bg); color: #fff;
  cursor: pointer; align-items: center; justify-content: center;
  transition: transform 0.2s;
}
.hamburger:active { transform: scale(0.92); }

.sidebar-overlay {
  display: none; position: fixed; inset: 0;
  background: rgba(0,0,0,0.5); z-index: 90;
  backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px);
  opacity: 0; transition: opacity 0.25s;
}
.sidebar-overlay.open { display: block; opacity: 1; }

/* ── Main content ── */
.main {
  margin-left: var(--sidebar-width);
  flex: 1; min-height: 100vh;
  transition: margin-left 0.25s cubic-bezier(.4,0,.2,1);
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

.topbar-left { display: flex; align-items: center; gap: 12px; min-width: 0; }

.topbar-title {
  font-size: 16px; font-weight: 600; color: var(--text);
}

/* Breadcrumbs */
.breadcrumbs {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: var(--muted);
}
.breadcrumbs a {
  color: var(--muted); text-decoration: none; transition: color 0.15s;
}
.breadcrumbs a:hover { color: var(--text); text-decoration: none; }
.breadcrumbs .bc-sep { opacity: 0.4; font-size: 10px; }
.breadcrumbs .bc-current { color: var(--text); font-weight: 600; }

.topbar-meta {
  display: flex; align-items: center; gap: 16px;
  font-size: 12px; color: var(--muted);
}

/* ── Command palette trigger ── */
.cmd-palette-trigger {
  display: flex; align-items: center; gap: 6px;
  padding: 5px 12px; border-radius: 8px;
  border: 1px solid var(--line); background: var(--paper);
  color: var(--muted); font-size: 12px;
  cursor: pointer; transition: all 0.15s;
}
.cmd-palette-trigger:hover { border-color: var(--info); color: var(--text); }
.cmd-palette-trigger kbd {
  font-size: 10px; padding: 1px 5px; border-radius: 4px;
  background: rgba(44,54,63,0.08); border: 1px solid var(--line);
  font-family: inherit; color: var(--muted);
}

/* ── Command palette overlay ── */
.cmd-overlay {
  display: none; position: fixed; inset: 0;
  background: rgba(0,0,0,0.5); backdrop-filter: blur(4px);
  z-index: 9998; align-items: flex-start; justify-content: center;
  padding-top: min(20vh, 160px);
}
.cmd-overlay.open { display: flex; animation: cmdFadeIn 0.15s ease; }
@keyframes cmdFadeIn { from { opacity: 0; } to { opacity: 1; } }

.cmd-dialog {
  width: 100%; max-width: 520px;
  background: var(--paper); border-radius: 16px;
  box-shadow: 0 24px 48px rgba(0,0,0,0.2);
  overflow: hidden; animation: cmdSlideIn 0.2s cubic-bezier(.4,0,.2,1);
}
@keyframes cmdSlideIn { from { transform: translateY(-12px) scale(0.98); opacity:0; } to { transform: none; opacity:1; } }

.cmd-input-wrap {
  display: flex; align-items: center; gap: 10px;
  padding: 16px 20px; border-bottom: 1px solid var(--line);
}
.cmd-input-wrap svg { width: 20px; height: 20px; color: var(--muted); flex-shrink: 0; }
.cmd-input {
  flex: 1; border: none; background: transparent;
  font-size: 15px; color: var(--text); outline: none;
  font-family: inherit;
}
.cmd-input::placeholder { color: var(--muted); }

.cmd-results {
  max-height: 320px; overflow-y: auto; padding: 8px;
}
.cmd-item {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 14px; border-radius: 10px; cursor: pointer;
  color: var(--text); text-decoration: none; transition: background 0.1s;
}
.cmd-item:hover, .cmd-item.selected { background: var(--info-bg); text-decoration: none; }
.cmd-item .nav-icon { width: 18px; height: 18px; color: var(--muted); }
.cmd-item-label { font-size: 14px; font-weight: 500; }
.cmd-item-section { font-size: 11px; color: var(--muted); margin-left: auto; }
.cmd-empty { padding: 24px; text-align: center; color: var(--muted); font-size: 13px; }
.cmd-footer {
  padding: 10px 20px; border-top: 1px solid var(--line);
  display: flex; gap: 16px; font-size: 11px; color: var(--muted);
}
.cmd-footer kbd {
  font-size: 10px; padding: 1px 5px; border-radius: 4px;
  background: rgba(44,54,63,0.08); border: 1px solid var(--line);
  font-family: inherit;
}

.content { padding: 24px 28px; }

/* ── Cards & forms ── */
.panel {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--panel);
  backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
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
  backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
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

/* Gradient accent borders via pseudo-element */
.kpi.accent-green, .kpi.accent-red, .kpi.accent-amber, .kpi.accent-blue {
  border-left: none; position: relative; overflow: hidden;
}
.kpi.accent-green::before, .kpi.accent-red::before, .kpi.accent-amber::before, .kpi.accent-blue::before {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; border-radius: 3px 0 0 3px;
}
.kpi.accent-green::before { background: linear-gradient(180deg, #10b981, #1a7a54, #065f46); }
.kpi.accent-red::before { background: linear-gradient(180deg, #f87171, #c0392b, #7f1d1d); }
.kpi.accent-amber::before { background: linear-gradient(180deg, #fbbf24, #b8860b, #78350f); }
.kpi.accent-blue::before { background: linear-gradient(180deg, #60a5fa, #2472a4, #1e3a5f); }

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
tbody tr { transition: background 0.15s, transform 0.15s; }
tbody tr:hover { background: rgba(0,0,0,0.025); transform: translateX(3px); }
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
  backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
}
.sb .v { font-size: 24px; font-weight: 700; color: var(--text); }
.sb .l { font-size: 11px; color: var(--muted); text-transform: uppercase; margin-top: 2px; }
.sb-active { border-color: var(--info); background: rgba(59,130,246,0.08); }

/* ── Sortable table headers ── */
.sortable { cursor: pointer; user-select: none; white-space: nowrap; }
.sortable:hover { color: var(--info); }
.sort-icon { font-size: 10px; margin-left: 2px; opacity: 0.7; }

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
.content { animation: contentIn 0.25s ease; }
@keyframes contentIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ── Staggered card entrance ── */
@keyframes cardIn {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}
.panel, .kpi, .sb, .stat-card {
  animation: cardIn 0.35s cubic-bezier(.4,0,.2,1) both;
}
.kpi-grid .kpi:nth-child(1), .sr .sb:nth-child(1), .stats-grid .stat-card:nth-child(1) { animation-delay: 0s; }
.kpi-grid .kpi:nth-child(2), .sr .sb:nth-child(2), .stats-grid .stat-card:nth-child(2) { animation-delay: 0.05s; }
.kpi-grid .kpi:nth-child(3), .sr .sb:nth-child(3), .stats-grid .stat-card:nth-child(3) { animation-delay: 0.1s; }
.kpi-grid .kpi:nth-child(4), .sr .sb:nth-child(4), .stats-grid .stat-card:nth-child(4) { animation-delay: 0.15s; }
.kpi-grid .kpi:nth-child(5), .sr .sb:nth-child(5), .stats-grid .stat-card:nth-child(5) { animation-delay: 0.2s; }
.kpi-grid .kpi:nth-child(6), .sr .sb:nth-child(6), .stats-grid .stat-card:nth-child(6) { animation-delay: 0.25s; }
.panel:nth-of-type(1) { animation-delay: 0.05s; }
.panel:nth-of-type(2) { animation-delay: 0.1s; }
.panel:nth-of-type(3) { animation-delay: 0.15s; }
.panel:nth-of-type(4) { animation-delay: 0.2s; }

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
.role-owner { background: rgba(220,38,38,0.12); color: #dc2626; }
.role-admin { background: rgba(124,58,237,0.12); color: #7c3aed; }
.role-manager { background: rgba(217,119,6,0.12); color: #d97706; }
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
  .sidebar {
    transform: translateX(-100%);
    width: var(--sidebar-width) !important; /* Never collapse on mobile, just slide */
  }
  .sidebar.open { transform: translateX(0); }
  .sidebar.collapsed { width: var(--sidebar-width) !important; }
  .sidebar.collapsed .nav-label { opacity: 1; width: auto; position: static; }
  .sidebar.collapsed .sidebar-brand-text { opacity: 1; width: auto; }
  .sidebar.collapsed .nav-btn { justify-content: flex-start; padding: 10px 14px; }
  .sidebar.collapsed .nav-section-label { justify-content: flex-start; padding: 12px 12px 6px; }
  .sidebar.collapsed .nav-section-label span:first-child { opacity: 1; width: auto; }
  .sidebar-toggle { display: none; }
  .sidebar-overlay.open { display: block; opacity: 1; }
  .hamburger { display: flex; }
  .main { margin-left: 0 !important; }
  .content { padding: 16px; }
  .topbar { padding: 12px 16px 12px 56px; }
  .fr, .fr3 { grid-template-columns: 1fr; }
  .sa { grid-template-columns: 1fr; }
  #mg { grid-template-columns: 1fr !important; }
  .breadcrumbs { display: none; }
  .cmd-palette-trigger span { display: none; }
  .cmd-dialog { margin: 0 12px; }
}

@media (max-width: 480px) {
  .topbar { padding: 10px 12px 10px 52px; }
  .content { padding: 12px; }
  .cmd-palette-trigger { padding: 5px 8px; }
}

/* ── Recent activity drawer ── */
.ra-overlay {
  display:none; position:fixed; inset:0; background:rgba(0,0,0,0.35);
  backdrop-filter:blur(2px); z-index:9990; opacity:0; transition:opacity .25s;
}
.ra-overlay.open { display:block; opacity:1; }
.ra-drawer {
  position:fixed; top:0; right:-420px; width:400px; max-width:92vw;
  height:100vh; background:var(--paper); z-index:9991;
  box-shadow:-8px 0 32px rgba(0,0,0,.12);
  display:flex; flex-direction:column;
  transition:right .3s cubic-bezier(.4,0,.2,1);
}
.ra-drawer.open { right:0; }
.ra-header {
  display:flex; align-items:center; justify-content:space-between;
  padding:16px 20px; border-bottom:1px solid var(--line);
  color:var(--text);
}
.ra-list {
  flex:1; overflow-y:auto; padding:0;
  scrollbar-width:thin; scrollbar-color:var(--line) transparent;
}
.ra-item {
  display:flex; gap:12px; padding:12px 20px;
  border-bottom:1px solid var(--line); transition:background .1s;
  cursor:default;
}
.ra-item:hover { background:rgba(0,0,0,.015); }
.ra-dot {
  width:8px; height:8px; border-radius:50%; margin-top:5px; flex-shrink:0;
}
.ra-body { flex:1; min-width:0; }
.ra-action { font-size:13px; font-weight:600; color:var(--text); }
.ra-summary { font-size:12px; color:var(--muted); margin-top:1px;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.ra-meta { font-size:11px; color:var(--muted); margin-top:3px; opacity:.7; }
.ra-empty { padding:40px; text-align:center; color:var(--muted); }

/* ── Loading skeleton ── */
@keyframes shimmer { to { background-position: -200% 0; } }
.skeleton {
  background: linear-gradient(90deg, var(--line) 25%, rgba(255,255,255,0.15) 50%, var(--line) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 6px; color: transparent !important;
  user-select: none; pointer-events: none;
}
.skeleton-text { height: 14px; margin-bottom: 10px; width: 80%; }
.skeleton-text.short { width: 40%; }
.skeleton-text.medium { width: 60%; }
.skeleton-heading { height: 24px; width: 50%; margin-bottom: 16px; }
.skeleton-card {
  height: 80px; border-radius: var(--radius);
  border: 1px solid var(--line); padding: 20px;
}
.skeleton-row { height: 44px; margin-bottom: 2px; }
[data-theme="dark"] .skeleton {
  background: linear-gradient(90deg, rgba(148,163,184,0.08) 25%, rgba(148,163,184,0.15) 50%, rgba(148,163,184,0.08) 75%);
  background-size: 200% 100%;
}

/* ── Standardized empty state ── */
.empty-state {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; padding: 48px 24px; text-align: center;
  color: var(--muted);
}
.empty-state svg, .empty-state .empty-icon {
  width: 48px; height: 48px; margin-bottom: 16px; opacity: 0.4;
  color: var(--muted);
}
.empty-state h3, .empty-state .empty-title {
  font-size: 15px; font-weight: 700; color: var(--text);
  margin: 0 0 6px;
}
.empty-state p, .empty-state .empty-desc {
  font-size: 13px; color: var(--muted); margin: 0 0 16px;
  max-width: 320px; line-height: 1.5;
}
.empty-state .btn { margin-top: 4px; }

/* ── Unified tab bar ── */
.tab-bar {
  display: flex; gap: 2px; margin-bottom: 20px;
  border-bottom: 2px solid var(--line); padding-bottom: 0;
}
.tab-btn {
  padding: 10px 18px; border: none; background: transparent;
  color: var(--muted); font-size: 13px; font-weight: 600;
  cursor: pointer; position: relative; transition: color 0.15s;
  font-family: inherit; border-radius: 8px 8px 0 0;
}
.tab-btn:hover { color: var(--text); background: rgba(0,0,0,0.02); }
.tab-btn.active {
  color: var(--info); background: transparent;
}
.tab-btn.active::after {
  content: ''; position: absolute; bottom: -2px; left: 0; right: 0;
  height: 2px; background: var(--info); border-radius: 2px 2px 0 0;
}
[data-theme="dark"] .tab-btn:hover { background: rgba(255,255,255,0.03); }
.tab-panel { display: none; }
.tab-panel.active { display: block; animation: contentIn 0.2s ease; }

/* ── Pill/segment tab variant ── */
.tab-pills {
  display: flex; gap: 4px; margin-bottom: 24px;
  background: var(--panel); border: 1px solid var(--line);
  border-radius: 12px; padding: 4px; overflow-x: auto;
}
.tab-pill {
  padding: 8px 16px; border-radius: 8px; border: none;
  background: transparent; color: var(--muted); font-size: 13px;
  font-weight: 600; cursor: pointer; transition: all 0.15s;
  font-family: inherit; white-space: nowrap;
}
.tab-pill:hover { background: rgba(44,54,63,0.06); color: var(--text); }
.tab-pill.active { background: var(--sidebar-bg); color: #fff; }
[data-theme="dark"] .tab-pills { background: rgba(30,37,48,0.6); }
[data-theme="dark"] .tab-pill:hover { background: rgba(255,255,255,0.06); }
[data-theme="dark"] .tab-pill.active { background: rgba(232,160,76,0.18); color: var(--sidebar-accent); }

/* ── Form validation states ── */
.fg label .required {
  color: var(--failure); font-weight: 700; margin-left: 2px;
}
.fg .is-invalid {
  border-color: var(--failure) !important;
  box-shadow: 0 0 0 2px var(--failure-bg);
}
.fg .field-error {
  font-size: 12px; color: var(--failure); margin-top: 4px;
  display: none;
}
.fg .field-error.show { display: block; animation: contentIn 0.15s ease; }
.fg .is-valid {
  border-color: var(--success) !important;
}

/* ── Category badge (semantic) ── */
.cat-badge {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;
  background: var(--line); color: var(--muted);
}
.cat-badge.cat-inventory { background: var(--info-bg); color: var(--info); }
.cat-badge.cat-auth { background: rgba(167,139,250,0.12); color: #a78bfa; }
.cat-badge.cat-admin { background: var(--warning-bg); color: var(--warning); }
.cat-badge.cat-scan { background: var(--success-bg); color: var(--success); }
.cat-badge.cat-import { background: rgba(6,182,212,0.12); color: #06b6d4; }
.cat-badge.cat-export { background: rgba(139,92,246,0.12); color: #8b5cf6; }
.cat-badge.cat-alert { background: var(--failure-bg); color: var(--failure); }
.cat-badge.cat-system { background: var(--line); color: var(--muted); }
[data-theme="dark"] .cat-badge.cat-auth { background: rgba(167,139,250,0.15); color: #c4b5fd; }
[data-theme="dark"] .cat-badge.cat-import { background: rgba(6,182,212,0.15); color: #67e8f9; }
[data-theme="dark"] .cat-badge.cat-export { background: rgba(139,92,246,0.15); color: #c4b5fd; }
</style>"""


# ── Shared JS utilities ──────────────────────────────────────────────

_LAYOUT_JS = """<script>
/* ── Theme toggle ── */
function toggleTheme(){
  const html=document.documentElement;
  const isDark=html.getAttribute('data-theme')==='dark';
  const next=isDark?'light':'dark';
  html.setAttribute('data-theme',next);
  try{localStorage.setItem('bb_theme',next)}catch(e){}
  updateThemeIcon(next);
}
function updateThemeIcon(theme){
  const sun=document.getElementById('theme-icon-sun');
  const moon=document.getElementById('theme-icon-moon');
  if(sun&&moon){
    sun.style.display=theme==='dark'?'block':'none';
    moon.style.display=theme==='dark'?'none':'block';
  }
}
(function(){
  const t=document.documentElement.getAttribute('data-theme')||'light';
  updateThemeIcon(t);
})();

async function apiCall(m,u,b){const o={method:m,headers:{'Content-Type':'application/json'}};if(b)o.body=JSON.stringify(b);const r=await fetch(u,o);if(r.status===401){toast('Session expired — redirecting to login','warning',2000);setTimeout(()=>location.href='/auth/login',1500);return{ok:false,status:401,data:{error:'Session expired'}}}return{ok:r.ok,status:r.status,data:await r.json()}}
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

/* ── Sidebar collapse ── */
function toggleSidebarCollapse(){
  const sb=document.getElementById('sidebar');
  sb.classList.toggle('collapsed');
  const collapsed=sb.classList.contains('collapsed');
  try{localStorage.setItem('bb_sidebar_collapsed',collapsed?'1':'0')}catch(e){}
  document.getElementById('sidebar-collapse-btn').setAttribute('aria-label',
    collapsed?'Expand sidebar':'Collapse sidebar');
}
(function(){
  try{
    if(localStorage.getItem('bb_sidebar_collapsed')==='1'&&window.innerWidth>900){
      document.getElementById('sidebar').classList.add('collapsed');
    }
  }catch(e){}
})();

/* ── Mobile menu ── */
function toggleMobileMenu(){
  const sb=document.getElementById('sidebar');
  const ov=document.getElementById('sidebar-overlay');
  const btn=document.getElementById('hamburger-btn');
  const open=!sb.classList.contains('open');
  sb.classList.toggle('open',open);
  ov.classList.toggle('open',open);
  btn.setAttribute('aria-expanded',open?'true':'false');
  btn.setAttribute('aria-label',open?'Close navigation menu':'Open navigation menu');
  if(open){
    /* Trap focus in sidebar on mobile */
    const first=sb.querySelector('.nav-btn');
    if(first)first.focus();
  }
}
function closeMobileMenu(){
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebar-overlay').classList.remove('open');
  document.getElementById('hamburger-btn').setAttribute('aria-expanded','false');
  document.getElementById('hamburger-btn').setAttribute('aria-label','Open navigation menu');
}

/* Swipe-to-close on mobile */
(function(){
  let sx=0,sy=0;
  const sb=document.getElementById('sidebar');
  if(!sb)return;
  sb.addEventListener('touchstart',e=>{sx=e.touches[0].clientX;sy=e.touches[0].clientY},{passive:true});
  sb.addEventListener('touchend',e=>{
    const dx=e.changedTouches[0].clientX-sx;
    const dy=Math.abs(e.changedTouches[0].clientY-sy);
    if(dx<-60&&dy<80)closeMobileMenu();
  },{passive:true});
})();

/* Close mobile menu on Escape */
document.addEventListener('keydown',e=>{
  if(e.key==='Escape'){
    const sb=document.getElementById('sidebar');
    if(sb&&sb.classList.contains('open'))closeMobileMenu();
  }
});

/* ── Collapsible nav sections ── */
function toggleNavSection(el){
  const section=el.closest('.nav-section');
  section.classList.toggle('collapsed');
  const expanded=!section.classList.contains('collapsed');
  el.setAttribute('aria-expanded',expanded?'true':'false');
  /* Persist */
  const id=section.dataset.section;
  try{
    const state=JSON.parse(localStorage.getItem('bb_nav_sections')||'{}');
    state[id]=expanded;
    localStorage.setItem('bb_nav_sections',JSON.stringify(state));
  }catch(e){}
}
/* Restore collapsed sections */
(function(){
  try{
    const state=JSON.parse(localStorage.getItem('bb_nav_sections')||'{}');
    Object.keys(state).forEach(id=>{
      if(!state[id]){
        const sec=document.querySelector('.nav-section[data-section="'+id+'"]');
        if(sec){
          sec.classList.add('collapsed');
          const lbl=sec.querySelector('.nav-section-label');
          if(lbl)lbl.setAttribute('aria-expanded','false');
        }
      }
    });
  }catch(e){}
})();

/* ── Scroll active nav item into view ── */
(function(){
  const active=document.querySelector('.sidebar-nav .nav-btn.active');
  if(active)active.scrollIntoView({block:'center',behavior:'instant'});
})();

/* ── Command palette ── */
const _cmdPages=[
  {label:'Dashboard',section:'Monitor',href:'/',icon:'monitor'},
  {label:'Scan',section:'Inventory',href:'/scan',icon:'scan'},
  {label:'Scan to PDF',section:'Inventory',href:'/scan-to-pdf',icon:'scan-to-pdf'},
  {label:'Items',section:'Inventory',href:'/inventory',icon:'items'},
  {label:'Calendar',section:'Inventory',href:'/calendar',icon:'calendar'},
  {label:'New Item',section:'Inventory',href:'/inventory/new',icon:'new-item'},
  {label:'Import CSV',section:'Inventory',href:'/inventory/bulk',icon:'import'},
  {label:'Analytics',section:'Monitor',href:'/analytics',icon:'analytics'},
  {label:'Activity Log',section:'Monitor',href:'/activity',icon:'activity'},
  {label:'Alerts',section:'Monitor',href:'/alerts',icon:'alerts'},
  {label:'Admin Panel',section:'System',href:'/admin',icon:'admin'},
  {label:'AI Chat',section:'AI',href:'/ai/chat',icon:'ai-chat'},
  {label:'Privacy & Data',section:'AI',href:'/ai/privacy',icon:'ai-privacy'},
  {label:'AI Settings',section:'AI',href:'/ai/settings',icon:'ai-settings'},
  {label:'AI Setup',section:'AI',href:'/ai/setup',icon:'ai-setup'},
  {label:'Team',section:'System',href:'/team',icon:'team'},
  {label:'Help & Feedback',section:'System',href:'/feedback',icon:'feedback'},
  {label:'Client Portal',section:'Monitor',href:'/client',icon:'monitor'},
  {label:'Profile',section:'Account',href:'/auth/profile',icon:'admin'},
];
let _cmdSel=0;

function openCmdPalette(){
  const ov=document.getElementById('cmd-overlay');
  const inp=document.getElementById('cmd-input');
  ov.classList.add('open');
  inp.value='';
  _cmdSel=0;
  renderCmdResults('');
  setTimeout(()=>inp.focus(),50);
}
function closeCmdPalette(){
  document.getElementById('cmd-overlay').classList.remove('open');
}
function renderCmdResults(q){
  const box=document.getElementById('cmd-results');
  const lq=q.toLowerCase().trim();
  const filtered=lq?_cmdPages.filter(p=>
    p.label.toLowerCase().includes(lq)||p.section.toLowerCase().includes(lq)
  ):_cmdPages;
  if(!filtered.length){
    box.innerHTML='<div class="cmd-empty">No pages found</div>';
    return;
  }
  if(_cmdSel>=filtered.length)_cmdSel=filtered.length-1;
  if(_cmdSel<0)_cmdSel=0;
  box.innerHTML=filtered.map((p,i)=>
    '<a class="cmd-item'+(i===_cmdSel?' selected':'')+'" href="'+esc(p.href)+'" role="option"'
    +(i===_cmdSel?' aria-selected="true"':'')+'>'
    +'<span class="cmd-item-label">'+esc(p.label)+'</span>'
    +'<span class="cmd-item-section">'+esc(p.section)+'</span></a>'
  ).join('');
}
document.getElementById('cmd-input').addEventListener('input',function(){
  _cmdSel=0;renderCmdResults(this.value);
});
document.getElementById('cmd-input').addEventListener('keydown',function(e){
  const items=document.querySelectorAll('.cmd-item');
  if(e.key==='ArrowDown'){e.preventDefault();_cmdSel=Math.min(_cmdSel+1,items.length-1);renderCmdResults(this.value)}
  else if(e.key==='ArrowUp'){e.preventDefault();_cmdSel=Math.max(_cmdSel-1,0);renderCmdResults(this.value)}
  else if(e.key==='Enter'){e.preventDefault();const sel=document.querySelector('.cmd-item.selected');if(sel)window.location.href=sel.getAttribute('href')}
  else if(e.key==='Escape'){closeCmdPalette()}
});

/* Ctrl+K to open command palette */
document.addEventListener('keydown',e=>{
  if((e.ctrlKey||e.metaKey)&&e.key==='k'){
    e.preventDefault();
    const ov=document.getElementById('cmd-overlay');
    if(ov.classList.contains('open'))closeCmdPalette();else openCmdPalette();
  }
});

/* ── Animated number counters ── */
(function(){
  function animateValue(el,start,end,duration){
    if(start===end)return;
    const range=end-start;
    const startTime=performance.now();
    const isFloat=String(end).includes('.');
    const decimals=isFloat?(String(end).split('.')[1]||'').length:0;
    const suffix=el.dataset.suffix||'';
    const prefix=el.dataset.prefix||'';
    function step(now){
      const elapsed=now-startTime;
      const progress=Math.min(elapsed/duration,1);
      const eased=1-Math.pow(1-progress,3);
      const current=start+range*eased;
      el.textContent=prefix+(isFloat?current.toFixed(decimals):Math.round(current).toLocaleString())+suffix;
      if(progress<1)requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }
  document.querySelectorAll('.kpi-value').forEach(el=>{
    const text=el.textContent.trim();
    const match=text.match(/^([^0-9-]*)(-?[\\d,]+\\.?\\d*)(.*)$/);
    if(!match)return;
    const prefix=match[1];const numStr=match[2].replace(/,/g,'');const suffix=match[3];
    const num=parseFloat(numStr);
    if(isNaN(num)||num===0)return;
    el.dataset.prefix=prefix;el.dataset.suffix=suffix;
    el.textContent=prefix+'0'+suffix;
    animateValue(el,0,num,800);
  });
})();

/* ── Alert badge polling (sidebar + topbar) ── */
(function(){
  function pollAlerts(){
    fetch('/api/alerts/count').then(r=>r.json()).then(d=>{
      const b=document.getElementById('alert-badge');
      const sb=document.getElementById('sidebar-alert-badge');
      const count=d.unread_count||0;
      if(b){if(count>0){b.textContent=count;b.style.display=''}else{b.style.display='none'}}
      if(sb){if(count>0){sb.textContent=count;sb.style.display=''}else{sb.style.display='none'}}
    }).catch(()=>{});
    setTimeout(pollAlerts,30000);
  }
  setTimeout(pollAlerts,2000);
})();

/* ── Keyboard nav: Enter on nav buttons ── */
document.querySelectorAll('.nav-btn').forEach(btn=>{
  btn.addEventListener('keydown',e=>{
    if(e.key==='Enter'||e.key===' '){e.preventDefault();btn.click()}
  });
});

/* ── Recent activity drawer ── */
const _raCv=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const _raCatColors={inventory:_raCv('--info'),auth:'#a78bfa',admin:_raCv('--warning'),scan:_raCv('--success'),'import':'#06b6d4','export':'#8b5cf6',alert:_raCv('--failure'),system:_raCv('--muted')};
function toggleRecentActivity(){
  const d=document.getElementById('ra-drawer');
  const o=document.getElementById('ra-overlay');
  const open=!d.classList.contains('open');
  d.classList.toggle('open',open);
  o.classList.toggle('open',open);
  if(open)loadRecentActivity();
}
function closeRecentActivity(){
  document.getElementById('ra-drawer').classList.remove('open');
  document.getElementById('ra-overlay').classList.remove('open');
}
function loadRecentActivity(){
  const list=document.getElementById('ra-list');
  fetch('/api/activity/recent?limit=25').then(r=>r.json()).then(d=>{
    if(!d.entries||!d.entries.length){
      list.innerHTML='<div class="ra-empty"><svg width="32" height="32" viewBox="0 0 20 20" fill="none" stroke="var(--muted)" stroke-width="1" style="margin-bottom:8px;opacity:.4"><path d="M10 2a8 8 0 100 16 8 8 0 000-16z"/><path d="M10 6v4l3 3"/></svg><div>No activity yet</div><div style="font-size:12px;margin-top:4px">Actions will appear here as they happen.</div></div>';
      return;
    }
    list.innerHTML=d.entries.map(e=>{
      const color=_raCatColors[e.category]||_raCatColors.system;
      const time=new Date(e.created_at);
      const ago=timeAgo(time);
      return `<div class="ra-item"><div class="ra-dot" style="background:${color}"></div><div class="ra-body"><div class="ra-action">${esc(e.action)}</div><div class="ra-summary">${esc(e.summary)}</div><div class="ra-meta">${esc(e.user_name)} &middot; ${ago}</div></div></div>`;
    }).join('');
  }).catch(()=>{list.innerHTML='<div class="ra-empty">Failed to load activity</div>'});
}
function timeAgo(d){
  const s=Math.floor((Date.now()-d.getTime())/1000);
  if(s<60)return 'just now';
  if(s<3600)return Math.floor(s/60)+'m ago';
  if(s<86400)return Math.floor(s/3600)+'h ago';
  if(s<604800)return Math.floor(s/86400)+'d ago';
  return d.toLocaleDateString();
}
document.addEventListener('keydown',e=>{
  if(e.key==='Escape'&&document.getElementById('ra-drawer').classList.contains('open'))closeRecentActivity();
});
</script>"""


# ── Navigation map ───────────────────────────────────────────────────

# Each entry: (section_label, [(icon_key, label, href, active_id), ...])
_NAV_SECTIONS: list[tuple[str, list[tuple[str, str, str, str]]]] = [
    ("Inventory", [
        ("scan", "Scan", "/scan", "scan"),
        ("scan-to-pdf", "Scan to PDF", "/scan-to-pdf", "scan-to-pdf"),
        ("items", "Items", "/inventory", "items"),
        ("calendar", "Calendar", "/calendar", "calendar"),
        ("new-item", "New Item", "/inventory/new", "new-item"),
        ("import", "Import CSV", "/inventory/bulk", "bulk-io"),
    ]),
    ("Monitor", [
        ("monitor", "Dashboard", "/", "monitor"),
        ("analytics", "Analytics", "/analytics", "analytics"),
        ("activity", "Activity Log", "/activity", "activity"),
        ("alerts", "Alerts", "/alerts", "alerts"),
    ]),
    ("AI", [
        ("ai-chat", "AI Chat", "/ai/chat", "ai-chat"),
        ("ai-privacy", "Privacy & Data", "/ai/privacy", "ai-privacy"),
        ("ai-settings", "AI Settings", "/ai/settings", "ai-settings"),
        ("ai-setup", "AI Setup", "/ai/setup", "ai-setup"),
    ]),
    ("System", [
        ("team", "Team", "/team", "team"),
        ("admin", "Admin Panel", "/admin", "admin"),
        ("feedback", "Help & Feedback", "/feedback", "feedback"),
    ]),
]


def _render_chat_fab() -> str:
    """Render a floating chat button + slide-out panel for quick AI chat."""
    return """
<style>
  .chat-fab { position: fixed; bottom: 24px; right: 24px; width: 56px; height: 56px; border-radius: 50%;
              background: var(--accent); color: #fff; border: none; cursor: pointer; z-index: 9000;
              box-shadow: 0 4px 16px rgba(0,0,0,.25); display: flex; align-items: center; justify-content: center;
              transition: transform .2s, box-shadow .2s; }
  .chat-fab:hover { transform: scale(1.08); box-shadow: 0 6px 20px rgba(0,0,0,.35); }
  .chat-fab svg { width: 26px; height: 26px; }
  .chat-panel { position: fixed; top: 0; right: -420px; width: 400px; height: 100vh; background: var(--bg);
                border-left: 1px solid var(--border); z-index: 9001; display: flex; flex-direction: column;
                transition: right .3s ease; box-shadow: -4px 0 24px rgba(0,0,0,.15); }
  .chat-panel.open { right: 0; }
  .chat-panel-header { padding: 14px 16px; border-bottom: 1px solid var(--border); display: flex;
                       justify-content: space-between; align-items: center; background: var(--surface); }
  .chat-panel-header h3 { margin: 0; font-size: 1rem; }
  .chat-panel-header button { background: none; border: none; cursor: pointer; color: var(--muted); font-size: 1.3rem; }
  .chat-panel-messages { flex: 1; overflow-y: auto; padding: 16px; }
  .chat-panel-messages .p-msg { margin-bottom: 12px; display: flex; }
  .chat-panel-messages .p-msg.user { justify-content: flex-end; }
  .chat-panel-messages .p-msg .p-bubble { max-width: 80%; padding: 10px 14px; border-radius: 14px;
                                          font-size: .88rem; line-height: 1.45; }
  .chat-panel-messages .p-msg.user .p-bubble { background: var(--accent); color: #fff; border-bottom-right-radius: 4px; }
  .chat-panel-messages .p-msg.assistant .p-bubble { background: var(--surface); border: 1px solid var(--border);
                                                    border-bottom-left-radius: 4px; }
  .chat-panel-input { padding: 12px; border-top: 1px solid var(--border); display: flex; gap: 8px; }
  .chat-panel-input input { flex: 1; padding: 10px 12px; border: 1px solid var(--border); border-radius: 10px;
                            font-size: .88rem; background: var(--surface); color: var(--text); }
  .chat-panel-input button { padding: 10px 16px; border: none; border-radius: 10px; background: var(--accent);
                             color: #fff; font-weight: 600; cursor: pointer; font-size: .85rem; }
  .p-typing { display: none; margin-bottom: 12px; }
  .p-typing.show { display: flex; }
  .p-typing .p-bubble { background: var(--surface); border: 1px solid var(--border); padding: 10px 16px;
                        border-radius: 14px; border-bottom-left-radius: 4px; }
  .p-dots span { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: var(--muted);
                 margin: 0 2px; animation: pdot .8s infinite; }
  .p-dots span:nth-child(2) { animation-delay: .15s; }
  .p-dots span:nth-child(3) { animation-delay: .3s; }
  @keyframes pdot { 0%,60%,100%{transform:translateY(0)} 30%{transform:translateY(-3px)} }
  @media (max-width: 480px) { .chat-panel { width: 100vw; right: -100vw; } }
</style>
<button class="chat-fab" id="chatFab" onclick="toggleChatPanel()" title="AI Chat">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
  </svg>
</button>
<div class="chat-panel" id="chatPanel">
  <div class="chat-panel-header">
    <h3>BarcodeBuddy AI</h3>
    <div>
      <button onclick="window.location.href='/ai/chat'" title="Full page">&#8599;</button>
      <button onclick="toggleChatPanel()" title="Close">&times;</button>
    </div>
  </div>
  <div class="chat-panel-messages" id="panelMessages">
    <div class="p-typing" id="panelTyping">
      <div class="p-bubble"><div class="p-dots"><span></span><span></span><span></span></div></div>
    </div>
  </div>
  <div class="chat-panel-input">
    <input type="text" id="panelInput" placeholder="Ask anything..."
           onkeydown="if(event.key==='Enter'){event.preventDefault();panelSend();}" maxlength="2000" />
    <button onclick="panelSend()">Send</button>
  </div>
</div>
<script>
(function(){
  let panelConvoId = '';
  let panelSending = false;
  window.toggleChatPanel = function() {
    document.getElementById('chatPanel').classList.toggle('open');
    if (document.getElementById('chatPanel').classList.contains('open'))
      document.getElementById('panelInput').focus();
  };
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') document.getElementById('chatPanel').classList.remove('open');
  });
  function panelAddMsg(role, text) {
    const c = document.getElementById('panelMessages');
    const t = document.getElementById('panelTyping');
    const d = document.createElement('div');
    d.className = 'p-msg ' + role;
    let s = (typeof esc === 'function') ? esc(text) : text.replace(/&/g,'&amp;').replace(/</g,'&lt;');
    s = s.replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>');
    s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
    s = s.replace(/\\n/g, '<br>');
    d.innerHTML = '<div class="p-bubble">' + s + '</div>';
    c.insertBefore(d, t);
    c.scrollTop = c.scrollHeight;
  }
  window.panelSend = async function() {
    if (panelSending) return;
    const inp = document.getElementById('panelInput');
    const text = inp.value.trim();
    if (!text) return;
    inp.value = '';
    panelAddMsg('user', text);
    panelSending = true;
    document.getElementById('panelTyping').classList.add('show');
    const r = await apiCall('POST', '/ai/api/chat', {conversation_id: panelConvoId, message: text});
    document.getElementById('panelTyping').classList.remove('show');
    panelSending = false;
    if (r.ok) {
      panelConvoId = r.data.conversation_id;
      panelAddMsg('assistant', r.data.message.content);
    } else {
      panelAddMsg('assistant', 'Error: ' + (r.data?.error || 'Something went wrong'));
    }
    inp.focus();
  };
})();
</script>
"""


def render_shell(
    *,
    title: str,
    active_nav: str,
    body_html: str,
    body_js: str = "",
    display_name: str = "User",
    role: str = "user",
    head_extra: str = "",
    ai_enabled: bool = False,
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
    ai_enabled:  Whether AI features are enabled (shows floating chat FAB).
    """
    is_admin = role in ("admin", "owner")

    # Build sidebar nav sections
    nav_html_parts: list[str] = []
    chevron_svg = (
        '<svg class="section-chevron" viewBox="0 0 16 16" fill="none" stroke="currentColor"'
        ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="4 6 8 10 12 6"/></svg>'
    )
    _admin_only_nav = {"admin", "ai-settings", "ai-setup"}  # nav items restricted to admin/owner
    for section_label, items in _NAV_SECTIONS:
        filtered = [
            (ik, lb, hr, aid) for ik, lb, hr, aid in items
            if aid not in _admin_only_nav or is_admin
        ]
        if not filtered:
            continue
        section_id = section_label.lower().replace(" ", "-")
        section_items = "\n".join(
            _nav_item(icon_key, label, href, active_id == active_nav)
            for icon_key, label, href, active_id in filtered
        )
        nav_html_parts.append(
            f'<div class="nav-section" data-section="{_E(section_id)}">'
            f'<div class="nav-section-label" role="button" tabindex="0"'
            f' aria-expanded="true" onclick="toggleNavSection(this)"'
            f' onkeydown="if(event.key===\'Enter\'||event.key===\' \'){{event.preventDefault();toggleNavSection(this)}}">'
            f'<span>{_E(section_label)}</span>{chevron_svg}</div>'
            f'<div class="nav-section-items" role="menu">{section_items}</div></div>'
        )
    nav_html = "\n".join(nav_html_parts)

    # Build breadcrumbs
    breadcrumb_section = ""
    breadcrumb_page = ""
    for section_label, items in _NAV_SECTIONS:
        for _, label, _, active_id in items:
            if active_id == active_nav:
                breadcrumb_section = section_label
                breadcrumb_page = label
                break
        if breadcrumb_page:
            break

    user_html = _user_section(display_name, role, is_admin)

    breadcrumb_html = ""
    if breadcrumb_section and breadcrumb_page:
        breadcrumb_html = (
            f'<nav class="breadcrumbs" aria-label="Breadcrumb">'
            f'<a href="/">Home</a>'
            f'<span class="bc-sep" aria-hidden="true">/</span>'
            f'<span>{_E(breadcrumb_section)}</span>'
            f'<span class="bc-sep" aria-hidden="true">/</span>'
            f'<span class="bc-current" aria-current="page">{_E(breadcrumb_page)}</span>'
            f'</nav>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script>try{{const t=localStorage.getItem('bb_theme');if(t)document.documentElement.setAttribute('data-theme',t)}}catch(e){{}}</script>
  <title>{_E(title)} - BarcodeBuddy</title>
  {_LAYOUT_CSS}
  {head_extra}
</head>
<body>
  <a href="#main-content" class="skip-link">Skip to content</a>

  <!-- Mobile hamburger -->
  <button class="hamburger" id="hamburger-btn" aria-label="Open navigation menu" aria-expanded="false"
    onclick="toggleMobileMenu()">
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="3" y1="5" x2="17" y2="5"/><line x1="3" y1="10" x2="17" y2="10"/><line x1="3" y1="15" x2="17" y2="15"/></svg>
  </button>
  <div class="sidebar-overlay" id="sidebar-overlay" onclick="closeMobileMenu()"></div>

  <nav class="sidebar" id="sidebar" role="navigation" aria-label="Main navigation">
    <div class="sidebar-brand">
      <div class="sidebar-brand-text">
        <h1>BarcodeBuddy</h1>
        <div class="brand-sub">Inventory Management</div>
      </div>
      <button class="sidebar-toggle" id="sidebar-collapse-btn" aria-label="Collapse sidebar"
        onclick="toggleSidebarCollapse()">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor"
          stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="10 3 5 8 10 13"/>
        </svg>
      </button>
    </div>
    <div class="sidebar-nav" id="sidebar-nav">
      {nav_html}
    </div>
    {user_html}
    <div class="sidebar-footer">BarcodeBuddy v3.0.0</div>
  </nav>

  <div class="main">
    <header class="topbar">
      <div class="topbar-left">
        <div>
          <div class="topbar-title">{_E(title)}</div>
          {breadcrumb_html}
        </div>
      </div>
      <div class="topbar-meta" style="display:flex;align-items:center;gap:12px;">
        <button class="cmd-palette-trigger" id="cmd-trigger" onclick="openCmdPalette()"
          aria-label="Open command palette (Ctrl+K)">
          <svg width="14" height="14" viewBox="0 0 20 20" fill="none" stroke="currentColor"
            stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="9" cy="9" r="6"/><line x1="13.5" y1="13.5" x2="18" y2="18"/>
          </svg>
          <span>Navigate...</span>
          <kbd>Ctrl K</kbd>
        </button>
        <button class="theme-toggle" id="theme-toggle" aria-label="Toggle dark mode" title="Toggle dark mode"
          onclick="toggleTheme()">
          <svg id="theme-icon-sun" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"
            stroke-linecap="round" stroke-linejoin="round" style="display:none">
            <circle cx="10" cy="10" r="4"/><path d="M10 2v2"/><path d="M10 16v2"/>
            <path d="M3.5 3.5l1.4 1.4"/><path d="M15.1 15.1l1.4 1.4"/>
            <path d="M2 10h2"/><path d="M16 10h2"/>
            <path d="M3.5 16.5l1.4-1.4"/><path d="M15.1 4.9l1.4-1.4"/>
          </svg>
          <svg id="theme-icon-moon" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"
            stroke-linecap="round" stroke-linejoin="round">
            <path d="M17 12.5A7 7 0 117.5 3a5.5 5.5 0 009.5 9.5z"/>
          </svg>
        </button>
        <button id="recent-activity-btn" aria-label="Recent activity" title="Recent Activity"
          onclick="toggleRecentActivity()"
          style="position:relative;color:var(--muted);background:none;border:none;cursor:pointer;display:flex;align-items:center;transition:color .2s;padding:0"
          onmouseover="this.style.color='var(--text)'" onmouseout="this.style.color='var(--muted)'">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M10 2a8 8 0 100 16 8 8 0 000-16z"/><path d="M10 6v4l3 3"/>
          </svg>
        </button>
        <a href="/alerts" id="alert-bell" aria-label="View alerts" style="position:relative;color:var(--muted);text-decoration:none;display:flex;align-items:center;transition:color .2s" onmouseover="this.style.color='var(--text)'" onmouseout="this.style.color='var(--muted)'">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M10 2a6 6 0 00-6 6c0 3-1.5 5-2 6h16c-.5-1-2-3-2-6a6 6 0 00-6-6z"/><path d="M8 16a2 2 0 004 0"/>
          </svg>
          <span id="alert-badge" style="display:none;position:absolute;top:-4px;right:-6px;background:var(--failure);color:#fff;font-size:10px;font-weight:700;min-width:16px;height:16px;border-radius:999px;text-align:center;line-height:16px;padding:0 4px" aria-live="polite"></span>
        </a>
      </div>
    </header>
    <div class="content" id="main-content">
      {body_html}
    </div>
  </div>

  <!-- Recent activity drawer -->
  <div class="ra-overlay" id="ra-overlay" onclick="closeRecentActivity()"></div>
  <div class="ra-drawer" id="ra-drawer">
    <div class="ra-header">
      <div style="display:flex;align-items:center;gap:8px">
        <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2a8 8 0 100 16 8 8 0 000-16z"/><path d="M10 6v4l3 3"/></svg>
        <span style="font-weight:700;font-size:15px;">Recent Activity</span>
      </div>
      <div style="display:flex;gap:8px;align-items:center">
        <a href="/activity" style="font-size:12px;color:var(--info);text-decoration:none;font-weight:600" onclick="closeRecentActivity()">View All</a>
        <button onclick="closeRecentActivity()" style="background:none;border:none;cursor:pointer;color:var(--muted);padding:2px" aria-label="Close">
          <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="5" y1="5" x2="15" y2="15"/><line x1="15" y1="5" x2="5" y2="15"/></svg>
        </button>
      </div>
    </div>
    <div class="ra-list" id="ra-list"><div style="padding:16px;display:flex;flex-direction:column;gap:12px"><div class="skeleton skeleton-row"></div><div class="skeleton skeleton-row"></div><div class="skeleton skeleton-row"></div><div class="skeleton skeleton-row"></div></div></div>
  </div>

  <!-- Command palette -->
  <div class="cmd-overlay" id="cmd-overlay" onclick="if(event.target===this)closeCmdPalette()">
    <div class="cmd-dialog" role="dialog" aria-label="Command palette">
      <div class="cmd-input-wrap">
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="9" cy="9" r="6"/><line x1="13.5" y1="13.5" x2="18" y2="18"/>
        </svg>
        <input class="cmd-input" id="cmd-input" type="text" placeholder="Search pages..."
          autocomplete="off" spellcheck="false" aria-label="Search pages">
      </div>
      <div class="cmd-results" id="cmd-results" role="listbox"></div>
      <div class="cmd-footer">
        <span><kbd>&uarr;&darr;</kbd> navigate</span>
        <span><kbd>Enter</kbd> open</span>
        <span><kbd>Esc</kbd> close</span>
      </div>
    </div>
  </div>

  <div class="toast-container" id="toast-container"></div>
  {_render_chat_fab() if ai_enabled else ""}
  {_LAYOUT_JS}
  {body_js}
</body>
</html>"""
