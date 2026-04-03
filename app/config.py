from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from app.contracts import DEFAULT_WORKFLOW_KEY


DEFAULT_CONFIG = {
    "workflow_key": DEFAULT_WORKFLOW_KEY,
    "input_path": "./data/input",
    "processing_path": "./data/processing",
    "output_path": "./data/output",
    "rejected_path": "./data/rejected",
    "log_path": "./data/logs",
    "barcode_types": ["code128", "auto"],
    "barcode_value_patterns": [],
    "scan_all_pages": True,
    "duplicate_handling": "timestamp",
    "file_stability_delay_ms": 2000,
    "max_pages_scan": 50,
    "poll_interval_ms": 500,
    "barcode_scan_dpi": 300,
    "barcode_upscale_factor": 1.0,
}

REQUIRED_KEYS = {
    "input_path",
    "processing_path",
    "output_path",
    "rejected_path",
    "log_path",
    "barcode_types",
    "scan_all_pages",
    "duplicate_handling",
    "file_stability_delay_ms",
    "max_pages_scan",
}

ALLOWED_KEYS = frozenset(DEFAULT_CONFIG.keys())


@dataclass(frozen=True)
class Settings:
    input_path: Path
    processing_path: Path
    output_path: Path
    rejected_path: Path
    log_path: Path
    barcode_types: tuple[str, ...]
    barcode_value_patterns: tuple[str, ...]
    scan_all_pages: bool
    duplicate_handling: str
    file_stability_delay_ms: int
    max_pages_scan: int
    poll_interval_ms: int
    barcode_scan_dpi: int
    barcode_upscale_factor: float
    workflow_key: str = DEFAULT_WORKFLOW_KEY
    config_version: str = "unknown"

    @property
    def log_file(self) -> Path:
        return self.log_path / "processing_log.jsonl"


def _normalize_barcode_type(value: str) -> str:
    return value.strip().lower().replace("-", "").replace("_", "")


def _normalize_workflow_key(value: str) -> str:
    return value.strip().lower().replace("-", "_")


def _resolve_path(base_dir: Path, configured_path: str) -> Path:
    path = Path(configured_path)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def _normalize_path_identity(path: Path) -> str:
    resolved = str(path)
    return resolved.casefold() if os.name == "nt" else resolved


def _nearest_existing_ancestor(path: Path) -> Path:
    current = path
    while not current.exists():
        parent = current.parent
        if parent == current:
            return current
        current = parent
    return current


def _device_identity(path: Path) -> tuple[str, int | None]:
    anchor = path.anchor.casefold() if os.name == "nt" else path.anchor
    ancestor = _nearest_existing_ancestor(path)
    try:
        device_id: int | None = ancestor.stat().st_dev
    except OSError:
        device_id = None
    return (anchor, device_id)


