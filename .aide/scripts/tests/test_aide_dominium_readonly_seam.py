import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.interop import dominium
from core.interop.dominium import conformance, models, references, validation

MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_dominium_readonly_seam", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_dominium_readonly_seam"] = aide_lite
SPEC.loader.exec_module(aide_lite)


def write_text(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(root: Path, rel: str, data: dict) -> None:
    write_text(root, rel, json.dumps(data, indent=2, sort_keys=True) + "\n")


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def create_dominium_fixture(root: Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True, text=True)
    run_git(root, "config", "user.email", "aide-tests@example.invalid")
    run_git(root, "config", "user.name", "AIDE Tests")
    run_git(root, "remote", "add", "origin", "https://github.com/Julesc013/dominium.git")
    write_text(root, "AGENTS.md", "# Dominium Operating Law\n\nFixture authority input.\n")
    write_text(
        root,
        ".aide/queue/current.toml",
        "\n".join(
            [
                'schema_version = "dominium.queue.current.v1"',
                'status = "needs_review"',
                "",
                "[current]",
                'current_task = "DOMINIUM-FIXTURE-READONLY-SEAM"',
                'result = "PASS"',
                'next_task = "DOMINIUM-FIXTURE-CHECK"',
                "",
            ]
        ),
    )
    write_text(root, "docs/canon/constitution_v1.md", "# Constitution\n\nFixture constitution.\n")
    write_text(root, "docs/canon/glossary_v1.md", "# Glossary\n\nFixture glossary.\n")
    write_text(
        root,
        "contracts/command/command_surface.contract.toml",
        "\n".join(
            [
                'schema_version = "dominium.command.surface.v1"',
                'status = "provisional"',
                'owner = "contracts.command"',
                "",
                "[policy]",
                "workbench_is_authority = false",
                "aide_is_authority = false",
                "runtime_dispatch_implemented_here = false",
                "",
                "[[command]]",
                'id = "dominium.validation.run"',
                'version = "0.1.0"',
                'kind = "validation"',
                'owner = "tools.validators"',
                'surfaces = ["cli", "headless", "aide", "test"]',
                'required_capabilities = ["dominium.repo.validate"]',
                "",
                "[[command]]",
                'id = "dominium.repo.fast_strict.run"',
                'version = "0.1.0"',
                'kind = "test"',
                'owner = "tools.test"',
                'surfaces = ["cli", "headless", "aide", "test"]',
                "required_capabilities = []",
                "",
            ]
        ),
    )
    write_text(root, "contracts/service/service.contract.toml", 'schema_version = "dominium.service.surface.v1"\n')
    write_text(root, "contracts/module/module_surface.contract.toml", 'schema_version = "dominium.module.surface.v1"\n')
    write_text(
        root,
        "contracts/workbench/workbench_surface.contract.toml",
        'schema_version = "dominium.workbench.surface.v1"\nworkbench_is_authority = false\n',
    )
    write_json(
        root,
        "contracts/refusal/refusal_code.registry.json",
        {
            "schema_version": "dominium.refusal.code_registry.v1",
            "status": "provisional",
            "owner": "contracts.refusal",
            "codes": [
                {
                    "refusal_id": "dominium.refusal.validation.invalid_target",
                    "code": "dominium.refusal.validation.invalid_target",
                    "owner": "tools.validators",
                    "category": "validation",
                    "summary": "Invalid validation target.",
                    "reason": "The requested validation target is invalid.",
                    "recovery": {"action": "select_alternative"},
                    "diagnostic_codes": ["DOM-VALIDATION-INVALID-TARGET"],
                    "related_commands": ["dominium.validation.run"],
                },
                {
                    "refusal_id": "dominium.refusal.command.unsupported_surface",
                    "code": "dominium.refusal.command.unsupported_surface",
                    "owner": "contracts.command",
                    "category": "command",
                    "summary": "Unsupported command surface.",
                    "reason": "The requested command surface is unsupported.",
                    "recovery": {"action": "select_alternative"},
                    "diagnostic_codes": ["DOM-CMD-UNSUPPORTED-SURFACE"],
                    "related_commands": ["dominium.validation.run"],
                },
            ],
        },
    )
    write_json(
        root,
        "contracts/diagnostic/diagnostic_code.registry.json",
        {
            "schema_version": "dominium.diagnostics.code_registry.v1",
            "status": "provisional",
            "owner": "contracts.diagnostics",
            "codes": [
                {
                    "id": "dominium.diagnostic.validation.invalid_target",
                    "code": "DOM-VALIDATION-INVALID-TARGET",
                    "owner": "tools.validators",
                    "severity": "error",
                    "category": "validation",
                    "summary": "Validation target is invalid.",
                },
                {
                    "id": "dominium.diagnostic.validation.warning",
                    "code": "DOM-VALIDATION-WARNING",
                    "owner": "tools.validators",
                    "severity": "warning",
                    "category": "validation",
                    "summary": "Validation completed with warnings.",
                },
            ],
        },
    )
    write_json(
        root,
        "contracts/diagnostic/diagnostic_severity.registry.json",
        {
            "schema_version": "dominium.diagnostics.severity_registry.v1",
            "status": "provisional",
            "owner": "contracts.diagnostics",
            "severities": [{"id": "info"}, {"id": "warning"}, {"id": "error"}],
        },
    )
    write_json(
        root,
        "contracts/capability/capability.registry.json",
        {
            "schema_version": "dominium.capability.registry.v1",
            "status": "provisional",
            "owner": "contracts.capability",
            "capabilities": [{"id": "dominium.repo.validate"}],
        },
    )
    write_text(root, "contracts/project_graph/project_graph_model.contract.toml", 'schema_version = "dominium.project_graph.model.v1"\n')
    write_text(root, "docs/repo/audits/PRESENTATION_CONTRACT_01.md", "# Presentation Contract\n\nEvidence fixture.\n")
    write_text(root, "docs/repo/audits/WORKBENCH_VALIDATION_SLICE_01.md", "# Workbench Validation\n\nEvidence fixture.\n")
    write_text(root, "docs/development/workbench_validation_slice.md", "# Workbench Validation Plan\n\nPlan fixture.\n")
    write_text(root, "docs/development/command_result_view_slice.md", "# Command Result View Plan\n\nPlan fixture.\n")
    run_git(root, "add", ".")
    run_git(root, "commit", "-m", "fixture: add Dominium seam inputs")
    return run_git(root, "rev-parse", "HEAD")


def copy_dominium_seam_source_files(root: Path) -> None:
    for rel in models.required_runtime_dependency_paths():
        src = REPO_ROOT / rel
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


class AIDEDominiumReadonlySeamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tmp_root = Path(cls._tmp.name)
        cls.dom_root = cls.tmp_root / "dominium"
        cls.aide_root = cls.tmp_root / "aide"
        cls.revision = create_dominium_fixture(cls.dom_root)
        copy_dominium_seam_source_files(cls.aide_root)
        cls.project_report = dominium.project_dominium_seam(cls.aide_root, dominium_root=cls.dom_root, revision=cls.revision, write_portability=False)
        cls.bundle = models.read_json(cls.aide_root / models.SEAM_BUNDLE_JSON)
        cls.validation_report = validation.validate_bundle(cls.bundle, dominium_root=cls.dom_root)
        cls.conformance_report = conformance.conformance_results(cls.bundle, cls.validation_report, dominium_root=cls.dom_root)
        cls.negative_case_reports = {}
        for case in validation.negative_fixture_cases(cls.bundle):
            expected_codes = set(case["expected_error_codes"])
            root = cls.dom_root if expected_codes.intersection({"diagnostic.registry", "refusal.registry"}) else None
            cls.negative_case_reports[case["name"]] = validation.validate_bundle(case["bundle"], dominium_root=root)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def assertInvalid(self, bundle: dict, needle: str) -> None:
        report = validation.validate_bundle(bundle, dominium_root=self.dom_root)
        self.assertTrue(any(needle in item for item in report["errors"]), report["errors"])

    def test_001_snapshot_reads_clean_git_fixture(self) -> None:
        snapshot = dominium.snapshot_dominium_source(self.aide_root, dominium_root=self.dom_root, revision=self.revision)
        self.assertEqual(snapshot["source_revision"], self.revision)
        self.assertEqual(snapshot["selected_file_count"], len(models.SELECTED_DOMINIUM_INPUTS))

    def test_002_snapshot_records_no_mutating_git_operations(self) -> None:
        snapshot = self.bundle["source_snapshot"]
        self.assertFalse(snapshot["read_only_operations"]["git_fetch"])
        self.assertFalse(snapshot["read_only_operations"]["git_pull"])
        self.assertFalse(snapshot["read_only_operations"]["git_checkout"])
        self.assertFalse(snapshot["read_only_operations"]["dominium_file_write"])

    def test_003_project_generates_complete_bundle(self) -> None:
        self.assertEqual(self.project_report["status"], "PASS_WITH_WARNINGS")
        self.assertEqual(self.bundle["kind"], "DominiumReadonlySeamBundle")
        self.assertEqual(self.bundle["manifest"]["record_count"], 30)

    def test_004_validation_passes_with_expected_warnings(self) -> None:
        self.assertEqual(self.validation_report["validation_status"], "PASS_WITH_WARNINGS")
        self.assertEqual(self.validation_report["errors"], [])
        self.assertGreaterEqual(len(self.validation_report["warnings"]), 1)

    def test_005_projection_is_byte_deterministic(self) -> None:
        first = (self.aide_root / models.SEAM_BUNDLE_JSON).read_bytes()
        dominium.project_dominium_seam(self.aide_root, dominium_root=self.dom_root, revision=self.revision, write_portability=False)
        second = (self.aide_root / models.SEAM_BUNDLE_JSON).read_bytes()
        self.assertEqual(first, second)

    def test_006_diff_confirms_repeat_projection_equality(self) -> None:
        report = dominium.dominium_seam_diff(self.aide_root, dominium_root=self.dom_root, revision=self.revision)
        self.assertEqual(report["status"], "PASS")
        self.assertTrue(report["byte_equal"])

    def test_007_demo_confirms_source_immutability(self) -> None:
        before = run_git(self.dom_root, "status", "--short", "--branch")
        report = dominium.run_dominium_seam_demo(self.aide_root, dominium_root=self.dom_root, revision=self.revision)
        after = run_git(self.dom_root, "status", "--short", "--branch")
        self.assertEqual(report["status"], "PASS_WITH_WARNINGS")
        self.assertEqual(report["source_mutation_count"], 0)
        self.assertEqual(before, after)

    def test_008_status_reports_readonly_capability(self) -> None:
        report = dominium.dominium_seam_status(self.aide_root, dominium_root=self.dom_root, revision=self.revision)
        self.assertEqual(report["status"], "PASS_WITH_WARNINGS")
        self.assertTrue(report["schema_exists"])
        self.assertTrue(report["dominium_available"])

    def test_009_cli_status_snapshot_project_validate_diff_demo(self) -> None:
        previous = os.environ.get("AIDE_DOMINIUM_PORTABILITY_CHILD")
        os.environ["AIDE_DOMINIUM_PORTABILITY_CHILD"] = "1"
        try:
            for command in ["status", "snapshot", "project", "validate"]:
                with self.subTest(command=command):
                    exit_code = aide_lite.main(
                        [
                            "--repo-root",
                            str(self.aide_root),
                            "dominium-seam",
                            command,
                            "--dominium-root",
                            str(self.dom_root),
                            "--revision",
                            self.revision,
                        ]
                    )
                    self.assertEqual(exit_code, 0)
        finally:
            if previous is None:
                os.environ.pop("AIDE_DOMINIUM_PORTABILITY_CHILD", None)
            else:
                os.environ["AIDE_DOMINIUM_PORTABILITY_CHILD"] = previous

    def test_010_cli_unsupported_verbs_refuse(self) -> None:
        for command in ["run", "invoke", "execute", "apply", "write", "sync", "push", "serve", "connect", "dispatch"]:
            with self.subTest(command=command):
                exit_code = aide_lite.main(["--repo-root", str(self.aide_root), "dominium-seam", command])
                self.assertEqual(exit_code, 2)

    def test_011_wrong_repository_identity_rejected(self) -> None:
        run_git(self.dom_root, "remote", "set-url", "origin", "https://github.com/example/not-dominium.git")
        try:
            with self.assertRaises(Exception):
                dominium.snapshot_dominium_source(self.aide_root, dominium_root=self.dom_root, revision=self.revision)
        finally:
            run_git(self.dom_root, "remote", "set-url", "origin", "https://github.com/Julesc013/dominium.git")

    def test_012_revision_mismatch_rejected(self) -> None:
        with self.assertRaises(Exception):
            dominium.snapshot_dominium_source(self.aide_root, dominium_root=self.dom_root, revision="HEAD")

    def test_013_dirty_authoritative_input_rejected(self) -> None:
        write_text(self.dom_root, "UNTRACKED.txt", "dirty\n")
        try:
            with self.assertRaises(Exception):
                dominium.snapshot_dominium_source(self.aide_root, dominium_root=self.dom_root, revision=self.revision)
        finally:
            (self.dom_root / "UNTRACKED.txt").unlink()

    def test_014_path_traversal_normalization_fails(self) -> None:
        with self.assertRaises(ValueError):
            references.normalize_repo_path("../AGENTS.md")

    def test_015_absolute_path_normalization_fails(self) -> None:
        with self.assertRaises(ValueError):
            references.normalize_repo_path("/tmp/AGENTS.md")

    def test_016_drive_path_normalization_fails(self) -> None:
        with self.assertRaises(ValueError):
            references.normalize_repo_path("C:/tmp/AGENTS.md")

    def test_017_sha256_validation_accepts_snapshot_digests(self) -> None:
        for item in self.bundle["source_snapshot"]["selected_files"]:
            self.assertTrue(references.is_sha256(item["sha256"]), item["path"])

    def test_018_commit_sha_validation_accepts_revision(self) -> None:
        self.assertTrue(references.is_commit_sha(self.revision))
        self.assertTrue(references.is_commit_sha(self.bundle["manifest"]["source_revision"]))

    def test_019_unknown_optional_metadata_is_tolerated(self) -> None:
        candidate = copy.deepcopy(self.bundle)
        candidate["metadata"]["x_optional_future"] = {"preserve": True}
        report = validation.validate_bundle(candidate, dominium_root=self.dom_root)
        self.assertEqual(report["errors"], [])

    def test_020_unknown_required_capability_fails_closed(self) -> None:
        candidate = copy.deepcopy(self.bundle)
        candidate["metadata"]["compatibility"]["requiredCapabilities"] = ["future.required"]
        self.assertInvalid(candidate, "unknown required capability")

    def test_021_source_digest_mutation_fails(self) -> None:
        candidate = copy.deepcopy(self.bundle)
        candidate["source_snapshot"]["selected_files"][0]["sha256"] = "sha256:" + "0" * 64
        self.assertInvalid(candidate, "source digest mismatch")

    def test_022_projection_index_digest_binding_fails_on_record_change(self) -> None:
        candidate = copy.deepcopy(self.bundle)
        candidate["records"]["host_manifest"]["spec"]["host_id"] = "changed"
        self.assertInvalid(candidate, "projection index digest mismatch")

    def test_023_workbench_remains_non_authority(self) -> None:
        bridge = self.bundle["records"]["dominium_bridge_manifest"]["spec"]
        self.assertEqual(bridge["ownership"]["Workbench"], "presentation, context capture, preview, approval interaction, apply requests")
        self.assertFalse(self.bundle["records"]["workspace_descriptor"]["status"]["workbench_started"])

    def test_024_command_mapping_does_not_invoke_dominium(self) -> None:
        command_mapping = self.bundle["records"]["dominium_bridge_manifest"]["spec"]["command_mapping"]
        self.assertTrue(command_mapping["registered_validation_command_present"])
        self.assertFalse(command_mapping["command_invocation_implemented"])

    def test_025_evidence_refs_are_projection_only(self) -> None:
        evidence = self.bundle["records"]["evidence_reference_set"]["spec"]
        self.assertEqual(evidence["native_evidence_meaning_owned_by"], "Dominium")
        self.assertEqual(evidence["aide_behavior"], "reference_and_aggregate_only")

    def test_026_event_envelopes_do_not_create_event_store(self) -> None:
        for event in self.bundle["records"]["event_envelopes"]:
            self.assertFalse(event["spec"]["universal_event_store_implemented"])
            self.assertTrue(event["spec"]["correlation_ref"].startswith("aide://seam-bundle/"))

    def test_027_reports_are_written(self) -> None:
        for rel in models.REQUIRED_REPORTS:
            if rel == models.PORTABILITY_RESULT_JSON:
                continue
            self.assertTrue((self.aide_root / rel).exists(), rel)

    def test_028_fixture_manifest_is_written(self) -> None:
        manifest = models.read_json(self.aide_root / models.FIXTURE_MANIFEST_JSON)
        self.assertEqual(manifest["fixture_count"], 43)
        self.assertTrue(all(item["sha256"].startswith("sha256:") for item in manifest["fixtures"]))


def make_positive_fixture_test(name: str):
    def test(self: AIDEDominiumReadonlySeamTests) -> None:
        path = self.aide_root / models.FIXTURE_ROOT / "positive" / name
        self.assertTrue(path.exists(), name)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsInstance(data, dict)

    return test


for index, fixture_name in enumerate(
    [
        "host-manifest.json",
        "host-capability-set.json",
        "workspace-descriptor.json",
        "context-descriptor.json",
        "artifact-references.json",
        "diagnostic-projections.json",
        "refusal-projections.json",
        "evidence-reference-set.json",
        "event-envelopes.json",
        "dominium-bridge-manifest.json",
        "complete-seam-bundle.json",
    ],
    start=29,
):
    setattr(
        AIDEDominiumReadonlySeamTests,
        f"test_{index:03d}_positive_fixture_{fixture_name.replace('-', '_').replace('.', '_')}",
        make_positive_fixture_test(fixture_name),
    )


def make_kind_test(kind: str):
    def test(self: AIDEDominiumReadonlySeamTests) -> None:
        records = []
        for value in self.bundle["records"].values():
            records.extend(value if isinstance(value, list) else [value])
        self.assertIn(kind, {item["kind"] for item in records})

    return test


for index, kind in enumerate(models.AUTHORIZED_SEAM_KINDS, start=40):
    setattr(AIDEDominiumReadonlySeamTests, f"test_{index:03d}_authorized_kind_{kind}", make_kind_test(kind))


def make_non_capability_test(name: str):
    def test(self: AIDEDominiumReadonlySeamTests) -> None:
        self.assertIn(name, self.bundle["explicit_non_capabilities"])
        for record_group in self.bundle["records"].values():
            records = record_group if isinstance(record_group, list) else [record_group]
            for record in records:
                self.assertIn(name, record["metadata"]["explicit_non_capabilities"])

    return test


for index, name in enumerate(models.EXPLICIT_NON_CAPABILITIES, start=50):
    setattr(AIDEDominiumReadonlySeamTests, f"test_{index:03d}_non_capability_{name}", make_non_capability_test(name))


def make_conformance_test(expectation_index: int):
    def test(self: AIDEDominiumReadonlySeamTests) -> None:
        result = self.conformance_report["results"][expectation_index]
        self.assertEqual(result["result"], "PASS", result)

    return test


for index, _expectation in enumerate(conformance.EXPECTATIONS, start=67):
    setattr(AIDEDominiumReadonlySeamTests, f"test_{index:03d}_conformance_{index - 66:02d}", make_conformance_test(index - 67))


NEGATIVE_CASE_NAMES = [
    "wrong_repository_identity",
    "stale_revision",
    "missing_required_contract",
    "invalid_reference_id",
    "duplicate_identity",
    "wrong_authority_role",
    "generated_projection_marked_canonical",
    "path_traversal",
    "absolute_path_escape",
    "digest_mismatch",
    "unknown_required_capability",
    "unsupported_version",
    "conflicting_ownership",
    "workbench_authority_overclaim",
    "private_tool_bypass_declaration",
    "mutation_capability_claim",
    "provider_network_worker_claim",
    "invalid_refusal_mapping",
    "invalid_diagnostic_severity",
    "broken_evidence_ref",
    "event_correlation_mismatch",
    "non_deterministic_ordering",
]


def make_negative_fixture_test(case_index: int, case_name: str):
    def test(self: AIDEDominiumReadonlySeamTests) -> None:
        cases = validation.negative_fixture_cases(self.bundle)
        case = cases[case_index]
        self.assertEqual(case["name"], case_name)
        expected_codes = set(case["expected_error_codes"])
        report = self.negative_case_reports[case["name"]]
        observed = {item["code"] for item in report["error_records"]}
        self.assertTrue(expected_codes.issubset(observed), report["error_records"])

    return test


for index, case_name in enumerate(NEGATIVE_CASE_NAMES, start=87):
    setattr(AIDEDominiumReadonlySeamTests, f"test_{index:03d}_negative_fixture_{case_name}", make_negative_fixture_test(index - 87, case_name))


if __name__ == "__main__":
    unittest.main()
