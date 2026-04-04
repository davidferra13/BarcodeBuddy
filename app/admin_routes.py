"""Admin dashboard routes for user management and system overview."""

from __future__ import annotations

import html as html_mod

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import User, UserSession, get_db

router = APIRouter(prefix="/admin", tags=["admin"])


class UpdateRoleRequest(BaseModel):
    role: str = Field(pattern="^(admin|user)$")


class UpdateActiveRequest(BaseModel):
    is_active: bool


# --- API Endpoints ---

@router.get("/api/users")
def list_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> JSONResponse:
    users = db.query(User).order_by(User.created_at.desc()).all()
    return JSONResponse(content={"users": [u.to_dict() for u in users]})


@router.put("/api/users/{user_id}/role")
def update_user_role(
    user_id: str,
    body: UpdateRoleRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> JSONResponse:
    if user_id == admin.id:
        return JSONResponse(status_code=400, content={"error": "Cannot change your own role"})
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return JSONResponse(status_code=404, content={"error": "User not found"})
    user.role = body.role
    db.commit()
    return JSONResponse(content={"user": user.to_dict()})


@router.put("/api/users/{user_id}/active")
def update_user_active(
    user_id: str,
    body: UpdateActiveRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> JSONResponse:
    if user_id == admin.id:
        return JSONResponse(status_code=400, content={"error": "Cannot deactivate yourself"})
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return JSONResponse(status_code=404, content={"error": "User not found"})
    user.is_active = body.is_active
    db.commit()
    if not body.is_active:
        # Revoke all active sessions for deactivated user
        db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_revoked == False,
        ).update({"is_revoked": True})
        db.commit()
    return JSONResponse(content={"user": user.to_dict()})


@router.delete("/api/users/{user_id}")
def delete_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> JSONResponse:
    if user_id == admin.id:
        return JSONResponse(status_code=400, content={"error": "Cannot delete yourself"})
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return JSONResponse(status_code=404, content={"error": "User not found"})
    db.delete(user)
    db.commit()
    return JSONResponse(content={"message": "User deleted"})


# --- HTML Dashboard ---

@router.get("", response_class=HTMLResponse)
def admin_dashboard(admin: User = Depends(require_admin)) -> HTMLResponse:
    return HTMLResponse(content=_render_admin_html(admin))


def _render_admin_html(admin: User) -> str:
    admin_name = html_mod.escape(admin.display_name)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Admin - Barcode Buddy</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0f172a; color: #e2e8f0; padding: 24px;
  }}
  .topbar {{
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 32px; padding-bottom: 16px; border-bottom: 1px solid #1e293b;
  }}
  .topbar h1 {{ font-size: 22px; color: #f8fafc; }}
  .topbar .nav {{ display: flex; gap: 16px; align-items: center; }}
  .topbar a {{
    color: #60a5fa; text-decoration: none; font-size: 14px;
  }}
  .topbar a:hover {{ text-decoration: underline; }}
  .topbar .admin-badge {{
    background: #7c3aed; color: #fff; padding: 4px 10px;
    border-radius: 6px; font-size: 12px; font-weight: 600;
  }}
  .section {{ margin-bottom: 32px; }}
  .section h2 {{
    font-size: 16px; font-weight: 600; color: #94a3b8;
    text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 16px;
  }}
  .card {{
    background: #1e293b; border-radius: 10px; padding: 20px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.2);
  }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{
    text-align: left; font-size: 12px; font-weight: 600;
    color: #64748b; text-transform: uppercase; letter-spacing: 0.5px;
    padding: 10px 12px; border-bottom: 1px solid #334155;
  }}
  td {{
    padding: 12px; border-bottom: 1px solid #1e293b; font-size: 14px;
  }}
  tr:hover td {{ background: #0f172a; }}
  .role-badge {{
    display: inline-block; padding: 3px 10px; border-radius: 6px;
    font-size: 12px; font-weight: 600;
  }}
  .role-admin {{ background: #7c3aed33; color: #a78bfa; }}
  .role-user {{ background: #3b82f633; color: #93c5fd; }}
  .status-active {{ color: #4ade80; }}
  .status-inactive {{ color: #f87171; }}
  .action-btn {{
    padding: 5px 12px; border-radius: 6px; border: 1px solid #334155;
    background: transparent; color: #94a3b8; font-size: 12px;
    cursor: pointer; transition: all 0.2s; margin: 0 2px;
  }}
  .action-btn:hover {{ background: #334155; color: #f8fafc; }}
  .action-btn.danger {{ border-color: #7f1d1d; color: #f87171; }}
  .action-btn.danger:hover {{ background: #7f1d1d; color: #fca5a5; }}
  .stats-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px; margin-bottom: 24px;
  }}
  .stat-card {{
    background: #1e293b; border-radius: 10px; padding: 20px; text-align: center;
  }}
  .stat-card .value {{ font-size: 32px; font-weight: 700; color: #f8fafc; }}
  .stat-card .label {{ font-size: 12px; color: #64748b; margin-top: 4px; text-transform: uppercase; }}
  #loading {{ text-align: center; padding: 40px; color: #64748b; }}
</style>
</head>
<body>
<div class="topbar">
  <h1>Admin Dashboard</h1>
  <div class="nav">
    <a href="/">Stats Dashboard</a>
    <span class="admin-badge">{admin_name}</span>
    <a href="#" onclick="logout()">Logout</a>
  </div>
</div>

<div class="stats-grid" id="stats-grid">
  <div class="stat-card"><div class="value" id="total-users">-</div><div class="label">Total Users</div></div>
  <div class="stat-card"><div class="value" id="active-users">-</div><div class="label">Active</div></div>
  <div class="stat-card"><div class="value" id="admin-count">-</div><div class="label">Admins</div></div>
  <div class="stat-card"><div class="value" id="user-count">-</div><div class="label">Users</div></div>
</div>

<div class="section">
  <h2>User Management</h2>
  <div class="card">
    <div id="loading">Loading users...</div>
    <table id="users-table" style="display:none">
      <thead><tr>
        <th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Created</th><th>Actions</th>
      </tr></thead>
      <tbody id="users-body"></tbody>
    </table>
  </div>
</div>

<script>
const ADMIN_ID = '{admin.id}';

async function loadUsers() {{
  const resp = await fetch('/admin/api/users');
  const data = await resp.json();
  renderUsers(data.users);
}}

function renderUsers(users) {{
  const tbody = document.getElementById('users-body');
  const table = document.getElementById('users-table');
  document.getElementById('loading').style.display = 'none';
  table.style.display = 'table';

  document.getElementById('total-users').textContent = users.length;
  document.getElementById('active-users').textContent = users.filter(u => u.is_active).length;
  document.getElementById('admin-count').textContent = users.filter(u => u.role === 'admin').length;
  document.getElementById('user-count').textContent = users.filter(u => u.role === 'user').length;

  tbody.innerHTML = users.map(u => `
    <tr>
      <td>${{esc(u.display_name)}}</td>
      <td>${{esc(u.email)}}</td>
      <td><span class="role-badge role-${{u.role}}">${{u.role}}</span></td>
      <td><span class="${{u.is_active ? 'status-active' : 'status-inactive'}}">${{u.is_active ? 'Active' : 'Inactive'}}</span></td>
      <td>${{new Date(u.created_at).toLocaleDateString()}}</td>
      <td>${{u.id === ADMIN_ID ? '<span style="color:#64748b;font-size:12px">Current user</span>' :
        `<button class="action-btn" onclick="toggleRole('${{u.id}}','${{u.role}}')">${{u.role === 'admin' ? 'Demote' : 'Promote'}}</button>
         <button class="action-btn" onclick="toggleActive('${{u.id}}', ${{u.is_active}})">${{u.is_active ? 'Deactivate' : 'Activate'}}</button>
         <button class="action-btn danger" onclick="deleteUser('${{u.id}}','${{esc(u.email)}}')">Delete</button>`
      }}</td>
    </tr>
  `).join('');
}}

function esc(s) {{ const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }}

async function toggleRole(id, current) {{
  const newRole = current === 'admin' ? 'user' : 'admin';
  await fetch(`/admin/api/users/${{id}}/role`, {{
    method: 'PUT', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{role: newRole}})
  }});
  loadUsers();
}}

async function toggleActive(id, current) {{
  await fetch(`/admin/api/users/${{id}}/active`, {{
    method: 'PUT', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{is_active: !current}})
  }});
  loadUsers();
}}

async function deleteUser(id, email) {{
  if (!confirm(`Delete user ${{email}}? This cannot be undone.`)) return;
  await fetch(`/admin/api/users/${{id}}`, {{method: 'DELETE'}});
  loadUsers();
}}

async function logout() {{
  await fetch('/auth/api/logout', {{method: 'POST'}});
  window.location.href = '/auth/login';
}}

loadUsers();
</script>
</body></html>"""
