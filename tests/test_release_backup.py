from __future__ import annotations
import hashlib
import importlib
import importlib.util
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest
from app.customer_provisioning import provision_customer


def api():
    assert importlib.util.find_spec("app.release_backup") is not None, "Verified backup support is missing"
    return importlib.import_module("app.release_backup")


def fixture(tmp_path):
    config = tmp_path / "config.customer.json"
    result = provision_customer(config_path=config, workflow_key="receiving", runtime_root=tmp_path / "runtime")
    (result.settings.log_path / "events.jsonl").write_text('{"event":"success"}\n')
    (result.settings.output_path / "PO-1.pdf").write_bytes(b"private-document")
    return config, result.settings


def rewrite_archive(source, destination, *, drop=None, replace=None, extra=None):
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(destination, "w") as dst:
        for info in src.infolist():
            if info.filename == drop:
                continue
            payload = (replace or {}).get(info.filename, src.read(info.filename))
            dst.writestr(info.filename, payload)
        for name, payload in (extra or {}).items():
            dst.writestr(name, payload)


def test_backup_round_trip_preserves_config_and_excludes_documents(tmp_path):
    config, _ = fixture(tmp_path)
    archive = tmp_path / "backup.zip"
    result = api().create_backup(config, archive)
    verified = api().verify_backup(archive)
    assert result["verified"] is True
    assert verified["verified"] is True
    with zipfile.ZipFile(archive) as z:
        assert "config/config.customer.json" in z.namelist()
        assert "logs/events.jsonl" in z.namelist()
        assert not any(name.startswith("documents/") for name in z.namelist())
    restored = tmp_path / "restored"
    api().verified_extract(archive, restored)
    assert (restored / "config/config.customer.json").read_bytes() == config.read_bytes()
    assert (restored / "logs/events.jsonl").read_text() == '{"event":"success"}\n'


def test_backup_includes_documents_only_when_requested(tmp_path):
    config, _ = fixture(tmp_path)
    archive = tmp_path / "with-docs.zip"
    api().create_backup(config, archive, include_documents=True)
    restored = tmp_path / "restored"
    api().verified_extract(archive, restored)
    assert (restored / "documents/output/PO-1.pdf").read_bytes() == b"private-document"


def test_backup_snapshots_committed_wal_rows_without_mutating_live_database(tmp_path):
    config, _ = fixture(tmp_path)
    database = tmp_path / "live.db"
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE orders (id TEXT)")
        connection.execute("INSERT INTO orders VALUES ('PO-101')")
        connection.commit()
        archive = tmp_path / "database.zip"
        api().create_backup(config, archive, database_path=database)
        restored = tmp_path / "restored"
        api().verified_extract(archive, restored)
        with sqlite3.connect(restored / "database/barcode_buddy.db") as restored_db:
            assert restored_db.execute("SELECT id FROM orders").fetchall() == [("PO-101",)]
            assert restored_db.execute("PRAGMA quick_check").fetchone() == ("ok",)
        assert connection.execute("SELECT id FROM orders").fetchall() == [("PO-101",)]
    finally:
        connection.close()


@pytest.mark.parametrize("mutation", ["changed", "missing", "extra"])
def test_backup_verification_rejects_tampered_or_incomplete_members(tmp_path, mutation):
    config, _ = fixture(tmp_path)
    good = tmp_path / "good.zip"
    api().create_backup(config, good)
    bad = tmp_path / "bad.zip"
    options = {
        "changed": {"replace": {"logs/events.jsonl": b"tampered"}},
        "missing": {"drop": "logs/events.jsonl"},
        "extra": {"extra": {"unlisted.txt": b"unexpected"}},
    }
    rewrite_archive(good, bad, **options[mutation])
    with pytest.raises(ValueError):
        api().verify_backup(bad)
    with pytest.raises(ValueError):
        api().verified_extract(bad, tmp_path / "extracted")
    assert not (tmp_path / "extracted").exists()


