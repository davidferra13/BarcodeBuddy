"""Authentication routes: login, signup, logout, password reset."""

from __future__ import annotations

import os
import re
import smtplib
import ssl
import time
from collections import defaultdict
from email.message import EmailMessage
from threading import Lock

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import (
    _OWNER_EMAIL_EXPLICIT,
    clear_auth_cookie,
    configure_owner_email,
    create_access_token,
    create_reset_token,
    hash_password,
    is_owner_email,
    OWNER_EMAIL,
    normalize_email,
    require_user,
    revoke_token,
    set_auth_cookie,
    verify_password,
    verify_reset_token,
    COOKIE_NAME,
)
from app.activity import log_activity
from app.database import SystemSettings, User, get_db
from app.layout import render_shell

router = APIRouter(prefix="/auth", tags=["auth"])


# --- Rate Limiter ---

class _RateLimiter:
    """Simple in-memory sliding-window rate limiter per IP."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            # Evict expired entries
            cutoff = now - self._window
            self._hits[key] = hits = [t for t in hits if t > cutoff]
            if len(hits) >= self._max:
                return False
            hits.append(now)
            return True


_auth_limiter = _RateLimiter(max_requests=10, window_seconds=60)


def _reset_rate_limiter() -> None:
    """Reset rate limiter state. Intended for tests only."""
    with _auth_limiter._lock:
        _auth_limiter._hits.clear()


def _get_client_ip(request: Request) -> str:
    """Extract the real client IP, respecting X-Forwarded-For from reverse proxies."""
    forwarded = (request.headers.get("x-forwarded-for") or "").strip()
    if forwarded:
        # First entry is the original client; later entries are proxies
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(request: Request) -> JSONResponse | None:
    """Return a 429 response if the client IP exceeds the rate limit, else None."""
    client_ip = _get_client_ip(request)
    if not _auth_limiter.is_allowed(client_ip):
        return JSONResponse(status_code=429, content={"error": "Too many requests. Please try again later."})
    return None


def _build_reset_url(request: Request, token: str) -> str:
    host = request.headers.get("host", "")
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    scheme = "https" if forwarded_proto == "https" else request.url.scheme
    if host:
        return f"{scheme}://{host}/auth/reset?token={token}"
    return f"/auth/reset?token={token}"


def _send_reset_email(to_email: str, reset_url: str) -> bool:
    """Best-effort SMTP delivery for password reset links."""
    smtp_host = (os.environ.get("BB_SMTP_HOST") or "").strip()
    smtp_port = int((os.environ.get("BB_SMTP_PORT") or "587").strip() or "587")
    smtp_user = (os.environ.get("BB_SMTP_USER") or "").strip()
    smtp_password = (os.environ.get("BB_SMTP_PASSWORD") or "").strip()
    from_email = (os.environ.get("BB_RESET_FROM") or "").strip()
    use_tls = (os.environ.get("BB_SMTP_USE_TLS") or "true").strip().lower() not in {"0", "false", "no"}

    if not smtp_host or not from_email:
        return False

    msg = EmailMessage()
    msg["Subject"] = "BarcodeBuddy password reset"
    msg["From"] = from_email
    msg["To"] = to_email
    msg.set_content(
        "A password reset was requested for your BarcodeBuddy account.\n\n"
        f"Use this link to set a new password: {reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )

    if use_tls:
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls(context=context)
            if smtp_user:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return True

    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
        if smtp_user:
            server.login(smtp_user, smtp_password)
        server.send_message(msg)
    return True


# --- Request Models ---

class SignupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: str
    password: str


class ResetRequestModel(BaseModel):
    email: str


class ResetConfirmModel(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


# --- API Endpoints ---

@router.post("/api/signup")
def api_signup(request: Request, body: SignupRequest, db: Session = Depends(get_db)) -> JSONResponse:
    blocked = _check_rate_limit(request)
    if blocked:
        return blocked

    email = normalize_email(body.email)
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return JSONResponse(status_code=400, content={"error": "Invalid email address"})

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return JSONResponse(status_code=409, content={"error": "Email already registered"})

    # First user becomes owner; subsequent users need open signup.
    user_count = db.query(User).count()
    if user_count == 0:
        if _OWNER_EMAIL_EXPLICIT and not is_owner_email(email):
            return JSONResponse(
                status_code=403,
                content={"error": f"The owner account must be created with {OWNER_EMAIL}"},
            )
        # Lock owner identity to the email actually used
        if not _OWNER_EMAIL_EXPLICIT:
            configure_owner_email(email)
        role = "owner"
    else:
        settings = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
        if settings and not settings.open_signup:
            return JSONResponse(
                status_code=403,
                content={"error": "Signup is currently disabled. Contact an administrator."},
            )
        role = "user"

    user = User(
        email=email,
        display_name=body.display_name.strip(),
        password_hash=hash_password(body.password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user, db)
    log_activity(db, user=user, action="User Signed Up", category="auth",
                 summary=f"{user.display_name} ({user.email}) — role: {user.role}",
                 detail={"email": user.email, "role": user.role})
    response = JSONResponse(content={"user": user.to_dict(), "redirect": "/"})
    set_auth_cookie(response, token, request=request)
    return response


@router.post("/api/login")
def api_login(request: Request, body: LoginRequest, db: Session = Depends(get_db)) -> JSONResponse:
    blocked = _check_rate_limit(request)
    if blocked:
        return blocked

    email = normalize_email(body.email)
    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if not user or not verify_password(body.password, user.password_hash):
        return JSONResponse(status_code=401, content={"error": "Invalid email or password"})

    token = create_access_token(user, db)
    log_activity(db, user=user, action="User Logged In", category="auth",
                 summary=f"{user.display_name} ({user.email})",
                 detail={"email": user.email})
    response = JSONResponse(content={"user": user.to_dict(), "redirect": "/"})
    set_auth_cookie(response, token, request=request)
    return response


@router.post("/api/logout")
def api_logout(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    token = request.cookies.get(COOKIE_NAME)
    # Resolve user for activity logging before revoking
    from app.auth import get_current_user
    user = get_current_user(request, db) if token else None
    if token:
        revoke_token(token, db)
    if user:
        log_activity(db, user=user, action="User Logged Out", category="auth",
                     summary=f"{user.display_name} ({user.email})",
                     detail={"email": user.email})
    response = JSONResponse(content={"redirect": "/auth/login"})
    clear_auth_cookie(response)
    return response


@router.post("/api/reset-request")
def api_reset_request(request: Request, body: ResetRequestModel, db: Session = Depends(get_db)) -> JSONResponse:
    """Request a password reset. Always returns success to prevent email enumeration."""
    blocked = _check_rate_limit(request)
    if blocked:
        return blocked

    email = normalize_email(body.email)
    user = db.query(User).filter(User.email == email).first()
    if user:
        reset_token = create_reset_token(user, db)
        import structlog

        reset_url = _build_reset_url(request, reset_token)
        delivered = False
        try:
            delivered = _send_reset_email(email, reset_url)
        except Exception as exc:
            structlog.get_logger().warning(
                "password_reset_email_delivery_failed",
                email=email,
                error=str(exc),
            )

        structlog.get_logger().info(
            "password_reset_requested",
            email=email,
            reset_url=reset_url,
            email_delivered=delivered,
        )
    return JSONResponse(
        content={
            "message": "If an account exists with that email, password reset instructions have been sent."
        }
    )


@router.post("/api/reset-confirm")
def api_reset_confirm(body: ResetConfirmModel, db: Session = Depends(get_db)) -> JSONResponse:
    user = verify_reset_token(body.token, db)
    if not user:
        return JSONResponse(status_code=400, content={"error": "Invalid or expired reset token"})
    user.password_hash = hash_password(body.new_password)
    db.commit()
    log_activity(db, user=user, action="Password Reset", category="auth",
                 summary=f"{user.display_name} reset their password",
                 detail={"email": user.email})
    return JSONResponse(content={"message": "Password reset successfully", "redirect": "/auth/login"})


@router.get("/api/me")
def api_me(user: User = Depends(require_user)) -> JSONResponse:
    return JSONResponse(content={"user": user.to_dict()})


# --- Profile self-service ---

class ProfileUpdateModel(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)


class PasswordChangeModel(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


@router.put("/api/me/profile")
def api_update_profile(
    body: ProfileUpdateModel,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    old_name = user.display_name
    user.display_name = body.display_name.strip()
    db.commit()
    log_activity(db, user=user, action="Profile Updated", category="auth",
                 summary=f"Changed display name from '{old_name}' to '{user.display_name}'",
                 detail={"old_name": old_name, "new_name": user.display_name})
    return JSONResponse(content={"user": user.to_dict()})


@router.put("/api/me/password")
def api_change_password(
    body: PasswordChangeModel,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    if not verify_password(body.current_password, user.password_hash):
        return JSONResponse(status_code=400, content={"error": "Current password is incorrect"})
    user.password_hash = hash_password(body.new_password)
    db.commit()
    log_activity(db, user=user, action="Password Changed", category="auth",
                 summary=f"{user.display_name} changed their password")
    return JSONResponse(content={"message": "Password updated successfully"})


# --- HTML Pages ---

_AUTH_STYLES = """
<style>
  :root {
    --auth-bg: #0f172a; --auth-card: #1e293b; --auth-text: #e2e8f0;
    --auth-heading: #f8fafc; --auth-muted: #94a3b8; --auth-input-bg: #0f172a;
    --auth-input-border: #334155; --auth-accent: #3b82f6; --auth-accent-hover: #2563eb;
    --auth-link: #60a5fa; --auth-err-bg: #450a0a; --auth-err-text: #fca5a5;
    --auth-ok-bg: #052e16; --auth-ok-text: #86efac;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: "Segoe UI Variable", "Segoe UI", "Aptos", system-ui, sans-serif;
    background: var(--auth-bg); color: var(--auth-text);
    min-height: 100vh; display: flex; align-items: center; justify-content: center;
  }
  @keyframes authCardIn {
    from { opacity: 0; transform: translateY(16px) scale(0.98); }
    to { opacity: 1; transform: translateY(0) scale(1); }
  }
  .auth-card {
    background: var(--auth-card); border-radius: 16px; padding: 40px;
    width: 100%; max-width: 420px; box-shadow: 0 8px 32px rgba(0,0,0,0.4);
    animation: authCardIn 0.35s cubic-bezier(.4,0,.2,1);
    backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
  }
  .auth-card h1 {
    font-size: 24px; font-weight: 700; margin-bottom: 8px; color: var(--auth-heading);
  }
  .auth-card .subtitle {
    font-size: 14px; color: var(--auth-muted); margin-bottom: 28px;
  }
  .form-group { margin-bottom: 18px; }
  .form-group label {
    display: block; font-size: 13px; font-weight: 600;
    color: var(--auth-muted); margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px;
  }
  .form-group input {
    width: 100%; padding: 10px 14px; border-radius: 8px;
    border: 1px solid var(--auth-input-border); background: var(--auth-input-bg); color: var(--auth-heading);
    font-size: 15px; outline: none; transition: border 0.2s, box-shadow 0.2s;
  }
  .form-group input:focus { border-color: var(--auth-accent); box-shadow: 0 0 0 3px rgba(59,130,246,0.15); }
  .btn {
    width: 100%; padding: 12px; border-radius: 8px; border: none;
    background: var(--auth-accent); color: #fff; font-size: 15px; font-weight: 600;
    cursor: pointer; transition: background 0.2s, transform 0.1s; margin-top: 8px;
  }
  .btn:hover { background: var(--auth-accent-hover); }
  .btn:active { transform: scale(0.98); }
  .btn:disabled { opacity: 0.6; cursor: not-allowed; }
  .error-msg {
    background: var(--auth-err-bg); color: var(--auth-err-text); padding: 10px 14px;
    border-radius: 8px; font-size: 13px; margin-bottom: 16px; display: none;
    animation: contentIn 0.2s ease;
  }
  @keyframes contentIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
  .success-msg {
    background: var(--auth-ok-bg); color: var(--auth-ok-text); padding: 10px 14px;
    border-radius: 8px; font-size: 13px; margin-bottom: 16px; display: none;
  }
  .link-row {
    text-align: center; margin-top: 20px; font-size: 14px; color: var(--auth-muted);
  }
  .link-row a { color: var(--auth-link); text-decoration: none; transition: color 0.15s; }
  .link-row a:hover { text-decoration: underline; }
  .brand {
    text-align: center; margin-bottom: 28px; font-size: 14px;
    color: #64748b; letter-spacing: 1px; text-transform: uppercase;
  }
