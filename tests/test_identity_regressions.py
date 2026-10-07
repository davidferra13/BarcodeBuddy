"""Regressions found by scripts/identity_acceptance.py on 2026-10-07.

Each one was invisible to the existing suite because the suite called the
processor, the backup and the feedback router directly instead of through the
running service a customer actually uses.
"""
from __future__ import annotations

import shutil
import sqlite3
import threading
import time
import zipfile
from contextlib import closing
from pathlib import Path

import pytest

from app.barcode_generator import generate_code128
from app.config import Settings, ensure_runtime_directories
from app.customer_provisioning import provision_customer
from app.processor import BarcodeBuddyService
from app.release_backup import create_backup, verified_extract
from app.runtime_lock import ServiceLock


def _default_timing_settings(root: Path) -> Settings:
    settings = Settings(
        input_path=root / "input", processing_path=root / "processing", output_path=root / "output",
        rejected_path=root / "rejected", log_path=root / "logs",
        barcode_types=("code128", "auto"), barcode_value_patterns=(r"^PO-[0-9]+$",),
        scan_all_pages=True, duplicate_handling="reject",
        file_stability_delay_ms=2000, poll_interval_ms=500, max_pages_scan=50,
        workflow_key="hot_folder",
    )
    ensure_runtime_directories(settings)
    return settings


def test_quiet_scan_is_filed_by_the_running_watcher_with_default_timing(tmp_path: Path) -> None:
    """A scan that lands and then sits still must be filed, not rejected as FILE_LOCKED.

    With the watcher re-checking only every 5 s, a quiet file hit the 10 s
    stuck-file limit before its four stability checks completed.
    """
    settings = _default_timing_settings(tmp_path / "runtime")
    source = tmp_path / "slip.pdf"
    image = generate_code128("PO-424242", scale=5).convert("RGB")
    try:
        image.save(source, "PDF")
    finally:
        image.close()

    service = BarcodeBuddyService(settings)
    worker = threading.Thread(target=service.run_forever, daemon=True)
    worker.start()
    try:
        time.sleep(1.0)  # let the watcher settle so the scan arrives into a quiet folder
        shutil.copyfile(source, settings.input_path / "scan0001.pdf")
        deadline = time.monotonic() + 9.0  # must beat the 10 s stuck-file limit
        while time.monotonic() < deadline and not list(settings.output_path.rglob("PO-424242.pdf")):
            time.sleep(0.1)
    finally:
        service.stop()
        worker.join(timeout=20)

    assert not worker.is_alive()
    assert [p.name for p in settings.rejected_path.iterdir()] == []
    assert len(list(settings.output_path.rglob("PO-424242.pdf"))) == 1
    assert [p for p in settings.input_path.iterdir() if p.is_file()] == []


def test_backup_succeeds_while_the_services_hold_their_files_open(tmp_path: Path) -> None:
    """Scheduled backups run while the system is up: the service lock is held
    and the database is open in WAL mode. Neither may break the backup."""
    config_path = tmp_path / "config.customer.json"
    settings = provision_customer(config_path=config_path, workflow_key="receiving",
                                  runtime_root=tmp_path / "runtime").settings
    database_path = settings.log_path / "barcode_buddy.db"
    lock = ServiceLock(settings.log_path / ".service.lock", metadata={"workflow": settings.workflow_key})
    lock.acquire()
    try:
        with closing(sqlite3.connect(database_path)) as live:
            live.execute("PRAGMA journal_mode=WAL")
            live.execute("CREATE TABLE marker (value TEXT)")
            live.execute("INSERT INTO marker VALUES ('kept')")
            live.commit()
            live.execute("BEGIN")
            live.execute("SELECT * FROM marker").fetchall()  # keep a read transaction open
            archive = tmp_path / "backups" / "running.zip"
            result = create_backup(config_path, archive, database_path=database_path, include_documents=True)
            live.rollback()
    finally:
        lock.release()

    assert result["verified"] is True
    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
    assert "logs/.service.lock" not in names
    assert not any(name.endswith((".db-wal", ".db-shm")) for name in names)
    assert {"logs/barcode_buddy.db", "database/barcode_buddy.db"} <= names

    verified_extract(archive, tmp_path / "restored")
    for member in ("logs/barcode_buddy.db", "database/barcode_buddy.db"):
        with closing(sqlite3.connect(tmp_path / "restored" / member)) as restored:
            assert restored.execute("PRAGMA quick_check").fetchall() == [("ok",)]
            assert restored.execute("SELECT value FROM marker").fetchall() == [("kept",)]


def test_feedback_is_written_to_the_installations_log_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Feedback used to land in ./data/logs relative to wherever the app was
    started, outside the customer's configured folder and outside its backup."""
    from app import feedback

    monkeypatch.delenv("BB_LOG_PATH", raising=False)
    monkeypatch.setattr(feedback, "_configured_log_path", None)
    assert feedback._feedback_file() == Path("data/logs") / "feedback.jsonl"

    feedback.configure_feedback_path(tmp_path / "customer-logs")
    assert feedback._feedback_file() == tmp_path / "customer-logs" / "feedback.jsonl"

    monkeypatch.setenv("BB_LOG_PATH", str(tmp_path / "explicit"))
    assert feedback._feedback_file() == tmp_path / "explicit" / "feedback.jsonl"


def test_web_app_points_feedback_at_its_configured_log_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app import database, feedback
    from app.stats import create_stats_app

    monkeypatch.delenv("BB_LOG_PATH", raising=False)
    monkeypatch.setattr(feedback, "_configured_log_path", None)
    settings = _default_timing_settings(tmp_path / "runtime").model_copy(
        update={"secret_key": "identity-regression-secret-0123456789abcdef"})
    app = create_stats_app(settings)
    try:
        assert feedback._feedback_file() == settings.log_path / "feedback.jsonl"
    finally:
        scheduler = getattr(app.state, "alert_scheduler", None)
        if scheduler is not None and scheduler.running:
            scheduler.shutdown(wait=False)
        database.shutdown_db()
