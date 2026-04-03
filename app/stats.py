from __future__ import annotations

import html
import json
from collections import Counter
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from statistics import mean
from typing import Any
from urllib.parse import urlsplit

from app.config import Settings
from app.contracts import (
    SERVICE_EVENT_HEARTBEAT,
    SERVICE_EVENT_SHUTDOWN,
    SERVICE_EVENT_STARTUP,
    STAGE_SERVICE,
)
from app.logging_utils import iter_jsonl_log_files


def build_stats_snapshot(
    settings: Settings,
    *,
    now: datetime | None = None,
    history_days: int = 14,
    recent_limit: int = 25,
) -> dict[str, Any]:
    generated_at = now or datetime.now().astimezone()
    total_lines = 0
    ignored_lines = 0
    latest_document_by_processing_id: dict[str, dict[str, Any]] = {}
    service_events: list[dict[str, Any]] = []
    stage_counts: Counter[str] = Counter()
    global_ordinal = 0

    log_file = settings.log_file
    log_files = iter_jsonl_log_files(log_file)
    for log_path in log_files:
        with log_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                global_ordinal += 1
                total_lines += 1
                raw_line = line.strip()
                if not raw_line:
                    ignored_lines += 1
                    continue

                try:
                    payload = json.loads(raw_line)
                except json.JSONDecodeError:
                    ignored_lines += 1
                    continue

                processing_id = str(payload.get("processing_id", "")).strip()
                if not processing_id:
                    ignored_lines += 1
                    continue

                event = _normalize_event(payload, global_ordinal)
                stage_counts[event["stage"]] += 1
                if event["is_service_event"]:
                    service_events.append(event)
                    continue
                latest_document_by_processing_id[processing_id] = event

    latest_events = sorted(
        latest_document_by_processing_id.values(),
        key=lambda item: item["ordinal"],
        reverse=True,
    )

    success_events = [event for event in latest_events if event["classified_status"] == "success"]
    failure_events = [event for event in latest_events if event["classified_status"] == "failure"]
    incomplete_events = [
        event for event in latest_events if event["classified_status"] == "incomplete"
    ]
    completed_events = success_events + failure_events

    average_completion_ms = None
    completion_durations = [
        event["duration_ms"]
        for event in completed_events
        if event["duration_ms"] is not None
    ]
    if completion_durations:
        average_completion_ms = round(mean(completion_durations))

    success_rate = None
    if completed_events:
        success_rate = round((len(success_events) / len(completed_events)) * 100, 1)

    last_processed_at = next(
        (event["timestamp"] for event in latest_events if event["timestamp"] is not None),
        None,
    )

    last_24h_window_start = generated_at - timedelta(hours=24)
    last_24h_events = [
        event
        for event in latest_events
        if event["timestamp_obj"] is not None and event["timestamp_obj"] >= last_24h_window_start
    ]

    history = _build_history(latest_events, generated_at, history_days)
    failure_reasons = _build_failure_reasons(failure_events)
    latency_snapshot = _build_latency_snapshot(completion_durations)
    queue_snapshot = _build_queue_snapshot(settings, generated_at)
    service_snapshot = _build_service_snapshot(service_events, settings, generated_at)

    recent_documents = [_serialize_recent_event(event) for event in latest_events[:recent_limit]]
    stage_summary = [
        {"stage": stage, "count": count}
        for stage, count in sorted(stage_counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    return {
        "generated_at": generated_at.isoformat(),
        "refresh_seconds": 15,
        "paths": {
            "input": str(settings.input_path),
            "processing": str(settings.processing_path),
            "output": str(settings.output_path),
            "rejected": str(settings.rejected_path),
            "log_file": str(settings.log_file),
            "log_path": str(settings.log_path),
        },
        "log": {
            "exists": bool(log_files),
            "active_exists": log_file.exists(),
            "files": len(log_files),
            "archived_files": max(0, len(log_files) - (1 if log_file.exists() else 0)),
            "lines": total_lines,
            "ignored_lines": ignored_lines,
        },
        "service": service_snapshot,
        "queues": queue_snapshot,
        "documents": {
            "seen": len(latest_events),
            "completed": len(completed_events),
            "succeeded": len(success_events),
            "failed": len(failure_events),
            "incomplete": len(incomplete_events),
            "success_rate": success_rate,
            "average_completion_ms": average_completion_ms,
            "last_processed_at": last_processed_at,
        },
        "latency_ms": latency_snapshot,
        "last_24_hours": {
            "documents": len(last_24h_events),
            "completed": sum(
                1 for event in last_24h_events if event["classified_status"] in {"success", "failure"}
            ),
            "succeeded": sum(
                1 for event in last_24h_events if event["classified_status"] == "success"
            ),
            "failed": sum(
                1 for event in last_24h_events if event["classified_status"] == "failure"
            ),
            "incomplete": sum(
                1 for event in last_24h_events if event["classified_status"] == "incomplete"
            ),
        },
        "daily_counts": history,
        "failure_reasons": failure_reasons,
        "stage_counts": stage_summary,
        "recent_documents": recent_documents,
    }


def render_stats_html(snapshot: dict[str, Any]) -> str:
    document_stats = snapshot["documents"]
    last_day_stats = snapshot["last_24_hours"]
    daily_counts = snapshot["daily_counts"]
    failure_reasons = snapshot["failure_reasons"]
    stage_counts = snapshot["stage_counts"]
    recent_documents = snapshot["recent_documents"]
    service_stats = snapshot.get(
        "service",
        {
            "status": "unknown",
            "last_event_type": None,
            "last_event_at": None,
            "last_heartbeat_at": None,
            "heartbeat_age_seconds": None,
            "lock_exists": False,
            "startups_last_24h": 0,
            "shutdowns_last_24h": 0,
        },
    )
    queue_stats = snapshot.get(
        "queues",
        {
            "input_backlog_count": 0,
            "oldest_input_age_seconds": None,
            "processing_count": 0,
            "journal_count": 0,
        },
    )
    latency_stats = snapshot.get(
        "latency_ms",
        {
            "p50": None,
            "p95": None,
            "p99": None,
        },
    )

    max_daily_total = max((day["total"] for day in daily_counts), default=1) or 1

    daily_rows = "\n".join(
        _render_daily_row(day, max_daily_total)
        for day in daily_counts
    )
    failure_rows = "\n".join(
        f"<tr><td>{_escape(item['reason'])}</td><td>{item['count']}</td></tr>"
        for item in failure_reasons
    ) or '<tr><td colspan="2" class="empty-cell">No failures recorded.</td></tr>'
    stage_rows = "\n".join(
        f"<tr><td>{_escape(item['stage'])}</td><td>{item['count']}</td></tr>"
        for item in stage_counts
    ) or '<tr><td colspan="2" class="empty-cell">No log events recorded.</td></tr>'
    recent_rows = "\n".join(_render_recent_row(item) for item in recent_documents)
    if not recent_rows:
        recent_rows = (
            '<tr><td colspan="5" class="empty-cell">'
            "No documents have been logged yet. Start the service and drop a file into the input folder."
            "</td></tr>"
        )

    generated_at = _format_display_timestamp(snapshot["generated_at"])
    last_processed_at = _format_display_timestamp(document_stats["last_processed_at"])
    heartbeat_at = _format_display_timestamp(service_stats["last_heartbeat_at"])
    service_last_event_at = _format_display_timestamp(service_stats["last_event_at"])
    service_status = service_stats["status"]
    service_value_class = (
        "success" if service_status == "healthy" else "failure" if service_status == "stopped" else "warning"
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="{snapshot['refresh_seconds']}">
  <title>Barcode Buddy Stats</title>
  <style>
    :root {{
      --bg: #f3ede1;
      --paper: rgba(255, 251, 245, 0.9);
      --panel: rgba(255, 255, 255, 0.78);
      --line: rgba(44, 54, 63, 0.14);
      --text: #20262d;
      --muted: #68737d;
      --accent: #885529;
      --accent-soft: rgba(136, 85, 41, 0.12);
      --success: #25624a;
      --failure: #912f2f;
      --warning: #9a6b13;
      --track: #d8d1c4;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(136, 85, 41, 0.14), transparent 38%),
        radial-gradient(circle at bottom right, rgba(37, 98, 74, 0.12), transparent 36%),
        repeating-linear-gradient(
          90deg,
          rgba(255, 255, 255, 0.18) 0,
          rgba(255, 255, 255, 0.18) 1px,
          transparent 1px,
          transparent 88px
        ),
        var(--bg);
      font-family: "Aptos", "Segoe UI Variable", "Segoe UI", sans-serif;
    }}

    .shell {{
      width: min(1200px, calc(100vw - 32px));
      margin: 24px auto;
      padding: 24px;
      border: 1px solid var(--line);
      border-radius: 24px;
      background: var(--paper);
      box-shadow: 0 18px 50px rgba(55, 45, 34, 0.12);
      backdrop-filter: blur(12px);
    }}

    .header {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: end;
      margin-bottom: 24px;
      flex-wrap: wrap;
    }}

    .eyebrow {{
      text-transform: uppercase;
      letter-spacing: 0.16em;
      font-size: 12px;
      color: var(--accent);
      margin-bottom: 10px;
      font-weight: 700;
    }}

    h1 {{
      margin: 0;
      font-family: "Bahnschrift", "Arial Narrow", sans-serif;
      font-size: clamp(32px, 5vw, 48px);
      line-height: 0.95;
      letter-spacing: 0.02em;
    }}

    .subtle {{
      color: var(--muted);
      font-size: 14px;
    }}

    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 14px;
      margin-bottom: 24px;
    }}

    .card {{
      padding: 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: var(--panel);
    }}

    .card h2 {{
      margin: 0 0 8px 0;
      font-size: 13px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
    }}

    .value {{
      font-size: clamp(28px, 4vw, 40px);
      line-height: 1;
      font-weight: 700;
    }}

    .value.success {{
      color: var(--success);
    }}

    .value.failure {{
      color: var(--failure);
    }}

    .value.warning {{
      color: var(--warning);
    }}

    .grid {{
      display: grid;
      grid-template-columns: 1.3fr 1fr;
      gap: 18px;
      margin-bottom: 18px;
    }}

    .panel {{
      border: 1px solid var(--line);
      border-radius: 20px;
      background: var(--panel);
      padding: 18px;
    }}

    .panel h3 {{
      margin: 0 0 6px 0;
      font-size: 20px;
    }}

    .panel p {{
      margin: 0 0 16px 0;
      color: var(--muted);
      font-size: 14px;
    }}

    .history {{
      display: grid;
      gap: 10px;
    }}

    .day-row {{
      display: grid;
      grid-template-columns: 96px 1fr 56px;
      gap: 12px;
      align-items: center;
      font-size: 14px;
    }}

    .bar-track {{
      height: 12px;
      background: var(--track);
      border-radius: 999px;
      overflow: hidden;
      display: flex;
    }}

    .bar-success {{
      background: linear-gradient(90deg, #2f7f61, #25624a);
    }}

    .bar-failure {{
      background: linear-gradient(90deg, #c55d5d, #912f2f);
    }}

    .bar-incomplete {{
      background: linear-gradient(90deg, #d7b363, #9a6b13);
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}

    th, td {{
      padding: 10px 0;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}

    th {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}

    .status-pill {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      padding: 5px 10px;
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      border: 1px solid transparent;
    }}

    .status-pill.success {{
      color: var(--success);
      background: rgba(37, 98, 74, 0.12);
      border-color: rgba(37, 98, 74, 0.2);
    }}

    .status-pill.failure {{
      color: var(--failure);
      background: rgba(145, 47, 47, 0.12);
      border-color: rgba(145, 47, 47, 0.2);
    }}

    .status-pill.incomplete {{
      color: var(--warning);
      background: rgba(154, 107, 19, 0.14);
      border-color: rgba(154, 107, 19, 0.22);
    }}

    .meta {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 12px;
      margin-top: 18px;
    }}

    .path-box {{
      border-radius: 16px;
      background: var(--accent-soft);
      border: 1px solid rgba(136, 85, 41, 0.16);
      padding: 14px;
    }}

    .path-box strong {{
      display: block;
      margin-bottom: 6px;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--accent);
    }}

    code {{
      font-family: "Consolas", "Cascadia Mono", monospace;
      font-size: 13px;
      word-break: break-word;
    }}

    .empty-cell {{
      color: var(--muted);
      padding: 14px 0;
    }}

    .wide-panel {{
      margin-top: 18px;
    }}

    .detail {{
      color: var(--muted);
    }}

    @media (max-width: 900px) {{
      .grid {{
        grid-template-columns: 1fr;
      }}

      .day-row {{
        grid-template-columns: 88px 1fr 42px;
      }}

      .shell {{
        width: min(1200px, calc(100vw - 18px));
        padding: 18px;
        margin: 10px auto;
      }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="header">
      <div>
        <div class="eyebrow">Single Stats Page</div>
        <h1>Barcode Buddy Stats</h1>
        <div class="subtle">Generated {generated_at}. Auto-refreshes every {snapshot['refresh_seconds']} seconds.</div>
      </div>
      <div class="subtle">
        Last processed: {_escape(last_processed_at)}<br>
        Log files: {snapshot['log']['files']} ({snapshot['log']['archived_files']} archived)<br>
        Log lines: {snapshot['log']['lines']}<br>
        Ignored lines: {snapshot['log']['ignored_lines']}
      </div>
    </section>

    <section class="summary-grid">
      <article class="card">
        <h2>Documents Seen</h2>
        <div class="value">{document_stats['seen']}</div>
      </article>
      <article class="card">
        <h2>Completed</h2>
        <div class="value">{document_stats['completed']}</div>
      </article>
      <article class="card">
        <h2>Succeeded</h2>
        <div class="value success">{document_stats['succeeded']}</div>
      </article>
      <article class="card">
        <h2>Failed</h2>
        <div class="value failure">{document_stats['failed']}</div>
      </article>
      <article class="card">
        <h2>Incomplete</h2>
        <div class="value warning">{document_stats['incomplete']}</div>
      </article>
      <article class="card">
        <h2>Success Rate</h2>
        <div class="value">{_format_percentage(document_stats['success_rate'])}</div>
        <div class="subtle">Average completion {_escape(_format_duration(document_stats['average_completion_ms']))}</div>
      </article>
      <article class="card">
        <h2>Service Health</h2>
        <div class="value {service_value_class}">{_escape(service_status.title())}</div>
        <div class="subtle">Heartbeat {_escape(heartbeat_at)}</div>
      </article>
      <article class="card">
        <h2>Input Backlog</h2>
        <div class="value">{queue_stats['input_backlog_count']}</div>
        <div class="subtle">Oldest {_escape(_format_seconds(queue_stats['oldest_input_age_seconds']))}</div>
      </article>
      <article class="card">
        <h2>P95 Latency</h2>
        <div class="value">{_escape(_format_duration(latency_stats['p95']))}</div>
        <div class="subtle">P50 {_escape(_format_duration(latency_stats['p50']))} | P99 {_escape(_format_duration(latency_stats['p99']))}</div>
      </article>
    </section>

    <section class="grid">
      <article class="panel">
        <h3>14-Day Volume</h3>
        <p>Latest known document state by processing ID. Incomplete means a trace never reached output success or a failure record.</p>
        <div class="history">
          {daily_rows}
        </div>
      </article>

      <article class="panel">
        <h3>Recent Window</h3>
        <p>Documents whose latest log event landed in the last 24 hours.</p>
        <table>
          <tbody>
            <tr><th>Seen</th><td>{last_day_stats['documents']}</td></tr>
            <tr><th>Completed</th><td>{last_day_stats['completed']}</td></tr>
            <tr><th>Succeeded</th><td>{last_day_stats['succeeded']}</td></tr>
            <tr><th>Failed</th><td>{last_day_stats['failed']}</td></tr>
            <tr><th>Incomplete</th><td>{last_day_stats['incomplete']}</td></tr>
          </tbody>
        </table>

        <h3 style="margin-top:22px;">Service State</h3>
        <p>Latest worker heartbeat and restart signals from the log plus the current lock file.</p>
        <table>
          <tbody>
            <tr><th>Status</th><td>{_escape(service_status)}</td></tr>
            <tr><th>Last event</th><td>{_escape(service_stats['last_event_type'] or '-')} at {_escape(service_last_event_at)}</td></tr>
            <tr><th>Heartbeat age</th><td>{_escape(_format_seconds(service_stats['heartbeat_age_seconds']))}</td></tr>
            <tr><th>Lock file</th><td>{'present' if service_stats['lock_exists'] else 'missing'}</td></tr>
            <tr><th>Startups 24h</th><td>{service_stats['startups_last_24h']}</td></tr>
            <tr><th>Shutdowns 24h</th><td>{service_stats['shutdowns_last_24h']}</td></tr>
          </tbody>
        </table>

        <h3 style="margin-top:22px;">Queue State</h3>
        <p>Current filesystem backlog and recovery-journal counts.</p>
        <table>
          <tbody>
            <tr><th>Input backlog</th><td>{queue_stats['input_backlog_count']}</td></tr>
            <tr><th>Oldest input</th><td>{_escape(_format_seconds(queue_stats['oldest_input_age_seconds']))}</td></tr>
            <tr><th>Processing files</th><td>{queue_stats['processing_count']}</td></tr>
            <tr><th>Journal files</th><td>{queue_stats['journal_count']}</td></tr>
          </tbody>
        </table>

        <h3 style="margin-top:22px;">Failure Reasons</h3>
        <p>Top terminal failure reasons from the latest outcome per document.</p>
        <table>
          <thead>
            <tr><th>Reason</th><th>Count</th></tr>
          </thead>
          <tbody>
            {failure_rows}
          </tbody>
        </table>

        <h3 style="margin-top:22px;">Stage Counts</h3>
        <p>Raw log entries by pipeline stage.</p>
        <table>
          <thead>
            <tr><th>Stage</th><th>Count</th></tr>
          </thead>
          <tbody>
            {stage_rows}
          </tbody>
        </table>
      </article>
    </section>

    <section class="panel wide-panel">
      <h3>Recent Documents</h3>
      <p>Newest processing IDs first. Status uses the latest event currently present in the log.</p>
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>File</th>
            <th>Status</th>
            <th>Detail</th>
            <th>Duration</th>
          </tr>
        </thead>
        <tbody>
          {recent_rows}
        </tbody>
      </table>
    </section>

    <section class="meta">
      <article class="path-box">
        <strong>Input</strong>
        <code>{_escape(snapshot['paths']['input'])}</code>
      </article>
      <article class="path-box">
        <strong>Processing</strong>
        <code>{_escape(snapshot['paths']['processing'])}</code>
      </article>
      <article class="path-box">
        <strong>Output</strong>
        <code>{_escape(snapshot['paths']['output'])}</code>
      </article>
      <article class="path-box">
        <strong>Rejected</strong>
        <code>{_escape(snapshot['paths']['rejected'])}</code>
      </article>
      <article class="path-box" style="grid-column: 1 / -1;">
        <strong>Active Log File</strong>
        <code>{_escape(snapshot['paths']['log_file'])}</code>
      </article>
      <article class="path-box" style="grid-column: 1 / -1;">
        <strong>Log Directory</strong>
        <code>{_escape(snapshot['paths']['log_path'])}</code>
      </article>
    </section>
  </main>
</body>
</html>
"""


class StatsHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        *,
        settings: Settings,
        refresh_seconds: int,
        history_days: int,
        recent_limit: int,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.settings = settings
        self.refresh_seconds = refresh_seconds
        self.history_days = history_days
        self.recent_limit = recent_limit


class StatsRequestHandler(BaseHTTPRequestHandler):
    server: StatsHTTPServer

    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        snapshot = build_stats_snapshot(
            self.server.settings,
            history_days=self.server.history_days,
            recent_limit=self.server.recent_limit,
        )
        snapshot["refresh_seconds"] = self.server.refresh_seconds

        if path in {"", "/"}:
            body = render_stats_html(snapshot).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/stats":
            payload = json.dumps(snapshot, ensure_ascii=True, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if path == "/health":
            status = snapshot["service"]["status"]
            payload = {
                "status": status,
                "heartbeat_age_seconds": snapshot["service"]["heartbeat_age_seconds"],
                "lock_exists": snapshot["service"]["lock_exists"],
                "input_backlog_count": snapshot["queues"]["input_backlog_count"],
                "processing_count": snapshot["queues"]["processing_count"],
                "journal_count": snapshot["queues"]["journal_count"],
            }
            body = json.dumps(payload, ensure_ascii=True, indent=2).encode("utf-8")
            self.send_response(200 if status == "healthy" else 503)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        body = b"Not found\n"
        self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def serve_stats_page(
    settings: Settings,
    *,
    host: str,
    port: int,
    refresh_seconds: int = 15,
    history_days: int = 14,
    recent_limit: int = 25,
) -> None:
    server = StatsHTTPServer(
        (host, port),
        StatsRequestHandler,
        settings=settings,
        refresh_seconds=refresh_seconds,
        history_days=history_days,
        recent_limit=recent_limit,
    )
    server.serve_forever()


def _build_history(
    latest_events: list[dict[str, Any]],
    generated_at: datetime,
    history_days: int,
) -> list[dict[str, Any]]:
    if history_days < 1:
        history_days = 1

    start_date = (generated_at - timedelta(days=history_days - 1)).date()
    history: list[dict[str, Any]] = []
    index_by_date: dict[str, dict[str, Any]] = {}

    for offset in range(history_days):
        current_day = start_date + timedelta(days=offset)
        bucket = {
            "date": current_day.isoformat(),
            "success": 0,
            "failure": 0,
            "incomplete": 0,
            "total": 0,
        }
        history.append(bucket)
        index_by_date[bucket["date"]] = bucket

    for event in latest_events:
        timestamp = event["timestamp_obj"]
        if timestamp is None:
            continue

        key = timestamp.date().isoformat()
        if key not in index_by_date:
            continue

        bucket = index_by_date[key]
        bucket[event["classified_status"]] += 1
        bucket["total"] += 1

    return history


def _build_failure_reasons(failure_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for event in failure_events:
        reason = event["error_code"] or event["reason"] or "UNKNOWN_FAILURE"
        counts[reason] += 1
    return [
        {"reason": reason, "count": count}
        for reason, count in counts.most_common(8)
    ]


def _build_latency_snapshot(completion_durations: list[int]) -> dict[str, int | None]:
    if not completion_durations:
        return {
            "p50": None,
            "p95": None,
            "p99": None,
        }

    ordered = sorted(completion_durations)
    return {
        "p50": _percentile(ordered, 50),
        "p95": _percentile(ordered, 95),
        "p99": _percentile(ordered, 99),
    }


def _build_queue_snapshot(settings: Settings, generated_at: datetime) -> dict[str, int | None]:
    journal_dir = settings.processing_path / ".journal"
    return {
        "input_backlog_count": _count_files(settings.input_path),
        "oldest_input_age_seconds": _oldest_file_age_seconds(settings.input_path, generated_at),
        "processing_count": _count_files(settings.processing_path),
        "journal_count": _count_files(journal_dir),
    }


def _build_service_snapshot(
    service_events: list[dict[str, Any]],
    settings: Settings,
    generated_at: datetime,
) -> dict[str, Any]:
    latest_event = max(service_events, key=lambda item: item["ordinal"], default=None)
    heartbeat_candidates = [
        event
        for event in service_events
        if event["event_type"] in {SERVICE_EVENT_STARTUP, SERVICE_EVENT_HEARTBEAT}
    ]
    latest_heartbeat = max(heartbeat_candidates, key=lambda item: item["ordinal"], default=None)
    latest_event_timestamp = latest_event["timestamp"] if latest_event is not None else None
    latest_heartbeat_timestamp = (
        latest_heartbeat["timestamp"] if latest_heartbeat is not None else None
    )
    heartbeat_age_seconds = None
    if latest_heartbeat is not None and latest_heartbeat["timestamp_obj"] is not None:
        heartbeat_age_seconds = max(
            0,
            int((generated_at - latest_heartbeat["timestamp_obj"]).total_seconds()),
        )

    lock_file = settings.log_path / ".service.lock"
    startups_last_24h = sum(
        1
        for event in service_events
        if event["event_type"] == SERVICE_EVENT_STARTUP
        and event["timestamp_obj"] is not None
        and event["timestamp_obj"] >= generated_at - timedelta(hours=24)
    )
    shutdowns_last_24h = sum(
        1
        for event in service_events
        if event["event_type"] == SERVICE_EVENT_SHUTDOWN
        and event["timestamp_obj"] is not None
        and event["timestamp_obj"] >= generated_at - timedelta(hours=24)
    )

    status = _classify_service_status(
        latest_event_type=latest_event["event_type"] if latest_event is not None else None,
        heartbeat_age_seconds=heartbeat_age_seconds,
        lock_exists=lock_file.exists(),
    )

    return {
        "status": status,
        "last_event_type": latest_event["event_type"] if latest_event is not None else None,
        "last_event_at": latest_event_timestamp,
        "last_heartbeat_at": latest_heartbeat_timestamp,
        "heartbeat_age_seconds": heartbeat_age_seconds,
        "lock_exists": lock_file.exists(),
        "startups_last_24h": startups_last_24h,
        "shutdowns_last_24h": shutdowns_last_24h,
        "event_count": len(service_events),
    }


def _normalize_event(payload: dict[str, Any], line_number: int) -> dict[str, Any]:
    timestamp = str(payload.get("timestamp", "")).strip() or None
    timestamp_obj = _parse_timestamp(timestamp)
    status = str(payload.get("status", "unknown")).strip().lower() or "unknown"
    stage = str(payload.get("stage", "unknown")).strip().lower() or "unknown"
    event_type = _optional_str(payload.get("event_type"))
    rejected_path = _optional_str(payload.get("rejected_path"))
    output_path = _optional_str(payload.get("output_path"))
    recovery_action = _optional_str(payload.get("recovery_action"))
    return {
        "processing_id": str(payload.get("processing_id", "")).strip(),
        "timestamp": timestamp,
        "timestamp_obj": timestamp_obj,
        "status": status,
        "stage": stage,
        "event_type": event_type,
        "is_service_event": stage == STAGE_SERVICE,
        "classified_status": _classify_latest_status(
            status,
            stage,
            event_type=event_type,
            output_path=output_path,
            rejected_path=rejected_path,
            recovery_action=recovery_action,
        ),
        "original_filename": str(payload.get("original_filename", "")).strip() or "(unknown file)",
        "duration_ms": _coerce_int(payload.get("duration_ms")),
        "reason": _optional_str(payload.get("reason")),
        "error_code": _optional_str(payload.get("error_code")),
        "barcode": _optional_str(payload.get("barcode")),
        "barcode_format": _optional_str(payload.get("barcode_format")),
        "output_path": output_path,
        "rejected_path": rejected_path,
        "recovery_action": recovery_action,
        "pages": _coerce_int(payload.get("pages")),
        "ordinal": line_number,
    }


def _serialize_recent_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "processing_id": event["processing_id"],
        "timestamp": event["timestamp"],
        "stage": event["stage"],
        "status": event["classified_status"],
        "error_code": event["error_code"],
        "original_filename": event["original_filename"],
        "duration_ms": event["duration_ms"],
        "reason": event["reason"],
        "barcode": event["barcode"],
        "barcode_format": event["barcode_format"],
        "output_path": event["output_path"],
        "rejected_path": event["rejected_path"],
        "recovery_action": event["recovery_action"],
        "pages": event["pages"],
    }


def _classify_latest_status(
    status: str,
    stage: str,
    *,
    event_type: str | None,
    output_path: str | None,
    rejected_path: str | None,
    recovery_action: str | None,
) -> str:
    if stage == STAGE_SERVICE or event_type in {
        SERVICE_EVENT_STARTUP,
        SERVICE_EVENT_HEARTBEAT,
        SERVICE_EVENT_SHUTDOWN,
    }:
        return "service"
    if status == "failure":
        return "failure"
    if recovery_action == "finalized_rejection_recovery":
        return "failure"
    if status == "success" and stage == "output":
        return "success"
    if output_path:
        return "success"
    if rejected_path:
        return "failure"
    return "incomplete"


def _classify_service_status(
    *,
    latest_event_type: str | None,
    heartbeat_age_seconds: int | None,
    lock_exists: bool,
) -> str:
    if latest_event_type == SERVICE_EVENT_SHUTDOWN:
        return "stopped"
    if heartbeat_age_seconds is None:
        return "unknown"
    if heartbeat_age_seconds <= 60 and lock_exists:
        return "healthy"
    return "stale"


def _count_files(directory: Path) -> int:
    if not directory.exists():
        return 0
    return sum(1 for path in directory.iterdir() if path.is_file())


def _oldest_file_age_seconds(directory: Path, now: datetime) -> int | None:
    if not directory.exists():
        return None

    oldest_timestamp: float | None = None
    for path in directory.iterdir():
        if not path.is_file():
            continue
        stat_result = path.stat()
        created = getattr(stat_result, "st_birthtime", stat_result.st_ctime)
        if oldest_timestamp is None or created < oldest_timestamp:
            oldest_timestamp = created

    if oldest_timestamp is None:
        return None
    return max(0, int(now.timestamp() - oldest_timestamp))


def _percentile(ordered_values: list[int], percentile: int) -> int | None:
    if not ordered_values:
        return None
    index = max(0, min(len(ordered_values) - 1, ((len(ordered_values) - 1) * percentile) // 100))
    return ordered_values[index]


def _coerce_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        timestamp = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return timestamp


def _render_daily_row(day: dict[str, Any], max_total: int) -> str:
    success_width = (day["success"] / max_total) * 100 if max_total else 0
    failure_width = (day["failure"] / max_total) * 100 if max_total else 0
    incomplete_width = (day["incomplete"] / max_total) * 100 if max_total else 0
    return (
        '<div class="day-row">'
        f"<div>{_escape(day['date'])}</div>"
        '<div class="bar-track">'
        f'<div class="bar-success" style="width:{success_width:.2f}%"></div>'
        f'<div class="bar-failure" style="width:{failure_width:.2f}%"></div>'
        f'<div class="bar-incomplete" style="width:{incomplete_width:.2f}%"></div>'
        "</div>"
        f"<div>{day['total']}</div>"
        "</div>"
    )


def _render_recent_row(event: dict[str, Any]) -> str:
    status = event["status"]
    detail = _escape(event["barcode"] or event["error_code"] or event["reason"] or "-")
    detail_suffix = []
    if event["barcode_format"]:
        detail_suffix.append(event["barcode_format"])
    if event["pages"] is not None:
        detail_suffix.append(f"{event['pages']} page(s)")
    if event["recovery_action"]:
        detail_suffix.append(f"recovery: {event['recovery_action']}")
    if event["stage"]:
        detail_suffix.append(f"stage: {event['stage']}")
    suffix = " | ".join(detail_suffix)
    if suffix:
        detail = f'{detail}<br><span class="detail">{_escape(suffix)}</span>'

    return (
        "<tr>"
        f"<td>{_escape(_format_display_timestamp(event['timestamp']))}</td>"
        f"<td>{_escape(event['original_filename'])}</td>"
        f'<td><span class="status-pill {status}">{_escape(status)}</span></td>'
        f"<td>{detail}</td>"
        f"<td>{_escape(_format_duration(event['duration_ms']))}</td>"
        "</tr>"
    )


def _format_display_timestamp(value: str | None) -> str:
    timestamp = _parse_timestamp(value)
    if timestamp is None:
        return "n/a"
    return timestamp.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def _format_duration(duration_ms: int | None) -> str:
    if duration_ms is None:
        return "n/a"
    if duration_ms < 1000:
        return f"{duration_ms} ms"
    seconds = duration_ms / 1000
    return f"{seconds:.2f} s"


def _format_seconds(value: int | None) -> str:
    if value is None:
        return "n/a"
    if value < 60:
        return f"{value}s"
    minutes, seconds = divmod(value, 60)
    if minutes < 60:
        return f"{minutes}m {seconds}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def _format_percentage(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f}%"


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)
