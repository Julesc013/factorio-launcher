# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import unittest
from pathlib import Path

import jsonschema

from tools import json_contract


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts/schema/facman/facman_setup_operation_journal.v1.schema.json"


class SelfSetupRecoveryContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.validator = jsonschema.Draft202012Validator(self.schema)
        self.value = {
            "schema": "facman.setup_operation_journal.v1",
            "operation_id": "setup.install.0123456789abcdef0123456789abcdef",
            "intent_digest": "e" * 64,
            "operation": "install",
            "install_root": "C:/Users/Tester/Programs/FacMan",
            "install_root_identity": "a" * 64,
            "product": "facman",
            "product_version": "0.1.0-alpha.6",
            "mode": "installed",
            "provider": {
                "revision": "d2a2aae7e61c47035c92334b0522143b4fea3880",
                "state_root": "C:/Users/Tester/AppData/Local/FacMan/usk-state",
                "acceptance_root": "C:/Users/Tester/Programs/FacMan",
                "source_digest": "d" * 64,
                "request_id": "request.setup.install.0123456789abcdef0123456789abcdef",
                "plan_id": "request.setup.install.0123456789abcdef0123456789abcdef",
                "transaction_id": "tx.setup.install.0123456789abcdef0123456789abcdef",
                "created_at": "2026-09-13T00:00:00Z",
                "plan_digest": "b" * 64,
                "receipt_identity": "c" * 64,
            },
            "recovery": {"plan_id": "", "plan_digest": "", "created_at": "", "action": ""},
            "effects": {
                "files": "applied",
                "shortcut": "applying",
                "registration": "pending",
            },
            "state": "native_applying",
            "recovery_boundary": "shortcut_pending",
            "last_error": "",
        }

    def assert_schema_valid(self, value: dict) -> None:
        self.assertEqual(list(self.validator.iter_errors(value)), [])

    def assert_schema_invalid(self, value: dict) -> None:
        self.assertTrue(list(self.validator.iter_errors(value)))

    @staticmethod
    def set_operation(value: dict, operation: str) -> None:
        suffix = "0123456789abcdef0123456789abcdef"
        operation_id = f"setup.{operation}.{suffix}"
        value["operation"] = operation
        value["operation_id"] = operation_id
        value["provider"]["request_id"] = f"request.{operation_id}"
        value["provider"]["plan_id"] = (
            f"request.{operation_id}" if operation == "install" else f"plan.{operation_id}"
        )
        value["provider"]["transaction_id"] = f"tx.{operation_id}"

    def test_schema_is_closed_and_accepts_a_recoverable_native_boundary(self) -> None:
        self.assertFalse(self.schema["additionalProperties"])
        self.assertEqual(json_contract.validate(self.value, self.schema), [])
        self.assert_schema_valid(self.value)

    def test_identity_or_effect_substitution_is_refused_by_the_contract(self) -> None:
        for key, value in (
            ("install_root_identity", "not-a-digest"),
            ("mode", "system"),
            ("state", "unknown"),
        ):
            with self.subTest(key=key):
                altered = dict(self.value)
                altered[key] = value
                self.assert_schema_invalid(altered)
        altered = json.loads(json.dumps(self.value))
        altered["effects"]["shortcut"] = "foreign"
        self.assert_schema_invalid(altered)
        altered = json.loads(json.dumps(self.value))
        altered["operation"] = "repair"
        self.assert_schema_invalid(altered)

    def test_phase_boundaries_cover_install_repair_uninstall_and_portable_modes(self) -> None:
        cases = (
            # Crash after the provider file receipt, before native integration.
            ("install", "installed", "files_applied", "pending", "pending"),
            # Crash after the shortcut receipt and before registry application.
            ("repair", "installed", "native_applying", "applied", "pending"),
            # Native effect may have happened although its receipt was lost.
            ("repair", "installed", "native_applying", "applying", "pending"),
            # USK uninstall can commit before owned native effects are removed.
            ("uninstall", "installed", "files_applied", "pending", "pending"),
            # --no-shell-integration never claims Windows effects.
            ("install", "portable", "completed", "not_applicable", "not_applicable"),
            # Provider rollback is terminal and permits a later fresh attempt.
            ("install", "installed", "rolled_back", "pending", "pending"),
        )
        for operation, mode, state, shortcut, registration in cases:
            with self.subTest(operation=operation, mode=mode, state=state):
                value = json.loads(json.dumps(self.value))
                self.set_operation(value, operation)
                value["mode"] = mode
                value["state"] = state
                value["effects"]["shortcut"] = shortcut
                value["effects"]["registration"] = registration
                if state == "rolled_back":
                    value["effects"]["files"] = "pending"
                    value["recovery"] = {
                        "plan_id": "recovery.plan.setup.install.0123456789abcdef",
                        "plan_digest": "f" * 64,
                        "created_at": "2026-09-13T00:00:01Z",
                        "action": "rollback",
                    }
                self.assert_schema_valid(value)

    def test_terminal_and_recovery_cross_fields_reject_incompatible_records(self) -> None:
        cases = []
        completed = json.loads(json.dumps(self.value))
        completed["state"] = "completed"
        completed["effects"]["shortcut"] = "pending"
        cases.append(completed)
        rolled_back = json.loads(json.dumps(self.value))
        rolled_back["state"] = "rolled_back"
        rolled_back["effects"] = {"files": "pending", "shortcut": "pending", "registration": "pending"}
        cases.append(rolled_back)
        partial_review = json.loads(json.dumps(self.value))
        partial_review["recovery"] = {"plan_id": "recovery.plan.setup.install.x", "plan_digest": "", "created_at": "", "action": "rollback"}
        cases.append(partial_review)
        abandoned = json.loads(json.dumps(self.value))
        abandoned["state"] = "abandoned"
        abandoned["effects"] = {"files": "pending", "shortcut": "pending", "registration": "pending"}
        abandoned["provider"]["plan_digest"] = ""
        abandoned["recovery_boundary"] = "wrong"
        cases.append(abandoned)
        for value in cases:
            self.assert_schema_invalid(value)

    def test_provider_authority_and_preapply_retirement_are_closed(self) -> None:
        value = json.loads(json.dumps(self.value))
        del value["provider"]["state_root"]
        self.assert_schema_invalid(value)
        value = json.loads(json.dumps(self.value))
        value["state"] = "abandoned"
        value["effects"] = {"files": "pending", "shortcut": "pending", "registration": "pending"}
        value["provider"]["plan_digest"] = ""
        value["provider"]["receipt_identity"] = ""
        value["recovery_boundary"] = "abandoned_before_provider_apply"
        self.assert_schema_valid(value)

    def test_runtime_admission_binds_stale_identity_and_ownership_to_recovery(self) -> None:
        source = (ROOT / "runtime/self_setup/facman_self_setup.cpp").read_text(encoding="utf-8")
        for boundary in (
            'discover_root_journal(coordinator.value(), root_identity)',
            'active.product_version = journal.product_version',
            'journal.provider_state_root',
            'abandoned_before_provider_apply',
            'observed == NativeOwnership::foreign',
            'observed == NativeOwnership::unreadable',
            '"self_setup_recovery_required"',
        ):
            with self.subTest(boundary=boundary):
                self.assertIn(boundary, source)

    def test_qualification_interrupt_is_paired_permit_bound_and_consumed_before_setup(self) -> None:
        source = (ROOT / "apps/setup/main.cpp").read_text(encoding="utf-8")
        for token in (
            "--qualification-interrupt-after",
            "--qualification-interrupt-permit",
            "duplicate option: --qualification-interrupt-after",
            "duplicate option: --qualification-interrupt-permit",
            "--noninteractive",
            "--shell-integration",
            "kQualificationPermitMaximumBytes = 4096U",
            "kQualificationPermitMaximumLifetimeSeconds = 120U",
            "now >= expires_at",
            "facman.self_setup_qualification_interrupt_permit.v1",
            '"issued_at_unix_seconds"',
            '"expires_at_unix_seconds"',
            "lowercase_hex_64(nonce)",
            "path_crosses_link_or_reparse_point",
            "validate_descendant(candidate, allow_absent_leaf)",
            "validate_qualification_direct_child",
            "must be a direct child of acceptance root",
            "commit_no_replace(permit_path, consumed_path)",
            "consumed.identity().same_object(permit.identity())",
            "QualificationInterruptHook",
            "request.durable_boundary_hook = &*qualification_hook",
            "request.qualification_claims = qualification_interrupt->claims",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)
        self.assertNotIn("getenv(", source)
        consumed = source.rindex("consume_qualification_interrupt(")
        default_paths = source.index("facman::platform::user_paths()")
        materialize = source.index("materialize_zip_overlay(", consumed)
        self.assertLess(consumed, default_paths)
        self.assertLess(consumed, materialize)
        runtime = (ROOT / "runtime/self_setup/facman_self_setup.cpp").read_text(encoding="utf-8")
        for token in (
            "qualification claims do not bind the unfinished setup journal",
            "qualification boundary was already crossed by the unfinished setup journal",
            "journal.mode != (qualification->installed_mode ? \"installed\" : \"portable\")",
            "self_setup_qualification_interrupt_invalid",
        ):
            with self.subTest(runtime_token=token):
                self.assertIn(token, runtime)


if __name__ == "__main__":
    unittest.main()
