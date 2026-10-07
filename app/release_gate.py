from __future__ import annotations
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from app import __version__
from app.acceptance import run_acceptance
from app.config import load_settings
from app.customer_provisioning import provision_customer
from app.release_backup import create_backup, verified_extract

MANDATORY_GATES = ("compile", "tests", "launcher", "config", "security", "acceptance", "backup", "git", "customer_package", "acquisition")


def build_receipt(gates: dict, metadata: dict) -> dict:
    missing = [name for name in MANDATORY_GATES if name not in gates]
    failed = [name for name in MANDATORY_GATES if name in gates and gates[name].get("passed") is not True]
    metadata = dict(metadata)
    customer = metadata.get("customer_acceptance")
    metadata["customer_ready"] = not missing and not failed and isinstance(customer, dict) and customer.get("passed") is True
    return {
        "schema_version": "1.0", "product": "BarcodeBuddy", "product_version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ready": not missing and not failed,
        "missing_gates": missing, "failed_gates": failed,
        "metadata": metadata, "gates": gates,
    }


def run_command(command: list[str], cwd: Path, log_path: Path, *, timeout_s: float = 600) -> dict:
    started = time.monotonic()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.run(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, timeout=timeout_s)
        return {"passed": process.returncode == 0, "returncode": process.returncode,
                "timed_out": False, "duration_seconds": round(time.monotonic()-started, 3),
                "log_sha256": hashlib.sha256(log_path.read_bytes()).hexdigest()}
    except subprocess.TimeoutExpired:
        return {"passed": False, "returncode": None, "timed_out": True,
                "duration_seconds": round(time.monotonic()-started, 3)}
    except OSError as error:
        return {"passed": False, "returncode": None, "error": type(error).__name__}


def capture_git_identity(repo: Path) -> dict:
    try:
        revision = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True, timeout=30).strip()
        dirty = bool(subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain"], text=True, timeout=30).strip())
        return {"revision": revision, "dirty": dirty}
    except (OSError, subprocess.SubprocessError):
        return {"revision": None, "dirty": True, "error": "Git evidence unavailable"}


def verify_git_identity(start: dict, end: dict) -> dict:
    passed = bool(start.get("revision")) and start.get("revision") == end.get("revision") and start.get("dirty") is False and end.get("dirty") is False
    return {"passed": passed, "revision": end.get("revision"), "dirty": end.get("dirty"),
            "source_before": start, "source_after": end}


def run_launcher_gate(repo: Path, report_dir: Path) -> dict:
    report = report_dir / "launcher.junit.xml"
    report.unlink(missing_ok=True)
    result = run_command(
        [sys.executable, "-B", "-m", "pytest", "tests/test_windows_scripts.py",
         "-q", "-ra", "--junitxml", str(report)],
        repo, report_dir / "launcher.log", timeout_s=90,
    )
    try:
        cases = ET.parse(report).getroot().findall(".//testcase")
        probes = [case for case in cases if case.get("name") == "test_native_launcher_preserves_spaces_and_customer_port"]
        executed = len(probes) == 1 and all(probes[0].find(tag) is None for tag in ("skipped", "failure", "error"))
    except (OSError, ET.ParseError):
        executed = False
    result["native_probe_passed"] = executed
    result["passed"] = result.get("passed") is True and executed
    if not executed:
        result["error"] = "Native launcher probe did not pass; missing or skipped evidence is not readiness."
    return result


def check_customer_security(config_path: Path, *, repository_config: Path | None) -> dict:
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    settings = load_settings(config_path)
    problems = []
    if settings.server_host != "127.0.0.1":
        problems.append("Customer default must bind loopback.")
    if len(raw.get("secret_key", "")) < 32:
        problems.append("Customer config must persist a strong installation secret.")
    if repository_config is not None and repository_config.exists():
        shared = json.loads(repository_config.read_text(encoding="utf-8")).get("secret_key")
        if shared and shared == raw.get("secret_key"):
            problems.append("Customer secret reuses the repository default.")
    return {"passed": not problems, "problems": problems}


def run_synthetic_acceptance(config_path: Path, report_dir: Path) -> dict:
    from PIL import Image
    from app.barcode_generator import save_barcode
    report_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="barcodebuddy-synthetic-") as tmp:
        base = Path(tmp)
        good = base / "good.png"
        duplicate = base / "duplicate.png"
        blank = base / "blank.png"
        invalid = base / "wrong-id.png"
        save_barcode("PO-810001", good, format="Code128", scale=5)
        shutil.copy2(good, duplicate)
        Image.new("RGB", (900, 500), "white").save(blank)
        save_barcode("SHIP-810002", invalid, format="Code128", scale=5)
        settings = load_settings(config_path)
        duplicate_outcome = (
            {"status": "failure", "reason": "DUPLICATE_FILE"}
            if settings.duplicate_handling == "reject"
            else {"status": "success", "barcode": "PO-810001"}
        )
        cases = [
            {"id": "barcode", "file": good.name, "expected": {"status": "success", "barcode": "PO-810001"}},
            {"id": "duplicate", "file": duplicate.name, "expected": duplicate_outcome},
            {"id": "blank", "file": blank.name, "expected": {"status": "failure", "reason": "BARCODE_NOT_FOUND"}},
        ]
        if settings.barcode_value_patterns:
            cases.append({"id": "wrong-routing-id", "file": invalid.name,
                          "expected": {"status": "failure", "reason": "INVALID_BARCODE_FORMAT"}})
        else:
            cases.append({"id": "second-id", "file": invalid.name,
                          "expected": {"status": "success", "barcode": "SHIP-810002"}})
        manifest = base / "manifest.json"
        manifest.write_text(json.dumps({"customer": "Internal synthetic fixtures", "workflow": settings.workflow_key, "cases": cases}))
        report = run_acceptance(config_path, manifest, report_dir)
    return {"passed": report["passed"], "cases": report["summary"]["total"],
            "report_sha256": hashlib.sha256((report_dir/"acceptance-report.json").read_bytes()).hexdigest(),
            "corpus": "synthetic", "customer_approval": False}


