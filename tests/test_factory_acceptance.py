"""Actual reference processing, safe recovery and database-backup evidence."""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from app import database
from scripts.factory_acceptance import run_reference_acceptance


@pytest.fixture(autouse=True)
def isolated_database_globals():
    # Existing suite fixtures initialize their own DB engines. Close test handles.
    database.shutdown_db()
    yield
    database.shutdown_db()


def test_real_reference_probes_and_evidence(tmp_path):
    root = tmp_path / "reference"
    report = run_reference_acceptance(root)
    assert report["passed"] is True, json.dumps(report, sort_keys=True)
    assert report["synthetic"] is True
    assert report["customer_approval"] is False
    assert report["deployment_verified"] is False
    assert {p["id"] for p in report["probes"]} == {
        "code128-pdf", "no-barcode-rejection", "duplicate-rejection",
        "stranded-file-recovery", "sqlite-backup",
    }
    assert all(p["passed"] is True for p in report["probes"])
    assert all("expected" in p and "observed" in p for p in report["probes"])
    json.dumps(report)
    rejected = sorted((root / "rejected").glob("*.meta.json"))
    assert len(rejected) == 2
    assert len(list((root / "output").rglob("PO-910001.pdf"))) == 1
    assert (root / "input" / "stranded.pdf").is_file()
    assert not (root / "processing" / "stranded.pdf").exists()
    backup = next((root / "backups").glob("*.db"))
    with sqlite3.connect(backup) as db:
        assert db.execute("pragma integrity_check").fetchone()[0] == "ok"
        assert db.execute("select open_signup from system_settings where id=1").fetchone() == (1,)
    assert database._engine is None


def test_existing_root_is_preserved_and_refused(tmp_path):
    marker = tmp_path / "buyer-document.pdf"
    marker.write_bytes(b"preserve buyer data")
    with pytest.raises(FileExistsError):
        run_reference_acceptance(tmp_path)
    assert marker.read_bytes() == b"preserve buyer data"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["buyer-document.pdf"]


def test_active_database_is_never_replaced(tmp_path):
    database.init_db(tmp_path / "active.db")
    engine = database._engine
    try:
        with pytest.raises(RuntimeError, match="active database"):
            run_reference_acceptance(tmp_path / "probe")
        assert database._engine is engine
        assert not (tmp_path / "probe").exists()
    finally:
        database.shutdown_db()


def test_failed_processor_probe_keeps_failure_evidence(tmp_path, monkeypatch):
    from app.processor import BarcodeBuddyService, ProcessingResult
    monkeypatch.setattr(BarcodeBuddyService, "process_file", lambda self, p: ProcessingResult(
        processing_id="synthetic-failure", status="failure", stage="validation",
        original_filename=p.name, duration_ms=0, reason="BARCODE_NOT_FOUND"))
    report = run_reference_acceptance(tmp_path / "failed")
    assert report["passed"] is False
    assert next(p for p in report["probes"] if p["id"] == "code128-pdf")["passed"] is False
    assert database._engine is None


def test_cli_writes_machine_readable_receipt_and_refuses_overwrite(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "factory_acceptance.py"
    receipt = tmp_path / "receipt.json"
    result = subprocess.run([sys.executable, str(script), "--output", str(receipt)],
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    report = json.loads(receipt.read_text(encoding="utf-8"))
    assert report["passed"] is True, json.dumps(report, sort_keys=True)
    assert all(p["passed"] for p in report["probes"])
    original = receipt.read_bytes()
    again = subprocess.run([sys.executable, str(script), "--output", str(receipt)],
                           capture_output=True, text=True, timeout=90)
    assert again.returncode != 0
    assert receipt.read_bytes() == original


def test_database_is_shutdown_after_backup_error(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("Synthetic backup failure")
    monkeypatch.setattr(database, "backup_database", fail)
    with pytest.raises(OSError, match="Synthetic backup failure"):
        run_reference_acceptance(tmp_path / "backup-error")
    assert database._engine is None


def test_read_only_database_connections_are_closed(tmp_path, monkeypatch):
    original_connect = sqlite3.connect
    read_connections = []
    def track(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        if kwargs.get("uri") and "?mode=ro" in str(args[0]):
            read_connections.append(connection)
        return connection
    monkeypatch.setattr(sqlite3, "connect", track)
    try:
        assert run_reference_acceptance(tmp_path / "closed-connections")["passed"] is True
        assert len(read_connections) == 2
        for connection in read_connections:
            with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
                connection.execute("SELECT 1")
    finally:
        for connection in read_connections:
            connection.close()
