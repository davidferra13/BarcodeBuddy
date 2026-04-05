"""Team management routes — create teams, manage members, assign tasks."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import (
    ROLE_LEVELS,
    get_role_level,
    log_audit,
    require_manager,
    require_user,
)
from app.activity import log_activity
from app.database import Team, TeamMember, TeamTask, User, get_db
from app.layout import render_shell

router = APIRouter(prefix="/team", tags=["team"])

# ── Permission helpers ──────────────────────────────────────────────

TEAM_ROLE_LEVELS = {"lead": 30, "member": 20, "viewer": 10}


def _is_owner_or_admin(user: User) -> bool:
    return user.role in ("owner", "admin")


def _get_team_role(db: Session, team_id: str, user_id: str) -> str | None:
    """Return the user's team role or None if not a member."""
    m = db.query(TeamMember).filter(
        TeamMember.team_id == team_id, TeamMember.user_id == user_id
    ).first()
    return m.team_role if m else None


def _can_manage_team(user: User, db: Session, team_id: str) -> bool:
    """Owner/admin always can. Team leads can."""
    if _is_owner_or_admin(user):
        return True
    role = _get_team_role(db, team_id, user.id)
    return role == "lead"


def _can_view_team(user: User, db: Session, team_id: str) -> bool:
    if _is_owner_or_admin(user):
        return True
    return _get_team_role(db, team_id, user.id) is not None


# ── Request models ──────────────────────────────────────────────────

class CreateTeamRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""


class UpdateTeamRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""


class AddMemberRequest(BaseModel):
    user_id: str
    team_role: str = Field(default="member", pattern="^(lead|member|viewer)$")


class UpdateMemberRoleRequest(BaseModel):
    team_role: str = Field(pattern="^(lead|member|viewer)$")


class CreateTaskRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str = ""
    assigned_to: Optional[str] = None
    priority: str = Field(default="medium", pattern="^(low|medium|high|urgent)$")
    due_date: Optional[str] = None  # ISO date string


class UpdateTaskRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    status: Optional[str] = Field(default=None, pattern="^(todo|in_progress|done|blocked)$")
    priority: Optional[str] = Field(default=None, pattern="^(low|medium|high|urgent)$")
    due_date: Optional[str] = None


# ── Team CRUD ───────────────────────────────────────────────────────

@router.post("/api/teams")
def create_team(
    body: CreateTeamRequest,
    user: User = Depends(require_manager),
    db: Session = Depends(get_db),
) -> JSONResponse:
    team = Team(name=body.name.strip(), description=body.description.strip(), created_by=user.id)
    db.add(team)
    db.flush()
    # Creator is automatically a lead
    db.add(TeamMember(team_id=team.id, user_id=user.id, team_role="lead", added_by=user.id))
    db.commit()
    log_audit(db, user, "create_team", target_id=team.id, detail={"name": team.name})
    log_activity(db, user=user, action="Team Created", category="admin",
                 summary=f"Created team \"{team.name}\"", detail={"team_id": team.id})
    return JSONResponse(status_code=201, content={"team": team.to_dict()})


