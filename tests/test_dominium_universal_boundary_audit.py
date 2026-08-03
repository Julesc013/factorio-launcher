# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "release/index/dominium_universal_boundary_audit.v1.toml"
REPORT = ROOT / "docs/product/dominium_universal_boundary_audit_01.md"
SOURCE_COMMIT = "623ab08ae8c867719d5abc2e60c16a6fbb37b313"
DELETE_GATE = "provider_equivalence_abi_reference_dual_run_and_rollback"
DISPOSITIONS = {"retain", "move", "adapt", "delete"}
OWNERS = {
    "product_policy_presentation",
    "usk_setup_lifecycle",
    "ulk_launcher_lifecycle",
    "development_tooling",
    "legacy_compat_retire",
}


def numbered(prefix: str, first: int, last: int) -> list[str]:
    return [f"{prefix}{number:02d}" for number in range(first, last + 1)]


EXPECTED_ROW_IDS = (
    numbered("S", 1, 10)
    + numbered("I", 1, 3)
    + numbered("R", 1, 11)
    + numbered("C", 1, 8)
    + numbered("L", 1, 3)
    + ["D01"]
    + numbered("N", 1, 20)
    + numbered("H", 1, 11)
)
EXPECTED_FILE_MAP_IDS = numbered("F", 1, 19)
EXPECTED_TEST_IDS = (
    numbered("U", 1, 16)
    + numbered("L", 1, 11)
    + numbered("P", 1, 6)
    + numbered("X", 1, 4)
    + ["D01"]
)

