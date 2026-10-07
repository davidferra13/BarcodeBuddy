from __future__ import annotations
import importlib
import importlib.util
import json
import sys
from pathlib import Path
import pytest
from app.customer_provisioning import provision_customer


def api():
    assert importlib.util.find_spec("app.release_gate") is not None, "Executable release gate is missing"
    return importlib.import_module("app.release_gate")


def test_release_receipt_fails_closed_for_missing_mandatory_evidence():
    receipt = api().build_receipt({"compile": {"passed": True}}, {"revision": "abc"})
    assert receipt["ready"] is False
    assert "tests" in receipt["missing_gates"]
    assert "acceptance" in receipt["missing_gates"]


def test_release_receipt_does_not_turn_failed_gate_green():
    gates = {name: {"passed": True} for name in api().MANDATORY_GATES}
    gates["backup"]["passed"] = False
    receipt = api().build_receipt(gates, {"revision": "abc"})
    assert receipt["ready"] is False
    assert receipt["failed_gates"] == ["backup"]


def test_release_receipt_requires_literal_true_status():
    gates = {name: {"passed": True} for name in api().MANDATORY_GATES}
    gates["tests"]["passed"] = "true"
    assert api().build_receipt(gates, {"revision": "abc"})["ready"] is False


def test_command_gate_records_real_failure_and_timeout(tmp_path):
    failed = api().run_command([sys.executable, "-c", "raise SystemExit(7)"], Path.cwd(), tmp_path / "failed.log", timeout_s=10)
    assert failed["passed"] is False
    assert failed["returncode"] == 7
    timed_out = api().run_command([sys.executable, "-c", "import time; time.sleep(5)"], Path.cwd(), tmp_path / "timeout.log", timeout_s=0.1)
    assert timed_out["passed"] is False
    assert timed_out["timed_out"] is True


def test_security_gate_rejects_lan_and_shared_repository_secret(tmp_path):
    config = tmp_path / "config.customer.json"
    provision_customer(config_path=config, workflow_key="receiving", runtime_root=tmp_path / "data")
    assert api().check_customer_security(config, repository_config=None)["passed"] is True
    raw = json.loads(config.read_text())
    raw["server_host"] = "0.0.0.0"
    config.write_text(json.dumps(raw))
    assert api().check_customer_security(config, repository_config=None)["passed"] is False
    raw["server_host"] = "127.0.0.1"
    config.write_text(json.dumps(raw))
    shared = tmp_path / "shared.json"
    shared.write_text(json.dumps(raw))
    assert api().check_customer_security(config, repository_config=shared)["passed"] is False


def test_real_synthetic_acceptance_and_backup_gate(tmp_path):
    config = tmp_path / "config.customer.json"
    provision_customer(config_path=config, workflow_key="receiving", runtime_root=tmp_path / "data", barcode_value_patterns=(r"^PO-[0-9]+$",), duplicate_handling="reject")
    result = api().run_synthetic_acceptance(config, tmp_path / "acceptance")
    assert result["passed"] is True
    assert result["cases"] >= 4
    backup = api().run_backup_roundtrip(config, tmp_path / "backup")
    assert backup["passed"] is True
    assert backup["database_verified"] is True

@pytest.mark.parametrize("parser_state", ["", "<skipped message='unavailable'/>", "<failure message='failed'/>"])
@pytest.mark.parametrize("runtime_state,expected", [("", True), ("<skipped message='unavailable'/>", False), ("<failure message='failed'/>", False)])
def test_launcher_gate_requires_executed_native_probe(tmp_path, monkeypatch, runtime_state, expected, parser_state):
    module=api()
    def command(command, cwd, log_path, **kwargs):
        report=Path(command[command.index("--junitxml")+1])
        report.write_text("<testsuites><testsuite><testcase name='test_launcher_scripts_parse_as_powershell'>"+parser_state+"</testcase><testcase name='test_native_launcher_preserves_spaces_and_customer_port'>"+runtime_state+"</testcase></testsuite></testsuites>")
        log_path.write_text("launcher evidence")
        return {"passed": True, "returncode": 0}
    monkeypatch.setattr(module, "run_command", command)
    result = module.run_launcher_gate(Path.cwd(), tmp_path)
    assert result["passed"] is (expected and not parser_state)
    assert result["native_parser_passed"] is (not parser_state)

