from __future__ import annotations

import argparse
from pathlib import Path

from app import __version__
from app.config import ensure_runtime_directories, load_settings
from app.logging_utils import configure_structlog
from app.stats import serve_stats_page


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the Barcode Buddy stats page.")
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to the JSON config file. Defaults to ./config.json",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface to bind. Defaults to 127.0.0.1",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to bind. Defaults to 8080",
    )
    parser.add_argument(
        "--refresh-seconds",
        type=int,
        default=15,
        help="Browser auto-refresh interval in seconds. Defaults to 15",
    )
    parser.add_argument(
        "--history-days",
        type=int,
        default=14,
        help="Number of days to show in the daily history chart. Defaults to 14",
    )
    parser.add_argument(
        "--recent-limit",
        type=int,
        default=25,
        help="Number of recent documents to show on the page. Defaults to 25",
    )
    return parser.parse_args()


def main() -> None:
    configure_structlog()
    args = parse_args()
    config_path = Path(args.config).resolve()
    settings = load_settings(config_path)
    ensure_runtime_directories(settings)

    print(f"Barcode Buddy v{__version__} stats page: http://{args.host}:{args.port}")
    print(f"Reading log file: {settings.log_file}")
    print(f"API docs available at: http://{args.host}:{args.port}/docs")
    serve_stats_page(
        settings,
        host=args.host,
        port=args.port,
        refresh_seconds=max(5, args.refresh_seconds),
        history_days=max(1, args.history_days),
        recent_limit=max(1, args.recent_limit),
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Barcode Buddy stats page stopped.")
