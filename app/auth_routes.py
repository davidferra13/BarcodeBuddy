"""Authentication routes: login, signup, logout, password reset."""

from __future__ import annotations

import re
import time
from collections import defaultdict
from threading import Lock

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import (
    clear_auth_cookie,
    create_access_token,
    create_reset_token,
    hash_password,
    require_user,
    revoke_token,
    set_auth_cookie,
    verify_password,
    verify_reset_token,
    COOKIE_NAME,
)
from app.database import SystemSettings, User, get_db

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


def _check_rate_limit(request: Request) -> JSONResponse | None:
    """Return a 429 response if the client IP exceeds the rate limit, else None."""
    client_ip = request.client.host if request.client else "unknown"
    if not _auth_limiter.is_allowed(client_ip):
        return JSONResponse(status_code=429, content={"error": "Too many requests. Please try again later."})
    return None


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
    email = body.email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return JSONResponse(status_code=400, content={"error": "Invalid email address"})

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return JSONResponse(status_code=409, content={"error": "Email already registered"})

    # First user becomes owner; subsequent users need open signup
    user_count = db.query(User).count()
    if user_count == 0:
        role = "owner"
    else:
        settings = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
        if settings and not settings.open_signup:
            return JSONResponse(status_code=403, content={"error": "Signup is currently disabled. Contact an administrator."})
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
    response = JSONResponse(content={"user": user.to_dict(), "redirect": "/"})
    set_auth_cookie(response, token)
    return response


@router.post("/api/login")
def api_login(request: Request, body: LoginRequest, db: Session = Depends(get_db)) -> JSONResponse:
    blocked = _check_rate_limit(request)
    if blocked:
        return blocked
    email = body.email.strip().lower()
    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if not user or not verify_password(body.password, user.password_hash):
        return JSONResponse(status_code=401, content={"error": "Invalid email or password"})

    token = create_access_token(user, db)
    response = JSONResponse(content={"user": user.to_dict(), "redirect": "/"})
    set_auth_cookie(response, token)
    return response


@router.post("/api/logout")
def api_logout(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        revoke_token(token, db)
    response = JSONResponse(content={"redirect": "/auth/login"})
    clear_auth_cookie(response)
    return response


@router.post("/api/reset-request")
def api_reset_request(request: Request, body: ResetRequestModel, db: Session = Depends(get_db)) -> JSONResponse:
    """Request a password reset. Always returns success to prevent email enumeration."""
    blocked = _check_rate_limit(request)
    if blocked:
        return blocked
    email = body.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user:
        reset_token = create_reset_token(user, db)
        import structlog
        structlog.get_logger().info("password_reset_requested", email=email, reset_url=f"/auth/reset?token={reset_token}")
    return JSONResponse(content={"message": "If an account exists with that email, a reset link has been generated. Check the application log."})


@router.post("/api/reset-confirm")
def api_reset_confirm(body: ResetConfirmModel, db: Session = Depends(get_db)) -> JSONResponse:
    user = verify_reset_token(body.token, db)
    if not user:
        return JSONResponse(status_code=400, content={"error": "Invalid or expired reset token"})
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return JSONResponse(content={"message": "Password reset successfully", "redirect": "/auth/login"})


@router.get("/api/me")
def api_me(user: User = Depends(require_user)) -> JSONResponse:
    return JSONResponse(content={"user": user.to_dict()})


# --- HTML Pages ---

_AUTH_STYLES = """
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0f172a; color: #e2e8f0;
    min-height: 100vh; display: flex; align-items: center; justify-content: center;
  }
  .auth-card {
    background: #1e293b; border-radius: 12px; padding: 40px;
    width: 100%; max-width: 420px; box-shadow: 0 4px 24px rgba(0,0,0,0.3);
  }
  .auth-card h1 {
    font-size: 24px; font-weight: 700; margin-bottom: 8px; color: #f8fafc;
  }
  .auth-card .subtitle {
    font-size: 14px; color: #94a3b8; margin-bottom: 28px;
  }
  .form-group { margin-bottom: 18px; }
  .form-group label {
    display: block; font-size: 13px; font-weight: 600;
    color: #94a3b8; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px;
  }
  .form-group input {
    width: 100%; padding: 10px 14px; border-radius: 8px;
    border: 1px solid #334155; background: #0f172a; color: #f8fafc;
    font-size: 15px; outline: none; transition: border 0.2s;
  }
  .form-group input:focus { border-color: #3b82f6; }
  .btn {
    width: 100%; padding: 12px; border-radius: 8px; border: none;
    background: #3b82f6; color: #fff; font-size: 15px; font-weight: 600;
    cursor: pointer; transition: background 0.2s; margin-top: 8px;
  }
  .btn:hover { background: #2563eb; }
  .btn:disabled { opacity: 0.6; cursor: not-allowed; }
  .error-msg {
    background: #450a0a; color: #fca5a5; padding: 10px 14px;
    border-radius: 8px; font-size: 13px; margin-bottom: 16px; display: none;
  }
  .success-msg {
    background: #052e16; color: #86efac; padding: 10px 14px;
    border-radius: 8px; font-size: 13px; margin-bottom: 16px; display: none;
  }
  .link-row {
    text-align: center; margin-top: 20px; font-size: 14px; color: #94a3b8;
  }
  .link-row a { color: #60a5fa; text-decoration: none; }
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
<title>Login - Barcode Buddy</title>{_AUTH_STYLES}</head>
<body>
<div class="auth-card">
  <div class="brand">Barcode Buddy</div>
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
<title>Sign Up - Barcode Buddy</title>{_AUTH_STYLES}</head>
<body>
<div class="auth-card">
  <div class="brand">Barcode Buddy</div>
  <h1>Create account</h1>
  <p class="subtitle">Get started with Barcode Buddy</p>
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
<title>Reset Password - Barcode Buddy</title>{_AUTH_STYLES}</head>
<body>
<div class="auth-card">
  <div class="brand">Barcode Buddy</div>
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
<title>Set New Password - Barcode Buddy</title>{_AUTH_STYLES}</head>
<body>
<div class="auth-card">
  <div class="brand">Barcode Buddy</div>
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
