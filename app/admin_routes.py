"""Admin dashboard routes for user management and system overview."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import (
    ASSIGNABLE_ROLES,
    ROLE_LEVELS,
    get_role_level,
    hash_password,
    log_audit,
    require_admin,
    require_owner,
)
from app.activity import log_activity
from app.database import AuditLog, SystemSettings, User, UserSession, get_db
from app.layout import render_shell

router = APIRouter(prefix="/admin", tags=["admin"])


class UpdateRoleRequest(BaseModel):
    role: str = Field(pattern="^(admin|manager|user)$")


class UpdateActiveRequest(BaseModel):
    is_active: bool


class TransferOwnershipRequest(BaseModel):
    target_user_id: str


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


class UpdateSignupRequest(BaseModel):
    open_signup: bool


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

    # Owner cannot be modified via this endpoint
    if user.role == "owner":
        return JSONResponse(status_code=403, content={"error": "Cannot modify the owner account"})

    # Only owner can promote to admin
    if body.role == "admin" and admin.role != "owner":
        return JSONResponse(status_code=403, content={"error": "Only the owner can promote users to admin"})

    # Prevent demoting if it would leave zero admin+ accounts
    if user.role == "admin" and body.role != "admin":
        admin_count = db.query(User).filter(
            User.role.in_(("owner", "admin")), User.is_active == True
        ).count()
        if admin_count <= 1:
            return JSONResponse(status_code=400, content={"error": "Cannot demote: this is the last administrator"})

    old_role = user.role
    user.role = body.role
    db.commit()
    log_audit(db, admin, "role_change", target_id=user.id, detail={"from": old_role, "to": body.role, "email": user.email})
    log_activity(db, user=admin, action="Role Changed", category="admin",
                 summary=f"{user.display_name} ({user.email}): {old_role} → {body.role}",
                 detail={"target": user.email, "from": old_role, "to": body.role})
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

    # Owner cannot be deactivated
    if user.role == "owner":
        return JSONResponse(status_code=403, content={"error": "Cannot deactivate the owner account"})

    # Non-owner admins cannot deactivate other admins
    if user.role == "admin" and admin.role != "owner":
        return JSONResponse(status_code=403, content={"error": "Only the owner can deactivate admin accounts"})

    user.is_active = body.is_active
    db.commit()
    if not body.is_active:
        db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_revoked == False,
        ).update({"is_revoked": True})
        db.commit()
    action = "deactivate_user" if not body.is_active else "activate_user"
    log_audit(db, admin, action, target_id=user.id, detail={"email": user.email})
    label = "User Deactivated" if not body.is_active else "User Activated"
    log_activity(db, user=admin, action=label, category="admin",
                 summary=f"{user.display_name} ({user.email})",
                 detail={"email": user.email})
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

    # Owner cannot be deleted
    if user.role == "owner":
        return JSONResponse(status_code=403, content={"error": "Cannot delete the owner account"})

    # Non-owner admins cannot delete other admins
    if user.role == "admin" and admin.role != "owner":
        return JSONResponse(status_code=403, content={"error": "Only the owner can delete admin accounts"})

    email = user.email
    display = user.display_name
    db.delete(user)
    db.commit()
    log_audit(db, admin, "delete_user", target_id=user_id, detail={"email": email})
    log_activity(db, user=admin, action="User Deleted", category="admin",
                 summary=f"{display} ({email})",
                 detail={"email": email})
    return JSONResponse(content={"message": "User deleted"})


# --- Admin Password Reset (admin+) ---

@router.put("/api/users/{user_id}/password")
def admin_reset_password(
    user_id: str,
    body: ResetPasswordRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Allow admins to reset a user's password directly."""
    if user_id == admin.id:
        return JSONResponse(status_code=400, content={"error": "Use your account settings to change your own password"})
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return JSONResponse(status_code=404, content={"error": "User not found"})

    # Only owner can reset admin/owner passwords
    if user.role in ("owner", "admin") and admin.role != "owner":
        return JSONResponse(status_code=403, content={"error": "Only the owner can reset admin passwords"})

    user.password_hash = hash_password(body.new_password)
    # Revoke all existing sessions so user must log in with new password
    db.query(UserSession).filter(
        UserSession.user_id == user_id,
        UserSession.is_revoked == False,
    ).update({"is_revoked": True})
    db.commit()
    log_audit(db, admin, "admin_reset_password", target_id=user.id, detail={"email": user.email})
    log_activity(db, user=admin, action="Admin Password Reset", category="admin",
                 summary=f"Reset password for {user.display_name} ({user.email})",
                 detail={"email": user.email})
    return JSONResponse(content={"message": f"Password reset for {user.email}"})


