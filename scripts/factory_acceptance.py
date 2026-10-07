"""Isolated reference acceptance. This proves no installed customer runtime."""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image
import pymupdf
from app import database
from app.barcode_generator import generate_code128
from app.config import Settings, ensure_runtime_directories
from app.processor import BarcodeBuddyService


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_reference_acceptance(work_root: Path) -> dict[str, object]:
    """Create a fresh synthetic workspace, execute native behavior, keep evidence."""
    if database._engine is not None:
        raise RuntimeError("Reference acceptance refuses an active database.")
    root = Path(work_root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    settings = Settings(
        **{f"{name}_path": root / name for name in ("input", "processing", "output", "rejected", "log")},
        barcode_types=("code128",), barcode_value_patterns=(r"^PO-[0-9]+$",),
        scan_all_pages=True, duplicate_handling="reject", file_stability_delay_ms=500,
        max_pages_scan=50, server_host="127.0.0.1", workflow_key="reference_receiving",
    )
    ensure_runtime_directories(settings)
    fixtures = root / "fixtures"
    fixtures.mkdir()
    barcode_pdf = fixtures / "barcode.pdf"
    barcode = generate_code128("PO-910001", scale=5).convert("RGB")
    try:
        barcode.save(barcode_pdf, "PDF")
    finally:
        barcode.close()
    blank_pdf = fixtures / "blank.pdf"
    blank = Image.new("RGB", (900, 500), "white")
    try:
        blank.save(blank_pdf, "PDF")
    finally:
        blank.close()

    probes: list[dict[str, object]] = []

    def record(probe_id, expected, observed, evidence=()):
        probes.append({"id": probe_id, "expected": expected, "observed": observed,
                       "passed": expected == observed, "evidence": list(evidence)})

    def rejection_preserved(result, source):
        rejected = result.rejected_path
        if rejected is None or not rejected.is_file():
            return False
        sidecar = rejected.with_suffix(".meta.json")
        if not sidecar.is_file() or _sha256(rejected) != _sha256(source):
            return False
        metadata = json.loads(sidecar.read_text(encoding="utf-8"))
        return metadata.get("reason") == result.reason

    service = BarcodeBuddyService(settings)
    try:
        good = settings.input_path / "barcode.pdf"
        shutil.copyfile(barcode_pdf, good)
        routed = service.process_file(good)
        readable = False
        if routed.output_path is not None and routed.output_path.is_file():
            with pymupdf.open(routed.output_path) as document:
                readable = document.page_count == 1
        record("code128-pdf", {"status": "success", "barcode": "PO-910001", "readable_pdf": True},
               {"status": routed.status, "barcode": routed.barcode, "readable_pdf": readable},
               ["output"])

        no_barcode = settings.input_path / "blank.pdf"
        shutil.copyfile(blank_pdf, no_barcode)
        rejected = service.process_file(no_barcode)
        record("no-barcode-rejection", {"status": "failure", "reason": "BARCODE_NOT_FOUND", "preserved": True},
               {"status": rejected.status, "reason": rejected.reason,
                "preserved": rejection_preserved(rejected, blank_pdf)}, ["rejected", "log"])

        duplicate = settings.input_path / "duplicate.pdf"
        shutil.copyfile(barcode_pdf, duplicate)
        rejected_duplicate = service.process_file(duplicate)
        record("duplicate-rejection", {"status": "failure", "reason": "DUPLICATE_FILE",
                                      "preserved": True, "output_count": 1},
               {"status": rejected_duplicate.status, "reason": rejected_duplicate.reason,
                "preserved": rejection_preserved(rejected_duplicate, barcode_pdf),
                "output_count": len(list(settings.output_path.rglob("*.pdf")))}, ["rejected", "output", "log"])

        stranded = settings.processing_path / "stranded.pdf"
        shutil.copyfile(barcode_pdf, stranded)
        original_hash = _sha256(stranded)
        service.recover_processing_files()
        recovered = settings.input_path / stranded.name
        record("stranded-file-recovery", {"requeued": True, "processing_removed": True, "preserved": True},
               {"requeued": recovered.is_file(), "processing_removed": not stranded.exists(),
                "preserved": recovered.is_file() and _sha256(recovered) == original_hash}, ["input", "log"])
    finally:
        service.stop()

    try:
        database.init_db(root / "reference.db")
        sessions = database.get_db()
        try:
            db = next(sessions)
            db.add(database.ActivityLog(action="Reference Acceptance", category="system", summary="Synthetic reference record"))
            db.commit()
        finally:
            sessions.close()
        backup = database.backup_database(root / "backups")
        with closing(sqlite3.connect(f"{backup.as_uri()}?mode=ro", uri=True)) as restored:
            integrity = restored.execute("PRAGMA integrity_check").fetchone()[0]
            count = restored.execute("SELECT count(*) FROM activity_log").fetchone()[0]
        with closing(sqlite3.connect(f"{(root / 'reference.db').as_uri()}?mode=ro", uri=True)) as source:
            mode = source.execute("PRAGMA journal_mode").fetchone()[0]
        record("sqlite-backup", {"integrity": "ok", "activity_count": 1, "source_mode": "wal"},
               {"integrity": integrity, "activity_count": count, "source_mode": mode}, ["backups"])
    finally:
        database.shutdown_db()

    return {"schema_version": 1, "product_key": "barcodebuddy",
            "passed": len(probes) == 5 and all(p["passed"] is True for p in probes),
            "synthetic": True, "customer_approval": False, "deployment_verified": False,
            "probes": probes}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        parser.error("Refusing to overwrite an existing acceptance receipt.")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        report = run_reference_acceptance(output.parent / f"{output.stem}-runtime")
    except Exception as exc:
        report = {"schema_version": 1, "product_key": "barcodebuddy", "passed": False,
                  "synthetic": True, "customer_approval": False, "deployment_verified": False,
                  "error_type": type(exc).__name__, "probes": []}
    with output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    print(json.dumps({"passed": report["passed"], "probe_count": len(report["probes"])}))
    return 0 if report["passed"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
