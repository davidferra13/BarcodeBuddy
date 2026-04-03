from __future__ import annotations

import unittest
from pathlib import Path

from app.config import load_settings


class ConfigExampleTests(unittest.TestCase):
    def test_example_configs_load(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        expected_data_root = repo_root / "data"
        config_paths = {
            repo_root / "configs" / "config.receiving.example.json": "receiving",
            repo_root / "configs" / "config.shipping-pod.example.json": "shipping_pod",
            repo_root / "configs" / "config.quality-compliance.example.json": "quality_compliance",
        }

        for config_path, workflow_key in config_paths.items():
            with self.subTest(config=config_path.name):
                settings = load_settings(config_path)
                self.assertTrue(settings.input_path.is_absolute())
                self.assertTrue(settings.processing_path.is_absolute())
                self.assertTrue(settings.output_path.is_absolute())
                self.assertTrue(settings.rejected_path.is_absolute())
                self.assertTrue(settings.log_path.is_absolute())
                self.assertTrue(str(settings.input_path).startswith(str(expected_data_root)))
                self.assertGreaterEqual(settings.poll_interval_ms, 500)
                self.assertEqual(settings.barcode_scan_dpi, 300)
                self.assertEqual(settings.workflow_key, workflow_key)


if __name__ == "__main__":
    unittest.main()
