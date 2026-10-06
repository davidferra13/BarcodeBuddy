from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.customer_provisioning import build_customer_config, provision_customer

ROOT = Path(__file__).resolve().parents[1]


def test_customer_config_uses_unique_secret_and_loopback_default(tmp_path: Path) -> None:
    first = build_customer_config("Receiving-POD", tmp_path / "runtime")
    second = build_customer_config("Receiving-POD", tmp_path / "runtime-2")

    assert first["workflow_key"] == "receiving_pod"
    assert first["server_host"] == "127.0.0.1"
    assert first["server_port"] == 8080
    assert isinstance(first["secret_key"], str)
    assert len(first["secret_key"]) >= 48
    assert first["secret_key"] != second["secret_key"]


def test_customer_config_paths_are_absolute_and_workflow_scoped(tmp_path: Path) -> None:
    runtime_root = tmp_path / "customer runtime"
    config = build_customer_config("shipping-pod", runtime_root)

    expected = (runtime_root.resolve() / "shipping_pod")
    assert Path(str(config["input_path"])) == expected / "input"
    assert Path(str(config["processing_path"])) == expected / "processing"
    assert Path(str(config["output_path"])) == expected / "output"
    assert Path(str(config["rejected_path"])) == expected / "rejected"
    assert Path(str(config["log_path"])) == expected / "logs"


@pytest.mark.parametrize("workflow_key", ["", "../escape", "bad workflow", "_leading", "x" * 65])
def test_customer_config_rejects_unsafe_workflow_keys(tmp_path: Path, workflow_key: str) -> None:
    with pytest.raises(ValueError):
        build_customer_config(workflow_key, tmp_path)


def test_provision_customer_writes_valid_config_and_directories(tmp_path: Path) -> None:
    config_path = tmp_path / "configs with spaces" / "config.customer.json"
    runtime_root = tmp_path / "runtime with spaces"

    result = provision_customer(
        config_path=config_path,
        workflow_key="receiving",
        runtime_root=runtime_root,
    )

    assert result.config_path == config_path.resolve()
    assert result.settings.workflow_key == "receiving"
    assert result.settings.server_host == "127.0.0.1"
    assert result.settings.secret_key
    assert config_path.is_file()
    for path in (
        result.settings.input_path,
        result.settings.processing_path,
        result.settings.output_path,
        result.settings.rejected_path,
        result.settings.log_path,
    ):
        assert path.is_dir()

    persisted = json.loads(config_path.read_text(encoding="utf-8"))
    assert persisted["secret_key"] == result.settings.secret_key


def test_provision_customer_refuses_to_overwrite_existing_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.customer.json"
    config_path.write_text('{"sentinel": true}\n', encoding="utf-8")

    with pytest.raises(FileExistsError):
        provision_customer(
            config_path=config_path,
            workflow_key="receiving",
            runtime_root=tmp_path / "runtime",
        )

    assert json.loads(config_path.read_text(encoding="utf-8")) == {"sentinel": True}


def test_customer_config_files_are_gitignored() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert re.search(r"(?m)^config\.customer\*\.json$", gitignore)


def test_powershell_provisioning_wrapper_exists_and_calls_python_cli() -> None:
    text = (ROOT / "provision-customer.ps1").read_text(encoding="utf-8")
    assert "scripts\\provision_customer.py" in text
    assert "WorkflowKey" in text
    assert "ConfigPath" in text
    assert "RuntimeRoot" in text
