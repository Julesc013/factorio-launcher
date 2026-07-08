from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_x_os_02", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_x_os_02"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


COMMAND_VECTORS = [
    ["capability", "status"],
    ["capability", "scan"],
    ["capability", "ledger"],
    ["capability", "overclaim-report"],
    ["capability", "validate"],
]


def write_fixture(root: Path) -> None:
    (root / ".aide/capabilities").mkdir(parents=True)
    (root / ".aide/reports").mkdir(parents=True)
    (root / ".aide/scripts").mkdir(parents=True)
    (root / ".aide/scripts/tests").mkdir(parents=True)
    (root / ".aide/evals/golden-tasks/capability_command_surface_golden").mkdir(parents=True)
    (root / "docs/reference").mkdir(parents=True)
    (root / ".aide/scripts/aide_lite.py").write_text("# command surface fixture\n", encoding="utf-8")
    (root / ".aide/scripts/tests/test_fixture.py").write_text("# test fixture\n", encoding="utf-8")
    (root / ".aide/evals/golden-tasks/capability_command_surface_golden/task.yaml").write_text("id: capability_command_surface_golden\n", encoding="utf-8")
    (root / "docs/reference/capability-reality-ledger.md").write_text("# Capability Reality Ledger\n", encoding="utf-8")
    (root / ".aide/capabilities/capability-seeds.yaml").write_text(
        "\n".join(
            [
                "schema_version: aide.capability-seeds.v0",
                "seeds:",
                "  - capability_id: fixture_report_command",
                "    title: Fixture Report Command",
                "    description: Fixture report-only command.",
                "    expected_state: exposed",
                "    expected_modifiers:",
                "      - report_only",
                "      - no_call",
                "    expected_evidence_hints:",
                "      - .aide/scripts/aide_lite.py",
                "      - docs/reference/capability-reality-ledger.md",
                "      - .aide/scripts/tests/test_fixture.py",
                "      - .aide/evals/golden-tasks/capability_command_surface_golden/task.yaml",
                "    known_limits:",
                "      - command is report-only",
                "  - capability_id: fixture_unknown",
                "    title: Fixture Unknown",
                "    description: Fixture unknown state.",
                "    expected_state: unknown",
                "    expected_modifiers:",
                "      - unknown",
                "    expected_evidence_hints:",
                "      - missing/evidence.md",
                "    known_limits:",
                "      - intentionally unverified",
                "",
            ]
        ),
        encoding="utf-8",
    )


class XOS02CapabilityRealityTests(unittest.TestCase):
    def test_parser_accepts_capability_commands(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        for command in COMMAND_VECTORS:
            parsed = parser.parse_args(command)
            self.assertTrue(callable(getattr(parsed, "handler", None)), command)

    def test_fixture_ledger_generation_is_no_apply(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_fixture(root)
            aide_lite.write_capability_scan(root)
            aide_lite.write_capability_ledger(root)
            ledger = json.loads((root / aide_lite.CAPABILITY_LEDGER_JSON_PATH).read_text(encoding="utf-8"))
            self.assertEqual(ledger["schema_version"], "aide.capability-ledger.v0")
            self.assertEqual(ledger["mode"], "report_only")
            self.assertIs(ledger["no_apply_boundary"]["task_execution"], False)
            self.assertIs(ledger["no_apply_boundary"]["repair_execution"], False)
            self.assertIs(ledger["no_apply_boundary"]["branch_mutation"], False)
            self.assertIs(ledger["no_apply_boundary"]["target_mutation"], False)
            self.assertEqual(ledger["no_apply_boundary"]["provider_or_model_calls"], "none")
            self.assertEqual(ledger["no_apply_boundary"]["network_calls"], "none")
            states = {record["dominant_state"] for record in ledger["records"]}
            self.assertIn("exposed", states)
            self.assertIn("unknown", states)
            markdown = (root / aide_lite.CAPABILITY_LEDGER_MD_PATH).read_text(encoding="utf-8")
            for marker in ["report_only", "target_mutation: false", "provider_or_model_calls: none", "network_calls: none"]:
                self.assertIn(marker, markdown)

    def test_overclaim_detector_flags_bad_claim(self) -> None:
        ledger = {
            "records": [
                {
                    "capability_id": "bad_docs_claim",
                    "dominant_state": "implemented",
                    "modifiers": ["docs_only"],
                    "evidence_classes": ["docs_only"],
                    "evidence_refs": ["docs/reference/example.md"],
                    "limitations": [],
                }
            ]
        }
        records = aide_lite.capability_overclaim_records(ledger)
        self.assertEqual(records[0]["overclaim_class"], "docs_only_claimed_as_implemented")
        self.assertIs(records[0]["blocking"], True)

    def test_current_repo_validation_registration_passes_without_reports(self) -> None:
        checks = aide_lite.validate_capability_files(REPO_ROOT, require_reports=False)
        failures = [check.message for check in checks if check.severity == "FAIL"]
        self.assertEqual(failures, [])

    def test_x_os_02_golden_runners_are_registered(self) -> None:
        definitions = {task.task_id for task in aide_lite.parse_golden_task_catalog(REPO_ROOT)}
        for task_id in aide_lite.CAPABILITY_GOLDEN_TASK_IDS:
            self.assertIn(task_id, definitions)


if __name__ == "__main__":
    unittest.main()
