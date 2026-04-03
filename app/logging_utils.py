from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any


def append_jsonl(log_file: Path, payload: dict[str, Any]) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    _rotate_log_if_needed(log_file, payload)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True))
        handle.write("\n")


def iter_jsonl_log_files(log_file: Path) -> list[Path]:
    log_dir = log_file.parent
    if not log_dir.exists():
        return []

    archive_pattern = f"{log_file.stem}.*{log_file.suffix}"
    archived_files = sorted(
        (
            path
            for path in log_dir.glob(archive_pattern)
            if path.is_file() and path != log_file
        ),
        key=lambda path: _archive_sort_key(path, log_file),
    )

    if log_file.exists():
        archived_files.append(log_file)
    return archived_files


def write_json_atomically(destination: Path, payload: dict[str, Any]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_name(f"{destination.name}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)
        handle.write("\n")
    temp_path.replace(destination)


def _rotate_log_if_needed(log_file: Path, payload: dict[str, Any]) -> None:
    if not log_file.exists():
        return

    target_date = _payload_log_date(payload)
    current_log_date = datetime.fromtimestamp(log_file.stat().st_mtime).astimezone().date()
    if current_log_date >= target_date:
        return

    archive_path = log_file.with_name(f"{log_file.stem}.{current_log_date.isoformat()}{log_file.suffix}")
    if archive_path.exists():
        with archive_path.open("a", encoding="utf-8") as archived_handle:
            with log_file.open("r", encoding="utf-8") as current_handle:
                for line in current_handle:
                    archived_handle.write(line)
        log_file.unlink()
        return

    log_file.replace(archive_path)


def _payload_log_date(payload: dict[str, Any]) -> date:
    timestamp_value = payload.get("timestamp")
    if timestamp_value is not None:
        normalized = str(timestamp_value).strip().replace("Z", "+00:00")
        if normalized:
            try:
                parsed = datetime.fromisoformat(normalized)
            except ValueError:
                pass
            else:
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
                return parsed.astimezone().date()
    return datetime.now().astimezone().date()


def _archive_sort_key(path: Path, active_log_file: Path) -> tuple[str, str]:
    archive_date = _archive_date_from_name(path, active_log_file)
    if archive_date is not None:
        return (archive_date.isoformat(), path.name)
    modified_at = datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat()
    return (modified_at, path.name)


def _archive_date_from_name(path: Path, active_log_file: Path) -> date | None:
    prefix = f"{active_log_file.stem}."
    suffix = active_log_file.suffix
    if not path.name.startswith(prefix) or not path.name.endswith(suffix):
        return None

    date_text = path.name[len(prefix):-len(suffix)]
    try:
        return date.fromisoformat(date_text)
    except ValueError:
        return None
