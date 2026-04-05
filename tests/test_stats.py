from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings, ensure_runtime_directories
from app.stats import build_stats_snapshot, render_stats_html


class BarcodeBuddyStatsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.root = Path(self._tempdir.name)
        self.settings = Settings(
            input_path=self.root / "input",
            processing_path=self.root / "processing",
            output_path=self.root / "output",
            rejected_path=self.root / "rejected",
            log_path=self.root / "logs",
            barcode_types=("code128", "auto"),
            barcode_value_patterns=(),
            scan_all_pages=True,
            duplicate_handling="timestamp",
            file_stability_delay_ms=2000,
            max_pages_scan=50,
            poll_interval_ms=500,
            barcode_scan_dpi=300,
            barcode_upscale_factor=1.0,
        )
        ensure_runtime_directories(self.settings)

    def test_build_stats_snapshot_uses_latest_event_per_processing_id(self) -> None:
        self._write_log_lines(
            [
                {
                    "timestamp": "2026-04-03T10:00:00+00:00",
                    "processing_id": "proc-1",
                    "stage": "processing",
                    "status": "success",
                    "duration_ms": 120,
                    "original_filename": "packing-slip.pdf",
                },
                {
                    "timestamp": "2026-04-03T10:00:01+00:00",
                    "processing_id": "proc-1",
                    "stage": "output",
                    "status": "success",
                    "duration_ms": 480,
                    "original_filename": "packing-slip.pdf",
                    "barcode": "PO-100",
                },
                {
                    "timestamp": "2026-04-03T10:05:00+00:00",
                    "processing_id": "proc-2",
                    "stage": "processing",
                    "status": "failure",
                    "duration_ms": 320,
                    "original_filename": "damaged.pdf",
                    "reason": "CORRUPT_FILE",
                    "error_code": "CORRUPT_FILE",
                },
                {
                    "timestamp": "2026-04-03T10:10:00+00:00",
                    "processing_id": "proc-3",
                    "stage": "processing",
                    "status": "success",
                    "duration_ms": 210,
                    "original_filename": "in-flight.pdf",
                },
            ]
        )

        snapshot = build_stats_snapshot(
            self.settings,
            now=datetime(2026, 4, 3, 12, 0, 0, tzinfo=timezone.utc),
            history_days=3,
            recent_limit=10,
        )

        self.assertEqual(snapshot["documents"]["seen"], 3)
        self.assertEqual(snapshot["documents"]["completed"], 2)
        self.assertEqual(snapshot["documents"]["succeeded"], 1)
        self.assertEqual(snapshot["documents"]["failed"], 1)
        self.assertEqual(snapshot["documents"]["incomplete"], 1)
        self.assertEqual(snapshot["documents"]["success_rate"], 50.0)
        self.assertEqual(snapshot["documents"]["average_completion_ms"], 400)
        self.assertEqual(
            snapshot["recent_documents"][0]["processing_id"],
            "proc-3",
        )
        self.assertEqual(
            snapshot["recent_documents"][1]["status"],
            "failure",
        )
        self.assertEqual(
            snapshot["failure_reasons"],
            [{"reason": "CORRUPT_FILE", "count": 1}],
        )
        self.assertEqual(snapshot["latency_ms"]["p95"], 320)

    def test_build_stats_snapshot_separates_service_events_and_reports_health(self) -> None:
        (self.settings.log_path / ".service.lock").write_text("locked\n", encoding="utf-8")
        queued = self.settings.input_path / "queued.pdf"
        queued.write_text("queued", encoding="utf-8")
        journal_dir = self.settings.processing_path / ".journal"
        journal_dir.mkdir(parents=True, exist_ok=True)
        (journal_dir / "proc-journal.json").write_text("{}", encoding="utf-8")

        self._write_log_lines(
            [
                {
                    "timestamp": "2026-04-03T11:59:00+00:00",
                    "processing_id": "service-1",
                    "stage": "service",
                    "status": "success",
                    "duration_ms": 0,
                    "original_filename": "(service lifecycle)",
                    "event_type": "startup",
                },
                {
                    "timestamp": "2026-04-03T11:59:45+00:00",
                    "processing_id": "service-1",
                    "stage": "service",
                    "status": "success",
                    "duration_ms": 0,
                    "original_filename": "(service lifecycle)",
                    "event_type": "heartbeat",
                },
                {
                    "timestamp": "2026-04-03T11:59:50+00:00",
                    "processing_id": "proc-1",
                    "stage": "output",
                    "status": "success",
                    "duration_ms": 480,
                    "original_filename": "packing-slip.pdf",
                    "barcode": "PO-100",
                },
            ]
        )

        snapshot = build_stats_snapshot(
            self.settings,
            now=datetime(2026, 4, 3, 12, 0, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(snapshot["documents"]["seen"], 1)
        self.assertEqual(snapshot["service"]["status"], "healthy")
        self.assertEqual(snapshot["service"]["startups_last_24h"], 1)
        self.assertEqual(snapshot["queues"]["input_backlog_count"], 1)
        self.assertEqual(snapshot["queues"]["journal_count"], 1)
        self.assertEqual(snapshot["stage_counts"][0]["stage"], "service")

    def test_build_stats_snapshot_reads_rotated_logs(self) -> None:
        archive_path = self.settings.log_file.with_name("processing_log.2026-04-02.jsonl")
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        archive_lines = [
            {
                "timestamp": "2026-04-02T23:59:40+00:00",
                "processing_id": "service-1",
                "stage": "service",
                "status": "success",
                "duration_ms": 0,
                "original_filename": "(service lifecycle)",
                "event_type": "startup",
            },
            {
                "timestamp": "2026-04-02T23:59:45+00:00",
                "processing_id": "proc-1",
                "stage": "processing",
                "status": "success",
                "duration_ms": 120,
                "original_filename": "archived.pdf",
            },
        ]
        archive_path.write_text(
            "\n".join(json.dumps(line, ensure_ascii=True) for line in archive_lines) + "\n",
            encoding="utf-8",
        )
        self._write_log_lines(
            [
                {
                    "timestamp": "2026-04-03T00:00:01+00:00",
                    "processing_id": "service-1",
                    "stage": "service",
                    "status": "success",
                    "duration_ms": 0,
                    "original_filename": "(service lifecycle)",
                    "event_type": "heartbeat",
                },
                {
                    "timestamp": "2026-04-03T00:00:05+00:00",
                    "processing_id": "proc-1",
                    "stage": "output",
                    "status": "success",
                    "duration_ms": 450,
                    "original_filename": "archived.pdf",
                    "barcode": "ARCHIVE_OK",
                },
            ]
        )

        snapshot = build_stats_snapshot(
            self.settings,
            now=datetime(2026, 4, 3, 0, 0, 10, tzinfo=timezone.utc),
        )

        self.assertEqual(snapshot["log"]["files"], 2)
        self.assertEqual(snapshot["log"]["archived_files"], 1)
        self.assertEqual(snapshot["log"]["lines"], 4)
        self.assertEqual(snapshot["documents"]["seen"], 1)
        self.assertEqual(snapshot["documents"]["succeeded"], 1)
        self.assertEqual(snapshot["service"]["last_event_type"], "heartbeat")
        self.assertEqual(snapshot["recent_documents"][0]["barcode"], "ARCHIVE_OK")

    def test_build_stats_snapshot_classifies_finalized_rejection_recovery_as_failure(self) -> None:
        self._write_log_lines(
            [
                {
                    "timestamp": "2026-04-03T10:00:00+00:00",
                    "processing_id": "proc-1",
                    "stage": "validation",
                    "status": "success",
                    "duration_ms": 0,
                    "original_filename": "recovered.pdf",
                    "reason": "INVALID_BARCODE_FORMAT",
                    "error_code": "INVALID_BARCODE_FORMAT",
                    "recovery_action": "finalized_rejection_recovery",
                    "rejected_path": str(self.settings.rejected_path / "recovered.pdf"),
                }
            ]
        )

        snapshot = build_stats_snapshot(
            self.settings,
            now=datetime(2026, 4, 3, 12, 0, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(snapshot["documents"]["failed"], 1)
        self.assertEqual(snapshot["recent_documents"][0]["status"], "failure")
        self.assertEqual(
            snapshot["failure_reasons"],
            [{"reason": "INVALID_BARCODE_FORMAT", "count": 1}],
        )

    def test_build_stats_snapshot_ignores_invalid_lines(self) -> None:
        self.settings.log_file.write_text(
            "\n".join(
                [
                    "",
                    "{not-json}",
                    json.dumps({"stage": "processing", "status": "success"}),
                    json.dumps(
                        {
                            "timestamp": "2026-04-03T10:00:00+00:00",
                            "processing_id": "proc-1",
                            "stage": "output",
                            "status": "success",
                            "duration_ms": 250,
                            "original_filename": "ok.pdf",
                        }
                    ),
                    "",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        snapshot = build_stats_snapshot(
            self.settings,
            now=datetime(2026, 4, 3, 12, 0, 0, tzinfo=timezone.utc),
        )

        self.assertTrue(snapshot["log"]["exists"])
        self.assertEqual(snapshot["log"]["lines"], 5)
        self.assertEqual(snapshot["log"]["ignored_lines"], 4)
        self.assertEqual(snapshot["documents"]["seen"], 1)
        self.assertEqual(snapshot["documents"]["succeeded"], 1)

    def test_render_stats_html_escapes_recent_document_fields(self) -> None:
        snapshot = {
            "generated_at": "2026-04-03T12:00:00+00:00",
            "refresh_seconds": 15,
            "paths": {
                "input": str(self.settings.input_path),
                "processing": str(self.settings.processing_path),
                "output": str(self.settings.output_path),
                "rejected": str(self.settings.rejected_path),
                "log_file": str(self.settings.log_file),
                "log_path": str(self.settings.log_path),
            },
            "log": {
                "exists": True,
                "active_exists": True,
                "files": 1,
                "archived_files": 0,
                "lines": 1,
                "ignored_lines": 0,
            },
            "service": {
                "status": "healthy",
                "last_event_type": "heartbeat",
                "last_event_at": "2026-04-03T12:00:00+00:00",
                "last_heartbeat_at": "2026-04-03T12:00:00+00:00",
                "heartbeat_age_seconds": 5,
                "lock_exists": True,
                "startups_last_24h": 1,
                "shutdowns_last_24h": 0,
                "event_count": 2,
            },
            "queues": {
                "input_backlog_count": 0,
                "oldest_input_age_seconds": None,
                "processing_count": 0,
                "journal_count": 0,
            },
            "documents": {
                "seen": 1,
                "completed": 1,
                "succeeded": 1,
                "failed": 0,
                "incomplete": 0,
                "success_rate": 100.0,
                "average_completion_ms": 300,
                "last_processed_at": "2026-04-03T12:00:00+00:00",
            },
            "latency_ms": {
                "p50": 300,
                "p95": 300,
                "p99": 300,
            },
            "last_24_hours": {
                "documents": 1,
                "completed": 1,
                "succeeded": 1,
                "failed": 0,
                "incomplete": 0,
            },
            "daily_counts": [
                {
                    "date": "2026-04-03",
                    "success": 1,
                    "failure": 0,
                    "incomplete": 0,
                    "total": 1,
                }
            ],
            "failure_reasons": [],
            "stage_counts": [{"stage": "output", "count": 1}],
            "recent_documents": [
                {
                    "processing_id": "proc-1",
                    "timestamp": "2026-04-03T12:00:00+00:00",
                    "stage": "output",
                    "status": "success",
                    "error_code": None,
                    "original_filename": "<packing>.pdf",
                    "duration_ms": 300,
                    "reason": None,
                    "barcode": "PO-100",
                    "barcode_format": "code128",
                    "output_path": str(self.settings.output_path / "PO-100.pdf"),
                    "rejected_path": None,
                    "recovery_action": None,
                    "pages": 1,
                }
            ],
        }

        html = render_stats_html(snapshot)

        self.assertIn("BarcodeBuddy", html)
        self.assertIn("&lt;packing&gt;.pdf", html)
        self.assertIn("PO-100", html)
        self.assertIn("Active Log File", html)
        self.assertIn("Log Directory", html)
        self.assertNotIn("<packing>.pdf", html)

    def _write_log_lines(self, payloads: list[dict[str, object]]) -> None:
        self.settings.log_file.parent.mkdir(parents=True, exist_ok=True)
        with self.settings.log_file.open("w", encoding="utf-8") as handle:
            for payload in payloads:
                handle.write(json.dumps(payload, ensure_ascii=True))
                handle.write("\n")


if __name__ == "__main__":
    unittest.main()
