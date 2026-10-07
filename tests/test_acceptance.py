from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.acceptance import load_manifest, run_acceptance
from app.processor import ProcessingResult

ROOT = Path(__file__).resolve().parents[1]


def _write_config(tmp_path: Path) -> Path:
    root = tmp_path / "runtime"
    config = {
        "workflow_key": "acceptance",
        "input_path": str(root / "input"),
        "processing_path": str(root / "processing"),
        "output_path": str(root / "output"),
        "rejected_path": str(root / "rejected"),
        "log_path": str(root / "logs"),
        "barcode_types": ["code128", "auto"],
        "barcode_value_patterns": [],
        "scan_all_pages": True,
        "duplicate_handling": "timestamp",
        "file_stability_delay_ms": 500,
        "max_pages_scan": 10,
        "server_host": "127.0.0.1",
        "server_port": 8080,
        "secret_key": "acceptance-test-secret-" + "x" * 32,
    }
    path = tmp_path / "config.customer.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def _write_manifest(base: Path, cases: list[dict]) -> Path:
    path = base / "manifest.json"
    path.write_text(
        json.dumps({"customer": "Test Company", "workflow": "receiving", "cases": cases}),
        encoding="utf-8",
    )
    return path


def test_manifest_rejects_duplicate_ids(tmp_path: Path) -> None:
    sample = tmp_path / "sample.png"
    sample.write_bytes(b"same")
    manifest = _write_manifest(tmp_path, [
        {"id": "one", "file": "sample.png", "expected": {"status": "success", "barcode": "PO-100"}},
        {"id": "one", "file": "sample.png", "expected": {"status": "failure", "reason": "BARCODE_NOT_FOUND"}},
    ])
    with pytest.raises(ValueError, match="duplicate"):
        load_manifest(manifest)