# --- Ownership Transfer (owner-only) ---

@router.post("/api/transfer-ownership")
def transfer_ownership(
    body: TransferOwnershipRequest,
    owner: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> JSONResponse:
    if body.target_user_id == owner.id:
        return JSONResponse(status_code=400, content={"error": "You are already the owner"})
    target = db.query(User).filter(User.id == body.target_user_id, User.is_active == True).first()
    if not target:
        return JSONResponse(status_code=404, content={"error": "Target user not found or inactive"})
    old_owner_id = owner.id
    target.role = "owner"
    owner.role = "admin"
    db.commit()
    log_audit(db, owner, "transfer_ownership", target_id=target.id, detail={
        "from": old_owner_id, "to": target.id, "target_email": target.email,
    })
    log_activity(db, user=owner, action="Ownership Transferred", category="admin",
                 summary=f"Transferred ownership to {target.display_name} ({target.email})",
                 detail={"to_email": target.email})
    return JSONResponse(content={"message": f"Ownership transferred to {target.display_name}", "user": target.to_dict()})


# --- System Settings (admin+) ---

@router.get("/api/settings")
def get_settings(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> JSONResponse:
    settings = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
    return JSONResponse(content={"open_signup": settings.open_signup if settings else True})


@router.put("/api/settings/signup")
def update_signup_setting(
    body: UpdateSignupRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> JSONResponse:
    settings = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
    if settings:
        settings.open_signup = body.open_signup
        db.commit()
    log_audit(db, admin, "update_signup", detail={"open_signup": body.open_signup})
    state = "enabled" if body.open_signup else "disabled"
    log_activity(db, user=admin, action="Signup Setting Changed", category="admin",
                 summary=f"Open signup {state}",
                 detail={"open_signup": body.open_signup})
    return JSONResponse(content={"open_signup": body.open_signup})


# --- Audit Log (admin+) ---

@router.get("/api/audit-log")
def get_audit_log(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> JSONResponse:
    entries = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(100).all()
    # Resolve actor names
    actor_ids = {e.actor_id for e in entries if e.actor_id}
    actors = {u.id: u.display_name for u in db.query(User).filter(User.id.in_(actor_ids)).all()} if actor_ids else {}
    result = []
    for e in entries:
        result.append({
            "id": e.id,
            "actor": actors.get(e.actor_id, "Unknown"),
            "action": e.action,
            "target_id": e.target_id,
            "detail": e.detail,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        })
    return JSONResponse(content={"entries": result})


# --- HTML Dashboard ---

@router.get("", response_class=HTMLResponse)
def admin_dashboard(admin: User = Depends(require_admin)) -> HTMLResponse:
    is_owner = admin.role == "owner"
    body = """
<p class="page-desc">Manage user accounts, roles, and access permissions.</p>

<div class="stats-grid" id="stats-grid">
  <div class="stat-card"><div class="value" id="total-users">-</div><div class="label">Total Users</div></div>
  <div class="stat-card"><div class="value" id="active-users">-</div><div class="label">Active</div></div>
  <div class="stat-card"><div class="value" id="admin-count">-</div><div class="label">Admins</div></div>
  <div class="stat-card"><div class="value" id="user-count">-</div><div class="label">Users</div></div>
</div>

<div class="panel">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;flex-wrap:wrap;gap:8px">
    <div class="form-section-title" style="margin:0">User Management</div>
    <div style="display:flex;gap:8px;align-items:center">
      <label style="font-size:12px;color:var(--muted);display:flex;align-items:center;gap:6px;cursor:pointer">
        <input type="checkbox" id="signup-toggle" onchange="toggleSignup(this.checked)" style="accent-color:var(--sidebar-accent)">
        Open signup
      </label>
    </div>
  </div>
  <div id="loading" style="padding:16px;display:flex;flex-direction:column;gap:6px"><div class="skeleton skeleton-row"></div><div class="skeleton skeleton-row"></div><div class="skeleton skeleton-row"></div><div class="skeleton skeleton-row"></div></div>
  <div style="overflow-x:auto">
    <table id="users-table" style="display:none">
      <thead><tr>
        <th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Created</th><th>Actions</th>
      </tr></thead>
      <tbody id="users-body"></tbody>
    </table>
  </div>
</div>

<div class="panel" style="margin-top:16px">
  <div class="form-section-title" style="margin-bottom:12px">Audit Log</div>
  <div id="audit-loading" style="padding:16px;display:flex;flex-direction:column;gap:6px"><div class="skeleton skeleton-row"></div><div class="skeleton skeleton-row"></div><div class="skeleton skeleton-row"></div></div>
  <div style="overflow-x:auto">
    <table id="audit-table" style="display:none">
      <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Detail</th></tr></thead>
      <tbody id="audit-body"></tbody>
    </table>
  </div>
</div>"""

    js = f"""<script>
const ADMIN_ID = '{admin.id}';
const IS_OWNER = {'true' if is_owner else 'false'};
const ROLE_ORDER = ['owner','admin','manager','user'];

async function loadUsers() {{
  const resp = await fetch('/admin/api/users');
  const data = await resp.json();
  renderUsers(data.users);
}}

async function loadSettings() {{
  const resp = await fetch('/admin/api/settings');
  const data = await resp.json();
  document.getElementById('signup-toggle').checked = data.open_signup;
}}

async function loadAuditLog() {{
  const resp = await fetch('/admin/api/audit-log');
  const data = await resp.json();
  renderAudit(data.entries);
}}

function renderUsers(users) {{
  const tbody = document.getElementById('users-body');
  const table = document.getElementById('users-table');
  document.getElementById('loading').style.display = 'none';
  table.style.display = 'table';

  document.getElementById('total-users').textContent = users.length;
  document.getElementById('active-users').textContent = users.filter(u => u.is_active).length;
  document.getElementById('admin-count').textContent = users.filter(u => u.role === 'admin' || u.role === 'owner').length;
  document.getElementById('user-count').textContent = users.filter(u => u.role === 'user' || u.role === 'manager').length;

  tbody.innerHTML = users.map(u => `
    <tr>
      <td>${{esc(u.display_name)}}</td>
      <td>${{esc(u.email)}}</td>
      <td><span class="role-badge role-${{u.role}}">${{u.role}}</span></td>
      <td><span class="${{u.is_active ? 'status-active' : 'status-inactive'}}">${{u.is_active ? 'Active' : 'Inactive'}}</span></td>
      <td>${{new Date(u.created_at).toLocaleDateString()}}</td>
      <td>${{renderActions(u)}}</td>
    </tr>
  `).join('');
}}

function renderActions(u) {{
  if (u.id === ADMIN_ID) return '<span style="color:var(--muted);font-size:12px">You</span>';
  if (u.role === 'owner') return '<span style="color:var(--muted);font-size:12px">Owner</span>';
  let btns = '';
  // Role selector
  const roles = IS_OWNER ? ['admin','manager','user'] : ['manager','user'];
  btns += `<select class="action-btn" onchange="changeRole('${{u.id}}',this.value)" style="padding:4px 8px;font-size:12px">`;
  for (const r of roles) {{
    btns += `<option value="${{r}}" ${{u.role===r?'selected':''}}>${{r}}</option>`;
  }}
  btns += '</select> ';
  btns += `<button class="action-btn" onclick="toggleActive('${{u.id}}', ${{u.is_active}})">${{u.is_active ? 'Deactivate' : 'Activate'}}</button> `;
  btns += `<button class="action-btn" onclick="resetPassword('${{u.id}}','${{esc(u.email)}}')">Reset&nbsp;PW</button> `;
  btns += `<button class="action-btn danger" onclick="deleteUser('${{u.id}}','${{esc(u.email)}}')">Delete</button>`;
  if (IS_OWNER) {{
    btns += ` <button class="action-btn" onclick="transferOwnership('${{u.id}}','${{esc(u.display_name)}}')" style="color:#d97706">Transfer&nbsp;Ownership</button>`;
  }}
  return btns;
}}

function renderAudit(entries) {{
  document.getElementById('audit-loading').style.display = 'none';
  const table = document.getElementById('audit-table');
  const tbody = document.getElementById('audit-body');
  table.style.display = 'table';
  if (!entries.length) {{
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--muted)">No audit entries yet</td></tr>';
    return;
  }}
  tbody.innerHTML = entries.slice(0, 50).map(e => {{
    let detail = '';
    try {{ const d = JSON.parse(e.detail); detail = Object.entries(d).map(([k,v])=>`${{k}}=${{v}}`).join(', '); }} catch(_) {{ detail = e.detail; }}
    return `<tr>
      <td style="white-space:nowrap">${{new Date(e.created_at).toLocaleString()}}</td>
      <td>${{esc(e.actor)}}</td>
      <td><code style="font-size:12px">${{esc(e.action)}}</code></td>
      <td style="font-size:12px;max-width:300px;overflow:hidden;text-overflow:ellipsis">${{esc(detail)}}</td>
    </tr>`;
  }}).join('');
}}

function esc(s) {{ const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }}

async function changeRole(id, newRole) {{
  const r = await fetch(`/admin/api/users/${{id}}/role`, {{
    method: 'PUT', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{role: newRole}})
  }});
  if (r.ok) {{ toast('Role updated to ' + newRole, 'success'); }}
  else {{ const d = await r.json(); toast(d.error || 'Failed', 'error'); }}
  loadUsers(); loadAuditLog();
}}

async function toggleActive(id, current) {{
  const r = await fetch(`/admin/api/users/${{id}}/active`, {{
    method: 'PUT', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{is_active: !current}})
  }});
  if (r.ok) {{ toast(current ? 'User deactivated' : 'User activated', 'success'); }}
  else {{ const d = await r.json(); toast(d.error || 'Failed', 'error'); }}
  loadUsers(); loadAuditLog();
}}

async function deleteUser(id, email) {{
  if (!confirm(`Delete user ${{email}}? This permanently removes all their data.`)) return;
  const r = await fetch(`/admin/api/users/${{id}}`, {{method: 'DELETE'}});
  if (r.ok) {{ toast('User deleted', 'success'); }} else {{ const d = await r.json(); toast(d.error || 'Failed', 'error'); }}
  loadUsers(); loadAuditLog();
}}

async function transferOwnership(id, name) {{
  if (!confirm(`Transfer system ownership to ${{name}}? You will be demoted to admin.`)) return;
  const r = await fetch('/admin/api/transfer-ownership', {{
    method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{target_user_id: id}})
  }});
  if (r.ok) {{ toast('Ownership transferred. Reloading...', 'success'); setTimeout(() => location.reload(), 1500); }}
  else {{ const d = await r.json(); toast(d.error || 'Failed', 'error'); }}
}}

async function resetPassword(id, email) {{
  const pw = prompt(`Enter new password for ${{email}} (min 8 characters):`);
  if (!pw) return;
  if (pw.length < 8) {{ toast('Password must be at least 8 characters', 'error'); return; }}
  const r = await fetch(`/admin/api/users/${{id}}/password`, {{
    method: 'PUT', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{new_password: pw}})
  }});
  if (r.ok) {{ toast('Password reset for ' + email, 'success'); }}
  else {{ const d = await r.json(); toast(d.error || 'Failed', 'error'); }}
  loadAuditLog();
}}

async function toggleSignup(checked) {{
  const r = await fetch('/admin/api/settings/signup', {{
    method: 'PUT', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{open_signup: checked}})
  }});
  if (r.ok) {{ toast(checked ? 'Signup enabled' : 'Signup disabled', 'success'); }}
  else {{ toast('Failed to update setting', 'error'); }}
  loadAuditLog();
}}

loadUsers();
loadSettings();
loadAuditLog();
</script>"""

    return HTMLResponse(content=render_shell(
        title="Admin Panel",
        active_nav="admin",
        body_html=body,
        body_js=js,
        display_name=admin.display_name,
        role=admin.role,
    ))