def load_settings(config_path: Path) -> Settings:
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        raw_config = json.load(handle)

    merged_config = {**DEFAULT_CONFIG, **raw_config}

    missing = REQUIRED_KEYS.difference(raw_config.keys())
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(f"Config file is missing required keys: {missing_list}")

    unexpected = set(raw_config.keys()).difference(ALLOWED_KEYS)
    if unexpected:
        unexpected_list = ", ".join(sorted(unexpected))
        raise ValueError(f"Config file contains unsupported keys: {unexpected_list}")

    base_dir = config_path.parent.resolve()
    barcode_types = tuple(_normalize_barcode_type(item) for item in merged_config["barcode_types"])
    if not barcode_types:
        raise ValueError("Config key 'barcode_types' must contain at least one value.")
    workflow_key = _normalize_workflow_key(str(merged_config["workflow_key"]))
    if not workflow_key:
        raise ValueError("Config key 'workflow_key' must contain at least one value.")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", workflow_key):
        raise ValueError(
            "Config key 'workflow_key' must match ^[a-z0-9][a-z0-9_-]{0,63}$."
        )
    barcode_value_patterns = tuple(str(item).strip() for item in merged_config["barcode_value_patterns"])
    for pattern in barcode_value_patterns:
        if not pattern:
            raise ValueError("Config key 'barcode_value_patterns' cannot contain empty values.")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"Invalid barcode value pattern: {pattern}") from exc

    duplicate_handling = str(merged_config["duplicate_handling"]).strip().lower()
    if duplicate_handling not in {"timestamp", "reject"}:
        raise ValueError("Only 'timestamp' and 'reject' duplicate handling are supported.")

    file_stability_delay_ms = int(merged_config["file_stability_delay_ms"])
    max_pages_scan = int(merged_config["max_pages_scan"])
    poll_interval_ms = int(merged_config["poll_interval_ms"])
    barcode_scan_dpi = int(merged_config["barcode_scan_dpi"])
    barcode_upscale_factor = float(merged_config["barcode_upscale_factor"])
    if file_stability_delay_ms < 500:
        raise ValueError("'file_stability_delay_ms' must be at least 500.")
    if max_pages_scan < 1:
        raise ValueError("'max_pages_scan' must be at least 1.")
    if poll_interval_ms < 100:
        raise ValueError("'poll_interval_ms' must be at least 100.")
    if barcode_scan_dpi < 72:
        raise ValueError("'barcode_scan_dpi' must be at least 72.")
    if barcode_upscale_factor < 1.0:
        raise ValueError("'barcode_upscale_factor' must be at least 1.0.")

    input_path = _resolve_path(base_dir, merged_config["input_path"])
    processing_path = _resolve_path(base_dir, merged_config["processing_path"])
    output_path = _resolve_path(base_dir, merged_config["output_path"])
    rejected_path = _resolve_path(base_dir, merged_config["rejected_path"])
    log_path = _resolve_path(base_dir, merged_config["log_path"])

    managed_paths = (
        input_path,
        processing_path,
        output_path,
        rejected_path,
        log_path,
    )
    normalized_identities = {_normalize_path_identity(path) for path in managed_paths}
    if len(normalized_identities) != len(managed_paths):
        raise ValueError("Managed runtime paths must be distinct.")

    device_identities = {_device_identity(path) for path in managed_paths}
    if len(device_identities) != 1:
        raise ValueError("Managed runtime paths must reside on the same filesystem volume.")

    effective_config = {
        "workflow_key": workflow_key,
        "input_path": merged_config["input_path"],
        "processing_path": merged_config["processing_path"],
        "output_path": merged_config["output_path"],
        "rejected_path": merged_config["rejected_path"],
        "log_path": merged_config["log_path"],
        "barcode_types": list(barcode_types),
        "barcode_value_patterns": list(barcode_value_patterns),
        "scan_all_pages": bool(merged_config["scan_all_pages"]),
        "duplicate_handling": duplicate_handling,
        "file_stability_delay_ms": file_stability_delay_ms,
        "max_pages_scan": max_pages_scan,
        "poll_interval_ms": poll_interval_ms,
        "barcode_scan_dpi": barcode_scan_dpi,
        "barcode_upscale_factor": barcode_upscale_factor,
    }
    config_version = hashlib.sha256(
        json.dumps(
            effective_config,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:12]

    return Settings(
        workflow_key=workflow_key,
        input_path=input_path,
        processing_path=processing_path,
        output_path=output_path,
        rejected_path=rejected_path,
        log_path=log_path,
        barcode_types=barcode_types,
        barcode_value_patterns=barcode_value_patterns,
        scan_all_pages=bool(merged_config["scan_all_pages"]),
        duplicate_handling=duplicate_handling,
        file_stability_delay_ms=file_stability_delay_ms,
        max_pages_scan=max_pages_scan,
        poll_interval_ms=poll_interval_ms,
        barcode_scan_dpi=barcode_scan_dpi,
        barcode_upscale_factor=barcode_upscale_factor,
        config_version=config_version,
    )


def ensure_runtime_directories(settings: Settings) -> None:
    for path in (
        settings.input_path,
        settings.processing_path,
        settings.output_path,
        settings.rejected_path,
        settings.log_path,
    ):
        path.mkdir(parents=True, exist_ok=True)
