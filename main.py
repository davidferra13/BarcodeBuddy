from __future__ import annotations

import argparse
import os
import signal
from datetime import datetime, timezone
from pathlib import Path

from app import __version__
from app.config import ensure_runtime_directories, load_settings
from app.contracts import SERVICE_EVENT_STARTUP
from app.logging_utils import configure_structlog
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
    configure_structlog()
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

            def _handle_stop_signal(signum: int, frame: object) -> None:
                print(f"Barcode Buddy received signal {signum}, shutting down...")
                service.stop()

            signal.signal(signal.SIGINT, _handle_stop_signal)
            signal.signal(signal.SIGTERM, _handle_stop_signal)

            service.log_service_event(SERVICE_EVENT_STARTUP)
            service.recover_processing_files()
            print(f"Barcode Buddy v{__version__} watching: {settings.input_path}")
            service.run_forever()
    except ServiceLockError as exc:
        raise SystemExit(str(exc)) from exc

    print("Barcode Buddy stopped.")


if __name__ == "__main__":
    main()