def test_launcher_gate_rejects_missing_probe_evidence(tmp_path, monkeypatch):
    module=api()
    monkeypatch.setattr(module, "run_command", lambda *args, **kwargs: {"passed": True})
    assert module.run_launcher_gate(Path.cwd(), tmp_path)["passed"] is False

def test_customer_ready_requires_entire_release(tmp_path):
    gates={name: {"passed": True} for name in api().MANDATORY_GATES}
    gates["backup"]["passed"]=False
    receipt=api().build_receipt(gates, {"customer_acceptance": {"passed": True}, "customer_ready": True})
    assert receipt["metadata"]["customer_ready"] is False

@pytest.mark.parametrize("start,end", [
    ({"revision": "old", "dirty": False}, {"revision": "new", "dirty": False}),
    ({"revision": "old", "dirty": True}, {"revision": "old", "dirty": False}),
    ({"revision": "old", "dirty": False}, {"revision": "old", "dirty": True}),
    ({"revision": None, "dirty": False}, {"revision": None, "dirty": False}),
])
def test_git_gate_rejects_changed_or_unverified_source(start, end):
    assert api().verify_git_identity(start, end)["passed"] is False

def test_git_gate_accepts_same_clean_revision(tmp_path):
    import subprocess
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.invalid"], check=True)
    (tmp_path/"source.py").write_text("value=1")
    subprocess.run(["git", "-C", str(tmp_path), "add", "source.py"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "fixture"], check=True, capture_output=True)
    start=api().capture_git_identity(tmp_path)
    assert api().verify_git_identity(start, api().capture_git_identity(tmp_path))["passed"] is True
    (tmp_path/"source.py").write_text("value=2")
    assert api().verify_git_identity(start, api().capture_git_identity(tmp_path))["passed"] is False

@pytest.mark.parametrize("scan_all_pages", [True, False])
@pytest.mark.parametrize("max_pages_scan", [1, 2])
def test_synthetic_release_exercises_conflicting_and_multipage_documents(tmp_path, scan_all_pages, max_pages_scan):
    config = tmp_path / "config.customer.json"
    provision_customer(config_path=config, workflow_key="receiving", runtime_root=tmp_path / "data",
                       barcode_value_patterns=(r"^PO-[0-9]+$",), duplicate_handling="reject")
    raw = json.loads(config.read_text())
    raw["scan_all_pages"] = scan_all_pages
    raw["max_pages_scan"] = max_pages_scan
    config.write_text(json.dumps(raw))
    result = api().run_synthetic_acceptance(config, tmp_path / "acceptance")
    report = json.loads((tmp_path / "acceptance" / "acceptance-report.json").read_text())
    cases = {case["id"]: case for case in report["cases"]}
    assert {"conflicting-image", "mixed-pdf", "repeated-id-pdf"} <= cases.keys()
    assert result["passed"] is True
    assert result["cases"] == 7
    assert all(case["passed"] and len(case["sha256"]) == 64 for case in cases.values())
    assert cases["conflicting-image"]["actual"]["reason"] == "AMBIGUOUS_BARCODE"
    assert cases["conflicting-image"]["actual"]["output_file"] is None
    if max_pages_scan < 2:
        for case_id in ("mixed-pdf", "repeated-id-pdf"):
            assert cases[case_id]["actual"]["reason"] == "PROCESSING_TIMEOUT"
            assert cases[case_id]["actual"]["output_file"] is None
    elif scan_all_pages:
        assert cases["mixed-pdf"]["actual"]["reason"] == "AMBIGUOUS_BARCODE"
        assert cases["mixed-pdf"]["actual"]["output_file"] is None
    else:
        assert cases["mixed-pdf"]["actual"]["barcode"] == "PO-810003"
    if max_pages_scan >= 2:
        assert cases["repeated-id-pdf"]["actual"]["status"] == "success"
        assert cases["repeated-id-pdf"]["actual"]["barcode"] == "PO-810005"