@pytest.mark.parametrize("unsafe", ["../escape.txt", "/absolute.txt", "C:/escape.txt", "dir\\escape.txt"])
def test_verified_extract_rejects_unsafe_archive_paths_before_writing(tmp_path, unsafe):
    archive = tmp_path / "unsafe.zip"
    payload = b"escape"
    manifest = {
        "schema_version": "1.0",
        "members": [{"path": unsafe, "sha256": hashlib.sha256(payload).hexdigest(), "size_bytes": len(payload)}],
    }
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("manifest.json", json.dumps(manifest))
        z.writestr(unsafe, payload)
    with pytest.raises(ValueError):
        api().verified_extract(archive, tmp_path / "restored")
    assert not (tmp_path / "restored").exists()
    assert not (tmp_path / "escape.txt").exists()


def test_restore_refuses_existing_directory_without_touching_it(tmp_path):
    config, _ = fixture(tmp_path)
    archive = tmp_path / "backup.zip"
    api().create_backup(config, archive)
    destination = tmp_path / "existing"
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("owner data")
    with pytest.raises(FileExistsError):
        api().verified_extract(archive, destination)
    assert sentinel.read_text() == "owner data"


def test_backup_refuses_missing_database_and_existing_archive(tmp_path):
    config, _ = fixture(tmp_path)
    archive = tmp_path / "backup.zip"
    with pytest.raises(FileNotFoundError):
        api().create_backup(config, archive, database_path=tmp_path / "missing.db")
    assert not archive.exists()
    api().create_backup(config, archive)
    before = archive.read_bytes()
    with pytest.raises(FileExistsError):
        api().create_backup(config, archive)
    assert archive.read_bytes() == before


def test_backup_rejects_symlinks_in_metadata(tmp_path):
    config, settings = fixture(tmp_path)
    outside = tmp_path / "private.txt"
    outside.write_text("unrelated private data")
    link = settings.log_path / "linked.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("Creating symlinks is unavailable on this Windows account")
    with pytest.raises(ValueError, match="symlink"):
        api().create_backup(config, tmp_path / "backup.zip")


def test_backup_with_active_workflow_lock_excludes_runtime_ownership(tmp_path):
    from app.runtime_lock import ServiceLock
    config, settings = fixture(tmp_path)
    lock_path = settings.log_path / ".service.lock"
    with ServiceLock(lock_path, metadata={"workflow": settings.workflow_key, "pid": 12345}):
        archive = tmp_path / "active-workflow.zip"
        result = api().create_backup(config, archive, include_documents=True)
        assert result["verified"] is True
        restored = tmp_path / "restored"
        api().verified_extract(archive, restored)
        assert not (restored / "logs/.service.lock").exists()
        assert (restored / "logs/events.jsonl").read_text() == '{"event":"success"}\n'
        assert (restored / "documents/output/PO-1.pdf").read_bytes() == b"private-document"


def test_live_database_in_log_folder_is_restored_only_from_snapshot(tmp_path):
    # The live database is never raw-copied. It is captured twice through SQLite's
    # backup API: at its own path (so a restored logs folder works as-is) and as
    # the canonical database/barcode_buddy.db. Its WAL, SHM and journal never are.
    from contextlib import closing
    config, settings = fixture(tmp_path)
    database = settings.log_path / "barcode_buddy.db"
    unrelated = settings.log_path / "other.db"
    unrelated.write_bytes(b"retain unrelated recorded file")
    with closing(sqlite3.connect(database)) as live:
        live.execute("PRAGMA journal_mode=WAL")
        live.execute("CREATE TABLE proof (value TEXT)")
        live.execute("INSERT INTO proof VALUES ('committed-reference-row')")
        live.commit()
        archive = tmp_path / "live-log-database.zip"
        result = api().create_backup(config, archive, database_path=database)
        members = {m["path"] for m in result["manifest"]["members"]}
        assert {"database/barcode_buddy.db", "logs/barcode_buddy.db"} <= members
        assert not any(m in members for m in (
            "logs/barcode_buddy.db-wal", "logs/barcode_buddy.db-shm", "logs/barcode_buddy.db-journal",
        ))
        restored = tmp_path / "restored"
        api().verified_extract(archive, restored)
        for member in ("database/barcode_buddy.db", "logs/barcode_buddy.db"):
            with closing(sqlite3.connect(restored / member)) as copied:
                assert copied.execute("SELECT value FROM proof").fetchall() == [("committed-reference-row",)]
                assert copied.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert (restored / "logs/other.db").read_bytes() == unrelated.read_bytes()
        assert live.execute("SELECT value FROM proof").fetchall() == [("committed-reference-row",)]
