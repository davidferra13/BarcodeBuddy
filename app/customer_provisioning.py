from __future__ import annotations

import json
import os
import re
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import Settings, ensure_runtime_directories, load_settings

_WORKFLOW_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


@dataclass(frozen=True)
class ProvisionResult:
    config_path: Path
    settings: Settings


def normalize_workflow_key(value: str) -> str:
    key = value.strip().lower().replace("-", "_")
    if not _WORKFLOW_PATTERN.fullmatch(key):
        raise ValueError(
            "workflow_key must match ^[a-z0-9][a-z0-9_-]{0,63}$ after normalization"
        )
    return key


def build_customer_config(
    workflow_key: str,
    runtime_root: Path,
    *,
    secret_key: str | None = None,
    server_port: int = 8080,
    barcode_value_patterns: tuple[str, ...] = (),
    duplicate_handling: str = "timestamp",
) -> dict[str, Any]:
    key = normalize_workflow_key(workflow_key)
    root = runtime_root.resolve() / key
    resolved_secret = (
        secret_key
        or (os.environ.get("BB_SECRET_KEY") or "").strip()
        or secrets.token_urlsafe(48)
    )
    if len(resolved_secret) < 32:
        raise ValueError("Customer secret_key must contain at least 32 characters.")

    return {
        "workflow_key": key,
        "input_path": str(root / "input"),
        "processing_path": str(root / "processing"),
        "output_path": str(root / "output"),
        "rejected_path": str(root / "rejected"),
        "log_path": str(root / "logs"),
        "barcode_types": ["code128", "auto"],
        "barcode_value_patterns": list(barcode_value_patterns),
        "scan_all_pages": True,
        "duplicate_handling": duplicate_handling,
        "file_stability_delay_ms": 2000,
        "max_pages_scan": 50,
        "poll_interval_ms": 500,
        "barcode_scan_dpi": 300,
        "barcode_upscale_factor": 1.0,
        "server_host": "127.0.0.1",
        "server_port": int(server_port),
        "secret_key": resolved_secret,
    }


def provision_customer(
    *,
    config_path: Path,
    workflow_key: str,
    runtime_root: Path,
    secret_key: str | None = None,
    server_port: int = 8080,
    barcode_value_patterns: tuple[str, ...] = (),
    duplicate_handling: str = "timestamp",
    overwrite: bool = False,
) -> ProvisionResult:
    destination = config_path.resolve()
    if destination.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing customer config: {destination}")

    config = build_customer_config(
        workflow_key,
        runtime_root,
        secret_key=secret_key,
        server_port=server_port,
        barcode_value_patterns=barcode_value_patterns,
        duplicate_handling=duplicate_handling,
    )

    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_name(destination.name + ".tmp")
    try:
        tmp.write_text(
            json.dumps(config, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        tmp.replace(destination)
    finally:
        tmp.unlink(missing_ok=True)

    settings = load_settings(destination)
    ensure_runtime_directories(settings)
    return ProvisionResult(config_path=destination, settings=settings)
