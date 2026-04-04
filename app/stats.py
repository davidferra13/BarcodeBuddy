from __future__ import annotations

import gzip
import html
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

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
        if log_path.name.endswith(".gz"):
            handle_ctx = gzip.open(log_path, "rt", encoding="utf-8")
        else:
            handle_ctx = log_path.open("r", encoding="utf-8")
        with handle_ctx as handle:
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

    hourly_throughput = _build_hourly_throughput(latest_events, generated_at)

    documents_block = {
        "seen": len(latest_events),
        "completed": len(completed_events),
        "succeeded": len(success_events),
        "failed": len(failure_events),
        "incomplete": len(incomplete_events),
        "success_rate": success_rate,
        "average_completion_ms": average_completion_ms,
        "last_processed_at": last_processed_at,
    }
    last_24_hours_block = {
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
    }

    # Build the base snapshot first so derived metrics can reference it
    snapshot: dict[str, Any] = {
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
        "documents": documents_block,
        "latency_ms": latency_snapshot,
        "last_24_hours": last_24_hours_block,
        "daily_counts": history,
        "failure_reasons": failure_reasons,
        "stage_counts": stage_summary,
        "recent_documents": recent_documents,
        "hourly_throughput": hourly_throughput,
    }

    # Derived metrics that depend on the base snapshot
    snapshot["health_score"] = _compute_health_score(snapshot)
    snapshot["achievements"] = _compute_achievements(history, documents_block)
    snapshot["queue_eta"] = _compute_queue_eta(queue_snapshot, average_completion_ms)

    return snapshot


