# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import unittest
from pathlib import Path

import jsonschema

from tools import json_contract


ROOT = Path(__file__).resolve().parents[1]
V1_SCHEMA_PATH = ROOT / "contracts/schema/facman/facman_setup_operation_journal.v1.schema.json"
V2_SCHEMA_PATH = ROOT / "contracts/schema/facman/facman_setup_operation_journal.v2.schema.json"


class SelfSetupRecoveryContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = json.loads(V1_SCHEMA_PATH.read_text(encoding="utf-8"))
        self.validator = jsonschema.Draft202012Validator(self.schema)
        self.v2_schema = json.loads(V2_SCHEMA_PATH.read_text(encoding="utf-8"))
        self.v2_validator = jsonschema.Draft202012Validator(self.v2_schema)
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
                "installed_source_digest": "d" * 64,
                "request_id": "request.setup.install.0123456789abcdef0123456789abcdef",
                "plan_id": "request.setup.install.0123456789abcdef0123456789abcdef",
                "transaction_id": "tx.setup.install.0123456789abcdef0123456789abcdef",
                "created_at": "2026-09-13T00:00:00Z",
                "plan_digest": "b" * 64,
                "phase": "apply_entered",
                "receipt_identity": "c" * 64,
            },
            "recovery": {"plan_id": "", "plan_digest": "", "created_at": "", "action": ""},
            "effects": {
                "files": "applied",
                "repair_source": "applied",
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

    def assert_v2_schema_valid(self, value: dict) -> None:
        self.assertEqual(json_contract.validate(value, self.v2_schema), [])
        self.assertEqual(list(self.v2_validator.iter_errors(value)), [])

    def assert_v2_schema_invalid(self, value: dict) -> None:
        self.assertTrue(list(self.v2_validator.iter_errors(value)))

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

    def test_v1_remains_the_closed_legacy_journal_contract(self) -> None:
        legacy_with_install_id = json.loads(json.dumps(self.value))
        legacy_with_install_id["install_id"] = "facman.self"
        self.assert_schema_invalid(legacy_with_install_id)

    def test_v2_requires_a_bounded_exact_install_id(self) -> None:
        value = json.loads(json.dumps(self.value))
        value["schema"] = "facman.setup_operation_journal.v2"
        value["install_id"] = "facman.self.generation.0123456789abcdef"
        self.assertFalse(self.v2_schema["additionalProperties"])
        self.assert_v2_schema_valid(value)
        self.assert_schema_invalid(value)

        missing = json.loads(json.dumps(value))
        del missing["install_id"]
        self.assert_v2_schema_invalid(missing)
        for invalid_id in ("facman/self", "", "x" * 161):
            with self.subTest(invalid_id=invalid_id):
                invalid = json.loads(json.dumps(value))
                invalid["install_id"] = invalid_id
                self.assert_v2_schema_invalid(invalid)

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
            ("install", "installed", "files_applied", "pending", "pending", "pending"),
            # Crash after the shortcut receipt and before registry application.
            ("repair", "installed", "native_applying", "applied", "applied", "pending"),
            # Native effect may have happened although its receipt was lost.
            ("repair", "installed", "native_applying", "applied", "applying", "pending"),
            # USK uninstall can commit before owned native effects are removed.
            ("uninstall", "installed", "files_applied", "not_applicable", "pending", "pending"),
            # --no-shell-integration never claims Windows effects.
            ("install", "portable", "completed", "not_applicable", "not_applicable", "not_applicable"),
            # Provider rollback is terminal and permits a later fresh attempt.
            ("install", "installed", "rolled_back", "applied", "pending", "pending"),
            # Repair retention may commit before a reviewed provider plan.
            ("repair", "installed", "intent", "applied", "pending", "pending"),
        )
        for operation, mode, state, repair_source, shortcut, registration in cases:
            with self.subTest(operation=operation, mode=mode, state=state):
                value = json.loads(json.dumps(self.value))
                self.set_operation(value, operation)
                value["mode"] = mode
                value["state"] = state
                value["effects"]["repair_source"] = repair_source
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
                if state == "intent":
                    value["effects"]["files"] = "pending"
                    value["provider"]["plan_digest"] = ""
                    value["provider"]["phase"] = "before_plan"
                    value["provider"]["receipt_identity"] = ""
                self.assert_schema_valid(value)

    def test_terminal_and_recovery_cross_fields_reject_incompatible_records(self) -> None:
        cases = []
        completed = json.loads(json.dumps(self.value))
        completed["state"] = "completed"
        completed["effects"]["shortcut"] = "pending"
        cases.append(completed)
        completed_uninstall = json.loads(json.dumps(self.value))
        self.set_operation(completed_uninstall, "uninstall")
        completed_uninstall["state"] = "completed"
        completed_uninstall["effects"] = {
            "files": "pending",
            "repair_source": "not_applicable",
            "shortcut": "pending",
            "registration": "pending",
        }
        cases.append(completed_uninstall)
        rolled_back = json.loads(json.dumps(self.value))
        rolled_back["state"] = "rolled_back"
        rolled_back["effects"] = {"files": "pending", "repair_source": "applied", "shortcut": "applied", "registration": "pending"}
        cases.append(rolled_back)
        partial_review = json.loads(json.dumps(self.value))
        partial_review["recovery"] = {"plan_id": "recovery.plan.setup.install.x", "plan_digest": "", "created_at": "", "action": "rollback"}
        cases.append(partial_review)
        abandoned = json.loads(json.dumps(self.value))
        abandoned["state"] = "abandoned"
        abandoned["effects"] = {"files": "pending", "repair_source": "pending", "shortcut": "pending", "registration": "pending"}
        abandoned["provider"]["plan_digest"] = ""
        abandoned["provider"]["phase"] = "before_plan"
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
        value["effects"] = {"files": "pending", "repair_source": "pending", "shortcut": "pending", "registration": "pending"}
        value["provider"]["plan_digest"] = ""
        value["provider"]["phase"] = "before_plan"
        value["provider"]["receipt_identity"] = ""
        value["recovery_boundary"] = "abandoned_before_provider_apply"
        self.assert_schema_valid(value)

    def test_provider_phase_separates_preentry_from_ambiguous_apply(self) -> None:
        preentry = json.loads(json.dumps(self.value))
        preentry["state"] = "files_applying"
        preentry["effects"]["files"] = "pending"
        preentry["effects"]["shortcut"] = "pending"
        preentry["effects"]["registration"] = "pending"
        preentry["provider"]["receipt_identity"] = ""
        preentry["provider"]["phase"] = "plan_reviewed"
        self.assert_schema_valid(preentry)

        contradictory = json.loads(json.dumps(preentry))
        contradictory["provider"]["phase"] = "before_plan"
        self.assert_schema_invalid(contradictory)

        crossed = json.loads(json.dumps(self.value))
        crossed["provider"]["phase"] = "plan_reviewed"
        self.assert_schema_invalid(crossed)

        legacy = json.loads(json.dumps(self.value))
        del legacy["provider"]["phase"]
        self.assert_schema_valid(legacy)

    def test_installed_source_identity_is_bound_when_provider_effects_can_exist(self) -> None:
        value = json.loads(json.dumps(self.value))
        value["provider"]["installed_source_digest"] = ""
        self.assert_schema_invalid(value)

        self.set_operation(value, "uninstall")
        value["effects"]["repair_source"] = "not_applicable"
        value["provider"]["plan_digest"] = ""
        value["provider"]["phase"] = "before_plan"
        value["state"] = "intent"
        value["effects"]["files"] = "pending"
        value["effects"]["shortcut"] = "pending"
        self.assert_schema_valid(value)
        value["provider"]["plan_digest"] = "b" * 64
        value["provider"]["phase"] = "plan_reviewed"
        self.assert_schema_invalid(value)
        value["provider"]["installed_source_digest"] = "d" * 64
        self.assert_schema_valid(value)

    def test_runtime_admission_binds_stale_identity_and_ownership_to_recovery(self) -> None:
        source = (ROOT / "runtime/self_setup/facman_self_setup.cpp").read_text(encoding="utf-8")
        for boundary in (
            'discover_root_journal(coordinator.value(), root_identity)',
            'active.product_version = journal.product_version',
            'journal.provider_state_root',
            'journal.provider_phase',
            'provider_plan_reviewed_before_apply',
            'repair_source_applied_before_provider',
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
            "current_executable_path",
            "SetupPackageMaterializer",
            "validate_maintenance_launcher",
            "request.durable_boundary_hook = &*qualification_hook",
            "request.qualification_claims = qualification_interrupt->claims",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)
        self.assertNotIn("getenv(", source)
        consumed = source.rindex("consume_qualification_interrupt(")
        default_paths = source.index("facman::platform::user_paths()")
        materializer_binding = source.index(
            "request.package_materializer = &package_materializer", consumed
        )
        self.assertLess(consumed, default_paths)
        self.assertLess(consumed, materializer_binding)
        runtime = (ROOT / "runtime/self_setup/facman_self_setup.cpp").read_text(encoding="utf-8")
        for token in (
            "qualification claims do not bind the unfinished setup journal",
            "qualification boundary was already crossed by the unfinished setup journal",
            "journal.mode != (qualification->installed_mode ? \"installed\" : \"portable\")",
            "self_setup_qualification_interrupt_invalid",
            "active.package_materializer->materialize(active.package)",
            "journal.repair_source == \"applied\"",
        ):
            with self.subTest(runtime_token=token):
                self.assertIn(token, runtime)

    def test_first_repair_retention_creates_and_pins_cache_before_leaf_validation(self) -> None:
        source = (ROOT / "apps/setup/main.cpp").read_text(encoding="utf-8")
        start = source.index("facman::self_setup::RetainedSourceResult retain_repair_source(")
        end = source.index("\nclass SetupNativeEffects final", start)
        retention = source[start:end]

        state_open = retention.index("state.open_no_follow(state_root)")
        absent_cache = retention.index("state.validate_descendant(directory, true)")
        create_cache = retention.index("fs::create_directory(directory, status)")
        pin_cache = retention.index("cache.open_no_follow(directory)")
        revalidate_state = retention.index("state.revalidate()", pin_cache)
        absent_destination = retention.index(
            "state.validate_descendant(destination, true)", pin_cache
        )
        self.assertLess(state_open, absent_cache)
        self.assertLess(absent_cache, create_cache)
        self.assertLess(create_cache, pin_cache)
        self.assertLess(pin_cache, revalidate_state)
        self.assertLess(revalidate_state, absent_destination)
        self.assertNotIn(
            "state.validate_descendant(destination, true)",
            retention[absent_cache:create_cache],
        )

    def test_provider_state_is_isolated_below_facman_owned_setup_state(self) -> None:
        source = (ROOT / "runtime/self_setup/facman_self_setup.cpp").read_text(
            encoding="utf-8"
        )
        command = source[source.index(
            "facman::core::Result<std::string> command_with("
        ) :]
        injected = command.index("provider->command(")
        provider_child = command.index('(state_root / "usk").lexically_normal()')
        provider_config = command.index("config.state_root = state.c_str()")
        self.assertLess(injected, provider_child)
        self.assertLess(provider_child, provider_config)
        self.assertIn(
            "return command_with(injected_provider", command
        )
        self.assertIn('active.state_root / "repair-sources"', source)

    def test_maintenance_cutover_holds_and_revalidates_native_edge_pins(self) -> None:
        source = (ROOT / "apps/setup/main.cpp").read_text(encoding="utf-8")
        maintenance = source[source.index(
            "class MaintenanceEffects final"
        ):source.index("class QualificationInterruptHook final")]
        for token in (
            "PinnedRepairSource target_pins_",
            "StableInputFile target_gui_",
            "StableInputFile target_maintenance_",
            "installed maintenance launcher differs from the retained helper",
            "target_gui_.revalidate_path()",
            "target_maintenance_.revalidate_path()",
            "return {false, true, {}, detail}",
        ):
            with self.subTest(token=token):
                self.assertIn(token, maintenance)
        apply = maintenance.index("apply_windows_cutover_effect")
        post_apply = maintenance.index("revalidate_target_pins()", apply)
        unknown = maintenance.index("return {false, true, {}, detail}", post_apply)
        self.assertLess(apply, post_apply)
        self.assertLess(post_apply, unknown)


if __name__ == "__main__":
    unittest.main()
