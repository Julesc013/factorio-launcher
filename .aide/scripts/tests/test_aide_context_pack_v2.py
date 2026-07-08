import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.protocol import context_pack_v2

MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_context_pack_v2", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_context_pack_v2"] = aide_lite
SPEC.loader.exec_module(aide_lite)


def context_pack_source_paths() -> list[str]:
    paths = set(context_pack_v2.source_artifact_paths(REPO_ROOT))
    record = context_pack_v2.build_context_pack(REPO_ROOT)
    for item in record["spec"]["source_refs"]:
        paths.add(item["path"])
    return sorted(paths)


def copy_context_pack_files(root: Path) -> None:
    for rel in context_pack_source_paths():
        src = REPO_ROOT / rel
        if src.exists():
            dst = root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


class AIDEContextPackV2Tests(unittest.TestCase):
    def test_schema_file_exists_and_parses(self) -> None:
        schema = context_pack_v2.load_context_pack_schema(REPO_ROOT)
        self.assertEqual(schema["title"], "AIDE Minimal ContextPack v2")
        self.assertEqual(schema["properties"]["kind"]["enum"], ["ContextPack"])

    def test_valid_minimal_context_pack_passes_with_warnings(self) -> None:
        record = context_pack_v2.build_context_pack(REPO_ROOT)
        schema = context_pack_v2.load_context_pack_schema(REPO_ROOT)
        errors, warnings = context_pack_v2.validate_context_pack_with_schema(record, schema)
        self.assertEqual(errors, [])
        self.assertTrue(warnings)
        self.assertEqual(record["kind"], "ContextPack")
        self.assertFalse(record["status"]["model_call_performed"])
        self.assertFalse(record["status"]["repository_mutated"])
        self.assertFalse(record["status"]["trusted"])

    def test_stable_context_pack_reference_form(self) -> None:
        record = context_pack_v2.build_context_pack(REPO_ROOT)
        self.assertEqual(record["spec"]["context_pack_ref"], "aide://context-pack/minimal-context-pack-v2-01")

    def test_projection_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_context_pack_files(root)
            context_pack_v2.write_context_pack_reports(root)
            first = (root / context_pack_v2.PACK_JSON).read_text(encoding="utf-8")
            context_pack_v2.write_context_pack_reports(root)
            second = (root / context_pack_v2.PACK_JSON).read_text(encoding="utf-8")
        self.assertEqual(first, second)

    def test_projection_does_not_mutate_source_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_context_pack_files(root)
            sources = [root / rel for rel in context_pack_source_paths()]
            before = {path.as_posix(): path.read_bytes() for path in sources if path.exists()}
            report = context_pack_v2.write_context_pack_reports(root)
            after = {path.as_posix(): path.read_bytes() for path in sources if path.exists()}
        self.assertEqual(before, after)
        self.assertFalse(report["source_artifacts_mutated"])

    def test_missing_required_section_fails(self) -> None:
        record = context_pack_v2.build_context_pack(REPO_ROOT)
        record["spec"]["sections"] = [item for item in record["spec"]["sections"] if item["id"] != "okf"]
        errors, _warnings = context_pack_v2.validate_context_pack_with_schema(record, {})
        self.assertTrue(any("missing required sections" in item for item in errors))

    def test_wrong_reference_kind_fails_closed(self) -> None:
        record = context_pack_v2.build_context_pack(REPO_ROOT)
        record["spec"]["context_pack_ref"] = "aide://capability/not-a-context-pack"
        record["spec"]["required_evidence_refs"] = ["aide://capability/not-evidence"]
        errors, _warnings = context_pack_v2.validate_context_pack_with_schema(record, {})
        self.assertTrue(any("reference kind must be context-pack" in item for item in errors))
        self.assertTrue(any("reference kind must be evidence" in item for item in errors))

    def test_missing_source_path_fails(self) -> None:
        record = context_pack_v2.build_context_pack(REPO_ROOT)
        record["spec"]["source_refs"][0]["exists"] = False
        errors, _warnings = context_pack_v2.validate_context_pack_with_schema(record, {})
        self.assertTrue(any("source path must exist" in item for item in errors))

    def test_invalid_source_digest_fails(self) -> None:
        record = context_pack_v2.build_context_pack(REPO_ROOT)
        record["spec"]["source_refs"][0]["sha256"] = "sha256:not-hex"
        errors, _warnings = context_pack_v2.validate_context_pack_with_schema(record, {})
        self.assertTrue(any("source sha256" in item for item in errors))

    def test_execution_status_flags_true_fail(self) -> None:
        for field in context_pack_v2.FALSE_STATUS_FIELDS:
            record = context_pack_v2.build_context_pack(REPO_ROOT)
            record["status"][field] = True
            errors, _warnings = context_pack_v2.validate_context_pack_with_schema(record, {})
            self.assertTrue(any(f"status.{field}" in item for item in errors))

    def test_unknown_required_capability_fails_closed(self) -> None:
        record = context_pack_v2.build_context_pack(REPO_ROOT)
        record["spec"]["required_capability_refs"].append("aide://capability/unknown-capability")
        errors, _warnings = context_pack_v2.validate_context_pack_with_schema(record, {})
        self.assertTrue(any("unknown capability ref" in item for item in errors))

    def test_explicit_non_capabilities_remain_present(self) -> None:
        record = context_pack_v2.build_context_pack(REPO_ROOT)
        self.assertEqual(record["spec"]["explicit_non_capabilities"], context_pack_v2.EXPLICIT_NON_CAPABILITIES)
        self.assertIn("model_calls", record["spec"]["explicit_non_capabilities"])
        self.assertIn("patch_application", record["spec"]["explicit_non_capabilities"])

    def test_cli_status_project_validate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_context_pack_files(root)
            for command in ["status", "project", "validate"]:
                with self.subTest(command=command):
                    exit_code = aide_lite.main(["--repo-root", str(root), "context-pack-v2", command])
                    self.assertEqual(exit_code, 0)
            report = json.loads((root / context_pack_v2.VALIDATION_JSON).read_text(encoding="utf-8"))
            self.assertEqual(report["validation_status"], "PASS_WITH_WARNINGS")


if __name__ == "__main__":
    unittest.main()
