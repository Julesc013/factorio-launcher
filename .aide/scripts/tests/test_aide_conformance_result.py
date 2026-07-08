from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from core.protocol import conformance_result, reference_id


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_conformance_result", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_conformance_result"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


def conformance_result_source_files() -> list[str]:
    files = {
        ".aide/scripts/aide_lite.py",
        ".aide/protocol/aide-conformance-result.schema.json",
        ".aide/protocol/aide-conformance-profile.schema.json",
        "core/protocol/__init__.py",
        "core/protocol/capability_manifest.py",
        "core/protocol/conformance_profile.py",
        "core/protocol/conformance_result.py",
        "core/protocol/envelope.py",
        "core/protocol/reference_id.py",
    }
    files.update(conformance_result.source_artifact_paths(REPO_ROOT))
    return sorted(files)


def copy_conformance_result_files(root: Path) -> None:
    for rel in conformance_result_source_files():
        source = REPO_ROOT / rel
        if source.exists():
            aide_lite.copy_pack_file(source, root / rel)


def loaded_profile() -> dict[str, object]:
    return conformance_result.load_accepted_conformance_profile(REPO_ROOT)


def independent_profile_digest(profile: dict[str, object]) -> str:
    canonical = json.dumps(
        profile,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def validation_errors(result: dict[str, object]) -> tuple[list[str], list[str]]:
    schema = conformance_result.load_conformance_result_schema(REPO_ROOT)
    return conformance_result.validate_conformance_result_with_schema(result, schema, loaded_profile())


class AIDEConformanceResultTests(unittest.TestCase):
    def test_schema_file_exists_and_parses(self) -> None:
        schema = conformance_result.load_conformance_result_schema(REPO_ROOT)
        self.assertEqual(schema["title"], "AIDE Minimal ConformanceResult")
        self.assertEqual(schema["properties"]["kind"]["enum"], ["ConformanceResult"])
        self.assertEqual(schema["required"], ["apiVersion", "kind", "metadata", "spec", "status"])

    def test_project_writes_required_reports_and_preserves_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_conformance_result_files(root)
            source_paths = [root / rel for rel in conformance_result.source_artifact_paths(root)]
            before = {path: path.read_bytes() for path in source_paths if path.exists()}
            report = conformance_result.write_conformance_result_reports(root)
            self.assertEqual(report["status"], "PASS_WITH_WARNINGS")
            self.assertFalse(report["source_artifacts_mutated"])
            self.assertTrue(report["record_valid"])
            self.assertTrue(report["record_complete"])
            self.assertTrue(report["profile_requirements_satisfied"])
            self.assertFalse(report["execution_performed"])
            self.assertFalse(report["admission_performed"])
            self.assertFalse(report["subject_admitted"])
            self.assertFalse(report["trusted"])
            self.assertEqual(before, {path: path.read_bytes() for path in before})
            for rel in conformance_result.REQUIRED_REPORTS:
                self.assertTrue((root / rel).exists(), rel.as_posix())

    def test_results_and_indexes_parse_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_conformance_result_files(root)
            conformance_result.write_conformance_result_reports(root)
            first = (root / ".aide/reports/conformance-result/results.json").read_text(encoding="utf-8")
            conformance_result.write_conformance_result_reports(root)
            second = (root / ".aide/reports/conformance-result/results.json").read_text(encoding="utf-8")
            self.assertEqual(first, second)
            result = json.loads(first)
            result_index = json.loads((root / ".aide/reports/conformance-result/result-index.json").read_text(encoding="utf-8"))
            case_index = json.loads((root / ".aide/reports/conformance-result/case-result-index.json").read_text(encoding="utf-8"))
            self.assertEqual(result["kind"], "ConformanceResult")
            self.assertEqual(result_index["report_type"], "conformance_result_index")
            self.assertEqual(case_index["report_type"], "conformance_case_result_index")
            self.assertEqual(result_index["case_result_count"], case_index["case_result_count"])

    def test_valid_projected_result_passes_schema_helper_validation(self) -> None:
        result = conformance_result.build_conformance_result(REPO_ROOT)
        errors, warnings = validation_errors(result)
        self.assertFalse(errors)
        self.assertTrue(warnings)
        self.assertEqual(result["spec"]["result_ref"], "aide://conformance-result/minimal_capability_manifest-v1.0.0-evidence-projection-01")
        self.assertEqual(result["spec"]["profile"]["ref"], "aide://conformance-profile/minimal_capability_manifest-v1.0.0")
        self.assertEqual(result["spec"]["subject"]["ref"], "aide://capability/minimal_capability_manifest")
        self.assertEqual(result["spec"]["observation"]["mode"], "evidence_projection")

    def test_record_valid_profile_satisfied_and_admission_are_independent(self) -> None:
        result = conformance_result.build_conformance_result(REPO_ROOT)
        self.assertTrue(result["status"]["record_valid"])
        self.assertTrue(result["status"]["profile_requirements_satisfied"])
        self.assertFalse(result["status"]["admission_performed"])
        self.assertFalse(result["status"]["subject_admitted"])
        self.assertFalse(result["status"]["trusted"])
        self.assertFalse(result["spec"]["subject"]["admission_performed"])
        self.assertFalse(result["spec"]["subject"]["subject_admitted"])
        self.assertFalse(result["spec"]["subject"]["trusted"])

    def test_invalid_result_ref_profile_ref_and_semver_fail(self) -> None:
        result = conformance_result.build_conformance_result(REPO_ROOT)
        result["spec"]["result_ref"] = "aide://conformance-result/wrong"
        result["spec"]["profile"]["ref"] = "aide://conformance-profile/wrong"
        result["spec"]["result_version"] = "not-semver"
        errors, _warnings = validation_errors(result)
        self.assertTrue(any("result_ref" in item for item in errors))
        self.assertTrue(any("profile.ref" in item for item in errors))
        self.assertTrue(any("SemVer" in item for item in errors))

    def test_profile_digest_mismatch_fails(self) -> None:
        result = conformance_result.build_conformance_result(REPO_ROOT)
        result["spec"]["profile"]["digest"] = "sha256:" + ("0" * 64)
        errors, _warnings = validation_errors(result)
        self.assertTrue(any("profile.digest" in item for item in errors))

    def test_profile_digest_matches_pristine_payload_independent_calculation(self) -> None:
        profile = json.loads((REPO_ROOT / ".aide/reports/conformance-profile/profiles.json").read_text(encoding="utf-8"))
        result = conformance_result.build_conformance_result(REPO_ROOT)
        expected = independent_profile_digest(profile)
        self.assertEqual(result["spec"]["profile"]["digest"], expected)
        self.assertEqual(result["spec"]["observation"]["source_profile_digest"], expected)

    def test_profile_digest_ignores_validation_warning_mutation_of_copy(self) -> None:
        profile = json.loads((REPO_ROOT / ".aide/reports/conformance-profile/profiles.json").read_text(encoding="utf-8"))
        mutated = copy.deepcopy(profile)
        mutated.setdefault("status", {}).setdefault("validation_warnings", []).append(
            "Profile lifecycle is candidate; result records observations but does not admit the subject."
        )
        result = conformance_result.build_conformance_result(REPO_ROOT)
        self.assertEqual(result["spec"]["profile"]["digest"], independent_profile_digest(profile))
        self.assertNotEqual(result["spec"]["profile"]["digest"], independent_profile_digest(mutated))
        errors, _warnings = conformance_result.validate_conformance_result_record(result, mutated)
        self.assertTrue(any("profile.digest" in item for item in errors))

    def test_profile_digest_changes_when_pristine_payload_changes(self) -> None:
        profile = json.loads((REPO_ROOT / ".aide/reports/conformance-profile/profiles.json").read_text(encoding="utf-8"))
        changed = copy.deepcopy(profile)
        changed["metadata"]["title"] = "Changed Profile Payload"
        self.assertNotEqual(independent_profile_digest(profile), independent_profile_digest(changed))

    def test_projection_and_validation_do_not_mutate_profile_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_conformance_result_files(root)
            profile_path = root / ".aide/reports/conformance-profile/profiles.json"
            before = profile_path.read_bytes()
            conformance_result.write_conformance_result_reports(root)
            self.assertEqual(before, profile_path.read_bytes())
            conformance_result.validate_conformance_result(root)
            self.assertEqual(before, profile_path.read_bytes())

    def test_subject_admission_or_trust_overclaim_fails(self) -> None:
        result = conformance_result.build_conformance_result(REPO_ROOT)
        result["status"]["subject_admitted"] = True
        result["spec"]["subject"]["trusted"] = True
        errors, _warnings = validation_errors(result)
        self.assertTrue(any("subject_admitted" in item for item in errors))
        self.assertTrue(any("trusted" in item for item in errors))

    def test_execution_or_runner_overclaim_fails(self) -> None:
        result = conformance_result.build_conformance_result(REPO_ROOT)
        result["spec"]["observation"]["execution_performed"] = True
        result["spec"]["observation"]["runner_ref"] = "aide://runner/local"
        result["spec"]["case_results"][0]["execution_performed"] = True
        errors, _warnings = validation_errors(result)
        self.assertTrue(any("execution_performed" in item for item in errors))
        self.assertTrue(any("runner_ref" in item for item in errors))

    def test_duplicate_unknown_and_missing_required_cases_fail(self) -> None:
        profile = loaded_profile()
        result = conformance_result.build_conformance_result(REPO_ROOT)
        result["spec"]["case_results"].append(copy.deepcopy(result["spec"]["case_results"][0]))
        errors, _warnings = conformance_result.validate_conformance_result_record(result, profile)
        self.assertTrue(any("unique" in item or "duplicate" in item for item in errors))

        unknown = conformance_result.build_conformance_result(REPO_ROOT)
        unknown["spec"]["case_results"][0]["case_id"] = "future-unknown-case"
        errors, _warnings = conformance_result.validate_conformance_result_record(unknown, profile)
        self.assertTrue(any("unknown case result" in item for item in errors))

        missing = conformance_result.build_conformance_result(REPO_ROOT)
        missing["spec"]["case_results"] = missing["spec"]["case_results"][1:]
        errors, _warnings = conformance_result.validate_conformance_result_record(missing, profile)
        self.assertTrue(any("missing required case result" in item for item in errors))

    def test_aggregation_required_fail_error_and_not_run_fail_closed(self) -> None:
        profile = loaded_profile()
        base = conformance_result.build_conformance_result(REPO_ROOT)
        for outcome, expected in [("FAIL", "FAIL"), ("ERROR", "ERROR"), ("NOT_RUN", "INCOMPLETE")]:
            result = copy.deepcopy(base)
            result["spec"]["case_results"][0]["outcome"] = outcome
            result["spec"]["case_results"][0]["observed"] = outcome != "NOT_RUN"
            result["spec"]["case_results"][0]["reason"] = f"forced {outcome}"
            aggregate = conformance_result.aggregate_case_results(profile, result["spec"]["case_results"])
            self.assertEqual(aggregate["aggregate_outcome"], expected)
            self.assertFalse(aggregate["profile_requirements_satisfied"])
            self.assertTrue(aggregate["fail_closed_triggered"])

    def test_aggregation_optional_and_advisory_findings_do_not_block_required_satisfaction(self) -> None:
        profile = loaded_profile()
        result = conformance_result.build_conformance_result(REPO_ROOT)
        optional = next(item for item in result["spec"]["case_results"] if item["requirement_level_snapshot"] == "optional")
        optional["outcome"] = "FAIL"
        optional["reason"] = "optional evidence retained as warning"
        optional["observed"] = True
        advisory = next(item for item in result["spec"]["case_results"] if item["requirement_level_snapshot"] == "advisory")
        advisory["outcome"] = "UNAVAILABLE"
        advisory["reason"] = "advisory evidence unavailable"
        advisory["observed"] = False
        aggregate = conformance_result.aggregate_case_results(profile, result["spec"]["case_results"])
        self.assertEqual(aggregate["aggregate_outcome"], "PASS_WITH_WARNINGS")
        self.assertTrue(aggregate["profile_requirements_satisfied"])
        self.assertTrue(aggregate["optional_findings"])
        self.assertTrue(aggregate["advisory_findings"])

    def test_case_outcome_semantics_fail_for_missing_refs_warnings_and_reasons(self) -> None:
        result = conformance_result.build_conformance_result(REPO_ROOT)
        result["spec"]["case_results"][0]["evidence_refs"] = []
        result["spec"]["case_results"][0]["report_refs"] = []
        result["spec"]["case_results"][0]["source_refs"] = []
        result["spec"]["case_results"][2]["warnings"] = []
        result["spec"]["case_results"][3]["outcome"] = "FAIL"
        result["spec"]["case_results"][3]["reason"] = None
        result["spec"]["case_results"][4]["outcome"] = "NOT_RUN"
        result["spec"]["case_results"][4]["observed"] = True
        result["spec"]["case_results"][4]["reason"] = None
        errors, _warnings = validation_errors(result)
        self.assertTrue(any("passing case" in item for item in errors))
        self.assertTrue(any("PASS_WITH_WARNINGS" in item for item in errors))
        self.assertTrue(any("failed or errored" in item for item in errors))
        self.assertTrue(any("non-observed" in item for item in errors))

    def test_reference_ids_parse(self) -> None:
        result = conformance_result.build_conformance_result(REPO_ROOT)
        for ref in [result["spec"]["result_ref"], result["spec"]["profile"]["ref"], result["spec"]["subject"]["ref"]]:
            self.assertTrue(reference_id.validate_reference_id(ref, required=True).valid, ref)
        for case in result["spec"]["case_results"]:
            self.assertTrue(reference_id.validate_reference_id(case["case_ref"].split("#", 1)[0], required=True).valid)
            for ref in case["source_refs"]:
                self.assertTrue(reference_id.validate_reference_id(ref, required=True).valid, ref)

    def test_validate_reports_pass_with_warnings_and_required_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_conformance_result_files(root)
            conformance_result.write_conformance_result_reports(root)
            validation = conformance_result.validate_conformance_result(root)
            self.assertEqual(validation["validation_status"], "PASS_WITH_WARNINGS")
            for key in [
                "schema_exists",
                "helper_exists",
                "cli_registered",
                "reports_generated",
                "results_json_valid",
                "result_index_json_valid",
                "case_result_index_json_valid",
                "projection_json_valid",
                "case_ids_unique",
                "case_results_bind_to_profile",
                "observed_outcomes_valid",
                "case_results_execution_false",
                "case_results_runner_null",
                "observation_mode_evidence_projection",
                "observation_execution_false",
                "observation_runner_null",
                "profile_digest_matches",
                "required_cases_accounted",
                "record_complete",
                "profile_requirements_satisfied",
                "record_valid_independent",
                "admission_not_performed",
                "subject_not_admitted",
                "trusted_not_promoted",
                "result_boundary_valid",
                "predecessor_compatibility_preserved",
                "overclaiming_check_passed",
                "forbidden_ops_preserved",
            ]:
                self.assertTrue(validation[key], key)

    def test_conformance_result_cli_status_project_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_conformance_result_files(root)
            parser = aide_lite.build_parser(REPO_ROOT)
            commands = [
                ["--repo-root", str(root), "conformance-result", "status"],
                ["--repo-root", str(root), "conformance-result", "project"],
                ["--repo-root", str(root), "conformance-result", "validate"],
            ]
            for command in commands:
                parsed = parser.parse_args(command)
                output = io.StringIO()
                with redirect_stdout(output):
                    result = parsed.handler(parsed)
                self.assertEqual(result, 0, output.getvalue())
                text = output.getvalue()
                self.assertIn("result_only: true", text)
                self.assertIn("projection_only: true", text)
                self.assertIn("execution_performed: false", text)
                self.assertIn("admission_performed: false", text)
                self.assertIn("subject_admitted: false", text)
                self.assertIn("trusted: false", text)
                self.assertIn("provider_or_model_calls: none", text)
                self.assertIn("network_calls: false", text)

    def test_cli_rejects_forbidden_execution_or_admission_subcommands(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        for subcommand in ["run", "execute", "collect", "admit", "trust", "activate", "adapter-run", "mutate"]:
            with self.subTest(subcommand=subcommand):
                stderr = io.StringIO()
                with redirect_stdout(io.StringIO()), redirect_stderr(stderr), self.assertRaises(SystemExit):
                    parser.parse_args(["conformance-result", subcommand])

    def test_reports_do_not_overclaim_future_layers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_conformance_result_files(root)
            conformance_result.write_conformance_result_reports(root)
            combined = "\n".join(
                (root / rel).read_text(encoding="utf-8").lower()
                for rel in [
                    ".aide/reports/conformance-result/projection-report.md",
                    ".aide/reports/conformance-result/validation.md",
                    ".aide/reports/conformance-result/results.md",
                    ".aide/reports/conformance-result/future-work.md",
                ]
            )
            for forbidden in [
                "admission_performed: true",
                "subject_admitted: true",
                "trusted: true",
                "execution_performed: true",
                "conformance runner implemented",
                "patchtransaction implemented",
                "adaptermanifest implemented",
                "contextpack v2 implemented",
                "runtime implemented",
                "provider/model calls implemented",
                "release ready",
                "production ready",
            ]:
                self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