def render_stats_html(snapshot: dict[str, Any], *, current_user: dict[str, Any] | None = None) -> str:
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

    # Health score
    health = snapshot.get("health_score", {"score": 0, "grade": "?", "components": {}})
    health_score_val = health["score"]
    health_grade = health["grade"]
    health_grade_colors = {"A": "var(--success)", "B": "var(--info)", "C": "var(--warning)", "D": "var(--failure)", "F": "var(--failure)"}
    health_grade_color = health_grade_colors.get(health_grade, "var(--muted)")
    health_ring_dash = round(health_score_val * 2.51, 1)

    # Achievements
    ach = snapshot.get("achievements", {"streak": {"zero_error_days": 0, "label": "—"}, "badge": {"name": None, "color": None, "total_succeeded": 0}, "next_tier": {"name": None, "target": None, "progress_pct": 0}, "milestones": []})
    streak = ach["streak"]
    badge = ach["badge"]
    next_tier = ach["next_tier"]
    milestones = ach["milestones"]

    # Queue ETA
    queue_eta = snapshot.get("queue_eta", {"backlog": 0, "eta_seconds": None, "eta_display": "n/a"})

    # Hourly throughput
    hourly = snapshot.get("hourly_throughput", [])
    max_hourly = max((h["total"] for h in hourly), default=1) or 1
    hourly_bars_html = ""
    for bucket in hourly:
        bar_h = max(2, round((bucket["total"] / max_hourly) * 60))
        s_h = round((bucket["success"] / max_hourly) * 60) if bucket["success"] else 0
        f_h = round((bucket["failure"] / max_hourly) * 60) if bucket["failure"] else 0
        hourly_bars_html += (
            f'<div style="display:flex;flex-direction:column;align-items:center;flex:1;min-width:0;">'
            f'<div style="width:100%;height:60px;display:flex;flex-direction:column;justify-content:flex-end;">'
            f'<div style="width:100%;border-radius:3px 3px 0 0;overflow:hidden;">'
            f'<div style="height:{s_h}px;background:var(--success);"></div>'
            f'<div style="height:{f_h}px;background:var(--failure);"></div>'
            f'</div></div>'
            f'<div style="font-size:9px;color:var(--muted);margin-top:3px;transform:rotate(-45deg);white-space:nowrap;">{_escape(bucket["hour"])}</div>'
            f'</div>'
        )

    # Build success rate ring for overview
    success_rate = document_stats["success_rate"]
    ring_pct = success_rate if success_rate is not None else 0
    ring_dash = round(ring_pct * 2.51, 1)  # circumference ~251 for r=40

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Barcode Buddy</title>
  <style>
    :root {{
      --bg: #f0ebe3;
      --sidebar-bg: #1e2530;
      --sidebar-text: #a0aab4;
      --sidebar-active: #ffffff;
      --sidebar-hover: rgba(255,255,255,0.08);
      --sidebar-accent: #e8a04c;
      --paper: rgba(255, 251, 245, 0.92);
      --panel: rgba(255, 255, 255, 0.82);
      --line: rgba(44, 54, 63, 0.10);
      --text: #1a1f26;
      --muted: #68737d;
      --accent: #885529;
      --accent-soft: rgba(136, 85, 41, 0.08);
      --success: #1a7a54;
      --success-bg: rgba(26, 122, 84, 0.08);
      --success-border: rgba(26, 122, 84, 0.18);
      --failure: #c0392b;
      --failure-bg: rgba(192, 57, 43, 0.08);
      --failure-border: rgba(192, 57, 43, 0.18);
      --warning: #b8860b;
      --warning-bg: rgba(184, 134, 11, 0.08);
      --warning-border: rgba(184, 134, 11, 0.18);
      --info: #2472a4;
      --info-bg: rgba(36, 114, 164, 0.08);
      --info-border: rgba(36, 114, 164, 0.18);
      --track: #e0dbd2;
      --radius: 16px;
      --sidebar-width: 230px;
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      display: flex;
      min-height: 100vh;
      color: var(--text);
      background: var(--bg);
      font-family: "Segoe UI Variable", "Segoe UI", "Aptos", system-ui, sans-serif;
      font-size: 14px;
      line-height: 1.5;
    }}

    /* ── Sidebar ── */
    .sidebar {{
      width: var(--sidebar-width);
      min-height: 100vh;
      background: var(--sidebar-bg);
      display: flex;
      flex-direction: column;
      position: fixed;
      top: 0;
      left: 0;
      z-index: 100;
      transition: transform 0.25s ease;
    }}

    .sidebar-brand {{
      padding: 24px 20px 20px;
      border-bottom: 1px solid rgba(255,255,255,0.06);
    }}

    .sidebar-brand h1 {{
      font-size: 18px;
      font-weight: 700;
      color: #fff;
      letter-spacing: 0.02em;
      line-height: 1.2;
    }}

    .sidebar-brand .brand-sub {{
      font-size: 11px;
      color: var(--sidebar-text);
      margin-top: 4px;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}

    .sidebar-nav {{
      padding: 12px 10px;
      flex: 1;
    }}

    .nav-section {{
      margin-bottom: 8px;
    }}

    .nav-section-label {{
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: rgba(255,255,255,0.28);
      padding: 12px 12px 6px;
      font-weight: 600;
    }}

    .nav-btn {{
      display: flex;
      align-items: center;
      gap: 12px;
      width: 100%;
      padding: 10px 14px;
      border: none;
      border-radius: 10px;
      background: transparent;
      color: var(--sidebar-text);
      font-size: 13.5px;
      font-family: inherit;
      cursor: pointer;
      transition: all 0.15s ease;
      text-align: left;
      position: relative;
    }}

    .nav-btn:hover {{
      background: var(--sidebar-hover);
      color: #d0d6dc;
    }}

    .nav-btn.active {{
      background: rgba(232, 160, 76, 0.14);
      color: var(--sidebar-active);
    }}

    .nav-btn.active::before {{
      content: '';
      position: absolute;
      left: 0;
      top: 50%;
      transform: translateY(-50%);
      width: 3px;
      height: 20px;
      background: var(--sidebar-accent);
      border-radius: 0 4px 4px 0;
    }}

    .nav-icon {{
      width: 20px;
      height: 20px;
      opacity: 0.7;
      flex-shrink: 0;
    }}

    .nav-btn.active .nav-icon {{
      opacity: 1;
    }}

    .sidebar-status {{
      padding: 16px 20px;
      border-top: 1px solid rgba(255,255,255,0.06);
    }}

    .status-indicator {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
    }}

    .status-dot {{
      width: 8px;
      height: 8px;
      border-radius: 50%;
      flex-shrink: 0;
    }}

    .status-dot.healthy {{
      background: #2ecc71;
      box-shadow: 0 0 6px rgba(46, 204, 113, 0.5);
    }}

    .status-dot.stopped {{
      background: var(--failure);
    }}

    .status-dot.stale, .status-dot.unknown {{
      background: var(--warning);
    }}

    .sidebar-footer {{
      padding: 14px 20px;
      border-top: 1px solid rgba(255,255,255,0.06);
      font-size: 11px;
      color: rgba(255,255,255,0.2);
    }}

    /* ── Mobile hamburger ── */
    .hamburger {{
      display: none;
      position: fixed;
      top: 12px;
      left: 12px;
      z-index: 200;
      width: 40px;
      height: 40px;
      border: none;
      border-radius: 10px;
      background: var(--sidebar-bg);
      color: #fff;
      cursor: pointer;
      align-items: center;
      justify-content: center;
    }}

    .sidebar-overlay {{
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.4);
      z-index: 90;
    }}

    /* ── Main content ── */
    .main {{
      margin-left: var(--sidebar-width);
      flex: 1;
      min-height: 100vh;
    }}

    .topbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 16px 28px;
      background: rgba(255,251,245,0.8);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--line);
      position: sticky;
      top: 0;
      z-index: 50;
    }}

    .topbar-title {{
      font-size: 16px;
      font-weight: 600;
      color: var(--text);
    }}

    .topbar-meta {{
      display: flex;
      align-items: center;
      gap: 16px;
      font-size: 12px;
      color: var(--muted);
    }}

    .refresh-badge {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 4px 10px;
      border-radius: 999px;
      background: var(--info-bg);
      color: var(--info);
      font-size: 11px;
      font-weight: 600;
      border: 1px solid var(--info-border);
    }}

    .content {{
      padding: 24px 28px;
    }}

    /* ── Pages ── */
    .page {{
      display: none;
      animation: fadeIn 0.2s ease;
    }}

    .page.active {{
      display: block;
    }}

    @keyframes fadeIn {{
      from {{ opacity: 0; transform: translateY(6px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}

    /* ── Cards ── */
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}

    .kpi {{
      padding: 20px;
      border-radius: var(--radius);
      border: 1px solid var(--line);
      background: var(--panel);
      transition: box-shadow 0.15s ease, transform 0.15s ease;
    }}

    .kpi:hover {{
      box-shadow: 0 4px 16px rgba(0,0,0,0.06);
      transform: translateY(-1px);
    }}

    .kpi-label {{
      font-size: 11.5px;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 8px;
      font-weight: 600;
    }}

    .kpi-value {{
      font-size: 32px;
      line-height: 1;
      font-weight: 700;
      letter-spacing: -0.01em;
    }}

    .kpi-sub {{
      font-size: 12px;
      color: var(--muted);
      margin-top: 6px;
    }}

    .kpi.accent-green {{ border-left: 3px solid var(--success); }}
    .kpi.accent-red {{ border-left: 3px solid var(--failure); }}
    .kpi.accent-amber {{ border-left: 3px solid var(--warning); }}
    .kpi.accent-blue {{ border-left: 3px solid var(--info); }}

    .color-success {{ color: var(--success); }}
    .color-failure {{ color: var(--failure); }}
    .color-warning {{ color: var(--warning); }}
    .color-info {{ color: var(--info); }}

    /* ── Panels ── */
    .panel {{
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--panel);
      padding: 20px;
      margin-bottom: 20px;
    }}

    .panel-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 16px;
    }}

    .panel-title {{
      font-size: 16px;
      font-weight: 600;
    }}

    .panel-badge {{
      font-size: 11px;
      padding: 3px 10px;
      border-radius: 999px;
      font-weight: 600;
    }}

    .panel-desc {{
      font-size: 13px;
      color: var(--muted);
      margin-bottom: 16px;
    }}

    .split {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }}

    /* ── Overview hero row ── */
    .hero-row {{
      display: grid;
      grid-template-columns: 1fr 1fr 180px 180px;
      gap: 20px;
      margin-bottom: 24px;
    }}

    .hero-card {{
      padding: 24px;
      border-radius: var(--radius);
      border: 1px solid var(--line);
      background: var(--panel);
    }}

    .hero-card h3 {{
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: var(--muted);
      margin-bottom: 16px;
      font-weight: 600;
    }}

    /* ── Service health badge ── */
    .health-display {{
      display: flex;
      align-items: center;
      gap: 14px;
    }}

    .health-icon {{
      width: 48px;
      height: 48px;
      border-radius: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
    }}

    .health-icon.healthy {{
      background: var(--success-bg);
      border: 1px solid var(--success-border);
      color: var(--success);
    }}

    .health-icon.stopped {{
      background: var(--failure-bg);
      border: 1px solid var(--failure-border);
      color: var(--failure);
    }}

    .health-icon.stale, .health-icon.unknown {{
      background: var(--warning-bg);
      border: 1px solid var(--warning-border);
      color: var(--warning);
    }}

    .health-label {{
      font-size: 24px;
      font-weight: 700;
      line-height: 1.1;
    }}

    .health-detail {{
      font-size: 12px;
      color: var(--muted);
      margin-top: 2px;
    }}

    /* ── Ring chart ── */
    .ring-container {{
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
    }}

    .ring-chart {{
      position: relative;
      width: 100px;
      height: 100px;
    }}

    .ring-chart svg {{
      transform: rotate(-90deg);
    }}

    .ring-track {{
      fill: none;
      stroke: var(--track);
      stroke-width: 8;
    }}

    .ring-fill {{
      fill: none;
      stroke-width: 8;
      stroke-linecap: round;
      transition: stroke-dasharray 0.6s ease;
    }}

    .ring-fill.good {{ stroke: var(--success); }}
    .ring-fill.warn {{ stroke: var(--warning); }}
    .ring-fill.bad {{ stroke: var(--failure); }}

    .ring-label {{
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
      font-weight: 700;
    }}

    .ring-caption {{
      font-size: 11px;
      color: var(--muted);
      margin-top: 8px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-weight: 600;
    }}

    /* ── Tables ── */
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13.5px;
    }}

    th, td {{
      padding: 10px 12px;
      text-align: left;
      vertical-align: top;
    }}

    thead th {{
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      font-weight: 600;
      border-bottom: 2px solid var(--line);
      padding-bottom: 8px;
    }}

    tbody td {{
      border-bottom: 1px solid var(--line);
    }}

    tbody tr:hover {{
      background: rgba(0,0,0,0.015);
    }}

    tbody tr:last-child td {{
      border-bottom: none;
    }}

    /* ── Status pills ── */
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 999px;
      padding: 4px 12px;
      font-size: 11.5px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      border: 1px solid transparent;
    }}

    .pill-dot {{
      width: 6px;
      height: 6px;
      border-radius: 50%;
      flex-shrink: 0;
    }}

    .pill.success {{
      color: var(--success);
      background: var(--success-bg);
      border-color: var(--success-border);
    }}
    .pill.success .pill-dot {{ background: var(--success); }}

    .pill.failure {{
      color: var(--failure);
      background: var(--failure-bg);
      border-color: var(--failure-border);
    }}
    .pill.failure .pill-dot {{ background: var(--failure); }}

    .pill.incomplete {{
      color: var(--warning);
      background: var(--warning-bg);
      border-color: var(--warning-border);
    }}
    .pill.incomplete .pill-dot {{ background: var(--warning); }}

    /* ── Volume bars ── */
    .history {{
      display: grid;
      gap: 8px;
    }}

    .day-row {{
      display: grid;
      grid-template-columns: 90px 1fr 50px;
      gap: 12px;
      align-items: center;
      font-size: 13px;
    }}

    .day-row .date-label {{
      color: var(--muted);
      font-variant-numeric: tabular-nums;
    }}

    .bar-track {{
      height: 14px;
      background: var(--track);
      border-radius: 999px;
      overflow: hidden;
      display: flex;
    }}

    .bar-success {{ background: linear-gradient(90deg, #34c47c, #1a7a54); }}
    .bar-failure {{ background: linear-gradient(90deg, #e74c3c, #c0392b); }}
    .bar-incomplete {{ background: linear-gradient(90deg, #f0c040, #b8860b); }}

    .day-row .count {{
      text-align: right;
      font-weight: 600;
      font-variant-numeric: tabular-nums;
    }}

    /* ── Volume legend ── */
    .chart-legend {{
      display: flex;
      gap: 20px;
      margin-bottom: 16px;
    }}

    .legend-item {{
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      color: var(--muted);
    }}

    .legend-dot {{
      width: 10px;
      height: 10px;
      border-radius: 3px;
    }}

    .legend-dot.success {{ background: var(--success); }}
    .legend-dot.failure {{ background: var(--failure); }}
    .legend-dot.incomplete {{ background: var(--warning); }}

    /* ── Config path cards ── */
    .path-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 14px;
    }}

    .path-card {{
      border-radius: var(--radius);
      padding: 16px;
      border: 1px solid var(--line);
      background: var(--panel);
    }}

    .path-card-label {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      font-weight: 600;
      margin-bottom: 8px;
    }}

    .path-card-label .folder-color {{
      width: 8px;
      height: 8px;
      border-radius: 3px;
    }}

    .path-card code {{
      font-family: "Cascadia Mono", "Consolas", monospace;
      font-size: 12.5px;
      word-break: break-all;
      color: var(--text);
      line-height: 1.5;
    }}

    /* ── Info table (key-value) ── */
    .info-table {{
      width: 100%;
    }}

    .info-table th {{
      text-align: left;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-weight: 600;
      padding: 10px 16px 10px 0;
      width: 180px;
      border-bottom: 1px solid var(--line);
    }}

    .info-table td {{
      padding: 10px 0;
      border-bottom: 1px solid var(--line);
      font-size: 14px;
    }}

    .info-table tr:last-child th,
    .info-table tr:last-child td {{
      border-bottom: none;
    }}

    /* ── Empty state ── */
    .empty-cell {{
      color: var(--muted);
      padding: 20px 12px;
      text-align: center;
      font-size: 13px;
    }}

    .detail {{
      color: var(--muted);
      font-size: 12px;
    }}

    code {{
      font-family: "Cascadia Mono", "Consolas", monospace;
      font-size: 13px;
      word-break: break-word;
    }}

    /* ── Responsive ── */
    @media (max-width: 900px) {{
      .sidebar {{
        transform: translateX(-100%);
      }}

      .sidebar.open {{
        transform: translateX(0);
      }}

      .sidebar-overlay.open {{
        display: block;
      }}

      .hamburger {{
        display: flex;
      }}

      .main {{
        margin-left: 0;
      }}

      .hero-row {{
        grid-template-columns: 1fr;
      }}

      .split {{
        grid-template-columns: 1fr;
      }}

      .kpi-grid {{
        grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
      }}

      .content {{
        padding: 16px;
      }}

      .topbar {{
        padding: 12px 16px 12px 56px;
      }}

      .day-row {{
        grid-template-columns: 78px 1fr 40px;
      }}
    }}
  </style>
</head>
<body>
  <!-- Mobile hamburger -->
  <button class="hamburger" onclick="document.querySelector('.sidebar').classList.toggle('open');document.querySelector('.sidebar-overlay').classList.toggle('open')" aria-label="Menu">
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="3" y1="5" x2="17" y2="5"/><line x1="3" y1="10" x2="17" y2="10"/><line x1="3" y1="15" x2="17" y2="15"/></svg>
  </button>
  <div class="sidebar-overlay" onclick="document.querySelector('.sidebar').classList.remove('open');this.classList.remove('open')"></div>

  <!-- Sidebar -->
  <nav class="sidebar">
    <div class="sidebar-brand">
      <h1>Barcode Buddy</h1>
      <div class="brand-sub">Document Processor</div>
    </div>

    <div class="sidebar-nav">
      <div class="nav-section">
        <div class="nav-section-label">Inventory</div>
        <a class="nav-btn" href="/scan" style="text-decoration:none;display:flex;align-items:center;gap:8px;">
          <svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 4V2h4"/><path d="M14 2h4v2"/><path d="M2 16v2h4"/><path d="M14 18h4v-2"/><line x1="6" y1="6" x2="6" y2="14"/><line x1="10" y1="6" x2="10" y2="14"/><line x1="14" y1="6" x2="14" y2="14"/></svg>
          Scan
        </a>
        <a class="nav-btn" href="/inventory" style="text-decoration:none;display:flex;align-items:center;gap:8px;">
          <svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h16v4H2z"/><path d="M2 9h16v8H2z"/><line x1="8" y1="12" x2="12" y2="12"/></svg>
          Items
        </a>
        <a class="nav-btn" href="/inventory/new" style="text-decoration:none;display:flex;align-items:center;gap:8px;">
          <svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="10" r="8"/><line x1="10" y1="6" x2="10" y2="14"/><line x1="6" y1="10" x2="14" y2="10"/></svg>
          New Item
        </a>
      </div>

      <div class="nav-section">
        <div class="nav-section-label">Monitor</div>
        <button class="nav-btn active" data-page="overview" onclick="switchPage('overview', this)">
          <svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="7" height="7" rx="1.5"/><rect x="11" y="2" width="7" height="4" rx="1.5"/><rect x="2" y="11" width="7" height="4" rx="1.5"/><rect x="11" y="8" width="7" height="7" rx="1.5"/></svg>
          Overview
        </button>
        <button class="nav-btn" data-page="documents" onclick="switchPage('documents', this)">
          <svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 2h7l4 4v11a1 1 0 01-1 1H5a1 1 0 01-1-1V3a1 1 0 011-1z"/><polyline points="12 2 12 6 16 6"/><line x1="7" y1="10" x2="13" y2="10"/><line x1="7" y1="13" x2="11" y2="13"/></svg>
          Documents
        </button>
      </div>

      <div class="nav-section">
        <div class="nav-section-label">Insights</div>
        <button class="nav-btn" data-page="analytics" onclick="switchPage('analytics', this)">
          <svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 6 12 12 8 8 2 14"/><polyline points="18 10 18 6 14 6"/></svg>
          Analytics
        </button>
        <button class="nav-btn" data-page="achievements" onclick="switchPage('achievements', this)">
          <svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="10 1 12.6 7.2 19 7.6 14 12 15.6 18.5 10 15 4.4 18.5 6 12 1 7.6 7.4 7.2"/></svg>
          Achievements
        </button>
      </div>

      <div class="nav-section">
        <div class="nav-section-label">System</div>
        <button class="nav-btn" data-page="service" onclick="switchPage('service', this)">
          <svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="10" r="3"/><path d="M17.4 12.4a1.5 1.5 0 00.3 1.65l.05.05a1.82 1.82 0 01-1.29 3.1 1.82 1.82 0 01-1.28-.53l-.06-.06a1.5 1.5 0 00-1.65-.3 1.5 1.5 0 00-.9 1.37V18a1.82 1.82 0 01-3.64 0v-.1a1.5 1.5 0 00-.98-1.37 1.5 1.5 0 00-1.65.3l-.06.06a1.82 1.82 0 01-2.57-2.57l.06-.06a1.5 1.5 0 00.3-1.65 1.5 1.5 0 00-1.37-.9H2a1.82 1.82 0 010-3.64h.1a1.5 1.5 0 001.37-.98 1.5 1.5 0 00-.3-1.65l-.06-.06a1.82 1.82 0 012.57-2.57l.06.06a1.5 1.5 0 001.65.3h.07a1.5 1.5 0 00.9-1.37V2a1.82 1.82 0 013.64 0v.1a1.5 1.5 0 00.9 1.37 1.5 1.5 0 001.65-.3l.06-.06a1.82 1.82 0 012.57 2.57l-.06.06a1.5 1.5 0 00-.3 1.65v.07a1.5 1.5 0 001.37.9H18a1.82 1.82 0 010 3.64h-.1a1.5 1.5 0 00-1.37.9z"/></svg>
          Service
        </button>
        <button class="nav-btn" data-page="config" onclick="switchPage('config', this)">
          <svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7V3h4"/><path d="M17 7V3h-4"/><path d="M3 13v4h4"/><path d="M17 13v4h-4"/><rect x="6" y="6" width="8" height="8" rx="1"/></svg>
          Configuration
        </button>
      </div>
    </div>

    <div class="sidebar-status">
      <div class="status-indicator">
        <span class="status-dot {_escape(service_status)}"></span>
        <span style="color: var(--sidebar-text); font-size: 12px;">
          Service: <strong style="color: var(--sidebar-active);">{_escape(service_status.title())}</strong>
        </span>
      </div>
    </div>

    {_render_user_nav(current_user)}

    <div class="sidebar-footer">
      Barcode Buddy v1.0.0
    </div>
  </nav>

  <!-- Main content -->
  <div class="main">
    <header class="topbar">
      <div class="topbar-title" id="page-title">Overview</div>
      <div class="topbar-meta">
        <span>Updated {_escape(generated_at)}</span>
        <span class="refresh-badge">
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M1 1v5h5"/><path d="M2.5 10A6.5 6.5 0 1014 8"/></svg>
          {snapshot['refresh_seconds']}s
        </span>
      </div>
    </header>

    <div class="content">

      <!-- ═══ OVERVIEW ═══ -->
      <div class="page active" id="page-overview">
        <div class="hero-row">
          <!-- Service health -->
          <div class="hero-card">
            <h3>Service Health</h3>
            <div class="health-display">
              <div class="health-icon {_escape(service_status)}">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                  {"<polyline points='20 6 9 17 4 12'/>" if service_status == "healthy" else "<line x1='18' y1='6' x2='6' y2='18'/><line x1='6' y1='6' x2='18' y2='18'/>" if service_status == "stopped" else "<path d='M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z'/><line x1='12' y1='9' x2='12' y2='13'/><line x1='12' y1='17' x2='12.01' y2='17'/>"}
                </svg>
              </div>
              <div>
                <div class="health-label color-{service_value_class}">{_escape(service_status.title())}</div>
                <div class="health-detail">Heartbeat {_escape(heartbeat_at)}</div>
              </div>
            </div>
          </div>

          <!-- Latency -->
          <div class="hero-card">
            <h3>Latency</h3>
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;text-align:center;">
              <div>
                <div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;">P50</div>
                <div style="font-size:22px;font-weight:700;">{_escape(_format_duration(latency_stats['p50']))}</div>
              </div>
              <div>
                <div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;">P95</div>
                <div style="font-size:22px;font-weight:700;color:var(--info);">{_escape(_format_duration(latency_stats['p95']))}</div>
              </div>
              <div>
                <div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;">P99</div>
                <div style="font-size:22px;font-weight:700;">{_escape(_format_duration(latency_stats['p99']))}</div>
              </div>
            </div>
          </div>

          <!-- Success ring -->
          <div class="hero-card ring-container">
            <h3 style="text-align:center;width:100%;">Success Rate</h3>
            <div class="ring-chart">
              <svg width="100" height="100" viewBox="0 0 100 100">
                <circle class="ring-track" cx="50" cy="50" r="40"/>
                <circle class="ring-fill {"good" if (success_rate or 0) >= 90 else "warn" if (success_rate or 0) >= 50 else "bad"}" cx="50" cy="50" r="40"
                  stroke-dasharray="{ring_dash} 251" />
              </svg>
              <div class="ring-label">{_format_percentage(success_rate)}</div>
            </div>
            <div class="ring-caption">Completion rate</div>
          </div>

          <!-- Health score -->
          <div class="hero-card ring-container">
            <h3 style="text-align:center;width:100%;">Health Score</h3>
            <div class="ring-chart">
              <svg width="100" height="100" viewBox="0 0 100 100">
                <circle class="ring-track" cx="50" cy="50" r="40"/>
                <circle class="ring-fill {"good" if health_score_val >= 80 else "warn" if health_score_val >= 50 else "bad"}" cx="50" cy="50" r="40"
                  stroke-dasharray="{health_ring_dash} 251" />
              </svg>
              <div class="ring-label" style="color:{health_grade_color};font-size:22px;">{_escape(health_grade)}</div>
            </div>
            <div class="ring-caption">{health_score_val}/100</div>
          </div>
        </div>

        <div class="kpi-grid">
          <article class="kpi accent-blue">
            <div class="kpi-label">Documents Seen</div>
            <div class="kpi-value">{document_stats['seen']}</div>
            <div class="kpi-sub">Last processed {_escape(last_processed_at)}</div>
          </article>
          <article class="kpi accent-green">
            <div class="kpi-label">Succeeded</div>
            <div class="kpi-value color-success">{document_stats['succeeded']}</div>
            <div class="kpi-sub">of {document_stats['completed']} completed</div>
          </article>
          <article class="kpi accent-red">
            <div class="kpi-label">Failed</div>
            <div class="kpi-value color-failure">{document_stats['failed']}</div>
          </article>
          <article class="kpi accent-amber">
            <div class="kpi-label">Incomplete</div>
            <div class="kpi-value color-warning">{document_stats['incomplete']}</div>
            <div class="kpi-sub">No terminal outcome yet</div>
          </article>
          <article class="kpi">
            <div class="kpi-label">Input Backlog</div>
            <div class="kpi-value">{queue_stats['input_backlog_count']}</div>
            <div class="kpi-sub">Oldest {_escape(_format_seconds(queue_stats['oldest_input_age_seconds']))}</div>
          </article>
          <article class="kpi">
            <div class="kpi-label">Avg Completion</div>
            <div class="kpi-value">{_escape(_format_duration(document_stats['average_completion_ms']))}</div>
          </article>
          <article class="kpi accent-blue">
            <div class="kpi-label">Queue ETA</div>
            <div class="kpi-value">{_escape(queue_eta['eta_display'])}</div>
            <div class="kpi-sub">{queue_eta['backlog']} files in backlog</div>
          </article>
        </div>

        <!-- 24h window -->
        <div class="panel">
          <div class="panel-header">
            <span class="panel-title">Last 24 Hours</span>
            <span class="pill success" style="font-size:10px;"><span class="pill-dot"></span>{last_day_stats['succeeded']} succeeded</span>
          </div>
          <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:14px;">
            <div style="text-align:center;padding:14px;border-radius:12px;background:var(--info-bg);border:1px solid var(--info-border);">
              <div style="font-size:28px;font-weight:700;color:var(--info);">{last_day_stats['documents']}</div>
              <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:var(--muted);margin-top:4px;">Seen</div>
            </div>
            <div style="text-align:center;padding:14px;border-radius:12px;background:var(--success-bg);border:1px solid var(--success-border);">
              <div style="font-size:28px;font-weight:700;color:var(--success);">{last_day_stats['succeeded']}</div>
              <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:var(--muted);margin-top:4px;">Succeeded</div>
            </div>
            <div style="text-align:center;padding:14px;border-radius:12px;background:var(--failure-bg);border:1px solid var(--failure-border);">
              <div style="font-size:28px;font-weight:700;color:var(--failure);">{last_day_stats['failed']}</div>
              <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:var(--muted);margin-top:4px;">Failed</div>
            </div>
            <div style="text-align:center;padding:14px;border-radius:12px;background:var(--warning-bg);border:1px solid var(--warning-border);">
              <div style="font-size:28px;font-weight:700;color:var(--warning);">{last_day_stats['incomplete']}</div>
              <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:var(--muted);margin-top:4px;">Incomplete</div>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══ DOCUMENTS ═══ -->
      <div class="page" id="page-documents">
        <div class="panel">
          <div class="panel-header">
            <span class="panel-title">Recent Documents</span>
            <span style="font-size:12px;color:var(--muted);">Newest first &middot; latest event per processing ID</span>
          </div>
          <div style="overflow-x:auto;">
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
          </div>
        </div>
      </div>

      <!-- ═══ ANALYTICS ═══ -->
      <div class="page" id="page-analytics">
        <div class="panel" style="margin-bottom:20px;">
          <div class="panel-header">
            <span class="panel-title">24-Hour Throughput</span>
            <span style="font-size:12px;color:var(--muted);">Files processed per hour</span>
          </div>
          <div class="chart-legend">
            <div class="legend-item"><div class="legend-dot success"></div>Succeeded</div>
            <div class="legend-item"><div class="legend-dot failure"></div>Failed</div>
          </div>
          <div style="display:flex;gap:2px;align-items:flex-end;height:90px;padding-bottom:24px;">
            {hourly_bars_html}
          </div>
        </div>

        <div class="split">
          <div class="panel">
            <div class="panel-header">
              <span class="panel-title">14-Day Volume</span>
            </div>
            <div class="chart-legend">
              <div class="legend-item"><div class="legend-dot success"></div>Succeeded</div>
              <div class="legend-item"><div class="legend-dot failure"></div>Failed</div>
              <div class="legend-item"><div class="legend-dot incomplete"></div>Incomplete</div>
            </div>
            <div class="history">
              {daily_rows}
            </div>
          </div>

          <div>
            <div class="panel">
              <div class="panel-header">
                <span class="panel-title">Failure Reasons</span>
              </div>
              <div class="panel-desc">Top terminal failure reasons from the latest outcome per document.</div>
              <table>
                <thead>
                  <tr><th>Reason</th><th style="text-align:right;">Count</th></tr>
                </thead>
                <tbody>
                  {failure_rows}
                </tbody>
              </table>
            </div>

            <div class="panel">
              <div class="panel-header">
                <span class="panel-title">Pipeline Stages</span>
              </div>
              <div class="panel-desc">Raw log entries by pipeline stage.</div>
              <table>
                <thead>
                  <tr><th>Stage</th><th style="text-align:right;">Count</th></tr>
                </thead>
                <tbody>
                  {stage_rows}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══ ACHIEVEMENTS ═══ -->
      <div class="page" id="page-achievements">
        <div class="kpi-grid" style="grid-template-columns:repeat(auto-fill,minmax(240px,1fr));">
          <!-- Streak card -->
          <article class="kpi accent-green" style="text-align:center;">
            <div class="kpi-label">Error-Free Streak</div>
            <div class="kpi-value color-success" style="font-size:48px;">{streak['zero_error_days']}</div>
            <div class="kpi-sub">{_escape(streak['label'])}</div>
          </article>

          <!-- Badge card -->
          <article class="kpi" style="text-align:center;border-left:3px solid {_escape(badge['color'] or 'var(--muted)')};">
            <div class="kpi-label">Throughput Badge</div>
            <div class="kpi-value" style="color:{_escape(badge['color'] or 'var(--muted)')};font-size:36px;">{_escape(badge['name'] or 'None yet')}</div>
            <div class="kpi-sub">{badge['total_succeeded']:,} documents succeeded</div>
          </article>

          <!-- Next tier card -->
          <article class="kpi accent-blue" style="text-align:center;">
            <div class="kpi-label">Next Tier</div>
            <div class="kpi-value" style="font-size:28px;">{_escape(next_tier['name'] or 'Max reached')}</div>
            {"<div class='kpi-sub'>" + str(next_tier['target'] or 0) + " target &mdash; " + str(next_tier['progress_pct']) + "% progress</div>" if next_tier['name'] else ""}
            {('<div style="margin-top:10px;height:8px;background:var(--track);border-radius:99px;overflow:hidden;"><div style="width:' + str(min(100, next_tier['progress_pct'])) + '%;height:100%;background:linear-gradient(90deg,var(--info),var(--success));border-radius:99px;"></div></div>') if next_tier['name'] else ''}
          </article>

          <!-- Health score card -->
          <article class="kpi" style="text-align:center;border-left:3px solid {health_grade_color};">
            <div class="kpi-label">Health Score</div>
            <div class="kpi-value" style="color:{health_grade_color};">{health_score_val}</div>
            <div class="kpi-sub">Grade {_escape(health_grade)}</div>
          </article>
        </div>

        <!-- Milestones -->
        <div class="panel">
          <div class="panel-header">
            <span class="panel-title">Milestones</span>
            <span style="font-size:12px;color:var(--muted);">Throughput achievements unlocked</span>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:12px;">
            {"".join(
              '<div style="padding:10px 18px;border-radius:12px;background:var(--success-bg);border:1px solid var(--success-border);text-align:center;">'
              '<div style="font-size:18px;font-weight:700;color:var(--success);">' + str(m["threshold"]) + '</div>'
              '<div style="font-size:10px;color:var(--muted);text-transform:uppercase;">Reached</div>'
              '</div>'
              for m in milestones
            ) or '<div style="color:var(--muted);padding:20px;text-align:center;">Process your first documents to unlock milestones.</div>'}
          </div>
        </div>

        <!-- Health score breakdown -->
        <div class="panel">
          <div class="panel-header">
            <span class="panel-title">Health Score Breakdown</span>
          </div>
          <div class="panel-desc">Composite score derived from four weighted signals.</div>
          <table class="info-table">
            <tbody>
              <tr><th>Success Rate (35%)</th><td>{health['components'].get('success_rate', 0)}/100</td></tr>
              <tr><th>Uptime (25%)</th><td>{health['components'].get('uptime', 0)}/100</td></tr>
              <tr><th>Throughput (20%)</th><td>{health['components'].get('throughput', 0)}/100</td></tr>
              <tr><th>Error Trend (20%)</th><td>{health['components'].get('error_trend', 0)}/100</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ═══ SERVICE ═══ -->
      <div class="page" id="page-service">
        <div class="split">
          <div>
            <div class="panel">
              <div class="panel-header">
                <span class="panel-title">Service State</span>
                <span class="pill {service_value_class}"><span class="pill-dot"></span>{_escape(service_status.title())}</span>
              </div>
              <div class="panel-desc">Latest worker heartbeat and restart signals from the log plus the current lock file.</div>
              <table class="info-table">
                <tbody>
                  <tr><th>Status</th><td><strong class="color-{service_value_class}">{_escape(service_status.title())}</strong></td></tr>
                  <tr><th>Last Event</th><td>{_escape(service_stats['last_event_type'] or '-')} at {_escape(service_last_event_at)}</td></tr>
                  <tr><th>Heartbeat Age</th><td>{_escape(_format_seconds(service_stats['heartbeat_age_seconds']))}</td></tr>
                  <tr><th>Lock File</th><td>
                    <span class="pill {"success" if service_stats["lock_exists"] else "failure"}" style="font-size:10px;">
                      <span class="pill-dot"></span>{"Present" if service_stats["lock_exists"] else "Missing"}
                    </span>
                  </td></tr>
                  <tr><th>Startups (24h)</th><td>{service_stats['startups_last_24h']}</td></tr>
                  <tr><th>Shutdowns (24h)</th><td>{service_stats['shutdowns_last_24h']}</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <div class="panel">
              <div class="panel-header">
                <span class="panel-title">Queue State</span>
              </div>
              <div class="panel-desc">Current filesystem backlog and recovery-journal counts.</div>
              <table class="info-table">
                <tbody>
                  <tr><th>Input Backlog</th><td><strong>{queue_stats['input_backlog_count']}</strong></td></tr>
                  <tr><th>Oldest Input</th><td>{_escape(_format_seconds(queue_stats['oldest_input_age_seconds']))}</td></tr>
                  <tr><th>Processing Files</th><td>{queue_stats['processing_count']}</td></tr>
                  <tr><th>Journal Files</th><td>{queue_stats['journal_count']}</td></tr>
                </tbody>
              </table>
            </div>

            <div class="panel">
              <div class="panel-header">
                <span class="panel-title">Log Info</span>
              </div>
              <table class="info-table">
                <tbody>
                  <tr><th>Log Files</th><td>{snapshot['log']['files']} ({snapshot['log']['archived_files']} archived)</td></tr>
                  <tr><th>Total Lines</th><td>{snapshot['log']['lines']}</td></tr>
                  <tr><th>Ignored Lines</th><td>{snapshot['log']['ignored_lines']}</td></tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══ CONFIGURATION ═══ -->
      <div class="page" id="page-config">
        <div class="panel">
          <div class="panel-header">
            <span class="panel-title">Directory Paths</span>
          </div>
          <div class="panel-desc">Active filesystem directories used by the processing service.</div>
          <div class="path-grid">
            <div class="path-card">
              <div class="path-card-label"><div class="folder-color" style="background:var(--info);"></div>Input</div>
              <code>{_escape(snapshot['paths']['input'])}</code>
            </div>
            <div class="path-card">
              <div class="path-card-label"><div class="folder-color" style="background:var(--warning);"></div>Processing</div>
              <code>{_escape(snapshot['paths']['processing'])}</code>
            </div>
            <div class="path-card">
              <div class="path-card-label"><div class="folder-color" style="background:var(--success);"></div>Output</div>
              <code>{_escape(snapshot['paths']['output'])}</code>
            </div>
            <div class="path-card">
              <div class="path-card-label"><div class="folder-color" style="background:var(--failure);"></div>Rejected</div>
              <code>{_escape(snapshot['paths']['rejected'])}</code>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <span class="panel-title">Log Configuration</span>
          </div>
          <div class="path-grid">
            <div class="path-card" style="grid-column:1/-1;">
              <div class="path-card-label"><div class="folder-color" style="background:var(--accent);"></div>Active Log File</div>
              <code>{_escape(snapshot['paths']['log_file'])}</code>
            </div>
            <div class="path-card" style="grid-column:1/-1;">
              <div class="path-card-label"><div class="folder-color" style="background:var(--accent);"></div>Log Directory</div>
              <code>{_escape(snapshot['paths']['log_path'])}</code>
            </div>
          </div>
        </div>
      </div>

    </div>
  </div>

  <script>
    const pageTitles = {{
      overview: 'Overview',
      documents: 'Documents',
      analytics: 'Analytics',
      achievements: 'Achievements',
      service: 'Service',
      config: 'Configuration'
    }};

    function switchPage(pageId, btn) {{
      document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      const page = document.getElementById('page-' + pageId);
      if (page) page.classList.add('active');
      if (btn) btn.classList.add('active');
      document.getElementById('page-title').textContent = pageTitles[pageId] || pageId;
      // Close mobile sidebar
      document.querySelector('.sidebar').classList.remove('open');
      document.querySelector('.sidebar-overlay').classList.remove('open');
      // Persist selection
      try {{ sessionStorage.setItem('bb_page', pageId); }} catch(e) {{}}
    }}

    // Restore page on load (survives auto-refresh)
    (function() {{
      try {{
        const saved = sessionStorage.getItem('bb_page');
        if (saved && document.getElementById('page-' + saved)) {{
          const btn = document.querySelector('[data-page="' + saved + '"]');
          switchPage(saved, btn);
        }}
      }} catch(e) {{}}
    }})();

    // Auto-refresh via fetch to preserve page state
    setTimeout(function autoRefresh() {{
      fetch(window.location.href, {{ headers: {{ 'Accept': 'text/html' }} }})
        .then(r => r.text())
        .then(html => {{
          const parser = new DOMParser();
          const doc = parser.parseFromString(html, 'text/html');
          const newContent = doc.querySelector('.content');
          const newTopbar = doc.querySelector('.topbar');
          const newSidebarStatus = doc.querySelector('.sidebar-status');
          if (newContent) document.querySelector('.content').innerHTML = newContent.innerHTML;
          if (newTopbar) {{
            const meta = document.querySelector('.topbar-meta');
            const newMeta = doc.querySelector('.topbar-meta');
            if (meta && newMeta) meta.innerHTML = newMeta.innerHTML;
          }}
          if (newSidebarStatus) document.querySelector('.sidebar-status').innerHTML = newSidebarStatus.innerHTML;
          // Re-apply active page
          try {{
            const saved = sessionStorage.getItem('bb_page');
            if (saved && document.getElementById('page-' + saved)) {{
              document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
              const page = document.getElementById('page-' + saved);
              if (page) page.classList.add('active');
            }}
          }} catch(e) {{}}
        }})
        .catch(() => {{}})
        .finally(() => setTimeout(autoRefresh, {snapshot['refresh_seconds']} * 1000));
    }}, {snapshot['refresh_seconds']} * 1000);
  </script>
</body>
</html>
"""


def render_client_html(snapshot: dict[str, Any]) -> str:
    """Render a read-only client portal — high-level KPIs, trends, and SLA metrics only."""
    docs = snapshot["documents"]
    last24 = snapshot["last_24_hours"]
    daily = snapshot["daily_counts"]
    health = snapshot.get("health_score", {"score": 0, "grade": "?", "components": {}})
    eta = snapshot.get("queue_eta", {"backlog": 0, "eta_display": "n/a"})
    latency = snapshot.get("latency_ms", {"p50": None, "p95": None, "p99": None})
    ach = snapshot.get("achievements", {"streak": {"zero_error_days": 0, "label": "—"}, "badge": {"name": None, "color": None}})
    hourly = snapshot.get("hourly_throughput", [])

    grade_colors = {"A": "#1a7a54", "B": "#2472a4", "C": "#b8860b", "D": "#c0392b", "F": "#8b0000"}
    grade_color = grade_colors.get(health["grade"], "#888")

    max_hourly = max((h["total"] for h in hourly), default=1) or 1
    hourly_bars = ""
    for bucket in hourly:
        bar_h = max(1, round((bucket["total"] / max_hourly) * 50))
        hourly_bars += (
            f'<div style="flex:1;min-width:0;display:flex;flex-direction:column;align-items:center;">'
            f'<div style="width:100%;height:50px;display:flex;align-items:flex-end;">'
            f'<div style="width:100%;height:{bar_h}px;background:linear-gradient(180deg,#34c47c,#1a7a54);border-radius:3px 3px 0 0;"></div>'
            f'</div>'
            f'<div style="font-size:8px;color:#aaa;margin-top:2px;">{_escape(bucket["hour"][:2])}</div>'
            f'</div>'
        )

    max_daily = max((d["total"] for d in daily), default=1) or 1
    daily_bars = ""
    for day in daily[-7:]:
        pct = min(100, round((day["total"] / max_daily) * 100))
        daily_bars += (
            f'<div style="display:flex;align-items:center;gap:8px;margin:3px 0;">'
            f'<span style="width:68px;font-size:12px;color:#aaa;">{_escape(day["date"])}</span>'
            f'<div style="flex:1;height:14px;background:#f0f0f0;border-radius:8px;overflow:hidden;">'
            f'<div style="width:{pct}%;height:100%;background:linear-gradient(90deg,#34c47c,#1a7a54);border-radius:8px;"></div>'
            f'</div>'
            f'<span style="width:32px;text-align:right;font-size:12px;font-weight:600;">{day["total"]}</span>'
            f'</div>'
        )

    refresh = snapshot.get("refresh_seconds", 15)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Barcode Buddy — Client Portal</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: "Segoe UI Variable","Segoe UI",system-ui,sans-serif; background: #f8f9fa; color: #1a1f26; min-height: 100vh; }}
    .header {{ background: linear-gradient(135deg, #1e2530 0%, #2c3e50 100%); padding: 32px 40px; color: #fff; }}
    .header h1 {{ font-size: 24px; font-weight: 700; margin-bottom: 4px; }}
    .header p {{ font-size: 13px; opacity: 0.65; }}
    .container {{ max-width: 1100px; margin: 0 auto; padding: 28px 24px; }}
    .grid-4 {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; margin-bottom: 28px; }}
    .card {{ background: #fff; border-radius: 14px; padding: 22px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); border: 1px solid #eee; }}
    .card-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; color: #999; font-weight: 600; margin-bottom: 8px; }}
    .card-value {{ font-size: 32px; font-weight: 700; line-height: 1; }}
    .card-sub {{ font-size: 12px; color: #999; margin-top: 6px; }}
    .panel {{ background: #fff; border-radius: 14px; padding: 24px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); border: 1px solid #eee; margin-bottom: 20px; }}
    .panel-title {{ font-size: 16px; font-weight: 600; margin-bottom: 16px; }}
    .split {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
    @media (max-width: 768px) {{ .split {{ grid-template-columns: 1fr; }} .grid-4 {{ grid-template-columns: 1fr 1fr; }} }}
  </style>
</head>
<body>
  <div class="header">
    <h1>Barcode Buddy</h1>
    <p>Client Portal &mdash; Updated {_escape(snapshot["generated_at"][:19])}</p>
  </div>
  <div class="container">

    <div class="grid-4">
      <div class="card" style="border-left:3px solid {grade_color};">
        <div class="card-label">Health Score</div>
        <div class="card-value" style="color:{grade_color};">{health["score"]}<span style="font-size:18px;margin-left:4px;">{_escape(health["grade"])}</span></div>
        <div class="card-sub">System health composite</div>
      </div>
      <div class="card" style="border-left:3px solid #1a7a54;">
        <div class="card-label">Documents Processed</div>
        <div class="card-value" style="color:#1a7a54;">{docs["succeeded"]:,}</div>
        <div class="card-sub">{_format_percentage(docs["success_rate"])} success rate</div>
      </div>
      <div class="card" style="border-left:3px solid #2472a4;">
        <div class="card-label">24h Processed</div>
        <div class="card-value" style="color:#2472a4;">{last24["completed"]}</div>
        <div class="card-sub">{last24["succeeded"]} succeeded, {last24["failed"]} failed</div>
      </div>
      <div class="card" style="border-left:3px solid #b8860b;">
        <div class="card-label">Queue ETA</div>
        <div class="card-value">{_escape(eta["eta_display"])}</div>
        <div class="card-sub">{eta["backlog"]} file(s) waiting</div>
      </div>
    </div>

    <div class="grid-4">
      <div class="card">
        <div class="card-label">Avg Completion</div>
        <div class="card-value" style="font-size:24px;">{_escape(_format_duration(docs["average_completion_ms"]))}</div>
      </div>
      <div class="card">
        <div class="card-label">P50 Latency</div>
        <div class="card-value" style="font-size:24px;">{_escape(_format_duration(latency["p50"]))}</div>
      </div>
      <div class="card">
        <div class="card-label">P95 Latency</div>
        <div class="card-value" style="font-size:24px;">{_escape(_format_duration(latency["p95"]))}</div>
      </div>
      <div class="card">
        <div class="card-label">Error-Free Streak</div>
        <div class="card-value" style="font-size:24px;color:#1a7a54;">{ach["streak"]["zero_error_days"]} days</div>
      </div>
    </div>

    <div class="split">
      <div class="panel">
        <div class="panel-title">24-Hour Throughput</div>
        <div style="display:flex;gap:2px;align-items:flex-end;height:70px;padding-bottom:16px;">
          {hourly_bars}
        </div>
      </div>
      <div class="panel">
        <div class="panel-title">7-Day Trend</div>
        {daily_bars}
      </div>
    </div>

    <div class="panel" style="text-align:center;color:#aaa;font-size:12px;padding:16px;">
      Barcode Buddy Client Portal &mdash; Auto-refreshes every {refresh}s
    </div>
  </div>

  <script>
    setTimeout(function autoRefresh() {{
      fetch(window.location.href, {{ headers: {{ 'Accept': 'text/html' }} }})
        .then(r => r.text())
        .then(html => {{
          const parser = new DOMParser();
          const doc = parser.parseFromString(html, 'text/html');
          const newContainer = doc.querySelector('.container');
          if (newContainer) document.querySelector('.container').innerHTML = newContainer.innerHTML;
          const newHeader = doc.querySelector('.header');
          if (newHeader) document.querySelector('.header').innerHTML = newHeader.innerHTML;
        }})
        .catch(() => {{}})
        .finally(() => setTimeout(autoRefresh, {refresh} * 1000));
    }}, {refresh} * 1000);
  </script>
</body>
</html>"""


def create_stats_app(
    settings: Settings,
    *,
    refresh_seconds: int = 15,
    history_days: int = 14,
    recent_limit: int = 25,
) -> FastAPI:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import RedirectResponse as StarletteRedirect

    from app.admin_routes import router as admin_router
    from app.auth import get_current_user, COOKIE_NAME, _get_token_from_request, _decode_token, _hash_token
    from app.auth_routes import router as auth_router
    from app.database import User, UserSession, get_db, init_db
    from app.inventory_pages import router as inventory_pages_router
    from app.inventory_routes import router as inventory_router

    # Initialize database
    db_path = settings.log_path / "barcode_buddy.db"
    init_db(db_path)

    app = FastAPI(title="Barcode Buddy Stats", docs_url="/docs", redoc_url=None)

    # --- Auth Middleware ---
    _PUBLIC_PREFIXES = ("/auth/", "/health", "/docs", "/openapi.json")

    class AuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            path = request.url.path
            if any(path.startswith(p) for p in _PUBLIC_PREFIXES):
                return await call_next(request)
            # Check authentication
            token = _get_token_from_request(request)
            if not token:
                if "text/html" in request.headers.get("accept", ""):
                    return StarletteRedirect(url="/auth/login", status_code=307)
                return JSONResponse(status_code=401, content={"error": "Not authenticated"})
            payload = _decode_token(token)
            if not payload:
                if "text/html" in request.headers.get("accept", ""):
                    return StarletteRedirect(url="/auth/login", status_code=307)
                return JSONResponse(status_code=401, content={"error": "Invalid token"})
            # Verify session not revoked (quick check via DB)
            jti = payload.get("jti")
            if jti:
                db_gen = get_db()
                db = next(db_gen)
                try:
                    session = db.query(UserSession).filter(
                        UserSession.token_hash == _hash_token(jti),
                        UserSession.is_revoked == False,
                    ).first()
                    if not session:
                        if "text/html" in request.headers.get("accept", ""):
                            return StarletteRedirect(url="/auth/login", status_code=307)
                        return JSONResponse(status_code=401, content={"error": "Session revoked"})
                    user = db.query(User).filter(
                        User.id == payload.get("sub"), User.is_active == True
                    ).first()
                    if not user:
                        if "text/html" in request.headers.get("accept", ""):
                            return StarletteRedirect(url="/auth/login", status_code=307)
                        return JSONResponse(status_code=401, content={"error": "User not found"})
                    # Store user info in request state for downstream use
                    request.state.user = user
                    request.state.user_dict = user.to_dict()
                finally:
                    try:
                        next(db_gen)
                    except StopIteration:
                        pass
            return await call_next(request)

    app.add_middleware(AuthMiddleware)

    # Include auth, admin, and inventory routers
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(inventory_router)
    app.include_router(inventory_pages_router)

    def _snapshot() -> dict[str, Any]:
        snapshot = build_stats_snapshot(
            settings,
            history_days=history_days,
            recent_limit=recent_limit,
        )
        snapshot["refresh_seconds"] = refresh_seconds
        return snapshot

    @app.get("/", response_class=HTMLResponse)
    def stats_page(request: Request) -> HTMLResponse:
        snapshot = _snapshot()
        user_dict = getattr(request.state, "user_dict", None)
        return HTMLResponse(content=render_stats_html(snapshot, current_user=user_dict))

    @app.get("/api/stats")
    def stats_json() -> JSONResponse:
        snapshot = _snapshot()
        return JSONResponse(
            content=snapshot,
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/health")
    def health_check() -> Response:
        snapshot = _snapshot()
        status = snapshot["service"]["status"]
        payload = {
            "status": status,
            "heartbeat_age_seconds": snapshot["service"]["heartbeat_age_seconds"],
            "lock_exists": snapshot["service"]["lock_exists"],
            "input_backlog_count": snapshot["queues"]["input_backlog_count"],
            "processing_count": snapshot["queues"]["processing_count"],
            "journal_count": snapshot["queues"]["journal_count"],
        }
        status_code = 200 if status == "healthy" else 503
        return JSONResponse(content=payload, status_code=status_code)

    @app.get("/api/queue")
    def queue_status() -> JSONResponse:
        snapshot = _snapshot()
        return JSONResponse(
            content={
                "queues": snapshot["queues"],
                "queue_eta": snapshot["queue_eta"],
                "processing_count": snapshot["queues"]["processing_count"],
            },
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/health-score")
    def health_score() -> JSONResponse:
        snapshot = _snapshot()
        return JSONResponse(
            content=snapshot["health_score"],
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/achievements")
    def achievements() -> JSONResponse:
        snapshot = _snapshot()
        return JSONResponse(
            content=snapshot["achievements"],
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/hourly")
    def hourly_throughput() -> JSONResponse:
        snapshot = _snapshot()
        return JSONResponse(
            content=snapshot["hourly_throughput"],
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/inventory", response_class=HTMLResponse)
    def inventory_page(request: Request) -> HTMLResponse:
        from app.inventory_ui import render_inventory_app
        user = getattr(request.state, "user", None)
        if not user:
            return HTMLResponse(content="<script>window.location='/auth/login'</script>")
        return HTMLResponse(content=render_inventory_app(user))

    @app.get("/client", response_class=HTMLResponse)
    def client_portal(request: Request) -> HTMLResponse:
        snapshot = _snapshot()
        return HTMLResponse(content=render_client_html(snapshot))

    @app.post("/api/reports/daily")
    def trigger_daily_report() -> JSONResponse:
        path = generate_daily_report(settings)
        return JSONResponse(content={"status": "ok", "path": str(path)})

    # --- Prometheus metrics endpoint ---
    @app.get("/metrics")
    def prometheus_metrics() -> Response:
        from prometheus_client import (
            CollectorRegistry,
            Gauge,
            generate_latest,
            CONTENT_TYPE_LATEST,
        )

        registry = CollectorRegistry()
        snapshot = _snapshot()

        docs = snapshot["documents"]
        svc = snapshot["service"]
        queues = snapshot["queues"]
        latency = snapshot["latency_ms"]

        Gauge("barcode_buddy_documents_seen_total", "Total documents seen", registry=registry).set(docs["seen"])
        Gauge("barcode_buddy_documents_succeeded_total", "Succeeded documents", registry=registry).set(docs["succeeded"])
        Gauge("barcode_buddy_documents_failed_total", "Failed documents", registry=registry).set(docs["failed"])
        Gauge("barcode_buddy_documents_incomplete_total", "Incomplete documents", registry=registry).set(docs["incomplete"])
        Gauge("barcode_buddy_success_rate_percent", "Success rate percentage", registry=registry).set(docs["success_rate"])
        Gauge("barcode_buddy_avg_completion_ms", "Average completion time ms", registry=registry).set(docs["average_completion_ms"])

        Gauge("barcode_buddy_latency_p50_ms", "P50 latency ms", registry=registry).set(latency["p50"])
        Gauge("barcode_buddy_latency_p95_ms", "P95 latency ms", registry=registry).set(latency["p95"])
        Gauge("barcode_buddy_latency_p99_ms", "P99 latency ms", registry=registry).set(latency["p99"])

        Gauge("barcode_buddy_service_healthy", "1 if healthy, 0 otherwise", registry=registry).set(1 if svc["status"] == "healthy" else 0)
        Gauge("barcode_buddy_heartbeat_age_seconds", "Seconds since last heartbeat", registry=registry).set(svc["heartbeat_age_seconds"])
        Gauge("barcode_buddy_startups_24h", "Startups in last 24h", registry=registry).set(svc["startups_last_24h"])

        Gauge("barcode_buddy_input_backlog_count", "Files in input queue", registry=registry).set(queues["input_backlog_count"])
        Gauge("barcode_buddy_processing_count", "Files being processed", registry=registry).set(queues["processing_count"])
        Gauge("barcode_buddy_journal_count", "Active journal entries", registry=registry).set(queues["journal_count"])

        return Response(
            content=generate_latest(registry),
            media_type=CONTENT_TYPE_LATEST,
        )

    return app


def serve_stats_page(
    settings: Settings,
    *,
    host: str,
    port: int,
    refresh_seconds: int = 15,
    history_days: int = 14,
    recent_limit: int = 25,
) -> None:
    import uvicorn
    from apscheduler.schedulers.background import BackgroundScheduler

    app = create_stats_app(
        settings,
        refresh_seconds=refresh_seconds,
        history_days=history_days,
        recent_limit=recent_limit,
    )

    # Schedule daily report generation at midnight
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        lambda: generate_daily_report(settings),
        "cron",
        hour=0,
        minute=5,
        id="daily_report",
        misfire_grace_time=3600,
    )
    scheduler.start()

    uvicorn.run(app, host=host, port=port, log_level="warning")


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
        f'<div class="date-label">{_escape(day["date"])}</div>'
        '<div class="bar-track">'
        f'<div class="bar-success" style="width:{success_width:.2f}%"></div>'
        f'<div class="bar-failure" style="width:{failure_width:.2f}%"></div>'
        f'<div class="bar-incomplete" style="width:{incomplete_width:.2f}%"></div>'
        "</div>"
        f'<div class="count">{day["total"]}</div>'
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
        f"<td><strong>{_escape(event['original_filename'])}</strong></td>"
        f'<td><span class="pill {status}"><span class="pill-dot"></span>{_escape(status)}</span></td>'
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


def _render_user_nav(current_user: dict[str, Any] | None) -> str:
    if not current_user:
        return ""
    name = _escape(current_user.get("display_name", "User"))
    role = _escape(current_user.get("role", "user"))
    is_admin = current_user.get("role") == "admin"
    admin_link = (
        '<a href="/admin" style="display:block;padding:6px 20px;color:var(--sidebar-text);'
        'text-decoration:none;font-size:13px;transition:color 0.2s;" '
        'onmouseover="this.style.color=\'var(--sidebar-active)\'" '
        'onmouseout="this.style.color=\'var(--sidebar-text)\'">'
        '<svg style="width:14px;height:14px;vertical-align:-2px;margin-right:6px" viewBox="0 0 20 20" '
        'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 14v2a2 2 0 01-2 2H4a2 2 0 01-2-2v-2"/>'
        '<path d="M16 7a4 4 0 00-8 0v3h8V7z"/><rect x="6" y="10" width="8" height="6" rx="1"/>'
        '</svg>Admin Panel</a>'
    ) if is_admin else ""
    role_badge_bg = "#7c3aed33" if is_admin else "#3b82f633"
    role_badge_color = "#a78bfa" if is_admin else "#93c5fd"
    return f"""
    <div style="padding:14px 20px;border-top:1px solid rgba(255,255,255,0.06);">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
        <div style="width:28px;height:28px;border-radius:50%;background:#334155;display:flex;
          align-items:center;justify-content:center;font-size:12px;font-weight:700;color:#f8fafc;">
          {_escape(name[0].upper())}
        </div>
        <div>
          <div style="font-size:13px;color:var(--sidebar-active);font-weight:600;">{name}</div>
          <span style="font-size:10px;padding:1px 6px;border-radius:4px;
            background:{role_badge_bg};color:{role_badge_color};font-weight:600;">
            {role}
          </span>
        </div>
      </div>
      {admin_link}
      <a href="#" onclick="fetch('/auth/api/logout',{{method:'POST'}}).then(()=>window.location.href='/auth/login');return false;"
        style="display:block;padding:6px 20px;color:var(--sidebar-text);text-decoration:none;font-size:13px;
        transition:color 0.2s;"
        onmouseover="this.style.color='#f87171'" onmouseout="this.style.color='var(--sidebar-text)'">
        <svg style="width:14px;height:14px;vertical-align:-2px;margin-right:6px" viewBox="0 0 20 20"
          fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M7 17H3a1 1 0 01-1-1V4a1 1 0 011-1h4"/><path d="M14 14l4-4-4-4"/><path d="M18 10H7"/>
        </svg>Sign Out
      </a>
    </div>"""


# ────────────────────────────────────────────────────────────────────
#  Health Score  (0–100 composite)
# ────────────────────────────────────────────────────────────────────

def _compute_health_score(
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Return a 0-100 health score composed of four weighted signals."""
    weights = {
        "success_rate": 0.35,
        "uptime": 0.25,
        "throughput": 0.20,
        "error_trend": 0.20,
    }

    # --- success_rate component (0-100) ---
    raw_success_rate = snapshot["documents"]["success_rate"]
    success_component = raw_success_rate if raw_success_rate is not None else 50.0

    # --- uptime component (0-100) ---
    service_status = snapshot["service"]["status"]
    if service_status == "healthy":
        uptime_component = 100.0
    elif service_status == "stale":
        uptime_component = 40.0
    elif service_status == "stopped":
        uptime_component = 0.0
    else:
        uptime_component = 50.0

    # --- throughput component (0-100) based on 24h volume ---
    last_24h_completed = snapshot["last_24_hours"]["completed"]
    # Scale: 0 = 0, 10+ = 100 (logarithmic feel for small installs)
    throughput_component = min(100.0, last_24h_completed * 10.0)

    # --- error_trend component (0-100) inverted recent error share ---
    last_24h_failed = snapshot["last_24_hours"]["failed"]
    last_24h_docs = snapshot["last_24_hours"]["documents"]
    if last_24h_docs > 0:
        error_share = last_24h_failed / last_24h_docs
        error_trend_component = max(0.0, (1.0 - error_share) * 100.0)
    else:
        error_trend_component = 50.0  # neutral when no data

    score = round(
        success_component * weights["success_rate"]
        + uptime_component * weights["uptime"]
        + throughput_component * weights["throughput"]
        + error_trend_component * weights["error_trend"],
        1,
    )

    if score >= 80:
        grade = "A"
    elif score >= 60:
        grade = "B"
    elif score >= 40:
        grade = "C"
    elif score >= 20:
        grade = "D"
    else:
        grade = "F"

    return {
        "score": score,
        "grade": grade,
        "components": {
            "success_rate": round(success_component, 1),
            "uptime": round(uptime_component, 1),
            "throughput": round(throughput_component, 1),
            "error_trend": round(error_trend_component, 1),
        },
        "weights": weights,
    }


# ────────────────────────────────────────────────────────────────────
#  Badges & Streaks
# ────────────────────────────────────────────────────────────────────

_THROUGHPUT_TIERS = [
    (100_000, "Platinum", "#8e44ad"),
    (10_000, "Gold", "#d4a017"),
    (1_000, "Silver", "#7f8c8d"),
    (100, "Bronze", "#b87333"),
]


def _compute_achievements(
    daily_counts: list[dict[str, Any]],
    documents: dict[str, Any],
) -> dict[str, Any]:
    """Compute streak and badge data from existing snapshot data."""
    # --- Zero-error streak (consecutive days with 0 failures, newest first) ---
    streak_days = 0
    for day in reversed(daily_counts):
        if day["total"] == 0:
            continue  # skip days with no activity
        if day["failure"] == 0:
            streak_days += 1
        else:
            break

    # --- Throughput badge ---
    total_succeeded = documents["succeeded"]
    badge_name = None
    badge_color = None
    badge_next_name = None
    badge_next_target = None
    badge_progress_pct = 0.0
    for threshold, name, color in _THROUGHPUT_TIERS:
        if total_succeeded >= threshold:
            badge_name = name
            badge_color = color
            break
    # Find next tier
    for threshold, name, _color in reversed(_THROUGHPUT_TIERS):
        if total_succeeded < threshold:
            badge_next_name = name
            badge_next_target = threshold
            # progress toward this tier from previous tier boundary
            prev_boundary = 0
            for prev_thresh, _n, _c in _THROUGHPUT_TIERS:
                if prev_thresh < threshold and prev_thresh > prev_boundary:
                    prev_boundary = prev_thresh
            span = threshold - prev_boundary
            badge_progress_pct = round(
                ((total_succeeded - prev_boundary) / span) * 100, 1
            ) if span > 0 else 0.0
            break

    # --- Milestone markers ---
    milestones_reached: list[dict[str, Any]] = []
    for m in [10, 50, 100, 500, 1_000, 5_000, 10_000, 50_000, 100_000]:
        if total_succeeded >= m:
            milestones_reached.append({"threshold": m, "reached": True})

    return {
        "streak": {
            "zero_error_days": streak_days,
            "label": f"{streak_days} day{'s' if streak_days != 1 else ''} error-free",
        },
        "badge": {
            "name": badge_name,
            "color": badge_color,
            "total_succeeded": total_succeeded,
        },
        "next_tier": {
            "name": badge_next_name,
            "target": badge_next_target,
            "progress_pct": badge_progress_pct,
        },
        "milestones": milestones_reached,
    }


# ────────────────────────────────────────────────────────────────────
#  Hourly Throughput (24h window)
# ────────────────────────────────────────────────────────────────────

def _build_hourly_throughput(
    latest_events: list[dict[str, Any]],
    generated_at: datetime,
) -> list[dict[str, Any]]:
    """Build 24 hourly buckets with success/failure/incomplete counts."""
    buckets: list[dict[str, Any]] = []
    bucket_index: dict[str, dict[str, Any]] = {}

    for offset in range(24):
        hour_start = generated_at.replace(minute=0, second=0, microsecond=0) - timedelta(hours=23 - offset)
        label = hour_start.strftime("%H:%M")
        bucket = {"hour": label, "iso": hour_start.isoformat(), "success": 0, "failure": 0, "incomplete": 0, "total": 0}
        buckets.append(bucket)
        bucket_index[label] = bucket

    for event in latest_events:
        ts = event["timestamp_obj"]
        if ts is None:
            continue
        label = ts.astimezone().replace(minute=0, second=0, microsecond=0).strftime("%H:%M")
        if label in bucket_index:
            bucket = bucket_index[label]
            status = event["classified_status"]
            if status in ("success", "failure", "incomplete"):
                bucket[status] += 1
            bucket["total"] += 1

    return buckets


# ────────────────────────────────────────────────────────────────────
#  Predictive ETA
# ────────────────────────────────────────────────────────────────────

def _compute_queue_eta(
    queue_snapshot: dict[str, Any],
    average_completion_ms: int | None,
) -> dict[str, Any]:
    """Estimate time to clear the input backlog."""
    backlog = queue_snapshot["input_backlog_count"]
    if backlog == 0 or average_completion_ms is None or average_completion_ms == 0:
        return {"backlog": backlog, "eta_seconds": None, "eta_display": "n/a"}
    eta_seconds = round((backlog * average_completion_ms) / 1000)
    return {
        "backlog": backlog,
        "eta_seconds": eta_seconds,
        "eta_display": _format_seconds(eta_seconds),
    }


# ────────────────────────────────────────────────────────────────────
#  Daily Summary Report
# ────────────────────────────────────────────────────────────────────

def generate_daily_report(settings: Settings) -> Path:
    """Generate a daily HTML+JSON summary report and write to the log directory."""
    snapshot = build_stats_snapshot(settings, history_days=14, recent_limit=10)
    snapshot["refresh_seconds"] = 0  # no auto-refresh for report

    health = _compute_health_score(snapshot)
    achievements = _compute_achievements(snapshot["daily_counts"], snapshot["documents"])
    eta = _compute_queue_eta(snapshot["queues"], snapshot["documents"]["average_completion_ms"])

    report_date = datetime.now().astimezone().strftime("%Y-%m-%d")
    report_dir = settings.log_path / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    # JSON report
    report_data = {
        "report_date": report_date,
        "generated_at": snapshot["generated_at"],
        "health_score": health,
        "achievements": achievements,
        "queue_eta": eta,
        "documents": snapshot["documents"],
        "last_24_hours": snapshot["last_24_hours"],
        "daily_counts": snapshot["daily_counts"],
        "failure_reasons": snapshot["failure_reasons"],
        "service": snapshot["service"],
    }
    json_path = report_dir / f"daily-report-{report_date}.json"
    from app.logging_utils import write_json_atomically
    write_json_atomically(json_path, report_data)

    # HTML report
    html_path = report_dir / f"daily-report-{report_date}.html"
    html_content = _render_daily_report_html(report_data)
    html_path.write_text(html_content, encoding="utf-8")

    return html_path


def _render_daily_report_html(report: dict[str, Any]) -> str:
    """Render a self-contained HTML daily summary email/report."""
    h = report["health_score"]
    d = report["documents"]
    last24 = report["last_24_hours"]
    ach = report["achievements"]
    eta = report["queue_eta"]
    failures = report["failure_reasons"]

    grade_colors = {"A": "#1a7a54", "B": "#2472a4", "C": "#b8860b", "D": "#c0392b", "F": "#8b0000"}
    grade_color = grade_colors.get(h["grade"], "#68737d")

    failure_rows = ""
    for item in failures[:5]:
        failure_rows += f'<tr><td style="padding:6px 12px;border-bottom:1px solid #eee;">{_escape(item["reason"])}</td><td style="padding:6px 12px;border-bottom:1px solid #eee;text-align:right;font-weight:600;">{item["count"]}</td></tr>'
    if not failure_rows:
        failure_rows = '<tr><td colspan="2" style="padding:12px;color:#999;text-align:center;">No failures</td></tr>'

    daily_bars = ""
    max_total = max((day["total"] for day in report["daily_counts"]), default=1) or 1
    for day in report["daily_counts"][-7:]:
        pct = min(100, round((day["total"] / max_total) * 100))
        daily_bars += f'<div style="display:flex;align-items:center;gap:8px;margin:4px 0;"><span style="width:72px;font-size:12px;color:#888;">{_escape(day["date"])}</span><div style="flex:1;height:16px;background:#f0f0f0;border-radius:8px;overflow:hidden;"><div style="width:{pct}%;height:100%;background:linear-gradient(90deg,#34c47c,#1a7a54);border-radius:8px;"></div></div><span style="width:36px;text-align:right;font-size:12px;font-weight:600;">{day["total"]}</span></div>'

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Barcode Buddy Daily Report — {_escape(report["report_date"])}</title></head>
<body style="margin:0;padding:0;font-family:'Segoe UI',system-ui,sans-serif;background:#f5f5f5;">
<div style="max-width:640px;margin:24px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);">

  <div style="background:linear-gradient(135deg,#1e2530,#2c3e50);padding:28px 32px;color:#fff;">
    <h1 style="margin:0 0 4px;font-size:22px;">Barcode Buddy Daily Report</h1>
    <p style="margin:0;font-size:13px;opacity:0.7;">{_escape(report["report_date"])} &mdash; Generated {_escape(report["generated_at"][:19])}</p>
  </div>

  <div style="padding:24px 32px;">
    <div style="display:flex;gap:16px;margin-bottom:24px;">
      <div style="flex:1;padding:20px;border-radius:12px;background:#f8f8f8;text-align:center;">
        <div style="font-size:42px;font-weight:800;color:{grade_color};">{h["grade"]}</div>
        <div style="font-size:28px;font-weight:700;color:#333;">{h["score"]}</div>
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:#999;margin-top:4px;">Health Score</div>
      </div>
      <div style="flex:1;padding:20px;border-radius:12px;background:#f0faf5;text-align:center;border:1px solid #d4edda;">
        <div style="font-size:28px;font-weight:700;color:#1a7a54;">{d["succeeded"]}</div>
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:#999;margin-top:4px;">Total Succeeded</div>
        <div style="font-size:13px;color:#1a7a54;margin-top:6px;font-weight:600;">{_format_percentage(d["success_rate"])}</div>
      </div>
      <div style="flex:1;padding:20px;border-radius:12px;background:#fff5f5;text-align:center;border:1px solid #f5c6cb;">
        <div style="font-size:28px;font-weight:700;color:#c0392b;">{d["failed"]}</div>
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:#999;margin-top:4px;">Total Failed</div>
      </div>
    </div>

    <h3 style="font-size:14px;text-transform:uppercase;letter-spacing:0.08em;color:#888;margin:0 0 12px;">Last 24 Hours</h3>
    <div style="display:flex;gap:12px;margin-bottom:24px;">
      <div style="flex:1;text-align:center;padding:12px;border-radius:10px;background:#edf7ff;"><strong style="font-size:20px;color:#2472a4;">{last24["documents"]}</strong><div style="font-size:11px;color:#999;margin-top:2px;">Seen</div></div>
      <div style="flex:1;text-align:center;padding:12px;border-radius:10px;background:#f0faf5;"><strong style="font-size:20px;color:#1a7a54;">{last24["succeeded"]}</strong><div style="font-size:11px;color:#999;margin-top:2px;">Succeeded</div></div>
      <div style="flex:1;text-align:center;padding:12px;border-radius:10px;background:#fff5f5;"><strong style="font-size:20px;color:#c0392b;">{last24["failed"]}</strong><div style="font-size:11px;color:#999;margin-top:2px;">Failed</div></div>
    </div>

    <h3 style="font-size:14px;text-transform:uppercase;letter-spacing:0.08em;color:#888;margin:0 0 12px;">Achievements</h3>
    <div style="display:flex;gap:12px;margin-bottom:24px;">
      <div style="flex:1;padding:14px;border-radius:10px;background:#f8f8f8;text-align:center;">
        <div style="font-size:24px;font-weight:700;">{ach["streak"]["zero_error_days"]}</div>
        <div style="font-size:11px;color:#999;">Error-Free Streak</div>
      </div>
      <div style="flex:1;padding:14px;border-radius:10px;background:#f8f8f8;text-align:center;">
        <div style="font-size:18px;font-weight:700;color:{_escape(ach['badge']['color'] or '#999')};">{_escape(ach["badge"]["name"] or "—")}</div>
        <div style="font-size:11px;color:#999;">Throughput Badge</div>
      </div>
      <div style="flex:1;padding:14px;border-radius:10px;background:#f8f8f8;text-align:center;">
        <div style="font-size:18px;font-weight:700;">{_escape(eta["eta_display"])}</div>
        <div style="font-size:11px;color:#999;">Queue ETA</div>
      </div>
    </div>

    <h3 style="font-size:14px;text-transform:uppercase;letter-spacing:0.08em;color:#888;margin:0 0 12px;">7-Day Volume</h3>
    <div style="margin-bottom:24px;">{daily_bars}</div>

    <h3 style="font-size:14px;text-transform:uppercase;letter-spacing:0.08em;color:#888;margin:0 0 12px;">Top Failure Reasons</h3>
    <table style="width:100%;border-collapse:collapse;margin-bottom:16px;font-size:13px;">
      <thead><tr><th style="text-align:left;padding:6px 12px;border-bottom:2px solid #eee;color:#999;font-size:11px;text-transform:uppercase;">Reason</th><th style="text-align:right;padding:6px 12px;border-bottom:2px solid #eee;color:#999;font-size:11px;text-transform:uppercase;">Count</th></tr></thead>
      <tbody>{failure_rows}</tbody>
    </table>
  </div>

  <div style="padding:16px 32px;background:#f8f8f8;border-top:1px solid #eee;font-size:11px;color:#aaa;text-align:center;">
    Barcode Buddy &mdash; Automated Daily Report
  </div>
</div>
</body></html>"""
