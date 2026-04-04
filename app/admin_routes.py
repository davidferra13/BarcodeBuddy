"""Admin dashboard routes for user management and system overview."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import User, UserSession, get_db
from app.layout import render_shell

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
    body = """
<p class="page-desc">Manage user accounts, roles, and access permissions.</p>

<div class="stats-grid" id="stats-grid">
  <div class="stat-card"><div class="value" id="total-users">-</div><div class="label">Total Users</div></div>
  <div class="stat-card"><div class="value" id="active-users">-</div><div class="label">Active</div></div>
  <div class="stat-card"><div class="value" id="admin-count">-</div><div class="label">Admins</div></div>
  <div class="stat-card"><div class="value" id="user-count">-</div><div class="label">Users</div></div>
</div>

<div class="panel">
  <div class="form-section-title" style="margin-bottom:12px">User Management</div>
  <div id="loading" class="empty" style="padding:30px">Loading users...</div>
  <div style="overflow-x:auto">
    <table id="users-table" style="display:none">
      <thead><tr>
        <th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Created</th><th>Actions</th>
      </tr></thead>
      <tbody id="users-body"></tbody>
    </table>
  </div>
</div>"""

    js = f"""<script>
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
      <td>${{u.id === ADMIN_ID ? '<span style="color:var(--muted);font-size:12px">Current user</span>' :
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
  const r = await fetch(`/admin/api/users/${{id}}/role`, {{
    method: 'PUT', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{role: newRole}})
  }});
  if (r.ok) {{ toast('Role updated to ' + newRole, 'success'); }} else {{ const d = await r.json(); toast(d.error || 'Failed to update role', 'error'); }}
  loadUsers();
}}

async function toggleActive(id, current) {{
  const r = await fetch(`/admin/api/users/${{id}}/active`, {{
    method: 'PUT', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{is_active: !current}})
  }});
  if (r.ok) {{ toast(current ? 'User deactivated' : 'User activated', 'success'); }} else {{ const d = await r.json(); toast(d.error || 'Failed to update status', 'error'); }}
  loadUsers();
}}

async function deleteUser(id, email) {{
  if (!confirm(`Delete user ${{email}}? This cannot be undone.`)) return;
  const r = await fetch(`/admin/api/users/${{id}}`, {{method: 'DELETE'}});
  if (r.ok) {{ toast('User deleted', 'success'); }} else {{ toast('Failed to delete user', 'error'); }}
  loadUsers();
}}

loadUsers();
</script>"""

    return HTMLResponse(content=render_shell(
        title="Admin Panel",
        active_nav="admin",
        body_html=body,
        body_js=js,
        display_name=admin.display_name,
        role=admin.role,
    ))