</style>
"""

_AUTH_SCRIPT = """
<script>
async function authSubmit(url, formId, fields) {
  const errEl = document.getElementById('error-msg');
  const successEl = document.getElementById('success-msg');
  const btn = document.querySelector('.btn');
  errEl.style.display = 'none';
  if (successEl) successEl.style.display = 'none';
  btn.disabled = true;
  const body = {};
  fields.forEach(f => { body[f] = document.getElementById(f).value; });
  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    if (!resp.ok) {
      errEl.textContent = data.error || 'Something went wrong';
      errEl.style.display = 'block';
      btn.disabled = false;
      return;
    }
    if (data.message && successEl) {
      successEl.textContent = data.message;
      successEl.style.display = 'block';
      btn.disabled = false;
      return;
    }
    if (data.redirect) window.location.href = data.redirect;
  } catch (e) {
    errEl.textContent = 'Network error. Please try again.';
    errEl.style.display = 'block';
    btn.disabled = false;
  }
}
</script>
"""


@router.get("/login", response_class=HTMLResponse)
def login_page() -> HTMLResponse:
    return HTMLResponse(content=f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Login - BarcodeBuddy</title>{_AUTH_STYLES}</head>
<body>
<div class="auth-card">
  <div class="brand">BarcodeBuddy</div>
  <h1>Welcome back</h1>
  <p class="subtitle">Sign in to your account</p>
  <div id="error-msg" class="error-msg"></div>
  <form onsubmit="event.preventDefault(); authSubmit('/auth/api/login', 'login', ['email','password'])">
    <div class="form-group">
      <label for="email">Email</label>
      <input type="email" id="email" name="email" required autocomplete="email" autofocus>
    </div>
    <div class="form-group">
      <label for="password">Password</label>
      <input type="password" id="password" name="password" required autocomplete="current-password">
    </div>
    <button type="submit" class="btn">Sign In</button>
  </form>
  <div class="link-row">
    Don't have an account? <a href="/auth/signup">Sign up</a>
  </div>
  <div class="link-row" style="margin-top:10px">
    <a href="/auth/reset-request">Forgot password?</a>
  </div>
</div>
{_AUTH_SCRIPT}
</body></html>""")


