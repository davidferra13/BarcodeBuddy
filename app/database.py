"""Database models and engine setup for Barcode Buddy multi-user system."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, event
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

Base = declarative_base()

_engine = None
_SessionLocal: sessionmaker | None = None
_db_path: Path | None = None


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="user")  # "owner", "admin", "manager", "user"
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "display_name": self.display_name,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(Boolean, nullable=False, default=False)

    user = relationship("User", back_populates="sessions")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, nullable=False, default=False)


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    sku = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=False, default="")
    quantity = Column(Integer, nullable=False, default=0)
    unit = Column(String(50), nullable=False, default="each")
    location = Column(String(255), nullable=False, default="")
    category = Column(String(100), nullable=False, default="")
    tags = Column(Text, nullable=False, default="")  # comma-separated
    notes = Column(Text, nullable=False, default="")
    status = Column(String(20), nullable=False, default="active")  # active, archived
    barcode_value = Column(String(255), nullable=False, index=True)
    barcode_type = Column(String(30), nullable=False, default="Code128")  # Code128, QRCode, etc.
    min_quantity = Column(Integer, nullable=False, default=0)
    cost = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User")
    transactions = relationship("InventoryTransaction", back_populates="item", cascade="all, delete-orphan",
                                order_by="InventoryTransaction.created_at.desc()")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "sku": self.sku,
            "description": self.description,
            "quantity": self.quantity,
            "unit": self.unit,
            "location": self.location,
            "category": self.category,
            "tags": self.tags,
            "notes": self.notes,
            "status": self.status,
            "barcode_value": self.barcode_value,
            "barcode_type": self.barcode_type,
            "min_quantity": self.min_quantity,
            "cost": self.cost,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    item_id = Column(String(36), ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    quantity_change = Column(Integer, nullable=False)
    quantity_after = Column(Integer, nullable=False)
    reason = Column(String(50), nullable=False)  # received, sold, adjusted, damaged, returned, initial
    notes = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    item = relationship("InventoryItem", back_populates="transactions")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "item_id": self.item_id,
            "user_id": self.user_id,
            "quantity_change": self.quantity_change,
            "quantity_after": self.quantity_after,
            "reason": self.reason,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(50), nullable=False)
    target_id = Column(String(36), nullable=True)
    detail = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)


class AlertConfig(Base):
    __tablename__ = "alert_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_type = Column(String(50), nullable=False)  # low_stock, out_of_stock, processing_failure
    enabled = Column(Boolean, nullable=False, default=True)
    webhook_url = Column(Text, nullable=False, default="")  # Optional webhook URL
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_type = Column(String(50), nullable=False)  # low_stock, out_of_stock, processing_failure
    severity = Column(String(20), nullable=False, default="warning")  # info, warning, critical
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False, default="")
    item_id = Column(String(36), nullable=True)  # Optional link to inventory item
    is_read = Column(Boolean, nullable=False, default=False)
    is_dismissed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class SystemSettings(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, default=1)
    open_signup = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


def _ensure_system_settings(session_factory: sessionmaker) -> None:
    """Ensure the single system_settings row exists."""
    db = session_factory()
    try:
        row = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
        if not row:
            db.add(SystemSettings(id=1, open_signup=False))
            db.commit()
    finally:
        db.close()


def init_db(db_path: Path) -> None:
    """Initialize the database engine and create tables."""
    global _engine, _SessionLocal, _db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_url = f"sqlite:///{db_path}"
    _engine = create_engine(db_url, connect_args={"check_same_thread": False})
    _db_path = db_path

    @event.listens_for(_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=_engine)
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    _ensure_system_settings(_SessionLocal)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


def shutdown_db() -> None:
    """Dispose engine/session globals to release open DB handles."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def get_database_path() -> Path:
    """Return the current database file path."""
    if _db_path is None:
        raise RuntimeError("Database path not initialized. Call init_db() first.")
    return _db_path


def backup_database(backup_dir: Path, *, max_backups: int = 14) -> Path:
    """Create a SQLite backup file and enforce a rolling retention policy."""
    source_path = get_database_path()
    backup_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = backup_dir / f"barcode_buddy.{stamp}.db"

    source = sqlite3.connect(str(source_path))
    destination = sqlite3.connect(str(target))
    try:
        source.backup(destination)
        destination.commit()
    finally:
        destination.close()
        source.close()

    backups = sorted(backup_dir.glob("barcode_buddy.*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for stale in backups[max(1, max_backups):]:
        stale.unlink(missing_ok=True)

    return target


def revoke_expired_sessions(now: datetime | None = None) -> int:
    """Revoke expired sessions and return affected row count."""
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    db = _SessionLocal()
    try:
        current = now or datetime.now(timezone.utc)
        affected = db.query(UserSession).filter(
            UserSession.is_revoked == False,
            UserSession.expires_at <= current,
        ).update({"is_revoked": True}, synchronize_session=False)
        db.commit()
        return int(affected or 0)
    finally:
        db.close()
