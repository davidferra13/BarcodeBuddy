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

@pytest.mark.parametrize("runtime_state,expected", [("", True), ("<skipped message='unavailable'/>", False), ("<failure message='failed'/>", False)])
def test_launcher_gate_requires_executed_native_probe(tmp_path, monkeypatch, runtime_state, expected):
    module=api()
    def command(command, cwd, log_path, **kwargs):
        report=Path(command[command.index("--junitxml")+1])
        report.write_text("<testsuites><testsuite><testcase name='test_launcher_scripts_parse_as_powershell'><skipped/></testcase><testcase name='test_native_launcher_preserves_spaces_and_customer_port'>"+runtime_state+"</testcase></testsuite></testsuites>")
        log_path.write_text("launcher evidence")
        return {"passed": True, "returncode": 0}
    monkeypatch.setattr(module, "run_command", command)
    assert module.run_launcher_gate(Path.cwd(), tmp_path)["passed"] is expected

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
