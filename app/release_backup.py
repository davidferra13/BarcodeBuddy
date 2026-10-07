from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import stat
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from app.config import load_settings

MANIFEST = "manifest.json"


def _safe_name(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError("Unsafe backup member path.")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {".", ".."} for part in value.split("/")) or str(path) != value:
        raise ValueError("Unsafe backup member path.")
    return value


def _hash_stream(handle) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
        size += len(chunk)
    return digest.hexdigest(), size


def _regular_files(root: Path):
    if root.is_symlink():
        raise ValueError("Backup sources cannot be symlinks.")
    if not root.exists():
        return
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Backup sources cannot contain symlinks.")
        if path.is_file():
            yield path, path.relative_to(root).as_posix()


def _sqlite_snapshot(source: Path, destination: Path) -> None:
    if source.is_symlink():
        raise ValueError("Database source cannot be a symlink.")
    if not source.is_file():
        raise FileNotFoundError(source)
    with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)) as live:
        with closing(sqlite3.connect(destination)) as snapshot:
            live.backup(snapshot)
            snapshot.commit()
            if snapshot.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise ValueError("SQLite backup integrity check failed.")


def _verify_open(archive: zipfile.ZipFile) -> dict:
    infos = archive.infolist()
    names = [info.filename for info in infos]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate archive members.")
    for info in infos:
        _safe_name(info.filename)
        if info.is_dir() or stat.S_ISLNK(info.external_attr >> 16):
            raise ValueError("Only regular backup members are permitted.")
    try:
        manifest = json.loads(archive.read(MANIFEST))
    except (KeyError, ValueError) as error:
        raise ValueError("Missing or invalid backup manifest.") from error
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "1.0":
        raise ValueError("Unsupported backup manifest.")
    members = manifest.get("members")
    if not isinstance(members, list) or not members:
        raise ValueError("Empty or invalid backup manifest.")
    expected = []
    for member in members:
        if not isinstance(member, dict):
            raise ValueError("Invalid backup member metadata.")
        name = _safe_name(member.get("path"))
        if name == MANIFEST or name in expected:
            raise ValueError("Duplicate or reserved manifest member.")
        expected.append(name)
        size = member.get("size_bytes")
        digest = member.get("sha256")
        if type(size) is not int or size < 0 or not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("Invalid checksum metadata.")
    if set(names) != set(expected) | {MANIFEST}:
        raise ValueError("Missing or unlisted backup members.")
    for member in members:
        info = archive.getinfo(member["path"])
        if info.file_size != member["size_bytes"]:
            raise ValueError("Backup member size mismatch.")
        with archive.open(info) as handle:
            digest, size = _hash_stream(handle)
        if digest != member["sha256"] or size != member["size_bytes"]:
            raise ValueError("Backup member checksum mismatch.")
    return {"verified": True, "member_count": len(members), "manifest": manifest}


def verify_backup(archive_path: Path) -> dict:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            return _verify_open(archive)
    except (zipfile.BadZipFile, RuntimeError) as error:
        raise ValueError("Unreadable backup archive.") from error


def create_backup(
    config_path: Path,
    destination: Path,
    *,
    database_path: Path | None = None,
    include_documents: bool = False,
) -> dict:
    config = config_path.resolve()
    if config_path.is_symlink():
        raise ValueError("Config source cannot be a symlink.")
    settings = load_settings(config)
    output = destination.resolve()
    if output.exists():
        raise FileExistsError(output)
    roots = [("logs", settings.log_path), ("journal", settings.processing_path / ".journal")]
    if include_documents:
        roots += [
            ("documents/input", settings.input_path),
            ("documents/processing", settings.processing_path),
            ("documents/output", settings.output_path),
            ("documents/rejected", settings.rejected_path),
        ]
    if any(output.is_relative_to(root.resolve()) for _, root in roots):
        raise ValueError("Backup destination must be outside captured runtime folders.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="barcodebuddy-backup-") as stage:
        sources = [("config/config.customer.json", config)]
        for prefix, root in roots:
            for path, relative in _regular_files(root):
                if prefix == "documents/processing" and relative.startswith(".journal/"):
                    continue
                sources.append((prefix + "/" + relative, path))
        if database_path is not None:
            snapshot = Path(stage) / "database.db"
            _sqlite_snapshot(database_path, snapshot)
            sources.append(("database/barcode_buddy.db", snapshot))
        fd, temp_name = tempfile.mkstemp(prefix=".barcodebuddy-backup-", suffix=".zip", dir=output.parent)
        os.close(fd)
        temporary = Path(temp_name)
        try:
            members = []
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name, source in sources:
                    _safe_name(name)
                    with source.open("rb") as handle:
                        digest, size = _hash_stream(handle)
                    archive.write(source, name)
                    members.append({"path": name, "sha256": digest, "size_bytes": size})
                manifest = {
                    "schema_version": "1.0",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "workflow": settings.workflow_key,
                    "config_version": settings.config_version,
                    "documents_included": include_documents,
                    "database_included": database_path is not None,
                    "members": members,
                }
                archive.writestr(MANIFEST, json.dumps(manifest, indent=2) + "\n")
            result = verify_backup(temporary)
            # Publish only a verified archive; link refuses to overwrite an existing file.
            os.link(temporary, output)
            return {**result, "archive": str(output)}
        finally:
            temporary.unlink(missing_ok=True)


def verified_extract(archive_path: Path, destination: Path) -> dict:
    target = destination.resolve()
    if target.exists():
        raise FileExistsError(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            result = _verify_open(archive)
            staging = Path(tempfile.mkdtemp(prefix=".barcodebuddy-restore-", dir=target.parent))
            try:
                for member in result["manifest"]["members"]:
                    path = staging / member["path"]
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member["path"]) as source, path.open("xb") as output:
                        shutil.copyfileobj(source, output)
                    with path.open("rb") as handle:
                        digest, size = _hash_stream(handle)
                    if digest != member["sha256"] or size != member["size_bytes"]:
                        raise ValueError("Extracted backup checksum mismatch.")
                database = staging / "database/barcode_buddy.db"
                if database.exists():
                    with closing(sqlite3.connect(database)) as restored:
                        if restored.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                            raise ValueError("Restored SQLite integrity check failed.")
                if target.exists():
                    raise FileExistsError(target)
                staging.rename(target)
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
            return {**result, "destination": str(target)}
    except zipfile.BadZipFile as error:
        raise ValueError("Unreadable backup archive.") from error