@router.get("/signup", response_class=HTMLResponse)
def signup_page() -> HTMLResponse:
    return HTMLResponse(content=f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sign Up - BarcodeBuddy</title>{_AUTH_STYLES}</head>
<body>
<div class="auth-card">
  <div class="brand">BarcodeBuddy</div>
  <h1>Create account</h1>
  <p class="subtitle">Get started with BarcodeBuddy</p>
  <div id="error-msg" class="error-msg"></div>
  <form onsubmit="event.preventDefault(); authSubmit('/auth/api/signup', 'signup', ['email','display_name','password'])">
    <div class="form-group">
      <label for="display_name">Display Name</label>
      <input type="text" id="display_name" name="display_name" required autofocus>
    </div>
    <div class="form-group">
      <label for="email">Email</label>
      <input type="email" id="email" name="email" required autocomplete="email">
    </div>
    <div class="form-group">
      <label for="password">Password</label>
      <input type="password" id="password" name="password" required minlength="8" autocomplete="new-password">
    </div>
    <button type="submit" class="btn">Create Account</button>
  </form>
  <div class="link-row">
    Already have an account? <a href="/auth/login">Sign in</a>
  </div>
</div>
{_AUTH_SCRIPT}
</body></html>""")


@router.get("/reset-request", response_class=HTMLResponse)
def reset_request_page() -> HTMLResponse:
    return HTMLResponse(content=f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reset Password - BarcodeBuddy</title>{_AUTH_STYLES}</head>
<body>
<div class="auth-card">
  <div class="brand">BarcodeBuddy</div>
  <h1>Reset password</h1>
  <p class="subtitle">Enter your email to receive a reset link</p>
  <div id="error-msg" class="error-msg"></div>
  <div id="success-msg" class="success-msg"></div>
  <form onsubmit="event.preventDefault(); authSubmit('/auth/api/reset-request', 'reset-request', ['email'])">
    <div class="form-group">
      <label for="email">Email</label>
      <input type="email" id="email" name="email" required autofocus>
    </div>
    <button type="submit" class="btn">Send Reset Link</button>
  </form>
  <div class="link-row">
    <a href="/auth/login">Back to login</a>
  </div>
</div>
{_AUTH_SCRIPT}
</body></html>""")


