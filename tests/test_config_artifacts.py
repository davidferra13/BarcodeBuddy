from __future__ import annotations

import json
import unittest
from pathlib import Path

from app.config import DEFAULT_CONFIG, REQUIRED_KEYS, load_settings


class BarcodeBuddyConfigArtifactTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parent.parent
        self.schema_path = self.repo_root / "config.schema.json"
        self.main_config_path = self.repo_root / "config.json"
        self.example_config_paths = sorted((self.repo_root / "configs").glob("*.example.json"))
        self.readme_path = self.repo_root / "README.md"
        self.current_system_truth_path = self.repo_root / "docs" / "current-system-truth.md"
        self.critical_builder_docs = [
            self.current_system_truth_path,
            self.repo_root / "docs" / "danpack-builder-handoff.md",
            self.repo_root / "docs" / "production-operations-blueprint.md",
            self.repo_root / "docs" / "builder-execution-plan.md",
            self.repo_root / "docs" / "runbooks" / "incident-response.md",
            self.repo_root / "docs" / "danpack-system-interaction-philosophy.md",
            self.repo_root / "docs" / "scan-record-workbench.md",
            self.repo_root / "docs" / "scan-record-builder-handoff.md",
            self.repo_root / "docs" / "operations-planner-product-spec.md",
            self.repo_root / "docs" / "operations-planner-technical-spec.md",
            self.repo_root / "docs" / "operations-planner-builder-handoff.md",
            self.repo_root / "docs" / "operations-planner-execution-plan.md",
            self.repo_root / "docs" / "contracts" / "scan-record.schema.json",
            self.repo_root / "docs" / "contracts" / "report-snapshot.schema.json",
            self.repo_root / "docs" / "contracts" / "scan-obligation.schema.json",
            self.repo_root / "docs" / "examples" / "scan-record.example.json",
            self.repo_root / "docs" / "examples" / "report-snapshot.example.json",
            self.repo_root / "docs" / "examples" / "scan-obligation.example.json",
            self.repo_root / "docs" / "prototypes" / "scan-record-workbench.html",
        ]

    def test_schema_covers_current_default_config_keys(self) -> None:
        schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
        properties = schema["properties"]

        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema["additionalProperties"])
        self.assertTrue(REQUIRED_KEYS.issubset(schema["required"]))
        self.assertTrue(set(DEFAULT_CONFIG).issubset(properties))
        self.assertEqual(properties["workflow_key"]["default"], "default")

    def test_main_config_and_example_configs_load_with_runtime_loader(self) -> None:
        settings = load_settings(self.main_config_path)
        self.assertEqual(settings.duplicate_handling, "timestamp")
        self.assertEqual(settings.workflow_key, "default")
        self.assertRegex(settings.config_version, r"^[0-9a-f]{12}$")

        self.assertEqual(len(self.example_config_paths), 3)
        for config_path in self.example_config_paths:
            with self.subTest(config=config_path.name):
                example_settings = load_settings(config_path)
                self.assertEqual(example_settings.barcode_value_patterns, ())
                self.assertIn(example_settings.duplicate_handling, {"timestamp", "reject"})
                self.assertTrue(str(example_settings.input_path).startswith(str(self.repo_root / "data")))
                self.assertRegex(example_settings.config_version, r"^[0-9a-f]{12}$")

    def test_example_workflow_configs_encode_expected_operating_split(self) -> None:
        expected = {
            "config.receiving.example.json": {
                "duplicate_handling": "reject",
                "workflow_key": "receiving",
            },
            "config.shipping-pod.example.json": {
                "duplicate_handling": "timestamp",
                "workflow_key": "shipping_pod",
            },
            "config.quality-compliance.example.json": {
                "duplicate_handling": "reject",
                "workflow_key": "quality_compliance",
            },
        }

        actual = {}
        for config_path in self.example_config_paths:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            actual[config_path.name] = {
                "duplicate_handling": payload["duplicate_handling"],
                "workflow_key": payload["workflow_key"],
            }
            self.assertEqual(payload["barcode_value_patterns"], [])

        self.assertEqual(actual, expected)

    def test_builder_handoff_artifacts_exist(self) -> None:
        for artifact_path in self.critical_builder_docs:
            with self.subTest(artifact=str(artifact_path.relative_to(self.repo_root))):
                self.assertTrue(artifact_path.exists(), f"Missing builder artifact: {artifact_path}")

    def test_markdown_builder_docs_carry_last_updated_marker(self) -> None:
        for artifact_path in self.critical_builder_docs:
            if artifact_path.suffix.lower() != ".md":
                continue
            with self.subTest(artifact=str(artifact_path.relative_to(self.repo_root))):
                content = artifact_path.read_text(encoding="utf-8")
                self.assertIn("Last updated:", content)

    def test_readme_and_current_truth_point_to_verified_builder_entry(self) -> None:
        readme = self.readme_path.read_text(encoding="utf-8")
        current_truth = self.current_system_truth_path.read_text(encoding="utf-8")

        self.assertIn("docs/current-system-truth.md", readme)
        self.assertIn("docs/danpack-builder-handoff.md", readme)
        self.assertIn("docs/production-operations-blueprint.md", readme)
        self.assertIn("docs/builder-execution-plan.md", readme)
        self.assertIn("docs/scan-record-workbench.md", readme)
        self.assertIn("docs/scan-record-builder-handoff.md", readme)
        self.assertIn("docs/operations-planner-product-spec.md", readme)
        self.assertIn("docs/operations-planner-builder-handoff.md", readme)
        self.assertIn("do not assume this workspace has Git metadata", readme)

        self.assertIn("py -B -m unittest discover -s tests -v", current_truth)
        self.assertIn("py -m compileall app tests main.py stats.py", current_truth)
        self.assertIn("Last updated:", current_truth)
        self.assertIn("docs/scan-record-workbench.md", current_truth)
        self.assertIn("docs/scan-record-builder-handoff.md", current_truth)
        self.assertIn("docs/operations-planner-product-spec.md", current_truth)
        self.assertIn("docs/operations-planner-builder-handoff.md", current_truth)
        self.assertIn("this workspace may not be a Git checkout", current_truth)
        self.assertIn("the codebase plus tests are the runtime truth", current_truth)
        self.assertIn("TECHNICAL_ARCHITECTURE_SPECIFICATION.md", current_truth)

    def test_runtime_contract_docs_match_verified_barcode_selection_rules(self) -> None:
        contract_fragments = [
            "`barcode_value_patterns` affect routing priority, but they do not create separate ambiguity or pattern-mismatch states",
            "after barcode selection, the chosen barcode is rejected as `INVALID_BARCODE_FORMAT` if it fails business-rule matching or filename safety rules",
            "the best candidate across the scanned document wins deterministically by business-rule match, then largest bounding box area, then earlier page number, then scan order",
            "- barcode text must still satisfy filename safety rules: printable characters only, length `4..64`, and characters limited to alphanumeric, dash, and underscore",
        ]
        contract_docs = [
            self.readme_path,
            self.repo_root / "docs" / "danpack-builder-handoff.md",
            self.repo_root / "docs" / "production-operations-blueprint.md",
        ]

        for doc_path in contract_docs:
            content = doc_path.read_text(encoding="utf-8")
            for fragment in contract_fragments:
                with self.subTest(doc=str(doc_path.relative_to(self.repo_root)), fragment=fragment):
                    self.assertIn(fragment, content)

    def test_runtime_docs_record_phase_one_hardening_state(self) -> None:
        readme = self.readme_path.read_text(encoding="utf-8")
        current_truth = self.current_system_truth_path.read_text(encoding="utf-8")
        execution_plan = (
            self.repo_root / "docs" / "builder-execution-plan.md"
        ).read_text(encoding="utf-8")
        production_blueprint = (
            self.repo_root / "docs" / "production-operations-blueprint.md"
        ).read_text(encoding="utf-8")

        self.assertIn("`workflow_key`", readme)
        self.assertIn("`schema_version`, `workflow`, `host`, `instance_id`, `config_version`, and `error_code`", readme)
        self.assertIn("magic-byte validation", readme)
        self.assertIn("startup lock", readme)
        self.assertIn("processing/.journal", readme)
        self.assertIn("heartbeat", readme)
        self.assertIn("processing_log.YYYY-MM-DD.jsonl", readme)

        self.assertIn("workflow_key", current_truth)
        self.assertIn("magic-byte validation", current_truth)
        self.assertIn("schema_version", current_truth)
        self.assertIn("startup lock", current_truth)
        self.assertIn("processing/.journal", current_truth)
        self.assertIn("heartbeat", current_truth)
        self.assertIn("date-stamped archives", current_truth)

        self.assertIn("Phase 1 is complete", execution_plan)
        self.assertIn("Phase 2 is complete", execution_plan)
        self.assertIn("Phase 3 is in progress", execution_plan)
        self.assertIn("magic-byte validation", execution_plan)
        self.assertIn("canonical error-code enum", execution_plan)
        self.assertIn("startup lock", execution_plan)
        self.assertIn("processing/.journal", execution_plan)
        self.assertIn("heartbeat", execution_plan)
        self.assertIn("processing_log.YYYY-MM-DD.jsonl", execution_plan)

        self.assertIn("\"workflow_key\": \"default|receiving|shipping_pod|quality_compliance\"", production_blueprint)
        self.assertIn("\"schema_version\": \"1.0\"", production_blueprint)
        self.assertIn("\"error_code\": \"string|null\"", production_blueprint)
        self.assertIn("startup lock", production_blueprint)
        self.assertIn("processing/.journal", production_blueprint)
        self.assertIn("heartbeat", production_blueprint)
        self.assertIn("processing_log.YYYY-MM-DD.jsonl", production_blueprint)

    def test_scan_record_handoff_matches_runtime_contract_summary(self) -> None:
        scan_record_handoff = (
            self.repo_root / "docs" / "scan-record-builder-handoff.md"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "when barcode candidates are found but the selected value does not match the configured business rule, the runtime rejects as `INVALID_BARCODE_FORMAT`",
            scan_record_handoff,
        )
        self.assertIn(
            "the runtime selects one candidate deterministically across the scanned document by business-rule match, then largest bounding box area, then earlier page number, then scan order",
            scan_record_handoff,
        )
        self.assertIn(
            "the runtime uses the configured business rules to prioritize candidates rather than to create a separate ambiguity state",
            scan_record_handoff,
        )
        self.assertIn(
            "`eligible_candidate_values` and `page_one_eligible_values` are still emitted as evidence fields for the future page, even though they are not current selection overrides",
            scan_record_handoff,
        )

    def test_runtime_contract_docs_do_not_claim_nonexistent_terminal_states(self) -> None:
        runtime_docs = [
            self.readme_path,
            self.repo_root / "docs" / "danpack-builder-handoff.md",
            self.repo_root / "docs" / "production-operations-blueprint.md",
            self.repo_root / "docs" / "scan-record-builder-handoff.md",
        ]

        for doc_path in runtime_docs:
            content = doc_path.read_text(encoding="utf-8")
            with self.subTest(doc=str(doc_path.relative_to(self.repo_root)), code="BARCODE_PATTERN_MISMATCH"):
                self.assertNotIn("`BARCODE_PATTERN_MISMATCH`", content)
            with self.subTest(doc=str(doc_path.relative_to(self.repo_root)), code="MULTIPLE_BARCODES_FOUND"):
                self.assertNotIn("`MULTIPLE_BARCODES_FOUND`", content)

    def test_scan_record_json_artifacts_parse(self) -> None:
        schema = json.loads(
            (self.repo_root / "docs" / "contracts" / "scan-record.schema.json").read_text(
                encoding="utf-8"
            )
        )
        example = json.loads(
            (self.repo_root / "docs" / "examples" / "scan-record.example.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(schema["type"], "object")
        self.assertIn("scan_id", example)
        self.assertTrue(example["scan_id"].startswith("scan_"))

    def test_operations_planner_json_artifacts_parse(self) -> None:
        report_schema = json.loads(
            (self.repo_root / "docs" / "contracts" / "report-snapshot.schema.json").read_text(
                encoding="utf-8"
            )
        )
        report_example = json.loads(
            (self.repo_root / "docs" / "examples" / "report-snapshot.example.json").read_text(
                encoding="utf-8"
            )
        )
        obligation_schema = json.loads(
            (self.repo_root / "docs" / "contracts" / "scan-obligation.schema.json").read_text(
                encoding="utf-8"
            )
        )
        obligation_example = json.loads(
            (self.repo_root / "docs" / "examples" / "scan-obligation.example.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(report_schema["type"], "object")
        self.assertIn("report_snapshot_id", report_example)
        self.assertEqual(report_example["report_key"], "tomorrow")
        self.assertEqual(report_example["report_kind"], "projection")

        self.assertEqual(obligation_schema["type"], "object")
        self.assertIn("obligation_id", obligation_example)
        self.assertEqual(obligation_example["status"], "overdue")
        self.assertEqual(obligation_example["workflow_key"], "shipping_pod")

    def test_operations_planner_handoff_stays_dependency_aware(self) -> None:
        planner_handoff = (
            self.repo_root / "docs" / "operations-planner-builder-handoff.md"
        ).read_text(encoding="utf-8")

        self.assertIn("Do not build the planner directly on top of ad hoc log-file parsing", planner_handoff)
        self.assertIn("1. stabilize runtime event truth", planner_handoff)
        self.assertIn("2. persist normalized operational state", planner_handoff)
        self.assertIn("3. introduce obligations", planner_handoff)
        self.assertIn("4. generate immutable reports", planner_handoff)
        self.assertIn("5. build planner surfaces on top of those contracts", planner_handoff)


if __name__ == "__main__":
    unittest.main()
