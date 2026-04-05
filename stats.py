from __future__ import annotations

import argparse
import os
from pathlib import Path

from rich.console import Console

from app import __version__
from app.config import ensure_runtime_directories, load_settings
from app.logging_utils import configure_structlog
from app.stats import serve_stats_page

console = Console(stderr=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the BarcodeBuddy stats page.")
    parser.add_argument(
        "--config",
        default=os.environ.get("BB_CONFIG", "config.json"),
        help="Path to the JSON config file. Defaults to BB_CONFIG env var or ./config.json",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Host interface to bind. Overrides config server_host. Defaults to 0.0.0.0",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind. Overrides config server_port. Defaults to 8080",
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

    # CLI flags override config; config overrides defaults
    host = args.host or settings.server_host
    port = args.port or settings.server_port

    console.print(f"[bold green]BarcodeBuddy v{__version__}[/bold green] stats page: [link=http://{host}:{port}]http://{host}:{port}[/link]")
    console.print(f"Reading log file: [cyan]{settings.log_file}[/cyan]")
    console.print(f"API docs: [link=http://{host}:{port}/docs]http://{host}:{port}/docs[/link]")
    serve_stats_page(
        settings,
        host=host,
        port=port,
        refresh_seconds=max(5, args.refresh_seconds),
        history_days=max(1, args.history_days),
        recent_limit=max(1, args.recent_limit),
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("[dim]BarcodeBuddy stats page stopped.[/dim]")
