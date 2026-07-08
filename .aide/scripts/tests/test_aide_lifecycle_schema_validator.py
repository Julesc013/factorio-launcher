from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lifecycle_schema_validator", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lifecycle_schema_validator"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


COMMAND_VECTORS = [
    ["lifecycle-schema", "status"],
    ["lifecycle-schema", "validate"],
    ["lifecycle-schema", "fixture-verify"],
]


def copy_lifecycle_validator_files(root: Path) -> None:
    for rel in [*aide_lite.LIFECYCLE_SCHEMA_REQUIRED_FILES, ".aide/scripts/aide_lite.py"]:
        source = REPO_ROOT / rel
        if source.exists():
            aide_lite.copy_pack_file(source, root / rel)


def rewrite_json(root: Path, rel: str, transform) -> None:
    path = root / rel
    data = json.loads(path.read_text(encoding="utf-8"))
    transformed = transform(data)
    path.write_text(json.dumps(transformed, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def failure_messages(checks: list[object]) -> list[str]:
    return [check.message for check in checks if check.severity == "FAIL"]


class AIDELifecycleSchemaValidatorTests(unittest.TestCase):
    def test_parser_accepts_lifecycle_schema_commands(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        for command in COMMAND_VECTORS:
            parsed = parser.parse_args(command)
            self.assertTrue(callable(getattr(parsed, "handler", None)), command)

    def test_current_repo_lifecycle_schema_validation_passes_without_reports(self) -> None:
        checks = aide_lite.validate_lifecycle_schema_files(REPO_ROOT, require_reports=False)
        self.assertEqual(failure_messages(checks), [])

    def test_validation_writes_reports_without_materializing_fixture_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_lifecycle_validator_files(root)
            target_root = root / ".aide/examples/apply/lifecycle-fixtures/target"
            self.assertFalse(target_root.exists())
            json_result, md_result, checks, data = aide_lite.write_lifecycle_schema_validation_outputs(root)
            fixture_json, fixture_md, fixture_checks, fixture_data = aide_lite.write_lifecycle_schema_fixture_validation_outputs(root)
            self.assertIn(json_result.action, {"written", "unchanged"})
            self.assertIn(md_result.action, {"written", "unchanged"})
            self.assertIn(fixture_json.action, {"written", "unchanged"})
            self.assertIn(fixture_md.action, {"written", "unchanged"})
            self.assertEqual(failure_messages(checks), [])
            self.assertEqual(failure_messages(fixture_checks), [])
            self.assertEqual(data["result"], "PASS")
            self.assertEqual(fixture_data["result"], "PASS")
            self.assertFalse(target_root.exists())

    def test_missing_schema_version_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_lifecycle_validator_files(root)
            rewrite_json(
                root,
                ".aide/examples/apply/lifecycle/lifecycle-plan.report-only.example.json",
                lambda data: {key: value for key, value in data.items() if key != "schema_version"},
            )
            checks = aide_lite.validate_lifecycle_schema_files(root, require_reports=False)
            self.assertTrue(any("schema_version" in message for message in failure_messages(checks)))

    def test_target_apply_and_mutation_claims_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_lifecycle_validator_files(root)

            def mutate(data: dict[str, object]) -> dict[str, object]:
                data["mode"] = "target-apply"
                data["fixture_only"] = False
                data["target_files_mutated_expected"] = True
                return data

            rewrite_json(root, ".aide/examples/apply/lifecycle/lifecycle-plan.report-only.example.json", mutate)
            messages = failure_messages(aide_lite.validate_lifecycle_schema_files(root, require_reports=False))
            self.assertTrue(any("non-mutating report/dry-run" in message for message in messages))
            self.assertTrue(any("fixture_only true" in message for message in messages))
            self.assertTrue(any("target_files_mutated_expected false" in message for message in messages))

    def test_protected_and_traversal_paths_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_lifecycle_validator_files(root)

            def mutate(data: dict[str, object]) -> dict[str, object]:
                data["explicit_paths"] = [".git/config", "../escape.md"]
                operations = data["explicit_operations"]
                assert isinstance(operations, list)
                operations[0]["path"] = "../escape.md"
                return data

            rewrite_json(root, ".aide/examples/apply/lifecycle/lifecycle-plan.report-only.example.json", mutate)
            messages = failure_messages(aide_lite.validate_lifecycle_schema_files(root, require_reports=False))
            self.assertTrue(any("avoids protected paths" in message for message in messages))
            self.assertTrue(any("traversal-safe" in message for message in messages))

    def test_unsupported_operation_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_lifecycle_validator_files(root)

            def mutate(data: dict[str, object]) -> dict[str, object]:
                data["operation_allowlist"] = ["delete"]
                operations = data["explicit_operations"]
                assert isinstance(operations, list)
                operations[0]["operation_type"] = "delete"
                return data

            rewrite_json(root, ".aide/examples/apply/lifecycle/lifecycle-plan.report-only.example.json", mutate)
            messages = failure_messages(aide_lite.validate_lifecycle_schema_files(root, require_reports=False))
            self.assertTrue(any("operation allowlist stays report/validate/noop/managed-section only" in message for message in messages))
            self.assertTrue(any("not prohibited: delete" in message for message in messages))

    def test_rollback_execution_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_lifecycle_validator_files(root)
            rewrite_json(root, ".aide/examples/apply/lifecycle/lifecycle-rollback-record.example.json", lambda data: {**data, "rollback_execution_implemented": True})
            messages = failure_messages(aide_lite.validate_lifecycle_schema_files(root, require_reports=False))
            self.assertTrue(any("rollback execution remains false" in message for message in messages))

    def test_fixture_spec_traversal_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_lifecycle_validator_files(root)
            rewrite_json(root, ".aide/examples/apply/lifecycle/fixture-repository-spec.example.json", lambda data: {**data, "target_root_path": "../target"})
            messages = failure_messages(aide_lite.lifecycle_fixture_shape_checks(root))
            self.assertTrue(any("Lifecycle fixture spec root matches plan: target_root_path" in message for message in messages))
            self.assertTrue(any("traversal-safe: target_root_path" in message for message in messages))

    def test_validator_does_not_require_jsonschema_import(self) -> None:
        script_text = (REPO_ROOT / ".aide/scripts/aide_lite.py").read_text(encoding="utf-8")
        self.assertNotRegex(script_text, r"(?m)^\s*import\s+jsonschema\b")


if __name__ == "__main__":
    unittest.main()
