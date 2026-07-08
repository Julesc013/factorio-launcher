from __future__ import annotations

import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from core.protocol import conformance_profile, reference_id


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_conformance_profile", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_conformance_profile"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


def conformance_profile_source_files() -> list[str]:
    files = {
        ".aide/scripts/aide_lite.py",
        ".aide/protocol/aide-conformance-profile.schema.json",
        "core/protocol/__init__.py",
        "core/protocol/conformance_profile.py",
        "core/protocol/envelope.py",
        "core/protocol/reference_id.py",
    }
    files.update(conformance_profile.source_artifact_paths(REPO_ROOT))
    return sorted(files)


def copy_conformance_profile_files(root: Path) -> None:
    for rel in conformance_profile_source_files():
        source = REPO_ROOT / rel
        if source.exists():
            aide_lite.copy_pack_file(source, root / rel)


def validation_errors(profile: dict[str, object]) -> tuple[list[str], list[str]]:
    schema = conformance_profile.load_conformance_profile_schema(REPO_ROOT)
    return conformance_profile.validate_conformance_profile_with_schema(profile, schema)


class AIDEConformanceProfileTests(unittest.TestCase):
    def test_schema_file_exists_and_parses(self) -> None:
        schema = conformance_profile.load_conformance_profile_schema(REPO_ROOT)
        self.assertEqual(schema["title"], "AIDE Minimal ConformanceProfile")
        self.assertEqual(schema["properties"]["kind"]["enum"], ["ConformanceProfile"])
        self.assertEqual(schema["required"], ["apiVersion", "kind", "metadata", "spec", "status"])

    def test_project_writes_required_reports_and_preserves_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_conformance_profile_files(root)
            source_paths = [root / rel for rel in conformance_profile.source_artifact_paths(root)]
            before = {path: path.read_bytes() for path in source_paths if path.exists()}
            report = conformance_profile.write_conformance_profile_reports(root)
            self.assertEqual(report["status"], "PASS_WITH_WARNINGS")
            self.assertFalse(report["source_artifacts_mutated"])
            self.assertEqual(report["profile_count"], 1)
            self.assertGreaterEqual(report["case_count"], 8)
            self.assertGreaterEqual(report["required_case_count"], 7)
            self.assertFalse(report["result_generated"])
            self.assertFalse(report["execution_implemented"])
            self.assertFalse(report["admission_performed"])
            self.assertEqual(before, {path: path.read_bytes() for path in before})
            for rel in conformance_profile.REQUIRED_REPORTS:
                self.assertTrue((root / rel).exists(), rel.as_posix())

    def test_profiles_and_indexes_parse_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_conformance_profile_files(root)
            conformance_profile.write_conformance_profile_reports(root)
            first = (root / ".aide/reports/conformance-profile/profiles.json").read_text(encoding="utf-8")
            conformance_profile.write_conformance_profile_reports(root)
            second = (root / ".aide/reports/conformance-profile/profiles.json").read_text(encoding="utf-8")
            self.assertEqual(first, second)
            profiles = json.loads(first)
            profile_index = json.loads((root / ".aide/reports/conformance-profile/profile-index.json").read_text(encoding="utf-8"))
            case_index = json.loads((root / ".aide/reports/conformance-profile/case-index.json").read_text(encoding="utf-8"))
            self.assertEqual(profiles["kind"], "ConformanceProfile")
            self.assertEqual(profile_index["report_type"], "conformance_profile_index")
            self.assertEqual(case_index["report_type"], "conformance_case_index")
            self.assertEqual(profile_index["case_count"], case_index["case_count"])

    def test_valid_profile_passes_schema_helper_validation(self) -> None:
        profile = conformance_profile.build_conformance_profile(REPO_ROOT)
        errors, warnings = validation_errors(profile)
        self.assertFalse(errors)
        self.assertEqual(warnings, [])
        self.assertEqual(profile["spec"]["profile_ref"], "aide://conformance-profile/minimal_capability_manifest-v1.0.0")
        self.assertEqual(profile["spec"]["subject"]["ref"], "aide://capability/minimal_capability_manifest")
        self.assertEqual(profile["spec"]["lifecycle"], "candidate")

    def test_invalid_profile_ref_and_semver_fail(self) -> None:
        profile = conformance_profile.build_conformance_profile(REPO_ROOT)
        profile["spec"]["profile_ref"] = "aide://conformance-profile/wrong"
        profile["spec"]["profile_version"] = "not-semver"
        errors, _warnings = validation_errors(profile)
        self.assertTrue(any("profile_ref" in item for item in errors))
        self.assertTrue(any("SemVer" in item for item in errors))

    def test_missing_or_invalid_subject_fails(self) -> None:
        profile = conformance_profile.build_conformance_profile(REPO_ROOT)
        profile["spec"]["subject"] = {"kind": "report", "ref": "not-a-ref"}
        errors, _warnings = validation_errors(profile)
        self.assertTrue(any("subject.kind" in item for item in errors))
        self.assertTrue(any("scheme" in item or "aide://" in item or "reference" in item.lower() for item in errors))

    def test_duplicate_case_id_fails(self) -> None:
        profile = conformance_profile.build_conformance_profile(REPO_ROOT)
        profile["spec"]["cases"][1]["case_id"] = profile["spec"]["cases"][0]["case_id"]
        errors, _warnings = validation_errors(profile)
        self.assertTrue(any("unique" in item for item in errors))

    def test_missing_dependency_and_cycle_fail(self) -> None:
        profile = conformance_profile.build_conformance_profile(REPO_ROOT)
        profile["spec"]["cases"][0]["dependencies"] = ["missing-case"]
        errors, _warnings = validation_errors(profile)
        self.assertTrue(any("dependency is missing" in item for item in errors))

        cyclic = conformance_profile.build_conformance_profile(REPO_ROOT)
        cyclic["spec"]["cases"][0]["dependencies"] = [cyclic["spec"]["cases"][1]["case_id"]]
        cyclic["spec"]["cases"][1]["dependencies"] = [cyclic["spec"]["cases"][0]["case_id"]]
        errors, _warnings = validation_errors(cyclic)
        self.assertTrue(any("cycle" in item for item in errors))

    def test_invalid_requirement_level_and_required_outcomes_fail(self) -> None:
        profile = conformance_profile.build_conformance_profile(REPO_ROOT)
        profile["spec"]["cases"][0]["requirement_level"] = "mandatory"
        profile["spec"]["cases"][1]["accepted_outcomes"] = []
        errors, _warnings = validation_errors(profile)
        self.assertTrue(any("requirement_level" in item for item in errors))
        self.assertTrue(any("accepted outcome" in item for item in errors))

    def test_unknown_evaluator_policy_fails_closed_for_required_and_warns_for_optional(self) -> None:
        profile = conformance_profile.build_conformance_profile(REPO_ROOT)
        profile["spec"]["cases"][0]["evaluator"] = "future-required-evaluator"
        errors, _warnings = validation_errors(profile)
        self.assertTrue(any("unknown" in item for item in errors))

        optional_profile = conformance_profile.build_conformance_profile(REPO_ROOT)
        optional_profile["spec"]["cases"][-1]["evaluator"] = "future-optional-evaluator"
        optional_profile["spec"]["cases"][-1]["requirement_level"] = "optional"
        errors, warnings = validation_errors(optional_profile)
        self.assertFalse(errors)
        self.assertTrue(any("unknown" in item for item in warnings))

        advisory_profile = conformance_profile.build_conformance_profile(REPO_ROOT)
        advisory_profile["spec"]["cases"][-2]["evaluator"] = "future-advisory-evaluator"
        advisory_profile["spec"]["cases"][-2]["requirement_level"] = "advisory"
        errors, warnings = validation_errors(advisory_profile)
        self.assertFalse(errors)
        self.assertTrue(any("unknown" in item for item in warnings))

    def test_boundary_flags_do_not_overclaim_results_admission_or_execution(self) -> None:
        profile = conformance_profile.build_conformance_profile(REPO_ROOT)
        self.assertTrue(profile["status"]["profile_only"])
        for field in ["result_generated", "execution_implemented", "admission_performed", "admitted", "trusted", "runtime", "mutating"]:
            self.assertFalse(profile["status"][field])
        self.assertFalse(profile["spec"]["result_model"]["implemented"])
        self.assertFalse(profile["spec"]["admission"]["implemented"])
        for case in profile["spec"]["cases"]:
            self.assertIsNone(case["result_ref"])
            self.assertFalse(case["result_generated"])
            self.assertFalse(case["execution_implemented"])
            self.assertFalse(case["admission_performed"])

    def test_refs_parse_and_initial_profile_contains_required_cases(self) -> None:
        profile = conformance_profile.build_conformance_profile(REPO_ROOT)
        self.assertTrue(reference_id.validate_reference_id(profile["spec"]["profile_ref"], required=True).valid)
        self.assertTrue(reference_id.validate_reference_id(profile["spec"]["subject"]["ref"], required=True).valid)
        case_ids = {case["case_id"] for case in profile["spec"]["cases"]}
        for expected in [
            "capability-manifest-schema-parses",
            "capability-manifest-projection-json-valid",
            "capability-manifest-validation-pass-with-warnings",
            "capability-manifest-acceptance-evidence-complete",
            "capability-manifest-declaration-only-boundary",
            "source-artifacts-not-mutated-by-profile",
        ]:
            self.assertIn(expected, case_ids)
        for case in profile["spec"]["cases"]:
            self.assertTrue(reference_id.validate_reference_id(case["case_ref"].split("#", 1)[0], required=True).valid)
            for ref in case["source_refs"]:
                self.assertTrue(reference_id.validate_reference_id(ref, required=True).valid, ref)

    def test_validate_reports_pass_with_warnings_and_required_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_conformance_profile_files(root)
            conformance_profile.write_conformance_profile_reports(root)
            validation = conformance_profile.validate_conformance_profile(root)
            self.assertEqual(validation["validation_status"], "PASS_WITH_WARNINGS")
            for key in [
                "schema_exists",
                "helper_exists",
                "cli_registered",
                "reports_generated",
                "profiles_json_valid",
                "profile_index_json_valid",
                "case_index_json_valid",
                "case_ids_unique",
                "dependencies_resolve",
                "dependency_cycles_absent",
                "requirement_levels_valid",
                "known_required_evaluators",
                "unknown_required_evaluator_fails_closed",
                "unknown_optional_evaluator_warns",
                "unknown_advisory_evaluator_warns",
                "required_cases_have_accepted_outcomes",
                "required_cases_fail_closed",
                "profile_lifecycle_candidate",
                "evidence_requirements_declared",
                "source_evidence_exists",
                "profile_boundary_valid",
                "result_not_generated",
                "execution_not_implemented",
                "admission_not_performed",
                "trusted_not_promoted",
                "predecessor_compatibility_preserved",
                "overclaiming_check_passed",
                "forbidden_ops_preserved",
            ]:
                self.assertTrue(validation[key], key)

    def test_conformance_profile_cli_status_project_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_conformance_profile_files(root)
            parser = aide_lite.build_parser(REPO_ROOT)
            commands = [
                ["--repo-root", str(root), "conformance-profile", "status"],
                ["--repo-root", str(root), "conformance-profile", "project"],
                ["--repo-root", str(root), "conformance-profile", "validate"],
            ]
            for command in commands:
                parsed = parser.parse_args(command)
                output = io.StringIO()
                with redirect_stdout(output):
                    result = parsed.handler(parsed)
                self.assertEqual(result, 0, output.getvalue())
                self.assertIn("profile_only: true", output.getvalue())
                self.assertIn("result_generated: false", output.getvalue())
                self.assertIn("execution_implemented: false", output.getvalue())
                self.assertIn("admission_performed: false", output.getvalue())
                self.assertIn("trusted: false", output.getvalue())
                self.assertIn("provider_or_model_calls: none", output.getvalue())
                self.assertIn("network_calls: false", output.getvalue())

    def test_cli_rejects_forbidden_execution_or_admission_subcommands(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        for subcommand in ["run", "execute", "admit", "result", "adapter-run", "repair", "mutate"]:
            with self.subTest(subcommand=subcommand):
                stderr = io.StringIO()
                with redirect_stdout(io.StringIO()), redirect_stderr(stderr), self.assertRaises(SystemExit):
                    parser.parse_args(["conformance-profile", subcommand])

    def test_reports_do_not_overclaim_future_layers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_conformance_profile_files(root)
            conformance_profile.write_conformance_profile_reports(root)
            combined = "\n".join(
                (root / rel).read_text(encoding="utf-8").lower()
                for rel in [
                    ".aide/reports/conformance-profile/projection-report.md",
                    ".aide/reports/conformance-profile/validation.md",
                    ".aide/reports/conformance-profile/profiles.md",
                    ".aide/reports/conformance-profile/future-work.md",
                ]
            )
            for forbidden in [
                "conformanceprofile admits capability",
                "conformanceprofile proves capability",
                "conformanceprofile executes checks",
                "conformanceresult implemented",
                "patchtransaction implemented",
                "adaptermanifest implemented",
                "contextpack v2 implemented",
                "runtime implemented",
                "provider/model calls implemented",
                "release ready",
                "production ready",
            ]:
                self.assertNotIn(forbidden, combined)

    def test_schema_validation_detects_status_overclaim(self) -> None:
        profile = copy.deepcopy(conformance_profile.build_conformance_profile(REPO_ROOT))
        profile["status"]["admitted"] = True
        errors, _warnings = validation_errors(profile)
        self.assertTrue(any("status.admitted" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