def test_manifest_rejects_path_traversal(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.png"
    outside.write_bytes(b"outside")
    manifest = _write_manifest(tmp_path, [
        {"id": "escape", "file": "../outside.png", "expected": {"status": "failure"}},
    ])
    with pytest.raises(ValueError, match="inside"):
        load_manifest(manifest)


def test_manifest_rejects_missing_files_and_bad_expected_status(tmp_path: Path) -> None:
    missing = _write_manifest(tmp_path, [
        {"id": "missing", "file": "nope.png", "expected": {"status": "maybe"}},
    ])
    with pytest.raises(ValueError):
        load_manifest(missing)


def test_run_acceptance_preserves_sources_and_writes_hash_only_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    good = tmp_path / "good.png"
    bad = tmp_path / "bad.png"
    good.write_bytes(b"not-real-image-good")
    bad.write_bytes(b"not-real-image-bad")
    good_before = good.read_bytes()
    bad_before = bad.read_bytes()

    manifest = _write_manifest(tmp_path, [
        {
            "id": "good",
            "file": "good.png",
            "expected": {"status": "success", "barcode": "PO-100"},
        },
        {
            "id": "bad",
            "file": "bad.png",
            "expected": {"status": "failure", "reason": "BARCODE_NOT_FOUND"},
        },
    ])
    config = _write_config(tmp_path)
    report_dir = tmp_path / "reports"

    def fake_process(self, file_path: Path) -> ProcessingResult:
        if "good" in file_path.name:
            return ProcessingResult(
                processing_id="p-good",
                status="success",
                stage="output",
                original_filename=file_path.name,
                duration_ms=12,
                barcode="PO-100",
                output_path=self.settings.output_path / "PO-100.pdf",
            )
        return ProcessingResult(
            processing_id="p-bad",
            status="failure",
            stage="processing",
            original_filename=file_path.name,
            duration_ms=8,
            reason="BARCODE_NOT_FOUND",
            rejected_path=self.settings.rejected_path / file_path.name,
        )

    monkeypatch.setattr("app.acceptance.BarcodeBuddyService.process_file", fake_process)
    result = run_acceptance(config, manifest, report_dir)

    assert result["passed"] is True
    assert result["summary"] == {"total": 2, "passed": 2, "failed": 0}
    assert good.read_bytes() == good_before
    assert bad.read_bytes() == bad_before
    assert result["cases"][0]["sha256"] == hashlib.sha256(good_before).hexdigest()
    assert result["cases"][1]["sha256"] == hashlib.sha256(bad_before).hexdigest()

    json_report = report_dir / "acceptance-report.json"
    markdown_report = report_dir / "acceptance-report.md"
    assert json_report.is_file()
    assert markdown_report.is_file()
    report_text = json_report.read_text(encoding="utf-8")
    assert "not-real-image-good" not in report_text
    assert "not-real-image-bad" not in report_text


def test_run_acceptance_marks_expectation_mismatch_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample = tmp_path / "sample.png"
    sample.write_bytes(b"sample")
    manifest = _write_manifest(tmp_path, [
        {
            "id": "wrong",
            "file": "sample.png",
            "expected": {"status": "success", "barcode": "EXPECTED"},
        },
    ])
    config = _write_config(tmp_path)

    def fake_process(self, file_path: Path) -> ProcessingResult:
        return ProcessingResult(
            processing_id="p",
            status="success",
            stage="output",
            original_filename=file_path.name,
            duration_ms=1,
            barcode="ACTUAL",
            output_path=self.settings.output_path / "ACTUAL.pdf",
        )

    monkeypatch.setattr("app.acceptance.BarcodeBuddyService.process_file", fake_process)
    result = run_acceptance(config, manifest, tmp_path / "reports")

    assert result["passed"] is False
    assert result["summary"]["failed"] == 1
    assert "barcode" in result["cases"][0]["mismatches"]


def test_real_processor_acceptance_routes_barcode_and_rejects_blank(tmp_path: Path) -> None:
    from PIL import Image
    from app.barcode_generator import save_barcode

    good = tmp_path / "real-good.png"
    bad = tmp_path / "real-blank.png"
    save_barcode("PO-1000", good, format="Code128", scale=5)
    Image.new("RGB", (900, 500), "white").save(bad)

    manifest = _write_manifest(tmp_path, [
        {"id": "real-good", "file": good.name, "expected": {"status": "success", "barcode": "PO-1000"}},
        {"id": "real-blank", "file": bad.name, "expected": {"status": "failure", "reason": "BARCODE_NOT_FOUND"}},
    ])
    config = _write_config(tmp_path)
    result = run_acceptance(config, manifest, tmp_path / "real-reports")

    assert result["passed"] is True
    assert result["summary"] == {"total": 2, "passed": 2, "failed": 0}

def test_reports_cannot_overwrite_source_documents(tmp_path: Path) -> None:
    source = tmp_path / "acceptance-report.json"
    original = b'{"private":"original sample"}'
    source.write_bytes(original)
    manifest = _write_manifest(tmp_path, [
        {"id": "collision", "file": source.name, "expected": {"status": "failure", "reason": "UNSUPPORTED_FORMAT"}},
    ])
    config = _write_config(tmp_path)
    with pytest.raises(ValueError, match="source|overlap"):
        run_acceptance(config, manifest, tmp_path)
    assert source.read_bytes() == original

@pytest.mark.parametrize("expected", [
    {"status": "success", "barocde": "PO-100"},
    {"status": "failure", "reson": "BARCODE_NOT_FOUND"},
    {"status": "success", "barcode": None},
    {"status": "success", "barcode": 123},
    {"status": "success", "barcode": ""},
    {"status": "success"},
    {"status": "failure"},
    {"status": "failure", "reason": "BARCODE_NOT_FUND"},
    {"status": "failure", "reason": None},
    {"status": "failure", "reason": 123},
    {"status": "success", "barcode": "   "},
])
def test_manifest_rejects_unknown_or_invalid_expectations(tmp_path, expected):
    (tmp_path/"sample.png").write_bytes(b"sample")
    manifest=_write_manifest(tmp_path, [{"id": "one", "file": "sample.png", "expected": expected}])
    with pytest.raises(ValueError, match="expected"):
        load_manifest(manifest)