def _acquisition_contract(repo):
    files = {
        "package.json": {"name": "builttoown"},
        "products/barcodebuddy/product.release.json": {"product_key": "barcodebuddy"},
        "products/barcodebuddy/offer.public.json": {},
        "products/barcodebuddy/instance-config.schema.json": {},
        "factory/adapters/barcodebuddy.mjs": None,
        "factory/core/validation.mjs": None,
        "factory/schemas/product-release.schema.json": {},
        "tests/factory/barcodebuddy-adapter.test.mjs": None,
    }
    for name, value in files.items():
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value) if value is not None else "// test fixture")
    return repo


def test_acquisition_gate_rejects_generic_website_without_adapter(tmp_path, monkeypatch):
    module = api()
    (tmp_path / "package.json").write_text(json.dumps({"name": "builttoown"}))
    monkeypatch.setattr(module, "run_command", lambda *a, **k: pytest.fail("Generic verify must not run for missing adapter"))
    result = module.run_acquisition_gate(tmp_path, tmp_path / "evidence")
    assert result["passed"] is False
    assert "factory/adapters/barcodebuddy.mjs" in result["missing"]
    assert "BarcodeBuddy" in result["error"]


@pytest.mark.parametrize("field", ["package", "product"])
def test_acquisition_gate_rejects_wrong_identity(tmp_path, monkeypatch, field):
    module = api()
    _acquisition_contract(tmp_path)
    target = tmp_path / ("package.json" if field == "package" else "products/barcodebuddy/product.release.json")
    target.write_text(json.dumps({"name": "unrelated", "product_key": "unrelated"}))
    monkeypatch.setattr(module, "run_command", lambda *a, **k: pytest.fail("Wrong integration target must not run"))
    result = module.run_acquisition_gate(tmp_path, tmp_path / "evidence")
    assert result["passed"] is False
    assert "identity" in result["error"]


def test_acquisition_gate_preserves_dirty_peer_work(tmp_path, monkeypatch):
    module = api()
    _acquisition_contract(tmp_path)
    monkeypatch.setattr(module, "capture_git_identity", lambda repo: {"revision": "a"*40, "dirty": True})
    monkeypatch.setattr(module, "run_command", lambda *a, **k: pytest.fail("Dirty peer target must not run"))
    result = module.run_acquisition_gate(tmp_path, tmp_path / "evidence")
    assert result["passed"] is False
    assert result["source_before"]["dirty"] is True


@pytest.mark.parametrize("changed", [True, False])
def test_acquisition_gate_requires_adapter_and_unchanged_clean_revision(tmp_path, monkeypatch, changed):
    module = api()
    _acquisition_contract(tmp_path)
    identities = iter([{"revision": "a"*40, "dirty": False},
                       {"revision": ("b" if changed else "a")*40, "dirty": False}])
    monkeypatch.setattr(module, "capture_git_identity", lambda repo: next(identities))
    monkeypatch.setattr(module.shutil, "which", lambda name: name)
    commands = []
    def command(command, *args, **kwargs):
        commands.append(command)
        return {"passed": True, "returncode": 0}
    monkeypatch.setattr(module, "run_command", command)
    result = module.run_acquisition_gate(tmp_path, tmp_path / "evidence")
    assert result["passed"] is (not changed)
    assert result["checks"]["adapter_tests"]["passed"] is True
    assert any("tests/factory/barcodebuddy-adapter.test.mjs" in command for command in commands)
    assert any(command[-2:] == ["run", "verify"] for command in commands)
