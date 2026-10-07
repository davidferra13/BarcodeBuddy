"""The sales demo kit must do on a call exactly what sales/DEMO.md says it does.

Both tests use the real barcode reader. The second one drops the kit into the
input folder of a running service, the same path a buyer's scanner uses, so a
broken watcher cannot hide behind a direct process_file call.
"""
from __future__ import annotations

import json
import shutil
import sys
import threading
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from make_demo_kit import DEMO_PATTERN, build_kit  # noqa: E402

from app.acceptance import run_acceptance  # noqa: E402
from app.customer_provisioning import provision_customer  # noqa: E402
from app.processor import BarcodeBuddyService  # noqa: E402

FILED = {"PO-10431", "PO-10432", "PO-10433", "PO-10434"}
REJECTED = Counter({"BARCODE_NOT_FOUND": 2, "INVALID_BARCODE_FORMAT": 1,
                    "AMBIGUOUS_BARCODE": 1, "DUPLICATE_FILE": 1})


def _demo_config(tmp_path: Path) -> Path:
    config = tmp_path / "config.demo.json"
    provision_customer(config_path=config, workflow_key="demo", runtime_root=tmp_path / "runtime",
                       barcode_value_patterns=(DEMO_PATTERN,), duplicate_handling="reject")
    return config


def test_demo_kit_matches_its_manifest_through_the_real_processor(tmp_path: Path) -> None:
    kit = tmp_path / "kit"
    manifest = build_kit(kit)
    assert len(manifest["cases"]) == 9
    report = run_acceptance(_demo_config(tmp_path), kit / "manifest.json", tmp_path / "report")
    failures = [case for case in report["cases"] if not case["passed"]]
    assert failures == [], json.dumps(failures, indent=2)
    assert report["summary"] == {"total": 9, "passed": 9, "failed": 0}


def test_demo_kit_dropped_into_the_watched_folder_files_and_rejects_as_promised(tmp_path: Path) -> None:
    kit = tmp_path / "kit"
    build_kit(kit)
    settings = provision_customer(config_path=tmp_path / "config.demo.json", workflow_key="demo",
                                  runtime_root=tmp_path / "runtime",
                                  barcode_value_patterns=(DEMO_PATTERN,),
                                  duplicate_handling="reject").settings
    service = BarcodeBuddyService(settings)
    worker = threading.Thread(target=service.run_forever, daemon=True)
    worker.start()
    try:
        time.sleep(1.0)
        for source in sorted((kit / "drop-these").iterdir()):
            shutil.copy2(source, settings.input_path / source.name)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            waiting = [p for p in settings.input_path.iterdir() if p.is_file()]
            busy = [p for p in settings.processing_path.iterdir() if p.is_file()]
            sidecars = list(settings.rejected_path.glob("*.meta.json"))
            filed = list(settings.output_path.rglob("*.pdf"))
            if not waiting and not busy and len(sidecars) + len(filed) >= 9:
                break
            time.sleep(0.25)
    finally:
        service.stop()
        worker.join(timeout=30)

    assert not worker.is_alive()
    filed = sorted(path.stem for path in settings.output_path.rglob("*.pdf"))
    assert set(filed) == FILED and len(filed) == 4, filed
    reasons = Counter(json.loads(path.read_text(encoding="utf-8"))["reason"]
                      for path in settings.rejected_path.glob("*.meta.json"))
    assert reasons == REJECTED, reasons
    assert [p for p in settings.input_path.iterdir() if p.is_file()] == []
