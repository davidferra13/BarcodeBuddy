from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import fitz
from PIL import Image

from app.barcode import BarcodeCandidate
from app.config import Settings, ensure_runtime_directories
from app.processor import BarcodeBuddyService


class BarcodeBuddyRuntimeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.root = Path(self._tempdir.name)
        self.fixed_now = datetime(2026, 4, 3, 15, 0, 0, tzinfo=timezone.utc)

    def test_supported_inputs_are_written_as_pdfs(self) -> None:
        fixtures = [
            ("sample.png", "png", "PNG_OK"),
            ("sample.jpg", "jpeg", "JPG_OK"),
            ("sample.jpeg", "jpeg", "JPEG_OK"),
            ("sample.pdf", "pdf", "PDF_OK"),
        ]

        for filename, kind, barcode in fixtures:
            with self.subTest(filename=filename):
                service, settings = self._make_service("supported")
                source_path = self._make_source_file(settings.input_path / filename, kind)
                service.scanner.scan_image_candidates = Mock(
                    return_value=[self._candidate(barcode)]
                )

                result = service.process_file(source_path)

                self.assertEqual(result.status, "success")
                self.assertEqual(result.stage, "output")
                self.assertEqual(result.barcode, barcode)
                self.assertIsNotNone(result.output_path)
                self.assertEqual(result.raw_detection_count, 1)
                self.assertEqual(result.candidate_values, (barcode,))
                self.assertEqual(result.eligible_candidate_values, (barcode,))
                self.assertEqual(result.page_one_eligible_values, (barcode,))
                assert result.output_path is not None
                self.assertTrue(result.output_path.exists())
                self.assertEqual(result.output_path.suffix.lower(), ".pdf")

    def test_success_log_events_include_runtime_metadata(self) -> None:
        service, settings = self._make_service("success-metadata")
        source_path = self._make_source_file(settings.input_path / "meta.png", "png")
        service.scanner.scan_image_candidates = Mock(
            return_value=[self._candidate("META_OK")]
        )

        result = service.process_file(source_path)

        self.assertEqual(result.status, "success")
        events = self._read_jsonl(settings.log_file)
        self.assertGreaterEqual(len(events), 1)
        for event in events:
            self.assertEqual(event["schema_version"], "1.0")
            self.assertEqual(event["workflow"], "success_metadata")
            self.assertEqual(event["host"], service.host)
            self.assertEqual(event["instance_id"], service.instance_id)
            self.assertEqual(event["config_version"], "test-config")
            self.assertIsNone(event["error_code"])

    def test_barcode_not_found_rejects_file(self) -> None:
        service, settings = self._make_service("barcode-not-found")
        source_path = self._make_source_file(settings.input_path / "missing.pdf", "pdf")
        service.scanner.scan_image_candidates = Mock(return_value=[])

        result = service.process_file(source_path)

        self.assertEqual(result.status, "failure")
        self.assertEqual(result.reason, "BARCODE_NOT_FOUND")
        self.assertEqual(result.stage, "processing")
        self.assertEqual(result.raw_detection_count, 0)
        self.assertEqual(result.candidate_values, ())

    def test_business_rule_mismatch_rejects_as_invalid_barcode_format(self) -> None:
        service, settings = self._make_service(
            "pattern-mismatch",
            barcode_value_patterns=(r"^PO-\d+$",),
        )
        source_path = self._make_source_file(settings.input_path / "mismatch.png", "png")
        service.scanner.scan_image_candidates = Mock(
            return_value=[
                self._candidate("SHIP-12345", matches_business_rule=False, area=400.0),
                self._candidate("BOX-777", matches_business_rule=False, area=300.0),
            ]
        )

        result = service.process_file(source_path)

        self.assertEqual(result.status, "failure")
        self.assertEqual(result.reason, "INVALID_BARCODE_FORMAT")
        self.assertEqual(result.stage, "validation")
        self.assertEqual(result.barcode, "SHIP-12345")
        self.assertEqual(result.candidate_values, ("SHIP-12345", "BOX-777"))
        self.assertEqual(result.eligible_candidate_values, ())

        assert result.rejected_path is not None
        sidecar = self._read_json(result.rejected_path.with_suffix(".meta.json"))
        self.assertEqual(sidecar["stage"], "validation")
        self.assertEqual(sidecar["barcode"], "SHIP-12345")
        self.assertEqual(sidecar["eligible_candidate_values"], [])
        self.assertEqual(sidecar["schema_version"], "1.0")
        self.assertEqual(sidecar["workflow"], "pattern_mismatch")
        self.assertEqual(sidecar["host"], service.host)
        self.assertEqual(sidecar["instance_id"], service.instance_id)
        self.assertEqual(sidecar["config_version"], "test-config")
        self.assertEqual(sidecar["error_code"], "INVALID_BARCODE_FORMAT")

        log_events = self._read_jsonl(settings.log_file)
        self.assertEqual(log_events[-1]["error_code"], "INVALID_BARCODE_FORMAT")

    def test_invalid_barcode_format_rejects_in_validation(self) -> None:
        service, settings = self._make_service("invalid-format")
        source_path = self._make_source_file(settings.input_path / "invalid.png", "png")
        service.scanner.scan_image_candidates = Mock(
            return_value=[self._candidate("BAD 123")]
        )

        result = service.process_file(source_path)

        self.assertEqual(result.status, "failure")
        self.assertEqual(result.reason, "INVALID_BARCODE_FORMAT")
        self.assertEqual(result.stage, "validation")
        self.assertEqual(result.barcode, "BAD 123")

    def test_multiple_eligible_barcodes_resolve_deterministically(self) -> None:
        service, settings = self._make_service(
            "ambiguous-across-pages",
            barcode_value_patterns=(r"^PO-\d+$",),
        )
        source_path = self._make_source_file(settings.input_path / "ambiguous.pdf", "pdf", pages=2)
        service.scanner.scan_image_candidates = Mock(
            side_effect=[
                [self._candidate("PO-100", matches_business_rule=True, area=100.0)],
                [self._candidate("PO-200", matches_business_rule=True, area=400.0)],
            ]
        )

        result = service.process_file(source_path)

        self.assertEqual(result.status, "success")
        self.assertEqual(result.stage, "output")
        self.assertEqual(result.barcode, "PO-200")
        self.assertEqual(result.eligible_candidate_values, ("PO-100", "PO-200"))
        self.assertEqual(result.page_one_eligible_values, ("PO-100",))
    def test_page_one_eligible_value_wins_when_later_pages_repeat_same_value(self) -> None:
        service, settings = self._make_service(
            "page-one-authority",
            barcode_value_patterns=(r"^PO-\d+$",),
        )
        source_path = self._make_source_file(settings.input_path / "stable.pdf", "pdf", pages=2)
        service.scanner.scan_image_candidates = Mock(
            side_effect=[
                [self._candidate("PO-100", matches_business_rule=True)],
                [self._candidate("PO-100", matches_business_rule=True)],
            ]
        )

        result = service.process_file(source_path)

        self.assertEqual(result.status, "success")
        self.assertEqual(result.stage, "output")
        self.assertEqual(result.barcode, "PO-100")
        self.assertEqual(result.page_one_eligible_values, ("PO-100",))

    def test_highest_priority_candidate_wins_without_business_rules(self) -> None:
        service, settings = self._make_service("highest-priority")
        source_path = self._make_source_file(settings.input_path / "multi-page.pdf", "pdf", pages=2)
        service.scanner.scan_image_candidates = Mock(
            side_effect=[
                [self._candidate("BOX-001", area=100.0, scan_order=(0.0, 0.0, 0))],
                [self._candidate("BOX-999", area=400.0, scan_order=(20.0, 20.0, 0))],
            ]
        )

        result = service.process_file(source_path)

        self.assertEqual(result.status, "success")
        self.assertEqual(result.barcode, "BOX-999")
        self.assertEqual(result.candidate_values, ("BOX-001", "BOX-999"))

    def test_matching_barcode_on_later_page_beats_larger_non_matching_barcode(self) -> None:
        service, settings = self._make_service(
            "matching-later-page",
            barcode_value_patterns=(r"^PO-\d+$",),
        )
        source_path = self._make_source_file(settings.input_path / "matched.pdf", "pdf", pages=2)
        service.scanner.scan_image_candidates = Mock(
            side_effect=[
                [self._candidate("SHIP-12345", matches_business_rule=False, area=500.0)],
                [self._candidate("PO-100", matches_business_rule=True, area=100.0)],
            ]
        )

        result = service.process_file(source_path)

        self.assertEqual(result.status, "success")
        self.assertEqual(result.stage, "output")
        self.assertEqual(result.barcode, "PO-100")
        self.assertEqual(result.eligible_candidate_values, ("PO-100",))

    def test_duplicate_reject_moves_file_to_rejected_and_writes_sidecar(self) -> None:
        service, settings = self._make_service(
            "duplicate-reject",
            duplicate_handling="reject",
        )
        barcode = "DUPLICATE_OK"
        source_path = self._make_source_file(settings.input_path / "duplicate.png", "png")
        service.scanner.scan_image_candidates = Mock(
            return_value=[self._candidate(barcode, orientation=90)]
        )

        output_dir = settings.output_path / self.fixed_now.strftime("%Y") / self.fixed_now.strftime("%m")
        output_dir.mkdir(parents=True, exist_ok=True)
        self._make_pdf(output_dir / f"{barcode}.pdf")

        result = service.process_file(source_path)

        self.assertEqual(result.status, "failure")
        self.assertEqual(result.reason, "DUPLICATE_FILE")
        assert result.rejected_path is not None
        sidecar = self._read_json(result.rejected_path.with_suffix(".meta.json"))
        self.assertEqual(sidecar["stage"], "output")
        self.assertEqual(sidecar["barcode"], barcode)

    def test_duplicate_timestamp_writes_unique_pdf(self) -> None:
        service, settings = self._make_service(
            "duplicate-timestamp",
            duplicate_handling="timestamp",
        )
        source_path = self._make_source_file(settings.input_path / "duplicate.jpg", "jpeg")
        service.scanner.scan_image_candidates = Mock(return_value=[self._candidate("TIMESTAMP_OK")])

        output_dir = settings.output_path / self.fixed_now.strftime("%Y") / self.fixed_now.strftime("%m")
        output_dir.mkdir(parents=True, exist_ok=True)
        self._make_pdf(output_dir / "TIMESTAMP_OK.pdf")

        result = service.process_file(source_path)

        self.assertEqual(result.status, "success")
        assert result.output_path is not None
        self.assertEqual(result.output_path.name, "TIMESTAMP_OK_20260403_150000.pdf")

    def test_corrupt_and_unsupported_inputs_reject(self) -> None:
        service, settings = self._make_service("bad-inputs")

        corrupt_pdf = settings.input_path / "corrupt.pdf"
        corrupt_pdf.parent.mkdir(parents=True, exist_ok=True)
        corrupt_pdf.write_bytes(b"%PDF-1.7\n1 0 obj\n<<\n")
        self.assertEqual(service.process_file(corrupt_pdf).reason, "CORRUPT_FILE")

        spoofed_pdf = settings.input_path / "spoofed.pdf"
        self._make_image(spoofed_pdf, "PNG")
        self.assertEqual(service.process_file(spoofed_pdf).reason, "UNSUPPORTED_FORMAT")

        unsupported = settings.input_path / "notes.txt"
        unsupported.write_text("unsupported", encoding="utf-8")
        self.assertEqual(service.process_file(unsupported).reason, "UNSUPPORTED_FORMAT")

    def test_recover_processing_files_moves_stranded_files_back_to_input(self) -> None:
        service, settings = self._make_service("recovery")
        stranded = self._make_source_file(settings.processing_path / "scan 1.png", "png")

        service.recover_processing_files()

        self.assertFalse(stranded.exists())
        recovered_names = sorted(path.name for path in settings.input_path.iterdir())
        self.assertTrue(any(name.startswith("scan_1") for name in recovered_names))

    def test_recover_processing_files_uses_journal_for_claimed_file(self) -> None:
        service, settings = self._make_service("journal-requeue")
        stranded = self._make_source_file(settings.processing_path / "scan 2.png", "png")
        context = service._new_context("scan 2.png")
        service._write_journal(
            context,
            processing_path=stranded,
            state="claimed",
            stage="processing",
        )

        service.recover_processing_files()

        self.assertFalse(stranded.exists())
        self.assertFalse(service._journal_path(context.processing_id).exists())
        recovery_events = [
            event for event in self._read_jsonl(settings.log_file)
            if event.get("recovery_action") == "requeued_processing_file"
        ]
        self.assertEqual(len(recovery_events), 1)
        self.assertEqual(recovery_events[0]["journal_state"], "claimed")
        self.assertEqual(recovery_events[0]["status"], "success")

    def test_recover_processing_files_finalizes_pending_output_journal(self) -> None:
        service, settings = self._make_service("journal-output")
        context = service._new_context("finished.pdf")
        output_path = settings.output_path / self.fixed_now.strftime("%Y") / self.fixed_now.strftime("%m") / "FINISHED_OK.pdf"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._make_pdf(output_path)
        processing_path = settings.processing_path / "finished.processing.pdf"
        service._write_journal(
            context,
            processing_path=processing_path,
            state="pending_output",
            stage="output",
            barcode="FINISHED_OK",
            output_path=output_path,
        )

        service.recover_processing_files()

        self.assertFalse(service._journal_path(context.processing_id).exists())
        recovery_events = [
            event for event in self._read_jsonl(settings.log_file)
            if event.get("recovery_action") == "finalized_output_recovery"
        ]
        self.assertEqual(len(recovery_events), 1)
        self.assertEqual(recovery_events[0]["stage"], "output")
        self.assertEqual(recovery_events[0]["status"], "success")
        self.assertEqual(Path(str(recovery_events[0]["output_path"])).name, "FINISHED_OK.pdf")

    def test_recover_processing_files_finalizes_pending_rejection_journal(self) -> None:
        service, settings = self._make_service("journal-rejection")
        context = service._new_context("failed.pdf")
        rejected_path = settings.rejected_path / "failed_rejected.pdf"
        self._make_pdf(rejected_path)
        processing_path = settings.processing_path / "failed.processing.pdf"
        service._write_journal(
            context,
            processing_path=processing_path,
            state="pending_rejection",
            stage="validation",
            barcode="FAILED_OK",
            reason="INVALID_BARCODE_FORMAT",
            rejected_path=rejected_path,
        )

        service.recover_processing_files()

        self.assertFalse(service._journal_path(context.processing_id).exists())
        recovery_events = [
            event for event in self._read_jsonl(settings.log_file)
            if event.get("recovery_action") == "finalized_rejection_recovery"
        ]
        self.assertEqual(len(recovery_events), 1)
        self.assertEqual(recovery_events[0]["stage"], "validation")
        self.assertEqual(recovery_events[0]["status"], "success")
        self.assertEqual(Path(str(recovery_events[0]["rejected_path"])).name, "failed_rejected.pdf")

    def test_file_becomes_ready_after_four_stable_checks(self) -> None:
        service, settings = self._make_service("stability-ready")
        source_path = self._make_source_file(settings.input_path / "stable.png", "png")

        with patch("app.processor.time.monotonic", side_effect=[0.0, 0.5, 1.0, 1.5, 2.0]):
            self.assertEqual(service._stability_state(source_path), "waiting")
            self.assertEqual(service._stability_state(source_path), "waiting")
            self.assertEqual(service._stability_state(source_path), "waiting")
            self.assertEqual(service._stability_state(source_path), "waiting")
            self.assertEqual(service._stability_state(source_path), "ready")

    def test_file_that_keeps_changing_for_ten_seconds_is_locked(self) -> None:
        service, settings = self._make_service("stability-locked")
        source_path = settings.input_path / "growing.pdf"
        source_path.write_bytes(b"a")

        monotonic_values = [0.0] + [step * 0.5 for step in range(1, 21)]
        with patch("app.processor.time.monotonic", side_effect=monotonic_values):
            self.assertEqual(service._stability_state(source_path), "waiting")
            state = "waiting"
            for index in range(1, 21):
                source_path.write_bytes(b"a" * (index + 1))
                state = service._stability_state(source_path)
                if state == "file_locked":
                    break

        self.assertEqual(state, "file_locked")

    def _make_service(
        self,
        case_name: str,
        *,
        duplicate_handling: str = "timestamp",
        barcode_value_patterns: tuple[str, ...] = (),
        scan_all_pages: bool = True,
    ) -> tuple[BarcodeBuddyService, Settings]:
        case_root = self.root / case_name
        settings = Settings(
            input_path=case_root / "input",
            processing_path=case_root / "processing",
            output_path=case_root / "output",
            rejected_path=case_root / "rejected",
            log_path=case_root / "logs",
            barcode_types=("code128", "auto"),
            barcode_value_patterns=barcode_value_patterns,
            scan_all_pages=scan_all_pages,
            duplicate_handling=duplicate_handling,
            file_stability_delay_ms=2000,
            max_pages_scan=50,
            poll_interval_ms=500,
            barcode_scan_dpi=300,
            barcode_upscale_factor=1.0,
            workflow_key=case_name.replace("-", "_"),
            config_version="test-config",
        )
        ensure_runtime_directories(settings)
        service = BarcodeBuddyService(settings)
        service._now = Mock(return_value=self.fixed_now)
        return service, settings

    def _make_source_file(self, path: Path, kind: str, *, pages: int = 1) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        if kind == "png":
            self._make_image(path, "PNG")
        elif kind == "jpeg":
            self._make_image(path, "JPEG")
        elif kind == "pdf":
            self._make_pdf(path, pages=pages)
        else:
            raise ValueError(f"Unsupported fixture kind: {kind}")
        return path

    def _make_image(self, path: Path, image_format: str) -> None:
        image = Image.new("RGB", (64, 32), "white")
        image.save(path, format=image_format)

    def _make_pdf(self, path: Path, *, pages: int = 1) -> None:
        document = fitz.open()
        try:
            for _ in range(pages):
                document.new_page(width=200, height=100)
            document.save(path)
        finally:
            document.close()

    def _candidate(
        self,
        text: str,
        *,
        matches_business_rule: bool = True,
        format_name: str = "code128",
        orientation: int = 0,
        area: float = 100.0,
        scan_order: tuple[float, float, int] = (0.0, 0.0, 0),
    ) -> BarcodeCandidate:
        normalized = text.strip()
        return BarcodeCandidate(
            text=normalized,
            normalized_text=normalized,
            format_name=format_name,
            orientation_degrees=orientation,
            matches_business_rule=matches_business_rule,
            bounding_box_area=area,
            scan_order_key=scan_order,
        )

    def _read_json(self, path: Path) -> dict[str, object]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _read_jsonl(self, path: Path) -> list[dict[str, object]]:
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]


if __name__ == "__main__":
    unittest.main()
