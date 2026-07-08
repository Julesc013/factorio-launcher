from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.protocol import trust_authorization


MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_trust_authorization_contract", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_trust_authorization_contract"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


SOURCE_FILES = [
    ".aide/scripts/aide_lite.py",
    ".aide/protocol/aide-principal.schema.json",
    ".aide/protocol/aide-admission-record.schema.json",
    ".aide/protocol/aide-policy-decision.schema.json",
    ".aide/protocol/aide-capability-grant.schema.json",
    ".aide/protocol/aide-delegation-record.schema.json",
    ".aide/protocol/aide-revocation-record.schema.json",
    ".aide/protocol/aide-authorization-evaluation.schema.json",
    "core/__init__.py",
    "core/protocol/__init__.py",
    "core/protocol/envelope.py",
    "core/protocol/trust_authorization.py",
]


def copy_contract_files(root: Path) -> None:
    for rel in SOURCE_FILES:
        source = REPO_ROOT / rel
        if source.exists():
            destination = root / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


class AIDETrustAuthorizationContractTests(unittest.TestCase):
    def test_all_sample_records_validate(self) -> None:
        for name, record in trust_authorization.sample_records().items():
            with self.subTest(name=name):
                self.assertEqual(trust_authorization.validate_trust_authorization_contract(record), [])

    def test_principal_is_ref_only_and_rejects_embedded_credentials(self) -> None:
        principal = trust_authorization.sample_principal()
        self.assertEqual(principal["spec"]["credential_refs"], ["aide://credential/ref-only-fixture"])
        principal["spec"]["credential"] = "not-allowed"
        errors = trust_authorization.validate_trust_authorization_contract(principal)
        self.assertIn("secret values must not be embedded in trust authorization records", errors)

    def test_admission_uses_exact_digest_and_separates_conformance_from_admission(self) -> None:
        admission = trust_authorization.sample_admission_record()
        self.assertRegex(admission["spec"]["implementation_digest"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(admission["spec"]["manifest_digest"], r"^sha256:[0-9a-f]{64}$")
        self.assertTrue(admission["spec"]["conformance_result_refs"])
        self.assertTrue(admission["spec"]["admitted_capability_refs"])
        broken = copy.deepcopy(admission)
        broken["spec"]["implementation_digest"] = "sha256:BAD"
        self.assertIn(
            "spec.implementation_digest must be sha256:<64 lowercase hex>",
            trust_authorization.validate_trust_authorization_contract(broken),
        )

    def test_authorization_success_and_required_refusal_matrix(self) -> None:
        success = trust_authorization.sample_authorization_evaluation()
        self.assertEqual(success["spec"]["result"], "allowed")
        self.assertEqual(success["spec"]["reason_codes"], [])
        matrix = trust_authorization.negative_evaluation_matrix()
        self.assertEqual(set(matrix), set(trust_authorization.REFUSAL_CODES))
        for code, evaluation in matrix.items():
            with self.subTest(code=code):
                self.assertIn(code, evaluation["spec"]["reason_codes"])
                self.assertIn(evaluation["spec"]["result"], {"denied", "approval_required", "quarantined"})
                self.assertEqual(trust_authorization.validate_trust_authorization_contract(evaluation), [])

    def test_delegation_only_narrows_and_scope_widening_fails(self) -> None:
        delegation = trust_authorization.sample_delegation_record()
        request = trust_authorization.sample_requested_operation()
        request["capability_ref"] = "aide://capability/other"
        evaluation = trust_authorization.evaluate_authorization(
            trust_authorization.sample_principal(),
            trust_authorization.sample_admission_record(),
            trust_authorization.sample_policy_decision(),
            trust_authorization.sample_capability_grant(),
            delegation,
            [],
            request,
        )
        self.assertEqual(evaluation["spec"]["reason_codes"], ["capability_not_admitted"])

    def test_unknown_optional_fields_tolerated_and_required_capability_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_contract_files(root)
            self.assertEqual(
                trust_authorization.validate_runtime(trust_authorization.sample_unknown_optional_record(), root)["status"],
                "PASS",
            )
            required = trust_authorization.validate_runtime(trust_authorization.sample_unknown_required_capability_record(), root)
            self.assertEqual(required["status"], "FAILED_VALIDATION")
            self.assertIn("unknown required capability: future.required", required["helper_validation_errors"])

    def test_schema_files_parse_and_align_with_helper(self) -> None:
        alignment = trust_authorization.check_schema_helper_alignment(REPO_ROOT)
        self.assertEqual(alignment["schema_helper_alignment_status"], "PASS")
        self.assertEqual(alignment["errors"], [])
        self.assertEqual(set(alignment["loaded_kinds"]), trust_authorization.RECORD_KINDS)

    def test_projection_and_validate_reports_are_projection_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_contract_files(root)
            report = trust_authorization.trust_validate(root)
            self.assertEqual(report["status"], "PASS_WITH_WARNINGS")
            self.assertTrue(report["projection_only_truthful"])
            self.assertTrue(report["all_required_refusal_codes_covered"])
            self.assertTrue(report["no_secret_values_embedded"])
            self.assertFalse(report["live_identity_implemented"])
            self.assertFalse(report["runtime_enforcement_implemented"])
            self.assertFalse(report["service_runtime_implemented"])
            self.assertTrue((root / ".aide/reports/trust-authorization-contract-v0/validation.json").exists())

    def test_trust_cli_status_project_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_contract_files(root)
            parser = aide_lite.build_parser(REPO_ROOT)
            commands = [
                ["--repo-root", str(root), "trust", "status"],
                ["--repo-root", str(root), "trust", "project", "--source", "contract-projection"],
                ["--repo-root", str(root), "trust", "validate"],
            ]
            for command in commands:
                parsed = parser.parse_args(command)
                output = StringIO()
                with redirect_stdout(output):
                    exit_code = parsed.handler(parsed)
                self.assertEqual(exit_code, 0, output.getvalue())
                self.assertIn("projection_only: true", output.getvalue())
                self.assertIn("live_identity_implemented: false", output.getvalue())
                self.assertIn("runtime_enforcement_implemented: false", output.getvalue())
                self.assertIn("provider_or_model_calls: none", output.getvalue())
                self.assertIn("network_calls: none", output.getvalue())

    def test_parser_rejects_live_trust_commands(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        stderr = StringIO()
        with self.assertRaises(SystemExit), redirect_stderr(stderr):
            parser.parse_args(["trust", "enforce"])
        self.assertIn("invalid choice", stderr.getvalue())

    def test_schema_validation_accepts_sample_records(self) -> None:
        for record in trust_authorization.sample_records().values():
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                copy_contract_files(root)
                runtime = trust_authorization.validate_runtime(record, root)
                self.assertEqual(runtime["status"], "PASS", json.dumps(runtime, indent=2))


if __name__ == "__main__":
    unittest.main()
