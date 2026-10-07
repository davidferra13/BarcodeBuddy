from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app import __version__
from app.config import ensure_runtime_directories, load_settings
from app.contracts import ERROR_CODES, STATUS_FAILURE, STATUS_SUCCESS
from app.processor import BarcodeBuddyService, ProcessingResult


@dataclass(frozen=True)
class AcceptanceCase:
    case_id: str
    source: Path
    display_file: str
    expected: dict[str, str]


@dataclass(frozen=True)
class AcceptanceManifest:
    path: Path
    customer: str
    workflow: str
    cases: tuple[AcceptanceCase, ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(manifest_path: Path) -> AcceptanceManifest:
    path = manifest_path.resolve()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Acceptance manifest must be a JSON object.")
    raw_cases = raw.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("Acceptance manifest must contain at least one case.")

    base = path.parent.resolve()
    seen: set[str] = set()
    cases: list[AcceptanceCase] = []
    for index, item in enumerate(raw_cases, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Acceptance case {index} must be an object.")
        case_id = str(item.get("id") or "").strip()
        if not case_id:
            raise ValueError(f"Acceptance case {index} is missing id.")
        if case_id in seen:
            raise ValueError(f"Acceptance manifest contains duplicate id: {case_id}")
        seen.add(case_id)

        display_file = str(item.get("file") or "").strip()
        if not display_file:
            raise ValueError(f"Acceptance case {case_id} is missing file.")
        requested = Path(display_file)
        if requested.is_absolute():
            raise ValueError(f"Acceptance case {case_id} file must stay inside the manifest directory.")
        source = (base / requested).resolve()
        if not source.is_relative_to(base):
            raise ValueError(f"Acceptance case {case_id} file must stay inside the manifest directory.")
        if not source.is_file():
            raise ValueError(f"Acceptance case {case_id} file does not exist: {display_file}")

        expected_raw = item.get("expected")
        if not isinstance(expected_raw, dict):
            raise ValueError(f"Acceptance case {case_id} is missing expected outcome.")
        status = str(expected_raw.get("status") or "").strip().lower()
        if status not in {STATUS_SUCCESS, STATUS_FAILURE}:
            raise ValueError(
                f"Acceptance case {case_id} expected.status must be 'success' or 'failure'."
            )
        unknown = set(expected_raw) - {"status", "barcode", "reason"}
        if unknown:
            raise ValueError(f"Acceptance case {case_id} has unknown expected fields: {sorted(unknown)}")
        required = "barcode" if status == STATUS_SUCCESS else "reason"
        if required not in expected_raw:
            raise ValueError(f"Acceptance case {case_id} expected.{required} is required.")
        expected: dict[str, str] = {"status": status}
        for key in ("barcode", "reason"):
            if key not in expected_raw:
                continue
            value = expected_raw[key]
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Acceptance case {case_id} expected.{key} must be a nonempty string.")
            if key == "reason" and value not in ERROR_CODES:
                raise ValueError(f"Acceptance case {case_id} expected.reason must be a known error code.")
            expected[key] = value

        cases.append(
            AcceptanceCase(
                case_id=case_id,
                source=source,
                display_file=display_file,
                expected=expected,
            )
        )

    return AcceptanceManifest(
        path=path,
        customer=str(raw.get("customer") or "").strip(),
        workflow=str(raw.get("workflow") or "").strip(),
        cases=tuple(cases),
    )


def _actual(result: ProcessingResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "stage": result.stage,
        "barcode": result.barcode,
        "reason": result.reason,
        "duration_ms": result.duration_ms,
        "processing_id": result.processing_id,
        "output_file": result.output_path.name if result.output_path else None,
        "rejected_file": result.rejected_path.name if result.rejected_path else None,
    }


def _compare(expected: dict[str, str], actual: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mismatches: dict[str, dict[str, Any]] = {}
    for key, value in expected.items():
        if actual.get(key) != value:
            mismatches[key] = {"expected": value, "actual": actual.get(key)}
    return mismatches


def _write_markdown(report: dict[str, Any], destination: Path) -> None:
    lines = [
        "# BarcodeBuddy acceptance report",
        "",
        f"- customer: {report['customer'] or 'not specified'}",
        f"- workflow: {report['workflow']}",
        f"- product version: {report['product_version']}",
        f"- config version: {report['config_version']}",
        f"- generated: {report['generated_at']}",
        f"- result: {'PASS' if report['passed'] else 'FAIL'}",
        f"- cases: {report['summary']['passed']}/{report['summary']['total']} passed",
        "",
        "| case | file | expected | actual | result |",
        "| --- | --- | --- | --- | --- |",
    ]
    for case in report["cases"]:
        expected = case["expected"]["status"]
        actual = case["actual"]["status"]
        verdict = "PASS" if case["passed"] else "FAIL"
        lines.append(
            f"| {case['id']} | {case['file']} | {expected} | {actual} | {verdict} |"
        )
    lines.extend(["", "Document contents are not stored in this report. SHA-256 hashes identify the tested samples.", ""])
    destination.write_text("\n".join(lines), encoding="utf-8")


def run_acceptance(
    config_path: Path,
    manifest_path: Path,
    report_dir: Path,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    base_settings = load_settings(config_path.resolve())
    destination = report_dir.resolve()
    protected = {manifest.path, config_path.resolve(), *(case.source for case in manifest.cases)}
    for filename in ("acceptance-report.json", "acceptance-report.md"):
        output = destination / filename
        if output.resolve() in protected or output.is_symlink():
            raise ValueError("Acceptance report must not overlap a source or symlink.")
    destination.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="barcodebuddy-acceptance-") as tmp:
        runtime = Path(tmp)
        test_settings = base_settings.model_copy(
            update={
                "input_path": runtime / "input",
                "processing_path": runtime / "processing",
                "output_path": runtime / "output",
                "rejected_path": runtime / "rejected",
                "log_path": runtime / "logs",
            }
        )
        ensure_runtime_directories(test_settings)
        service = BarcodeBuddyService(test_settings)

        for index, case in enumerate(manifest.cases, start=1):
            before_hash = _sha256(case.source)
            copied = test_settings.input_path / f"{index:03d}_{case.source.name}"
            shutil.copy2(case.source, copied)
            result = service.process_file(copied)
            after_exists = case.source.is_file()
            after_hash = _sha256(case.source) if after_exists else None

            actual = _actual(result)
            mismatches = _compare(case.expected, actual)
            if not after_exists or after_hash != before_hash:
                mismatches["source_integrity"] = {
                    "expected": before_hash,
                    "actual": after_hash,
                }

            results.append(
                {
                    "id": case.case_id,
                    "file": case.display_file,
                    "sha256": before_hash,
                    "expected": case.expected,
                    "actual": actual,
                    "passed": not mismatches,
                    "mismatches": mismatches,
                }
            )

    passed_count = sum(1 for item in results if item["passed"])
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "product": "BarcodeBuddy",
        "product_version": __version__,
        "customer": manifest.customer,
        "workflow": manifest.workflow or base_settings.workflow_key,
        "config_version": base_settings.config_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": passed_count == len(results),
        "summary": {
            "total": len(results),
            "passed": passed_count,
            "failed": len(results) - passed_count,
        },
        "cases": results,
    }
    (destination / "acceptance-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    _write_markdown(report, destination / "acceptance-report.md")
    return report