@router.get("/reset", response_class=HTMLResponse)
def reset_page(token: str = "") -> HTMLResponse:
    return HTMLResponse(content=f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Set New Password - BarcodeBuddy</title>{_AUTH_STYLES}</head>
<body>
<div class="auth-card">
  <div class="brand">BarcodeBuddy</div>
  <h1>Set new password</h1>
  <p class="subtitle">Enter your new password</p>
  <div id="error-msg" class="error-msg"></div>
  <div id="success-msg" class="success-msg"></div>
  <input type="hidden" id="token" value="{token}">
  <form onsubmit="event.preventDefault(); authSubmit('/auth/api/reset-confirm', 'reset', ['token','new_password'])">
    <div class="form-group">
      <label for="new_password">New Password</label>
      <input type="password" id="new_password" name="new_password" required minlength="8" autofocus>
    </div>
    <button type="submit" class="btn">Reset Password</button>
  </form>
  <div class="link-row">
    <a href="/auth/login">Back to login</a>
  </div>
</div>
{_AUTH_SCRIPT}
</body></html>""")


# --- Profile page (authenticated, inside render_shell) ---

@router.get("/profile", response_class=HTMLResponse)
def profile_page(user: User = Depends(require_user)) -> HTMLResponse:
    import html as _h
    name = _h.escape(user.display_name)
    email = _h.escape(user.email)
    role = _h.escape(user.role)
    created = user.created_at.strftime("%B %d, %Y") if user.created_at else "Unknown"

    body = f"""
<style>
  .profile-card {{ background:var(--paper); border:1px solid var(--line); border-radius:12px; padding:28px; max-width:520px; }}
  .profile-card h2 {{ font-size:18px; font-weight:700; margin-bottom:20px; color:var(--text); }}
  .profile-field {{ margin-bottom:16px; }}
  .profile-field label {{ display:block; font-size:12px; font-weight:600; color:var(--muted);
    text-transform:uppercase; letter-spacing:.5px; margin-bottom:4px; }}
  .profile-field .val {{ font-size:15px; color:var(--text); }}
  .profile-field input {{ width:100%; padding:10px 14px; border-radius:8px; border:1px solid var(--line);
    background:var(--paper); color:var(--text); font-size:14px; font-family:inherit; }}
  .profile-field input:focus {{ outline:none; border-color:var(--info); box-shadow:0 0 0 3px rgba(59,130,246,0.15); }}
  .profile-actions {{ display:flex; gap:10px; margin-top:20px; }}
  .profile-actions button {{ padding:10px 20px; border-radius:8px; font-size:14px; font-weight:600;
    cursor:pointer; border:none; transition:all .15s; font-family:inherit; }}
  .profile-actions .btn-primary {{ background:var(--info); color:#fff; }}
  .profile-actions .btn-primary:hover {{ filter:brightness(1.1); }}
  .profile-divider {{ border:none; border-top:1px solid var(--line); margin:24px 0; }}
  .profile-msg {{ padding:10px 14px; border-radius:8px; font-size:13px; margin-bottom:12px; display:none; }}
  .profile-msg.ok {{ background:rgba(52,211,153,0.1); color:var(--success); display:block; }}
  .profile-msg.err {{ background:rgba(248,113,113,0.1); color:var(--failure); display:block; }}
</style>

<div class="page-header">
  <div><p class="page-desc" style="margin-bottom:0">Manage your account settings.</p></div>
</div>

<div class="profile-card">
  <h2>Profile</h2>
  <div id="profile-msg" class="profile-msg"></div>
  <div class="profile-field">
    <label>Email</label>
    <div class="val">{email}</div>
  </div>
  <div class="profile-field">
    <label>Role</label>
    <div class="val" style="text-transform:capitalize">{role}</div>
  </div>
  <div class="profile-field">
    <label>Member Since</label>
    <div class="val">{created}</div>
  </div>
  <div class="profile-field">
    <label>Display Name</label>
    <input type="text" id="prof-name" value="{name}" maxlength="100">
  </div>
  <div class="profile-actions">
    <button class="btn-primary" onclick="saveName()">Save Name</button>
  </div>

  <hr class="profile-divider">

  <h2>Change Password</h2>
  <div id="pw-msg" class="profile-msg"></div>
  <div class="profile-field">
    <label>Current Password</label>
    <input type="password" id="pw-current" autocomplete="current-password">
  </div>
  <div class="profile-field">
    <label>New Password (min 8 characters)</label>
    <input type="password" id="pw-new" minlength="8" autocomplete="new-password">
  </div>
  <div class="profile-actions">
    <button class="btn-primary" onclick="changePw()">Change Password</button>
  </div>
</div>
"""

    js = """<script>
function showMsg(id, msg, ok) {{
  const el = document.getElementById(id);
  el.textContent = msg;
  el.className = 'profile-msg ' + (ok ? 'ok' : 'err');
  setTimeout(() => {{ el.style.display = 'none'; el.className = 'profile-msg'; }}, 5000);
}}

async function saveName() {{
  const name = document.getElementById('prof-name').value.trim();
  if (!name) {{ showMsg('profile-msg', 'Display name cannot be empty', false); return; }}
  const r = await fetch('/auth/api/me/profile', {{
    method: 'PUT', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{display_name: name}})
  }});
  const d = await r.json();
  if (r.ok) {{ showMsg('profile-msg', 'Display name updated', true); }}
  else {{ showMsg('profile-msg', d.error || 'Failed to update', false); }}
}}

async function changePw() {{
  const cur = document.getElementById('pw-current').value;
  const nw = document.getElementById('pw-new').value;
  if (!cur || !nw) {{ showMsg('pw-msg', 'Please fill in both fields', false); return; }}
  if (nw.length < 8) {{ showMsg('pw-msg', 'New password must be at least 8 characters', false); return; }}
  const r = await fetch('/auth/api/me/password', {{
    method: 'PUT', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{current_password: cur, new_password: nw}})
  }});
  const d = await r.json();
  if (r.ok) {{
    showMsg('pw-msg', 'Password changed successfully', true);
    document.getElementById('pw-current').value = '';
    document.getElementById('pw-new').value = '';
  }} else {{ showMsg('pw-msg', d.error || 'Failed to change password', false); }}
}}
</script>"""

    return HTMLResponse(content=render_shell(
        title="Profile",
        active_nav="profile",
        body_html=body,
        body_js=js,
        display_name=user.display_name,
        role=user.role,
    ))
