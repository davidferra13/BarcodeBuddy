from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

from app import __version__
from app.config import ensure_runtime_directories, load_settings
from app.contracts import SERVICE_EVENT_STARTUP
from app.processor import BarcodeBuddyService
from app.runtime_lock import ServiceLock, ServiceLockError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Barcode Buddy ingestion service.")
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to the JSON config file. Defaults to ./config.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = Path(args.config).resolve()
    settings = load_settings(config_path)
    ensure_runtime_directories(settings)

    lock = ServiceLock(
        settings.log_path / ".service.lock",
        metadata={
            "workflow": settings.workflow_key,
            "config_path": str(config_path),
            "config_version": settings.config_version,
            "pid": os.getpid(),
            "acquired_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    try:
        with lock:
            service = BarcodeBuddyService(settings)
            service.log_service_event(SERVICE_EVENT_STARTUP)
            service.recover_processing_files()
            print(f"Barcode Buddy v{__version__} watching: {settings.input_path}")
            service.run_forever()
    except ServiceLockError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Barcode Buddy stopped.")
