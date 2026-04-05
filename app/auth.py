"""Authentication utilities: JWT tokens, password hashing, FastAPI dependencies."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.database import AuditLog, User, UserSession, get_db

# --- Role Hierarchy ---

ROLE_LEVELS: dict[str, int] = {
    "owner": 40,
    "admin": 30,
    "manager": 20,
    "user": 10,
}

VALID_ROLES = frozenset(ROLE_LEVELS.keys())
ASSIGNABLE_ROLES = ("admin", "manager", "user")  # owner is never assignable via API
DEFAULT_OWNER_EMAIL = "mferragamo@danpack.com"
_OWNER_EMAIL_EXPLICIT = bool((os.environ.get("BB_OWNER_EMAIL") or "").strip())
OWNER_EMAIL = (os.environ.get("BB_OWNER_EMAIL", DEFAULT_OWNER_EMAIL) or DEFAULT_OWNER_EMAIL).strip().lower()


def normalize_email(email: str) -> str:
    """Normalize email addresses for storage and identity checks."""
    return email.strip().lower()


def is_owner_email(email: str) -> bool:
    """Return True when the email matches the reserved system owner identity."""
    return normalize_email(email) == OWNER_EMAIL


def configure_owner_email(email: str | None) -> None:
    """Set the reserved owner identity from runtime configuration/environment."""
    global OWNER_EMAIL
    normalized = normalize_email(email or "")
    if normalized:
        OWNER_EMAIL = normalized


def get_role_level(user: User) -> int:
    """Return the numeric privilege level for a user's role."""
    return ROLE_LEVELS.get(user.role, 0)


# --- Configuration ---

_GENERATED_SECRET = secrets.token_hex(32)
SECRET_KEY: str = _GENERATED_SECRET  # Overridden by configure_secret_key() if config provides one
ALGORITHM = "HS256"


def configure_secret_key(key: str) -> None:
    """Set a persistent secret key from config. Sessions survive restarts."""
    global SECRET_KEY
    if key:
        SECRET_KEY = key
ACCESS_TOKEN_EXPIRE_HOURS = 24
COOKIE_NAME = "bb_session"


# --- Password Hashing (bcrypt) ---

def hash_password(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    import bcrypt
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


# --- Token Management ---

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(user: User, db: Session) -> str:
    """Create a JWT access token and persist the session in the database."""
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    jti = secrets.token_hex(16)

    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "jti": jti,
        "iat": now,
        "exp": expires,
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    session = UserSession(
        user_id=user.id,
        token_hash=_hash_token(jti),
        created_at=now,
        expires_at=expires,
    )
    db.add(session)
    db.commit()
    return token


def revoke_token(token: str, db: Session) -> None:
    """Revoke a session by marking it in the database."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        if jti:
            session = db.query(UserSession).filter(
                UserSession.token_hash == _hash_token(jti)
            ).first()
            if session:
                session.is_revoked = True
                db.commit()
    except jwt.PyJWTError:
        pass


def _decode_token(token: str) -> dict | None:
    """Decode and validate a JWT token. Returns payload or None."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


# --- Password Reset ---

def create_reset_token(user: User, db: Session) -> str:
    """Create a password reset token (valid for 1 hour)."""
    from app.database import PasswordResetToken

    raw_token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    reset = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_token(raw_token),
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    db.add(reset)
    db.commit()
    return raw_token


def verify_reset_token(raw_token: str, db: Session) -> User | None:
    """Verify a reset token and return the user if valid."""
    from app.database import PasswordResetToken

    token_hash = _hash_token(raw_token)
    reset = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.used == False,
        PasswordResetToken.expires_at > datetime.now(timezone.utc),
    ).first()
    if not reset:
        return None
    reset.used = True
    db.commit()
    return db.query(User).filter(User.id == reset.user_id).first()


# --- Audit Logging ---

def log_audit(db: Session, actor: User, action: str, target_id: str | None = None, detail: dict | None = None) -> None:
    """Write an entry to the audit log."""
    db.add(AuditLog(
        actor_id=actor.id,
        action=action,
        target_id=target_id,
        detail=json.dumps(detail or {}, default=str),
    ))
    db.commit()


# --- FastAPI Dependencies ---

def _get_token_from_request(request: Request) -> str | None:
    """Extract token from cookie or Authorization header."""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        return token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    """Returns the current user or None if not authenticated."""
    token = _get_token_from_request(request)
    if not token:
        return None
    payload = _decode_token(token)
    if not payload:
        return None

    # Verify session not revoked
    jti = payload.get("jti")
    if jti:
        now = datetime.now(timezone.utc)
        session = db.query(UserSession).filter(
            UserSession.token_hash == _hash_token(jti),
            UserSession.is_revoked == False,
            UserSession.expires_at > now,
        ).first()
        if not session:
            return None

    user_id = payload.get("sub")
    if not user_id:
        return None
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    return user


def require_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Require an authenticated user. Redirects to login for HTML requests, 401 for API."""
    user = get_current_user(request, db)
    if user is None:
        if _is_html_request(request):
            raise HTTPException(
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": "/auth/login"},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


def require_manager(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Require manager or higher (manager, admin, owner)."""
    user = require_user(request, db)
    if get_role_level(user) < ROLE_LEVELS["manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager access required",
        )
    return user


def require_admin(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Require admin or higher (admin, owner)."""
    user = require_user(request, db)
    if get_role_level(user) < ROLE_LEVELS["admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


def require_owner(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Require the system owner."""
    user = require_user(request, db)
    if user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner access required",
        )
    return user


def _is_html_request(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept


def _should_secure_cookie(request: Request | None = None) -> bool:
    if request is None:
        return False

    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    if forwarded_proto == "https":
        return True
    return request.url.scheme.lower() == "https"


def set_auth_cookie(
    response: Response,
    token: str,
    *,
    request: Request | None = None,
    secure_override: bool | None = None,
) -> None:
    """Set the authentication cookie on a response."""
    secure_flag = _should_secure_cookie(request) if secure_override is None else secure_override
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure_flag,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    """Clear the authentication cookie."""
    response.delete_cookie(key=COOKIE_NAME, path="/")