EXPECTED_TEST_LOCATORS = {
    "U01": (
        "tests/characterization/universal/usk_manifest_contract_tests.py::"
        "test_install_manifest_canonical_bytes_refs_and_cross_platform_hash"
    ),
    "U02": (
        "tests/characterization/universal/usk_plan_tests.py::"
        "test_plan_is_deterministic_and_side_effect_free"
    ),
    "U03": (
        "tests/characterization/universal/usk_install_transaction_tests.py::"
        "test_fresh_install_atomic_commit"
    ),
    "U04": (
        "tests/characterization/universal/usk_install_transaction_tests.py::"
        "test_failure_injection_restores_install_and_preexisting_data_exactly"
    ),
    "U05": (
        "tests/characterization/universal/usk_repair_transaction_tests.py::"
        "test_repair_failure_restores_exact_tree_and_retains_terminal_rollback"
    ),
    "U06": (
        "tests/characterization/universal/usk_uninstall_transaction_tests.py::"
        "test_uninstall_success_and_failure_preserve_policy_and_terminal_log"
    ),
    "U07": (
        "tests/characterization/universal/usk_update_tests.py::"
        "test_check_plan_apply_require_confirmation_and_never_download_silently"
    ),
    "U08": (
        "tests/characterization/universal/usk_update_tests.py::"
        "test_update_failure_and_restart_recover_exact_prior_or_target_state"
    ),
    "U09": (
        "tests/characterization/universal/usk_rollback_tests.py::"
        "test_select_restore_and_restart_rollback_transaction"
    ),
    "U10": (
        "tests/characterization/universal/usk_registry_tests.py::"
        "test_multi_install_registry_atomic_sorted_and_recoverable"
    ),
    "U11": (
        "tests/characterization/universal/usk_package_verify_tests.py::"
        "test_package_lock_manifest_trust_and_offline_verification"
    ),
    "U12": (
        "tests/characterization/universal/usk_store_publication_tests.py::"
        "test_store_publication_atomic_hash_checked_concurrent_and_idempotent"
    ),
    "U13": (
        "tests/characterization/universal/usk_store_reachability_tests.py::"
        "test_reachability_follows_every_governed_manifest_and_nested_reference"
    ),
    "U14": (
        "tests/characterization/universal/usk_store_gc_tests.py::"
        "test_gc_none_safe_aggressive_portable_and_conflict_are_transactional"
    ),
    "U15": (
        "tests/characterization/universal/usk_operation_journal_tests.py::"
        "test_each_operation_has_one_terminal_outcome_and_replays_after_crash"
    ),
    "U16": (
        "tests/characterization/universal/usk_extraction_bounds_tests.py::"
        "test_staging_rejects_traversal_symlink_escape_quota_and_partial_payload"
    ),
    "L01": (
        "tests/characterization/universal/ulk_reference_tests.py::"
        "test_product_install_instance_profile_artifact_refs_roundtrip_and_refuse_invalid"
    ),
    "L02": (
        "tests/characterization/universal/ulk_discovery_tests.py::"
        "test_install_discovery_precedence_and_ambiguity"
    ),
    "L03": (
        "tests/characterization/universal/ulk_profile_preference_tests.py::"
        "test_profile_instance_and_preferences_persist_atomically_and_recover"
    ),
    "L04": (
        "tests/characterization/universal/ulk_preflight_tests.py::"
        "test_full_degraded_frozen_inspect_and_refuse_matrix"
    ),
    "L05": (
        "tests/characterization/universal/ulk_launch_plan_tests.py::"
        "test_launch_plan_determinism_and_staleness"
    ),
    "L06": (
        "tests/characterization/universal/ulk_process_tests.py::"
        "test_spawn_success_nonzero_missing_executable_and_signal_terminal_outcomes"
    ),
    "L07": (
        "tests/characterization/universal/ulk_process_tests.py::"
        "test_process_identity_cwd_environment_and_containment"
    ),
    "L08": (
        "tests/characterization/universal/ulk_process_tests.py::"
        "test_bounded_stdout_stderr_timeout_and_cancellation"
    ),
    "L09": (
        "tests/characterization/universal/ulk_session_journal_tests.py::"
        "test_operation_attempt_execution_session_identity_and_crash_recovery"
    ),
    "L10": (
        "tests/characterization/universal/ulk_client_parity_tests.py::"
        "test_cli_c_api_and_dominium_facade_emit_equivalent_requests_and_results"
    ),
    "L11": (
        "tests/characterization/universal/ulk_concurrency_tests.py::"
        "test_duplicate_and_concurrent_attempt_policy"
    ),
    "P01": (
        "tests/characterization/dominium/product_recipe_tests.py::"
        "test_dominium_recipe_golden_binaries_packs_descriptors_and_defaults"
    ),
    "P02": (
        "tests/characterization/dominium/setup_launcher_ui_parity_tests.py::"
        "test_cli_tui_gui_actions_and_refusals_are_equivalent"
    ),
    "P03": (
        "tests/characterization/dominium/launch_adapter_tests.py::"
        "test_dominium_session_to_ulk_process_spec"
    ),
    "P04": (
        "tests/characterization/dominium/launcher_authority_tests.py::"
        "test_entitlement_profile_and_token_mapping"
    ),
    "P05": (
        "tests/characterization/dominium/release_policy_tests.py::"
        "test_channel_support_downgrade_trust_and_no_silent_update_policy"
    ),
    "P06": (
        "tests/characterization/dominium/platform_packaging_smoke_tests.py::"
        "test_supported_legacy_platform_adapters_invoke_same_provider_contract"
    ),
    "X01": (
        "tests/characterization/convergence/local_provider_differential_tests.py::"
        "test_local_and_provider_outputs_trees_refusals_and_logs_match"
    ),
    "X02": (
        "tests/characterization/convergence/provider_purity_tests.py::"
        "test_provider_has_no_dominium_import_ids_paths_or_default_policy"
    ),
    "X03": (
        "tests/characterization/convergence/provider_rollback_tests.py::"
        "test_feature_flag_returns_to_local_engine_with_dual_readable_state"
    ),
    "X04": (
        "tests/characterization/convergence/deletion_gate_tests.py::"
        "test_candidate_has_no_build_reference_runtime_import_exported_abi_or_unique_behavior"
    ),
    "D01": (
        "tests/characterization/dominium/release_tooling_tests.py::"
        "test_generators_consume_provider_schemas_without_owning_runtime_policy"
    ),
}

EXPECTED_MIGRATIONS = [
    "Freeze the named characterization corpus and golden state and log schemas.",
    (
        "Publish neutral USK/ULK identity, refusal, operation, journal and "
        "reference contracts."
    ),
    (
        "Extract read-only USK verification and planning plus ULK reference "
        "and discovery first."
    ),
    (
        "Extract store reads and reachability; redesign atomic publication and "
        "transactional GC before routing writes."
    ),
    (
        "Implement USK transactions with durable recovery, then dual-run install, "
        "repair, update, uninstall and rollback."
    ),
    (
        "Implement ULK launch plans, process backend, attempts, sessions, "
        "containment and bounded I/O."
    ),
    (
        "Adapt Dominium recipes, launch.py, native CLI/TUI/GUI and packaging "
        "facades."
    ),
    "Prove a second non-Dominium consumer and the provider-purity characterization.",
    (
        "Default provider routing on with a one-release local fallback and "
        "dual-readable state."
    ),
    "Only then apply conditional delete rows.",
]


class DominiumUniversalBoundaryAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with MATRIX.open("rb") as handle:
            cls.data = tomllib.load(handle)
        cls.report = REPORT.read_text(encoding="utf-8")

    def test_exact_snapshot_is_read_only_and_moved_no_implementation(self) -> None:
        self.assertEqual(
            self.data["schema"],
            "facman.dominium_universal_boundary_audit.v1",
        )
        self.assertEqual(
            self.data["audit_id"],
            "DOMINIUM-UNIVERSAL-BOUNDARY-AUDIT-01",
        )
        self.assertEqual(self.data["source_repository"], "Julesc013/dominium")
        self.assertEqual(self.data["source_commit"], SOURCE_COMMIT)
        self.assertEqual(self.data["source_branch"], "main")
        self.assertEqual(self.data["source_upstream_delta"], "+0/-0")
        self.assertTrue(self.data["read_only"])
        self.assertFalse(self.data["implementation_moved"])
        self.assertFalse(self.data["implementation_extraction_started"])
        self.assertEqual(self.data["files_modified_in_source"], 0)
        self.assertEqual(self.data["source_worktree_before"], "clean")
        self.assertEqual(self.data["source_worktree_after"], "clean")
        self.assertIn("No implementation code moved", self.data["no_code_move_verdict"])

    def test_grouped_rows_have_exact_ids_and_required_schema(self) -> None:
        rows = self.data["row"]
        self.assertEqual(self.data["grouped_row_count"], 67)
        self.assertEqual([row["id"] for row in rows], EXPECTED_ROW_IDS)
        self.assertEqual(len({row["id"] for row in rows}), len(rows))
        required = {
            "id",
            "kind",
            "paths",
            "symbols",
            "responsibility",
            "permanent_owner",
            "disposition",
            "tests",
            "dependencies",
            "rollback",
            "conditional_delete",
            "delete_gate",
        }
        for row in rows:
            self.assertEqual(set(row), required, row["id"])
            self.assertEqual(row["kind"], "grouped_symbol", row["id"])
            self.assertTrue(row["paths"], row["id"])
            self.assertTrue(row["symbols"], row["id"])
            self.assertTrue(row["responsibility"], row["id"])
            self.assertIsInstance(row["tests"], list, row["id"])
            self.assertIsInstance(row["dependencies"], list, row["id"])
            self.assertTrue(
                all("@" in symbol for symbol in row["symbols"]),
                row["id"],
            )

    def test_file_map_has_exact_rows_and_array_fields(self) -> None:
        rows = self.data["file_map"]
        self.assertEqual(self.data["file_map_row_count"], 19)
        self.assertEqual([row["id"] for row in rows], EXPECTED_FILE_MAP_IDS)
        required = {
            "id",
            "kind",
            "paths",
            "symbols",
            "responsibility",
            "permanent_owner",
            "disposition",
            "tests",
            "dependencies",
            "rollback",
            "conditional_delete",
            "delete_gate",
            "destinations",
            "note",
        }
        for row in rows:
            self.assertEqual(set(row), required, row["id"])
            self.assertEqual(row["kind"], "file_map", row["id"])
            self.assertTrue(row["paths"], row["id"])
            self.assertEqual(row["symbols"], [], row["id"])
            self.assertIsInstance(row["tests"], list, row["id"])
            self.assertIsInstance(row["dependencies"], list, row["id"])
            self.assertTrue(row["destinations"], row["id"])

    def test_owner_and_disposition_enums_are_closed(self) -> None:
        self.assertEqual(set(self.data["allowed_dispositions"]), DISPOSITIONS)
        self.assertEqual(set(self.data["allowed_permanent_owners"]), OWNERS)
        for row in self.data["row"] + self.data["file_map"]:
            self.assertIn(row["disposition"], DISPOSITIONS, row["id"])
            self.assertIn(row["permanent_owner"], OWNERS, row["id"])
        for capability in self.data["capability"]:
            self.assertIn(
                capability["permanent_owner"],
                OWNERS,
                capability["id"],
            )

    def test_delete_dispositions_are_conditional_and_reversible(self) -> None:
        gate = self.data["delete_gate"]
        self.assertTrue(gate["conditional"])
        self.assertEqual(gate["code"], DELETE_GATE)
        self.assertFalse(gate["current_deletion_ratified"])
        all_rows = self.data["row"] + self.data["file_map"]
        delete_rows = [row for row in all_rows if row["disposition"] == "delete"]
        self.assertTrue(delete_rows)
        for row in all_rows:
            is_delete = row["disposition"] == "delete"
            self.assertEqual(row["conditional_delete"], is_delete, row["id"])
            self.assertEqual(
                row["delete_gate"],
                DELETE_GATE if is_delete else "not_applicable",
                row["id"],
            )
            if is_delete:
                self.assertIn("X04", row["tests"], row["id"])
                self.assertIn(row["rollback"], {"R3", "R4"}, row["id"])
        self.assertEqual(set(self.data["rollback_law"]), {"R0", "R1", "R2", "R3", "R4"})

    def test_characterization_inventory_is_exact(self) -> None:
        tests = self.data["characterization_test"]
        self.assertEqual(self.data["characterization_test_count"], 38)
        self.assertEqual([test["id"] for test in tests], EXPECTED_TEST_IDS)
        actual = {
            test["id"]: f'{test["path"]}::{test["function"]}'
            for test in tests
        }
        self.assertEqual(actual, EXPECTED_TEST_LOCATORS)
        self.assertTrue(all(test["assertion"] for test in tests))
        known_tests = set(EXPECTED_TEST_IDS)
        for row in self.data["row"] + self.data["file_map"]:
            self.assertLessEqual(set(row["tests"]), known_tests, row["id"])

    def test_migration_order_is_exact_and_deletion_is_last(self) -> None:
        steps = self.data["migration_step"]
        self.assertEqual([step["order"] for step in steps], list(range(1, 11)))
        self.assertEqual(
            [step["id"] for step in steps],
            numbered("M", 1, 10),
        )
        self.assertEqual(
            [step["requirement"] for step in steps],
            EXPECTED_MIGRATIONS,
        )
        self.assertEqual(steps[-1]["requirement"], "Only then apply conditional delete rows.")

    def test_minimum_scope_and_runtime_process_surface_are_present(self) -> None:
        paths = {
            path
            for row in self.data["row"] + self.data["file_map"]
            for path in row["paths"]
        }
        required = {
            "tools/package/setup/setup_cli.py",
            "tools/package/libraries/install/install_validator.py",
            "runtime/package/install_discovery_engine.py",
            "tools/release/update_resolver.py",
            "tools/release/component_graph_resolver.py",
            "tools/package/libraries/store/content_store.py",
            "tools/package/libraries/store/reachability_engine.py",
            "runtime/storage/gc_engine.py",
            "tools/package/launcher/launcher_cli.py",
            "tools/package/launcher/launch.py",
            "apps/setup/cli/setup_cli_main.c",
            "apps/launcher/cli/launcher_cli_main.c",
            "apps/launcher/lifecycle/launcher_process_stub.c",
            "runtime/platform/win32/setup/win32/dsu_gui_stub.c",
            "runtime/platform/win32/launcher/win32/launcher_app_win32.cpp",
        }
        self.assertLessEqual(required, paths)

    def test_references_are_repository_relative_and_dependencies_resolve(self) -> None:
        dependency_ids = {item["id"] for item in self.data["dependency"]}
        windows_absolute = re.compile(r"^[A-Za-z]:[\\/]")
        for row in self.data["row"] + self.data["file_map"]:
            for path in row["paths"]:
                self.assertFalse(Path(path).is_absolute(), path)
                self.assertIsNone(windows_absolute.match(path), path)
            self.assertLessEqual(set(row["dependencies"]), dependency_ids, row["id"])
            self.assertIn(row["rollback"], self.data["rollback_law"], row["id"])

    def test_capability_and_defect_inventories_are_present(self) -> None:
        capabilities = {item["id"] for item in self.data["capability"]}
        self.assertEqual(
            capabilities,
            {
                "package_authoring",
                "package_verification",
                "install",
                "repair",
                "uninstall",
                "update",
                "rollback_recovery",
                "installed_state_registry",
                "install_product_instance_refs",
                "profiles_instances",
                "content_store",
                "store_reachability_gc",
                "preflight",
                "launch_plan_staleness",
                "process_supervision",
                "launch_sessions_journals",
                "cli_tui_gui",
                "entitlement_authority_mapping",
                "legacy_os_packaging",
            },
        )
        self.assertEqual(
            [item["id"] for item in self.data["defect"]],
            numbered("DEF", 1, 12),
        )

    def test_markdown_report_carries_snapshot_rows_and_verdict(self) -> None:
        self.assertIn(SOURCE_COMMIT, self.report)
        self.assertIn("read_only = true", self.report)
        self.assertIn("implementation_moved = false", self.report)
        self.assertIn("No-code-move verdict", self.report)
        self.assertIn("Expansion rule", self.report)
        for row_id in EXPECTED_ROW_IDS:
            self.assertRegex(self.report, rf"(?m)^{re.escape(row_id)}$")
        for test_id in EXPECTED_TEST_IDS:
            self.assertRegex(self.report, rf"(?m)^{re.escape(test_id)}$")


if __name__ == "__main__":
    unittest.main()