@router.get("/api/teams")
def list_teams(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    if _is_owner_or_admin(user):
        teams = db.query(Team).order_by(Team.created_at.desc()).all()
    else:
        member_team_ids = [
            m.team_id for m in db.query(TeamMember).filter(TeamMember.user_id == user.id).all()
        ]
        teams = db.query(Team).filter(Team.id.in_(member_team_ids)).order_by(Team.created_at.desc()).all() if member_team_ids else []

    result = []
    for t in teams:
        d = t.to_dict()
        d["member_count"] = db.query(TeamMember).filter(TeamMember.team_id == t.id).count()
        d["task_count"] = db.query(TeamTask).filter(TeamTask.team_id == t.id).count()
        result.append(d)
    return JSONResponse(content={"teams": result})


@router.get("/api/teams/{team_id}")
def get_team(
    team_id: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        return JSONResponse(status_code=404, content={"error": "Team not found"})
    if not _can_view_team(user, db, team_id):
        return JSONResponse(status_code=403, content={"error": "Not a member of this team"})

    members = db.query(TeamMember).filter(TeamMember.team_id == team_id).all()
    user_ids = {m.user_id for m in members}
    users_map = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}

    members_data = []
    for m in members:
        u = users_map.get(m.user_id)
        md = m.to_dict()
        md["display_name"] = u.display_name if u else "Unknown"
        md["email"] = u.email if u else ""
        md["user_role"] = u.role if u else ""
        md["is_active"] = u.is_active if u else False
        members_data.append(md)

    tasks = db.query(TeamTask).filter(TeamTask.team_id == team_id).order_by(TeamTask.created_at.desc()).all()
    assignee_ids = {t.assigned_to for t in tasks if t.assigned_to}
    all_user_ids = user_ids | assignee_ids
    all_users = {u.id: u for u in db.query(User).filter(User.id.in_(all_user_ids)).all()}

    tasks_data = []
    for t in tasks:
        td = t.to_dict()
        a = all_users.get(t.assigned_to)
        td["assignee_name"] = a.display_name if a else None
        tasks_data.append(td)

    d = team.to_dict()
    d["members"] = members_data
    d["tasks"] = tasks_data
    d["can_manage"] = _can_manage_team(user, db, team_id)
    return JSONResponse(content={"team": d})


@router.put("/api/teams/{team_id}")
def update_team(
    team_id: str,
    body: UpdateTeamRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        return JSONResponse(status_code=404, content={"error": "Team not found"})
    if not _can_manage_team(user, db, team_id):
        return JSONResponse(status_code=403, content={"error": "Not authorized to edit this team"})
    team.name = body.name.strip()
    team.description = body.description.strip()
    db.commit()
    log_audit(db, user, "update_team", target_id=team.id, detail={"name": team.name})
    log_activity(db, user=user, action="Team Updated", category="admin",
                 summary=f"Updated team \"{team.name}\"", detail={"team_id": team.id})
    return JSONResponse(content={"team": team.to_dict()})


@router.delete("/api/teams/{team_id}")
def delete_team(
    team_id: str,
    user: User = Depends(require_manager),
    db: Session = Depends(get_db),
) -> JSONResponse:
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        return JSONResponse(status_code=404, content={"error": "Team not found"})
    if not _is_owner_or_admin(user):
        return JSONResponse(status_code=403, content={"error": "Only owner/admin can delete teams"})
    name = team.name
    db.delete(team)
    db.commit()
    log_audit(db, user, "delete_team", target_id=team_id, detail={"name": name})
    log_activity(db, user=user, action="Team Deleted", category="admin",
                 summary=f"Deleted team \"{name}\"")
    return JSONResponse(content={"message": "Team deleted"})


# ── Member management ───────────────────────────────────────────────

@router.post("/api/teams/{team_id}/members")
def add_member(
    team_id: str,
    body: AddMemberRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        return JSONResponse(status_code=404, content={"error": "Team not found"})
    if not _can_manage_team(user, db, team_id):
        return JSONResponse(status_code=403, content={"error": "Not authorized"})

    target = db.query(User).filter(User.id == body.user_id, User.is_active == True).first()
    if not target:
        return JSONResponse(status_code=404, content={"error": "User not found or inactive"})

    existing = db.query(TeamMember).filter(
        TeamMember.team_id == team_id, TeamMember.user_id == body.user_id
    ).first()
    if existing:
        return JSONResponse(status_code=409, content={"error": "User is already a member"})

    # Only owner/admin can assign lead role
    if body.team_role == "lead" and not _is_owner_or_admin(user):
        return JSONResponse(status_code=403, content={"error": "Only owner/admin can assign lead role"})

    member = TeamMember(team_id=team_id, user_id=body.user_id, team_role=body.team_role, added_by=user.id)
    db.add(member)
    db.commit()
    log_audit(db, user, "add_team_member", target_id=team_id, detail={
        "user": target.email, "role": body.team_role,
    })
    log_activity(db, user=user, action="Member Added", category="admin",
                 summary=f"Added {target.display_name} to team as {body.team_role}",
                 detail={"team_id": team_id, "email": target.email})
    return JSONResponse(status_code=201, content={"member": member.to_dict()})


@router.put("/api/teams/{team_id}/members/{member_id}")
def update_member_role(
    team_id: str,
    member_id: str,
    body: UpdateMemberRoleRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    if not _can_manage_team(user, db, team_id):
        return JSONResponse(status_code=403, content={"error": "Not authorized"})

    member = db.query(TeamMember).filter(TeamMember.id == member_id, TeamMember.team_id == team_id).first()
    if not member:
        return JSONResponse(status_code=404, content={"error": "Member not found"})

    if body.team_role == "lead" and not _is_owner_or_admin(user):
        return JSONResponse(status_code=403, content={"error": "Only owner/admin can assign lead role"})

    old_role = member.team_role
    member.team_role = body.team_role
    db.commit()
    log_audit(db, user, "update_member_role", target_id=member_id, detail={
        "from": old_role, "to": body.team_role,
    })
    log_activity(db, user=user, action="Member Role Changed", category="admin",
                 summary=f"Changed role from {old_role} to {body.team_role}",
                 detail={"from": old_role, "to": body.team_role}, item_id=member_id)
    return JSONResponse(content={"member": member.to_dict()})


@router.delete("/api/teams/{team_id}/members/{member_id}")
def remove_member(
    team_id: str,
    member_id: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    if not _can_manage_team(user, db, team_id):
        return JSONResponse(status_code=403, content={"error": "Not authorized"})

    member = db.query(TeamMember).filter(TeamMember.id == member_id, TeamMember.team_id == team_id).first()
    if not member:
        return JSONResponse(status_code=404, content={"error": "Member not found"})

    # Don't let the last lead remove themselves
    if member.user_id == user.id and member.team_role == "lead":
        lead_count = db.query(TeamMember).filter(
            TeamMember.team_id == team_id, TeamMember.team_role == "lead"
        ).count()
        if lead_count <= 1 and not _is_owner_or_admin(user):
            return JSONResponse(status_code=400, content={"error": "Cannot remove the last team lead"})

    target_user = db.query(User).filter(User.id == member.user_id).first()

    # Unassign tasks from the departing member so they don't orphan
    unassigned = db.query(TeamTask).filter(
        TeamTask.team_id == team_id,
        TeamTask.assigned_to == member.user_id,
    ).update({"assigned_to": None}, synchronize_session=False)

    db.delete(member)
    db.commit()
    removed_name = target_user.display_name if target_user else "Unknown"
    removed_email = target_user.email if target_user else member.user_id
    log_audit(db, user, "remove_team_member", target_id=team_id,
              detail={"user": removed_email, "tasks_unassigned": unassigned})
    log_activity(db, user=user, action="Member Removed", category="admin",
                 summary=f"Removed {removed_name} from team"
                         + (f" ({unassigned} task(s) unassigned)" if unassigned else ""),
                 detail={"team_id": team_id, "email": removed_email, "tasks_unassigned": unassigned})
    return JSONResponse(content={"message": "Member removed", "tasks_unassigned": unassigned})


# ── Task management ─────────────────────────────────────────────────

@router.post("/api/teams/{team_id}/tasks")
def create_task(
    team_id: str,
    body: CreateTaskRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    if not _can_manage_team(user, db, team_id):
        team_role = _get_team_role(db, team_id, user.id)
        if team_role != "member":
            return JSONResponse(status_code=403, content={"error": "Not authorized to create tasks"})

    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        return JSONResponse(status_code=404, content={"error": "Team not found"})

    due = None
    if body.due_date:
        try:
            due = datetime.fromisoformat(body.due_date.replace("Z", "+00:00"))
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "Invalid due_date format"})

    if body.assigned_to:
        is_member = db.query(TeamMember).filter(
            TeamMember.team_id == team_id, TeamMember.user_id == body.assigned_to
        ).first()
        if not is_member and not _is_owner_or_admin(
            db.query(User).filter(User.id == body.assigned_to).first() or user
        ):
            return JSONResponse(status_code=400, content={"error": "Assignee must be a team member"})

    task = TeamTask(
        team_id=team_id,
        title=body.title.strip(),
        description=body.description.strip(),
        assigned_to=body.assigned_to,
        created_by=user.id,
        priority=body.priority,
        due_date=due,
    )
    db.add(task)
    db.commit()
    log_audit(db, user, "create_task", target_id=task.id, detail={"title": task.title, "team": team.name})
    log_activity(db, user=user, action="Task Created", category="admin",
                 summary=f"Created task \"{task.title}\" in {team.name}",
                 detail={"team_id": team_id, "task_id": task.id})
    return JSONResponse(status_code=201, content={"task": task.to_dict()})


@router.put("/api/teams/{team_id}/tasks/{task_id}")
def update_task(
    team_id: str,
    task_id: str,
    body: UpdateTaskRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    if not _can_view_team(user, db, team_id):
        return JSONResponse(status_code=403, content={"error": "Not a member of this team"})

    task = db.query(TeamTask).filter(TeamTask.id == task_id, TeamTask.team_id == team_id).first()
    if not task:
        return JSONResponse(status_code=404, content={"error": "Task not found"})

    # Members can update status on tasks assigned to them; leads/owner/admin can update anything
    can_manage = _can_manage_team(user, db, team_id)
    is_assignee = task.assigned_to == user.id
    team_role = _get_team_role(db, team_id, user.id)

    if not can_manage and not is_assignee and team_role != "member":
        return JSONResponse(status_code=403, content={"error": "Not authorized to update this task"})

    # Non-managers can only update status
    if not can_manage and not is_assignee:
        return JSONResponse(status_code=403, content={"error": "You can only update tasks assigned to you"})

    changes = {}
    if body.title is not None and can_manage:
        task.title = body.title.strip()
        changes["title"] = task.title
    if body.description is not None and can_manage:
        task.description = body.description.strip()
    if body.status is not None:
        changes["status"] = body.status
        task.status = body.status
    if body.priority is not None and can_manage:
        task.priority = body.priority
        changes["priority"] = body.priority
    if body.assigned_to is not None and can_manage:
        if body.assigned_to:
            is_member = db.query(TeamMember).filter(
                TeamMember.team_id == team_id, TeamMember.user_id == body.assigned_to
            ).first()
            if not is_member and not _is_owner_or_admin(user):
                return JSONResponse(status_code=400, content={"error": "Assignee must be a team member"})
        task.assigned_to = body.assigned_to or None
        changes["assigned_to"] = body.assigned_to
    if body.due_date is not None and can_manage:
        if body.due_date:
            try:
                task.due_date = datetime.fromisoformat(body.due_date.replace("Z", "+00:00"))
            except ValueError:
                return JSONResponse(status_code=400, content={"error": "Invalid due_date"})
        else:
            task.due_date = None

    db.commit()
    log_audit(db, user, "update_task", target_id=task.id, detail=changes)
    log_activity(db, user=user, action="Task Updated", category="admin",
                 summary=f"Updated task '{task.title}': {', '.join(changes.keys())}",
                 detail=changes, item_id=task.id)
    return JSONResponse(content={"task": task.to_dict()})


@router.delete("/api/teams/{team_id}/tasks/{task_id}")
def delete_task(
    team_id: str,
    task_id: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    if not _can_manage_team(user, db, team_id):
        return JSONResponse(status_code=403, content={"error": "Not authorized"})

    task = db.query(TeamTask).filter(TeamTask.id == task_id, TeamTask.team_id == team_id).first()
    if not task:
        return JSONResponse(status_code=404, content={"error": "Task not found"})

    title = task.title
    db.delete(task)
    db.commit()
    log_audit(db, user, "delete_task", target_id=task_id, detail={"title": title})
    log_activity(db, user=user, action="Task Deleted", category="admin",
                 summary=f"Deleted task '{title}'", item_id=task_id)
    return JSONResponse(content={"message": "Task deleted"})


# ── Available users for adding to teams ─────────────────────────────

@router.get("/api/available-users")
def available_users(
    user: User = Depends(require_manager),
    db: Session = Depends(get_db),
) -> JSONResponse:
    users = db.query(User).filter(User.is_active == True).order_by(User.display_name).all()
    return JSONResponse(content={"users": [
        {"id": u.id, "display_name": u.display_name, "email": u.email, "role": u.role}
        for u in users
    ]})


# ── HTML Page ───────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
def team_page(user: User = Depends(require_user)) -> HTMLResponse:
    is_manager = get_role_level(user) >= ROLE_LEVELS["manager"]
    is_admin = user.role in ("owner", "admin")

    body = """
<style>
  .team-grid { display: grid; grid-template-columns: 320px 1fr; gap: 16px; min-height: 500px; }
  @media (max-width: 900px) { .team-grid { grid-template-columns: 1fr; } }
  .team-list { display: flex; flex-direction: column; gap: 6px; }
  .team-card { padding: 12px 14px; border-radius: 8px; background: var(--paper); cursor: pointer;
    border: 2px solid transparent; transition: all .15s; }
  .team-card:hover { border-color: var(--sidebar-accent); }
  .team-card.active { border-color: var(--sidebar-accent); background: rgba(96,165,250,.08); }
  .team-card .tc-name { font-weight: 600; font-size: 14px; }
  .team-card .tc-meta { font-size: 12px; color: var(--muted); margin-top: 4px; display: flex; gap: 12px; }
  .team-detail { background: var(--paper); border-radius: 10px; padding: 20px; min-height: 400px; }
  .team-detail .empty-detail { display: flex; align-items: center; justify-content: center;
    height: 300px; color: var(--muted); font-size: 14px; }
  /* Tab bar — uses .tab-bar/.tab-btn from layout.py */
  .tab-content { display: none; }
  .tab-content.active { display: block; }
  .member-row { display: flex; align-items: center; gap: 12px; padding: 10px 12px; border-radius: 8px;
    background: rgba(255,255,255,.02); margin-bottom: 6px; }
  .member-row:hover { background: rgba(255,255,255,.05); }
  .member-info { flex: 1; }
  .member-name { font-weight: 600; font-size: 13px; }
  .member-email { font-size: 12px; color: var(--muted); }
  .member-actions { display: flex; gap: 6px; align-items: center; }
  .team-role-badge { font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 600; text-transform: uppercase; }
  .team-role-lead { background: rgba(245,158,11,.15); color: #f59e0b; }
  .team-role-member { background: rgba(96,165,250,.15); color: #60a5fa; }
  .team-role-viewer { background: rgba(148,163,184,.15); color: #94a3b8; }
  .task-row { display: flex; align-items: flex-start; gap: 10px; padding: 10px 12px; border-radius: 8px;
    background: rgba(255,255,255,.02); margin-bottom: 6px; cursor: pointer; }
  .task-row:hover { background: rgba(255,255,255,.05); }
  .task-check { margin-top: 2px; cursor: pointer; accent-color: #22c55e; width: 16px; height: 16px; }
  .task-body { flex: 1; }
  .task-title { font-size: 13px; font-weight: 500; }
  .task-title.done { text-decoration: line-through; color: var(--muted); }
  .task-meta { display: flex; gap: 10px; margin-top: 4px; font-size: 11px; color: var(--muted); flex-wrap: wrap; }
  .priority-badge { font-size: 10px; padding: 1px 6px; border-radius: 8px; font-weight: 600; text-transform: uppercase; }
  .priority-urgent { background: var(--failure-bg); color: var(--failure); }
  .priority-high { background: var(--warning-bg); color: var(--warning); }
  .priority-medium { background: var(--info-bg); color: var(--info); }
  .priority-low { background: rgba(148,163,184,.15); color: var(--muted); }
  .status-pill { font-size: 10px; padding: 1px 6px; border-radius: 8px; font-weight: 600; }
  .status-todo { background: rgba(148,163,184,.15); color: var(--muted); }
  .status-in_progress { background: var(--info-bg); color: var(--info); }
  .status-done { background: var(--success-bg); color: var(--success); }
  .status-blocked { background: var(--failure-bg); color: var(--failure); }
  .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.55); z-index: 1000;
    display: flex; align-items: center; justify-content: center; }
  .modal { background: var(--sidebar-bg); border-radius: 12px; padding: 24px; width: 440px; max-width: 90vw;
    max-height: 85vh; overflow-y: auto; box-shadow: 0 20px 60px rgba(0,0,0,.4); }
  .modal h3 { margin: 0 0 16px; font-size: 16px; }
  .modal label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; margin-top: 12px; }
  .modal input, .modal select, .modal textarea { width: 100%; padding: 8px 10px; border-radius: 6px;
    border: 1px solid rgba(255,255,255,.1); background: rgba(255,255,255,.05); color: var(--text);
    font-size: 13px; box-sizing: border-box; }
  .modal textarea { min-height: 70px; resize: vertical; }
  .modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 18px; }
  .btn-primary { padding: 8px 18px; border-radius: 6px; border: none; background: var(--sidebar-accent);
    color: #fff; font-weight: 600; font-size: 13px; cursor: pointer; }
  .btn-primary:hover { filter: brightness(1.1); }
  .btn-secondary { padding: 8px 18px; border-radius: 6px; border: 1px solid rgba(255,255,255,.1);
    background: transparent; color: var(--text); font-size: 13px; cursor: pointer; }
  .btn-danger-sm { padding: 4px 10px; border-radius: 5px; border: none; background: var(--failure-bg);
    color: var(--failure); font-size: 11px; cursor: pointer; font-weight: 600; }
  .btn-danger-sm:hover { background: rgba(239,68,68,.25); }
  .add-bar { display: flex; gap: 8px; margin-bottom: 14px; flex-wrap: wrap; }
  .section-hdr { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
  .section-hdr h2 { margin: 0; font-size: 16px; }
  .filter-row { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
  .filter-chip { padding: 4px 10px; border-radius: 12px; font-size: 11px; border: 1px solid rgba(255,255,255,.1);
    background: transparent; color: var(--muted); cursor: pointer; font-weight: 500; }
  .filter-chip.active { background: var(--sidebar-accent); color: #fff; border-color: var(--sidebar-accent); }
  .overview-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; margin-bottom: 16px; }
  .overview-stat { background: rgba(255,255,255,.03); border-radius: 8px; padding: 12px; text-align: center; }
  .overview-stat .val { font-size: 22px; font-weight: 700; }
  .overview-stat .lbl { font-size: 11px; color: var(--muted); margin-top: 2px; }
</style>

<div class="section-hdr">
  <h2>Team Management</h2>
  <div class="add-bar" id="create-team-bar" style="display:none">
    <button class="btn-primary" onclick="showCreateTeamModal()">+ New Team</button>
  </div>
</div>

<div class="overview-stats" id="overview-stats"></div>

<div class="team-grid">
  <div>
    <div class="team-list" id="team-list">
      <div style="padding:16px;display:flex;flex-direction:column;gap:8px"><div class="skeleton skeleton-card"></div><div class="skeleton skeleton-card"></div></div>
    </div>
  </div>
  <div class="team-detail" id="team-detail">
    <div class="empty-detail">Select a team to view details</div>
  </div>
</div>

<div id="modal-root"></div>
"""

    js = f"""<script>
const USER_ID = '{user.id}';
const IS_MANAGER = {'true' if is_manager else 'false'};
const IS_ADMIN = {'true' if is_admin else 'false'};
let teams = [];
let selectedTeamId = null;
let selectedTeam = null;
let allUsers = [];
let taskFilter = 'all';

function esc(s) {{ const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }}

// ── Data loading ──

async function loadTeams() {{
  const r = await fetch('/team/api/teams');
  const d = await r.json();
  teams = d.teams;
  renderTeamList();
  renderOverviewStats();
  if (selectedTeamId) loadTeamDetail(selectedTeamId);
}}

async function loadTeamDetail(teamId) {{
  selectedTeamId = teamId;
  const r = await fetch(`/team/api/teams/${{teamId}}`);
  if (!r.ok) {{ toast('Failed to load team', 'error'); return; }}
  const d = await r.json();
  selectedTeam = d.team;
  renderTeamDetail();
  // Update active card
  document.querySelectorAll('.team-card').forEach(c => c.classList.toggle('active', c.dataset.id === teamId));
}}

async function loadAvailableUsers() {{
  if (!IS_MANAGER) return;
  const r = await fetch('/team/api/available-users');
  const d = await r.json();
  allUsers = d.users;
}}

// ── Rendering ──

function renderOverviewStats() {{
  const el = document.getElementById('overview-stats');
  const totalMembers = teams.reduce((s, t) => s + (t.member_count || 0), 0);
  const totalTasks = teams.reduce((s, t) => s + (t.task_count || 0), 0);
  el.innerHTML = `
    <div class="overview-stat"><div class="val">${{teams.length}}</div><div class="lbl">Teams</div></div>
    <div class="overview-stat"><div class="val">${{totalMembers}}</div><div class="lbl">Members</div></div>
    <div class="overview-stat"><div class="val">${{totalTasks}}</div><div class="lbl">Tasks</div></div>
  `;
}}

function renderTeamList() {{
  const el = document.getElementById('team-list');
  if (IS_MANAGER) document.getElementById('create-team-bar').style.display = 'flex';
  if (!teams.length) {{
    el.innerHTML = '<div style="padding:30px;text-align:center;color:var(--muted)">No teams yet</div>';
    return;
  }}
  el.innerHTML = teams.map(t => `
    <div class="team-card ${{t.id === selectedTeamId ? 'active' : ''}}" data-id="${{t.id}}"
         onclick="loadTeamDetail('${{t.id}}')">
      <div class="tc-name">${{esc(t.name)}}</div>
      <div class="tc-meta">
        <span>${{t.member_count || 0}} member${{t.member_count !== 1 ? 's' : ''}}</span>
        <span>${{t.task_count || 0}} task${{t.task_count !== 1 ? 's' : ''}}</span>
      </div>
    </div>
  `).join('');
}}

function renderTeamDetail() {{
  const el = document.getElementById('team-detail');
  const t = selectedTeam;
  if (!t) {{ el.innerHTML = '<div class="empty-detail">Select a team</div>'; return; }}
  const canManage = t.can_manage;

  el.innerHTML = `
    <div class="section-hdr">
      <div>
        <h2 style="margin:0">${{esc(t.name)}}</h2>
        ${{t.description ? `<p style="color:var(--muted);font-size:13px;margin:4px 0 0">${{esc(t.description)}}</p>` : ''}}
      </div>
      <div style="display:flex;gap:6px">
        ${{canManage ? `<button class="btn-secondary" onclick="showEditTeamModal()">Edit</button>` : ''}}
        ${{IS_ADMIN ? `<button class="btn-danger-sm" onclick="deleteTeam()">Delete Team</button>` : ''}}
      </div>
    </div>
    <div class="tab-bar">
      <button class="tab-btn active" onclick="switchTab(this,'members-tab')">Members (${{t.members.length}})</button>
      <button class="tab-btn" onclick="switchTab(this,'tasks-tab')">Tasks (${{t.tasks.length}})</button>
    </div>
    <div class="tab-content active" id="members-tab">
      ${{canManage ? `<div class="add-bar"><button class="btn-primary" onclick="showAddMemberModal()">+ Add Member</button></div>` : ''}}
      <div id="members-list">${{renderMembers(t.members, canManage)}}</div>
    </div>
    <div class="tab-content" id="tasks-tab">
      ${{canManage || _getMemberRole() === 'member' ? `<div class="add-bar"><button class="btn-primary" onclick="showCreateTaskModal()">+ New Task</button></div>` : ''}}
      <div class="filter-row">
        <button class="filter-chip ${{taskFilter==='all'?'active':''}}" onclick="setTaskFilter('all')">All</button>
        <button class="filter-chip ${{taskFilter==='todo'?'active':''}}" onclick="setTaskFilter('todo')">To Do</button>
        <button class="filter-chip ${{taskFilter==='in_progress'?'active':''}}" onclick="setTaskFilter('in_progress')">In Progress</button>
        <button class="filter-chip ${{taskFilter==='done'?'active':''}}" onclick="setTaskFilter('done')">Done</button>
        <button class="filter-chip ${{taskFilter==='blocked'?'active':''}}" onclick="setTaskFilter('blocked')">Blocked</button>
      </div>
      <div id="tasks-list">${{renderTasks(t.tasks, canManage)}}</div>
    </div>
  `;
}}

function _getMemberRole() {{
  if (!selectedTeam) return null;
  const m = selectedTeam.members.find(m => m.user_id === USER_ID);
  return m ? m.team_role : null;
}}

function switchTab(btn, tabId) {{
  btn.closest('.team-detail').querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  btn.closest('.team-detail').querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  document.getElementById(tabId).classList.add('active');
}}

function renderMembers(members, canManage) {{
  if (!members.length) return '<div style="color:var(--muted);padding:16px;text-align:center">No members</div>';
  return members.map(m => `
    <div class="member-row">
      <div class="member-info">
        <div class="member-name">${{esc(m.display_name)}} ${{m.user_role ? `<span class="role-badge role-${{m.user_role}}" style="font-size:10px;padding:1px 6px">${{m.user_role}}</span>` : ''}}</div>
        <div class="member-email">${{esc(m.email)}}</div>
      </div>
      <span class="team-role-badge team-role-${{m.team_role}}">${{m.team_role}}</span>
      ${{canManage ? `
        <div class="member-actions">
          <select style="padding:3px 6px;font-size:11px;border-radius:5px;background:rgba(255,255,255,.05);
            border:1px solid rgba(255,255,255,.1);color:var(--text)" onchange="changeMemberRole('${{m.id}}',this.value)">
            ${{['lead','member','viewer'].map(r => `<option value="${{r}}" ${{m.team_role===r?'selected':''}}>${{r}}</option>`).join('')}}
          </select>
          <button class="btn-danger-sm" onclick="removeMember('${{m.id}}','${{esc(m.display_name)}}')">Remove</button>
        </div>
      ` : ''}}
    </div>
  `).join('');
}}

function setTaskFilter(f) {{
  taskFilter = f;
  renderTeamDetail();
  // Re-activate tasks tab
  const detail = document.getElementById('team-detail');
  detail.querySelectorAll('.tab-btn')[1].click();
}}

function renderTasks(tasks, canManage) {{
  let filtered = tasks;
  if (taskFilter !== 'all') filtered = tasks.filter(t => t.status === taskFilter);
  if (!filtered.length) return '<div class="empty-state" style="padding:32px"><svg width="40" height="40" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1"><rect x="3" y="3" width="14" height="14" rx="2"/><path d="M7 8h6M7 11h4"/></svg><h3>No tasks</h3><p>Create a task to get started.</p></div>';
  return filtered.map(t => `
    <div class="task-row" onclick="showTaskDetailModal('${{t.id}}')">
      <input type="checkbox" class="task-check" ${{t.status==='done'?'checked':''}}
        onclick="event.stopPropagation();toggleTaskDone('${{t.id}}','${{t.status}}')" />
      <div class="task-body">
        <div class="task-title ${{t.status==='done'?'done':''}}">${{esc(t.title)}}</div>
        <div class="task-meta">
          <span class="priority-badge priority-${{t.priority}}">${{t.priority}}</span>
          <span class="status-pill status-${{t.status}}">${{t.status.replace('_',' ')}}</span>
          ${{t.assignee_name ? `<span>Assigned: ${{esc(t.assignee_name)}}</span>` : '<span style="color:var(--failure)">Unassigned</span>'}}
          ${{t.due_date ? `<span>Due: ${{new Date(t.due_date).toLocaleDateString()}}</span>` : ''}}
        </div>
      </div>
      ${{canManage ? `<button class="btn-danger-sm" onclick="event.stopPropagation();deleteTask('${{t.id}}')" style="margin-top:2px">Delete</button>` : ''}}
    </div>
  `).join('');
}}

// ── Actions ──

async function deleteTeam() {{
  if (!confirm('Delete this team and all its tasks? This cannot be undone.')) return;
  const r = await fetch(`/team/api/teams/${{selectedTeamId}}`, {{method:'DELETE'}});
  if (r.ok) {{ toast('Team deleted','success'); selectedTeamId=null; selectedTeam=null;
    document.getElementById('team-detail').innerHTML='<div class="empty-detail">Select a team</div>'; loadTeams(); }}
  else {{ const d = await r.json(); toast(d.error||'Failed','error'); }}
}}

async function changeMemberRole(memberId, newRole) {{
  const r = await fetch(`/team/api/teams/${{selectedTeamId}}/members/${{memberId}}`, {{
    method:'PUT', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{team_role:newRole}})
  }});
  if (r.ok) {{ toast('Role updated','success'); loadTeamDetail(selectedTeamId); }}
  else {{ const d = await r.json(); toast(d.error||'Failed','error'); }}
}}

async function removeMember(memberId, name) {{
  if (!confirm(`Remove ${{name}} from this team?`)) return;
  const r = await fetch(`/team/api/teams/${{selectedTeamId}}/members/${{memberId}}`, {{method:'DELETE'}});
  if (r.ok) {{ toast('Member removed','success'); loadTeamDetail(selectedTeamId); loadTeams(); }}
  else {{ const d = await r.json(); toast(d.error||'Failed','error'); }}
}}

async function toggleTaskDone(taskId, current) {{
  const newStatus = current === 'done' ? 'todo' : 'done';
  const r = await fetch(`/team/api/teams/${{selectedTeamId}}/tasks/${{taskId}}`, {{
    method:'PUT', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{status:newStatus}})
  }});
  if (r.ok) loadTeamDetail(selectedTeamId);
  else {{ const d = await r.json(); toast(d.error||'Failed','error'); }}
}}

async function deleteTask(taskId) {{
  if (!confirm('Delete this task?')) return;
  const r = await fetch(`/team/api/teams/${{selectedTeamId}}/tasks/${{taskId}}`, {{method:'DELETE'}});
  if (r.ok) {{ toast('Task deleted','success'); loadTeamDetail(selectedTeamId); loadTeams(); }}
  else {{ const d = await r.json(); toast(d.error||'Failed','error'); }}
}}

// ── Modals ──

function closeModal() {{ document.getElementById('modal-root').innerHTML = ''; }}

function showCreateTeamModal() {{
  document.getElementById('modal-root').innerHTML = `
    <div class="modal-overlay" onclick="if(event.target===this)closeModal()">
      <div class="modal">
        <h3>Create Team</h3>
        <label>Team Name</label>
        <input id="m-team-name" placeholder="e.g. Warehouse Crew" maxlength="255" />
        <label>Description</label>
        <textarea id="m-team-desc" placeholder="What does this team do?"></textarea>
        <div class="modal-actions">
          <button class="btn-secondary" onclick="closeModal()">Cancel</button>
          <button class="btn-primary" onclick="submitCreateTeam()">Create</button>
        </div>
      </div>
    </div>`;
  document.getElementById('m-team-name').focus();
}}

async function submitCreateTeam() {{
  const name = document.getElementById('m-team-name').value.trim();
  const desc = document.getElementById('m-team-desc').value.trim();
  if (!name) {{ toast('Team name is required','error'); return; }}
  const r = await fetch('/team/api/teams', {{
    method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{name, description:desc}})
  }});
  if (r.ok) {{ closeModal(); toast('Team created','success'); loadTeams(); const d = await r.clone().json(); loadTeamDetail(d.team.id); }}
  else {{ const d = await r.json(); toast(d.error||'Failed','error'); }}
}}

function showEditTeamModal() {{
  const t = selectedTeam;
  document.getElementById('modal-root').innerHTML = `
    <div class="modal-overlay" onclick="if(event.target===this)closeModal()">
      <div class="modal">
        <h3>Edit Team</h3>
        <label>Team Name</label>
        <input id="m-team-name" value="${{esc(t.name)}}" maxlength="255" />
        <label>Description</label>
        <textarea id="m-team-desc">${{esc(t.description)}}</textarea>
        <div class="modal-actions">
          <button class="btn-secondary" onclick="closeModal()">Cancel</button>
          <button class="btn-primary" onclick="submitEditTeam()">Save</button>
        </div>
      </div>
    </div>`;
}}

async function submitEditTeam() {{
  const name = document.getElementById('m-team-name').value.trim();
  const desc = document.getElementById('m-team-desc').value.trim();
  if (!name) {{ toast('Team name is required','error'); return; }}
  const r = await fetch(`/team/api/teams/${{selectedTeamId}}`, {{
    method:'PUT', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{name, description:desc}})
  }});
  if (r.ok) {{ closeModal(); toast('Team updated','success'); loadTeams(); loadTeamDetail(selectedTeamId); }}
  else {{ const d = await r.json(); toast(d.error||'Failed','error'); }}
}}

function showAddMemberModal() {{
  const existing = new Set(selectedTeam.members.map(m => m.user_id));
  const available = allUsers.filter(u => !existing.has(u.id));
  document.getElementById('modal-root').innerHTML = `
    <div class="modal-overlay" onclick="if(event.target===this)closeModal()">
      <div class="modal">
        <h3>Add Member</h3>
        <label>User</label>
        <select id="m-user-id">
          ${{available.length ? available.map(u => `<option value="${{u.id}}">${{esc(u.display_name)}} (${{esc(u.email)}})</option>`).join('') : '<option value="">No available users</option>'}}
        </select>
        <label>Team Role</label>
        <select id="m-team-role">
          ${{IS_ADMIN ? '<option value="lead">Lead</option>' : ''}}
          <option value="member" selected>Member</option>
          <option value="viewer">Viewer</option>
        </select>
        <div class="modal-actions">
          <button class="btn-secondary" onclick="closeModal()">Cancel</button>
          <button class="btn-primary" onclick="submitAddMember()" ${{!available.length?'disabled':''}}>Add</button>
        </div>
      </div>
    </div>`;
}}

async function submitAddMember() {{
  const userId = document.getElementById('m-user-id').value;
  const role = document.getElementById('m-team-role').value;
  if (!userId) return;
  const r = await fetch(`/team/api/teams/${{selectedTeamId}}/members`, {{
    method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{user_id:userId, team_role:role}})
  }});
  if (r.ok) {{ closeModal(); toast('Member added','success'); loadTeamDetail(selectedTeamId); loadTeams(); }}
  else {{ const d = await r.json(); toast(d.error||'Failed','error'); }}
}}

function showCreateTaskModal() {{
  const members = selectedTeam.members;
  document.getElementById('modal-root').innerHTML = `
    <div class="modal-overlay" onclick="if(event.target===this)closeModal()">
      <div class="modal">
        <h3>Create Task</h3>
        <label>Title</label>
        <input id="m-task-title" placeholder="What needs to be done?" maxlength="500" />
        <label>Description</label>
        <textarea id="m-task-desc" placeholder="Additional details..."></textarea>
        <label>Assign To</label>
        <select id="m-task-assign">
          <option value="">Unassigned</option>
          ${{members.map(m => `<option value="${{m.user_id}}">${{esc(m.display_name)}}</option>`).join('')}}
        </select>
        <label>Priority</label>
        <select id="m-task-priority">
          <option value="low">Low</option>
          <option value="medium" selected>Medium</option>
          <option value="high">High</option>
          <option value="urgent">Urgent</option>
        </select>
        <label>Due Date</label>
        <input id="m-task-due" type="date" />
        <div class="modal-actions">
          <button class="btn-secondary" onclick="closeModal()">Cancel</button>
          <button class="btn-primary" onclick="submitCreateTask()">Create</button>
        </div>
      </div>
    </div>`;
  document.getElementById('m-task-title').focus();
}}

async function submitCreateTask() {{
  const title = document.getElementById('m-task-title').value.trim();
  const desc = document.getElementById('m-task-desc').value.trim();
  const assignedTo = document.getElementById('m-task-assign').value || null;
  const priority = document.getElementById('m-task-priority').value;
  const dueDate = document.getElementById('m-task-due').value || null;
  if (!title) {{ toast('Task title is required','error'); return; }}
  const r = await fetch(`/team/api/teams/${{selectedTeamId}}/tasks`, {{
    method:'POST', headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{title, description:desc, assigned_to:assignedTo, priority, due_date:dueDate}})
  }});
  if (r.ok) {{ closeModal(); toast('Task created','success'); loadTeamDetail(selectedTeamId); loadTeams(); }}
  else {{ const d = await r.json(); toast(d.error||'Failed','error'); }}
}}

function showTaskDetailModal(taskId) {{
  const t = selectedTeam.tasks.find(x => x.id === taskId);
  if (!t) return;
  const canManage = selectedTeam.can_manage;
  const isAssignee = t.assigned_to === USER_ID;
  const members = selectedTeam.members;

  document.getElementById('modal-root').innerHTML = `
    <div class="modal-overlay" onclick="if(event.target===this)closeModal()">
      <div class="modal">
        <h3>${{canManage ? 'Edit Task' : 'Task Details'}}</h3>
        <label>Title</label>
        <input id="m-task-title" value="${{esc(t.title)}}" ${{canManage?'':'readonly'}} />
        <label>Description</label>
        <textarea id="m-task-desc" ${{canManage?'':'readonly'}}>${{esc(t.description)}}</textarea>
        <label>Status</label>
        <select id="m-task-status" ${{canManage || isAssignee ? '' : 'disabled'}}>
          ${{['todo','in_progress','done','blocked'].map(s => `<option value="${{s}}" ${{t.status===s?'selected':''}}>${{s.replace('_',' ')}}</option>`).join('')}}
        </select>
        ${{canManage ? `
        <label>Assign To</label>
        <select id="m-task-assign">
          <option value="">Unassigned</option>
          ${{members.map(m => `<option value="${{m.user_id}}" ${{t.assigned_to===m.user_id?'selected':''}}>${{esc(m.display_name)}}</option>`).join('')}}
        </select>
        <label>Priority</label>
        <select id="m-task-priority">
          ${{['low','medium','high','urgent'].map(p => `<option value="${{p}}" ${{t.priority===p?'selected':''}}>${{p}}</option>`).join('')}}
        </select>
        <label>Due Date</label>
        <input id="m-task-due" type="date" value="${{t.due_date ? t.due_date.split('T')[0] : ''}}" />
        ` : ''}}
        <div class="modal-actions">
          <button class="btn-secondary" onclick="closeModal()">Cancel</button>
          ${{canManage || isAssignee ? `<button class="btn-primary" onclick="submitEditTask('${{t.id}}')">Save</button>` : ''}}
        </div>
      </div>
    </div>`;
}}

async function submitEditTask(taskId) {{
  const payload = {{}};
  const canManage = selectedTeam.can_manage;
  payload.status = document.getElementById('m-task-status').value;
  if (canManage) {{
    payload.title = document.getElementById('m-task-title').value.trim();
    payload.description = document.getElementById('m-task-desc').value.trim();
    payload.assigned_to = document.getElementById('m-task-assign').value || null;
    payload.priority = document.getElementById('m-task-priority').value;
    payload.due_date = document.getElementById('m-task-due').value || null;
  }}
  const r = await fetch(`/team/api/teams/${{selectedTeamId}}/tasks/${{taskId}}`, {{
    method:'PUT', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(payload)
  }});
  if (r.ok) {{ closeModal(); toast('Task updated','success'); loadTeamDetail(selectedTeamId); }}
  else {{ const d = await r.json(); toast(d.error||'Failed','error'); }}
}}

// ── Init ──
loadTeams();
loadAvailableUsers();
</script>"""

    return HTMLResponse(content=render_shell(
        title="Team Management",
        active_nav="team",
        body_html=body,
        body_js=js,
        display_name=user.display_name,
        role=user.role,
    ))