def run_backup_roundtrip(config_path: Path, report_dir: Path) -> dict:
    report_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="barcodebuddy-backup-proof-") as tmp:
        base = Path(tmp)
        database = base / "live.db"
        with closing(sqlite3.connect(database)) as live:
            live.execute("PRAGMA journal_mode=WAL")
            live.execute("CREATE TABLE proof (value TEXT)")
            live.execute("INSERT INTO proof VALUES ('committed-wal-row')")
            live.commit()
            archive = base / "roundtrip.zip"
            create_backup(config_path, archive, database_path=database)
            restored = base / "restored"
            verified_extract(archive, restored)
            with closing(sqlite3.connect(restored/"database/barcode_buddy.db")) as restored_db:
                valid = restored_db.execute("SELECT value FROM proof").fetchall() == [("committed-wal-row",)]
            proof = {"passed": valid, "database_verified": valid,
                     "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}
    (report_dir/"backup-roundtrip.json").write_text(json.dumps(proof, indent=2)+"\n")
    return proof


def _attempt(callback) -> dict:
    try:
        return callback()
    except Exception as error:
        return {"passed": False, "error": type(error).__name__}


def run_release_gate(repo: Path, report_dir: Path, *, acquisition_repo: Path | None = None,
                     customer_config: Path | None = None, customer_manifest: Path | None = None,
                     timeout_s: float = 600) -> dict:
    repo = repo.resolve()
    report_dir = report_dir.resolve()
    if report_dir.is_relative_to(repo):
        raise ValueError("Release evidence must be outside the source checkout.")
    if (customer_config is None) != (customer_manifest is None):
        raise ValueError("Customer config and manifest must be supplied together.")
    report_dir.mkdir(parents=True, exist_ok=True)
    source_before = capture_git_identity(repo)
    gates = {}
    gates["compile"] = run_command([sys.executable, "-m", "compileall", "-q", "app", "scripts", "tests", "main.py", "stats.py"], repo, report_dir/"compile.log", timeout_s=timeout_s)
    gates["tests"] = run_command([sys.executable, "-B", "-m", "pytest", "tests/", "-q", "-ra"], repo, report_dir/"tests.log", timeout_s=timeout_s)
    gates["launcher"] = run_launcher_gate(repo, report_dir)
    with tempfile.TemporaryDirectory(prefix="barcodebuddy-release-proof-") as tmp:
        base = Path(tmp)
        config = base/"config.customer.json"
        provision_customer(config_path=config, workflow_key="release_proof", runtime_root=base/"runtime",
                           barcode_value_patterns=(r"^PO-[0-9]+$",), duplicate_handling="reject")
        def validate_configs():
            paths = [repo/"config.json"] + sorted((repo/"configs").glob("*.json"))
            for path in paths: load_settings(path)
            return {"passed": True, "validated": len(paths)}
        gates["config"] = _attempt(validate_configs)
        gates["security"] = _attempt(lambda: check_customer_security(config, repository_config=repo/"config.json"))
        gates["acceptance"] = _attempt(lambda: run_synthetic_acceptance(config, report_dir/"acceptance"))
        gates["backup"] = _attempt(lambda: run_backup_roundtrip(config, report_dir/"backup"))
    customer_result = None
    if customer_config is not None:
        customer_result = _attempt(lambda: {
            "passed": run_acceptance(customer_config, customer_manifest, report_dir/"customer-acceptance")["passed"],
            "corpus": "provided-customer-manifest",
        })
    required = ["docs/customer/INSTALL.md", "docs/customer/ACCEPTANCE.md", "docs/customer/OPERATIONS.md",
                "docs/customer/ADMIN-RECOVERY.md", "docs/customer/SECURITY.md", "sales/OFFER.md",
                "sales/DISCOVERY.md", "sales/SAMPLE-REQUEST.md", "sales/STATEMENT-OF-WORK.md", "sales/QUALIFICATION.json"]
    missing = [name for name in required if not (repo/name).is_file()]
    gates["customer_package"] = {"passed": not missing, "missing": missing}
    if acquisition_repo is not None:
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
        if npm:
            gates["acquisition"] = run_command([npm, "run", "verify"], acquisition_repo, report_dir/"acquisition.log", timeout_s=timeout_s)
        else:
            gates["acquisition"] = {"passed": False, "error": "npm unavailable"}
    else:
        gates["acquisition"] = {"passed": False, "error": "Built To Own verification target not supplied"}
    gates["git"] = verify_git_identity(source_before, capture_git_identity(repo))
    revision = gates["git"]["revision"]
    receipt = build_receipt(gates, {"revision": revision, "customer_acceptance": customer_result,
                                  "customer_ready": customer_result is not None and customer_result.get("passed") is True})
    path = report_dir/"release-receipt.json"
    path.write_text(json.dumps(receipt, indent=2)+"\n", encoding="utf-8")
    return receipt
