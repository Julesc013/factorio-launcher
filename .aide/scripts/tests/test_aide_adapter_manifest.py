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

from core.protocol import adapter_manifest

MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_adapter_manifest", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_adapter_manifest"] = aide_lite
SPEC.loader.exec_module(aide_lite)


def copy_adapter_manifest_files(root: Path) -> None:
    for rel in adapter_manifest.source_artifact_paths(REPO_ROOT):
        src = REPO_ROOT / rel
        if src.exists():
            dst = root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


class AIDEAdapterManifestTests(unittest.TestCase):
    def test_schema_file_exists_and_parses(self) -> None:
        schema = adapter_manifest.load_adapter_manifest_schema(REPO_ROOT)
        self.assertEqual(schema["title"], "AIDE Minimal AdapterManifest")
        self.assertEqual(schema["properties"]["kind"]["enum"], ["AdapterManifest"])

    def test_valid_minimal_adapter_manifest_passes_with_warnings(self) -> None:
        record = adapter_manifest.build_adapter_manifest(REPO_ROOT)
        schema = adapter_manifest.load_adapter_manifest_schema(REPO_ROOT)
        errors, warnings = adapter_manifest.validate_adapter_manifest_with_schema(record, schema)
        self.assertEqual(errors, [])
        self.assertTrue(warnings)
        self.assertEqual(record["kind"], "AdapterManifest")
        self.assertFalse(record["status"]["admitted"])
        self.assertFalse(record["status"]["trusted"])

    def test_stable_adapter_reference_form(self) -> None:
        record = adapter_manifest.build_adapter_manifest(REPO_ROOT)
        self.assertEqual(record["spec"]["adapter_ref"], "aide://adapter/minimal-local-disposable-worker-declaration-01")

    def test_projection_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_adapter_manifest_files(root)
            adapter_manifest.write_adapter_manifest_reports(root)
            first = (root / adapter_manifest.MANIFESTS_JSON).read_text(encoding="utf-8")
            adapter_manifest.write_adapter_manifest_reports(root)
            second = (root / adapter_manifest.MANIFESTS_JSON).read_text(encoding="utf-8")
        self.assertEqual(first, second)

    def test_projection_does_not_mutate_source_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_adapter_manifest_files(root)
            sources = [root / rel for rel in adapter_manifest.source_artifact_paths(root)]
            before = {path.as_posix(): path.read_bytes() for path in sources if path.exists()}
            report = adapter_manifest.write_adapter_manifest_reports(root)
            after = {path.as_posix(): path.read_bytes() for path in sources if path.exists()}
        self.assertEqual(before, after)
        self.assertFalse(report["source_artifacts_mutated"])

    def test_unknown_required_capability_fails_closed(self) -> None:
        record = adapter_manifest.build_adapter_manifest(REPO_ROOT)
        record["spec"]["required_capability_refs"].append("aide://capability/unknown-capability")
        errors, _warnings = adapter_manifest.validate_adapter_manifest_with_schema(record, {})
        self.assertTrue(any("unknown capability ref" in item for item in errors))

    def test_wrong_kind_refs_fail_closed(self) -> None:
        record = adapter_manifest.build_adapter_manifest(REPO_ROOT)
        record["spec"]["adapter_ref"] = "aide://capability/not-an-adapter"
        record["spec"]["required_conformance_result_refs"] = ["aide://capability/not-a-result"]
        errors, _warnings = adapter_manifest.validate_adapter_manifest_with_schema(record, {})
        self.assertTrue(any("reference kind must be adapter" in item for item in errors))
        self.assertTrue(any("reference kind must be conformance-result" in item for item in errors))

    def test_conformance_result_ref_does_not_set_trusted(self) -> None:
        record = adapter_manifest.build_adapter_manifest(REPO_ROOT)
        self.assertTrue(record["spec"]["required_conformance_result_refs"])
        self.assertFalse(record["status"]["trusted"])
        errors, _warnings = adapter_manifest.validate_adapter_manifest_with_schema(record, {})
        self.assertEqual(errors, [])

    def test_admission_or_trust_true_fails(self) -> None:
        for field in ["admission_performed", "admitted", "trusted"]:
            record = adapter_manifest.build_adapter_manifest(REPO_ROOT)
            record["status"][field] = True
            errors, _warnings = adapter_manifest.validate_adapter_manifest_with_schema(record, {})
            self.assertTrue(any(f"status.{field}" in item for item in errors))

    def test_execution_network_credentials_and_target_mutation_fail(self) -> None:
        for field in ["execution_performed", "worker_started", "network_call_performed", "credential_resolution_performed", "target_mutated"]:
            record = adapter_manifest.build_adapter_manifest(REPO_ROOT)
            record["status"][field] = True
            errors, _warnings = adapter_manifest.validate_adapter_manifest_with_schema(record, {})
            self.assertTrue(any(f"status.{field}" in item for item in errors))

    def test_unknown_integration_surface_fails(self) -> None:
        record = adapter_manifest.build_adapter_manifest(REPO_ROOT)
        record["spec"]["integration_surfaces"].append("launch_provider")
        errors, _warnings = adapter_manifest.validate_adapter_manifest_with_schema(record, {})
        self.assertTrue(any("unknown integration surface" in item for item in errors))

    def test_explicit_non_capabilities_remain_present(self) -> None:
        record = adapter_manifest.build_adapter_manifest(REPO_ROOT)
        self.assertEqual(record["spec"]["explicit_non_capabilities"], adapter_manifest.EXPLICIT_NON_CAPABILITIES)

    def test_cli_status_project_validate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_adapter_manifest_files(root)
            for command in ["status", "project", "validate"]:
                with self.subTest(command=command):
                    exit_code = aide_lite.main(["--repo-root", str(root), "adapter-manifest", command])
                    self.assertEqual(exit_code, 0)
            report = json.loads((root / adapter_manifest.VALIDATION_JSON).read_text(encoding="utf-8"))
            self.assertEqual(report["validation_status"], "PASS_WITH_WARNINGS")


if __name__ == "__main__":
    unittest.main()
