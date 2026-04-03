from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from app.config import DEFAULT_CONFIG, load_settings


class LoadSettingsTests(unittest.TestCase):
    def test_repository_configs_load(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        config_paths = [
            repo_root / "config.json",
            repo_root / "configs" / "config.receiving.example.json",
            repo_root / "configs" / "config.shipping-pod.example.json",
            repo_root / "configs" / "config.quality-compliance.example.json",
        ]

        for config_path in config_paths:
            with self.subTest(config_path=config_path.name):
                settings = load_settings(config_path)
                self.assertTrue(settings.input_path.is_absolute())
                self.assertEqual(
                    5,
                    len(
                        {
                            settings.input_path,
                            settings.processing_path,
                            settings.output_path,
                            settings.rejected_path,
                            settings.log_path,
                        }
                    ),
                )
                self.assertTrue(settings.workflow_key)
                self.assertRegex(settings.config_version, r"^[0-9a-f]{12}$")

    def test_rejects_unknown_config_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            self._write_config(config_path, {"unexpected_key": True})

            with self.assertRaisesRegex(ValueError, "unsupported keys"):
                load_settings(config_path)

    def test_rejects_duplicate_managed_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            self._write_config(
                config_path,
                {
                    "processing_path": "./data/shared",
                    "output_path": "./data/shared",
                },
            )

            with self.assertRaisesRegex(ValueError, "must be distinct"):
                load_settings(config_path)

    def test_normalizes_workflow_key_and_sets_config_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            self._write_config(config_path, {"workflow_key": "Receiving-POD"})

            settings = load_settings(config_path)

            self.assertEqual(settings.workflow_key, "receiving_pod")
            self.assertRegex(settings.config_version, r"^[0-9a-f]{12}$")

    def test_rejects_invalid_workflow_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            self._write_config(config_path, {"workflow_key": "bad workflow key"})

            with self.assertRaisesRegex(ValueError, "workflow_key"):
                load_settings(config_path)

    @unittest.skipUnless(os.name == "nt", "Windows drive semantics are required for this check.")
    def test_rejects_cross_volume_managed_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            current_drive = Path(temp_dir).drive.upper()
            other_drive = "D:" if current_drive != "D:" else "E:"
            self._write_config(
                config_path,
                {
                    "output_path": f"{other_drive}\\barcodebuddy\\output",
                },
            )

            with self.assertRaisesRegex(ValueError, "same filesystem volume"):
                load_settings(config_path)

    def _write_config(self, config_path: Path, overrides: dict[str, object]) -> None:
        config = dict(DEFAULT_CONFIG)
        config.update(
            {
                "input_path": "./data/input",
                "processing_path": "./data/processing",
                "output_path": "./data/output",
                "rejected_path": "./data/rejected",
                "log_path": "./data/logs",
                "barcode_types": ["code128", "auto"],
                "barcode_value_patterns": [],
                "scan_all_pages": True,
                "duplicate_handling": "timestamp",
                "file_stability_delay_ms": 2000,
                "max_pages_scan": 50,
                "poll_interval_ms": 500,
                "barcode_scan_dpi": 300,
                "barcode_upscale_factor": 1.0,
            }
        )
        config.update(overrides)

        with config_path.open("w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2)
            handle.write("\n")


if __name__ == "__main__":
    unittest.main()
