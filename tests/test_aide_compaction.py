# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest
import json
import hashlib
import re
import sys
import tempfile
from pathlib import Path

from tools import aide_compaction_check, project_state

sys.path.insert(0, str(project_state.ROOT / ".aide" / "scripts"))
import aide_lifecycle


class AideCompactionTests(unittest.TestCase):
    def test_queue_history_and_docs_are_compact_and_consistent(self) -> None:
        self.assertEqual([], aide_compaction_check.validate())

    def test_machine_state_has_every_required_truth_family(self) -> None:
        data = project_state.collect()
        for key in (
            "current_revisions", "active_work_unit", "last_closed_work_unit",
            "r3_8_repair", "r3_8_public_integration", "m1_managed_portable_install",
            "m1_public_integration",
            "gate3_public_integration",
            "hermetic_standalone_play_policy",
            "hermetic_standalone_play_candidate",
            "m2_live_portable_setup",
            "m2_wu1_target_policy",
            "m2_wu2_public_lifecycle",
            "m2_wu3_live_evidence",
            "m2_wu4_live_acceptance",
            "m2_wu5_interruption_recovery",
            "m2_wu6_launcher_handoff",
            "m2_wu7_facman_live_portable_workflow",
            "m2_wu8_generated_frontend_workflow",
            "m2_wu9_cross_platform_adversarial_proof",
            "m2_wu10_operator_live_target_verdict",
            "m2_wu10_automated_acceptance_policy",
            "m2_wu10_automated_acceptance_result_attempt",
            "m2_wu10_machine_acceptance_candidate",
            "m2_wu10_machine_acceptance_result",
            "m2_closeout_candidate",
            "m3_existing_portable_adoption",
            "universal_repository_licenses",
            "next_authority_gate",
            "product", "readiness", "execution_foundation", "instance_product_program",
            "operation_permit_program", "host_environment_program", "multi_version_install_lifecycle",
            "gate0_product_convergence_integration", "gate1_installation_model_v2_readonly_closeout",
            "gate2_instance_spec_and_readiness_closeout",
            "execution_modes", "capabilities",
            "quarantined_capabilities", "claim_levels", "provider_pins", "platforms",
            "known_blockers", "current_checkpoint", "completed_wave", "command_law",
            "machine_protocol", "execution", "release", "validation", "safe_beta",
        ):
            self.assertIn(key, data)
        self.assertFalse(data["truth_boundaries"][2].startswith("Automated checks pass"))

    def test_instance_product_model_is_menu_first_and_supersedes_world_aggregate(self) -> None:
        architecture = (
            project_state.ROOT / "docs" / "architecture" / "instance_product_model.md"
        ).read_text(encoding="utf-8")
        superseded = (
            project_state.ROOT / "docs" / "architecture" / "world_product_model.md"
        ).read_text(encoding="utf-8")

        self.assertIn("FacMan's primary product and UX aggregate is a **game instance**", architecture)
        self.assertIn("`facman play <instance>` means `menu`", architecture)
        self.assertIn("A save or world is optional", architecture)
        self.assertIn("`PlatformAccountBinding`", architecture)
        self.assertIn("ModsetSpec", architecture)
        self.assertIn("continue_last", architecture)
        self.assertIn("FACMAN-WORLD-BUNDLE-AND-SAVE-COMPATIBILITY-01", architecture)
        self.assertIn("## Safety laws", architecture)
        safety_laws = architecture.split("## Safety laws", maxsplit=1)[1].split(
            "## Candidate stable workflow surface", maxsplit=1
        )[0]
        self.assertEqual(
            15,
            sum(1 for line in safety_laws.splitlines() if re.match(r"^\d+\. ", line)),
        )
        self.assertIn("It never contains", architecture)
        self.assertRegex(architecture, r"credential\s+values")
        self.assertIn("superseded", superseded)
        self.assertIn("Instance product model", superseded)

    def test_completed_permit_foundation_preserves_historical_proof_and_future_gates(self) -> None:
        data = project_state.collect()
        self.assertEqual(
            "hermetic-standalone-play-verdict",
            data["current_checkpoint"],
        )
        self.assertEqual("real-play-isolation", data["next_authority_gate"])
        self.assertEqual("unavailable", data["execution"]["status"])
        self.assertEqual("Fail", data["execution"]["operator_verdict"])
        self.assertEqual("historical_steam_backed_h1_only", data["execution"]["operator_verdict_scope"])
        self.assertEqual(
            "FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-01",
            data["active_work_unit"],
        )
        self.assertEqual(
            "FACMAN-HERMETIC-STANDALONE-PLAY-CANDIDATE-01",
            data["last_closed_work_unit"],
        )
        self.assertEqual(
            "FACMAN-HERMETIC-STANDALONE-PLAY-ROUTE-PROMOTION-01",
            data["product"]["next_work_unit"],
        )
        instance_program = data["instance_product_program"]
        self.assertEqual("gate2_read_only_projection_complete", instance_program["status"])
        self.assertEqual("FACMAN-INSTANCE-SPEC-AND-READINESS-01", instance_program["work_unit"])
        self.assertEqual("InstanceSpec", instance_program["portable_record"])
        self.assertEqual("InstanceBinding", instance_program["machine_local_record"])
        self.assertEqual("InstanceView", instance_program["ui_aggregate"])
        self.assertEqual("menu", instance_program["default_launch_intent"])
        self.assertEqual("optional_content_within_instance", instance_program["save_role"])
        self.assertIn("account_bindings", instance_program["composition"])
        self.assertIn("modset_spec", instance_program["composition"])
        self.assertEqual("menu", instance_program["launch_intents"][0])
        self.assertIn("map_editor", instance_program["launch_intents"])
        self.assertIn("GraphicsProfile", instance_program["profile_families"])
        self.assertIn("FactorioAccountBinding", instance_program["account_binding_types"])
        self.assertEqual(
            ["ModsetSpec", "ModsetLock", "ModpackBundle"],
            instance_program["mod_content_records"],
        )
        self.assertEqual(
            "FACMAN-WORLD-BUNDLE-AND-SAVE-COMPATIBILITY-01",
            instance_program["world_save_work_unit"],
        )
        self.assertTrue(instance_program["templates_are_initializers"])
        self.assertFalse(instance_program["conflicts_silently_resolved"])
        self.assertFalse(instance_program["credential_values_in_instance"])
        self.assertFalse(instance_program["presets_grant_authority"])
        self.assertFalse(instance_program["foreign_installation_mutation"])
        self.assertFalse(instance_program["runtime_authority"])
        self.assertEqual(
            "dev_integrated_candidate_reviewed_reproduced",
            data["product"]["truth_scope"],
        )
        self.assertFalse(data["product"]["canonical_integration"])
        self.assertTrue(data["product"]["local_counts_promoted"])
        self.assertTrue(data["operation_permit_program"]["provider_revalidation_required"])
        self.assertFalse(data["operation_permit_program"]["permit_issuance_authority"])
        gate3 = data["gate3_operation_permit_closeout"]
        self.assertEqual("accepted_reviewed_dev_integration", gate3["status"])
        self.assertEqual(42, gate3["implementation_pull_request"])
        self.assertEqual(
            "91c2aa4fe0a30be97bf16165b41a95a8fab4cd11",
            gate3["dev_integration_revision"],
        )
        self.assertTrue(gate3["exact_dev_clean_reproduction"])
        self.assertFalse(gate3["permit_issuance_authority"])
        self.assertFalse(gate3["real_factorio_execution"])
        gate3_integration = data["gate3_public_integration"]
        self.assertEqual(
            "accepted_canonical_main_dev_synchronized",
            gate3_integration["status"],
        )
        self.assertEqual(44, gate3_integration["promotion_pull_request"])
        self.assertEqual(
            "810e92ccd52ad89fada8a9bb5699805cb5580c24",
            gate3_integration["canonical_main_revision"],
        )
        self.assertEqual(45, gate3_integration["synchronization_pull_request"])
        self.assertEqual(
            "08d4318ffd32bd9553ce8914cbd8bfc98fde7b74",
            gate3_integration["final_dev_revision"],
        )
        self.assertTrue(gate3_integration["main_is_ancestor_of_dev"])
        self.assertTrue(gate3_integration["trees_equal_at_synchronization"])
        self.assertFalse(gate3_integration["authority_promotion"])
        self.assertFalse(gate3_integration["permit_issuance_authority"])
        self.assertFalse(gate3_integration["real_factorio_execution"])
        hermetic_policy = data["hermetic_standalone_play_policy"]
        self.assertEqual(
            "accepted_canonical_main_dev_synchronized",
            hermetic_policy["status"],
        )
        self.assertEqual(47, hermetic_policy["implementation_pull_request"])
        self.assertEqual(
            "cf674d852e16ceb237ab83dc9254b37b0d900aa2",
            hermetic_policy["reviewed_head_revision"],
        )
        self.assertEqual(
            "51f4fc24c9164762a88b92b4f865b04fe9256d4b",
            hermetic_policy["dev_integration_revision"],
        )
        self.assertTrue(hermetic_policy["local_full_matrix"])
        self.assertTrue(hermetic_policy["exact_dev_clean_reproduction"])
        self.assertEqual(47, hermetic_policy["native_test_count"])
        self.assertEqual(372, hermetic_policy["python_test_count"])
        self.assertEqual(2, hermetic_policy["python_expected_skips"])
        self.assertEqual(
            "6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2",
            hermetic_policy["policy_digest"],
        )
        self.assertEqual("factorio.hermetic_process_tree.v1", hermetic_policy["claim_id"])
        self.assertEqual("menu", hermetic_policy["launch_intent"])
        self.assertEqual("hermetic", hermetic_policy["isolation_mode"])
        self.assertFalse(hermetic_policy["whole_host_immutability_claimed"])
        self.assertFalse(hermetic_policy["permit_issuance_authority"])
        self.assertFalse(hermetic_policy["real_factorio_execution"])
        self.assertFalse(hermetic_policy["authority_promotion"])
        self.assertEqual(48, hermetic_policy["closeout_pull_request"])
        self.assertEqual(49, hermetic_policy["promotion_pull_request"])
        self.assertEqual(50, hermetic_policy["synchronization_pull_request"])
        self.assertEqual(
            "ca9ca5db443544868f3add2802593b7073a5cb20",
            hermetic_policy["canonical_main_revision"],
        )
        self.assertEqual(
            "0b87833252330b8c60df8b096a322fd481a18589",
            hermetic_policy["final_dev_revision"],
        )
        self.assertTrue(hermetic_policy["main_is_ancestor_of_dev"])
        self.assertTrue(hermetic_policy["trees_equal_at_synchronization"])
        self.assertTrue(hermetic_policy["canonical_main_promotion"])
        hermetic_candidate = data["hermetic_standalone_play_candidate"]
        self.assertEqual(
            "accepted_closed_reviewed_dev_integration_eligible_for_human_verdict",
            hermetic_candidate["status"],
        )
        self.assertEqual(52, hermetic_candidate["implementation_pull_request"])
        self.assertEqual(
            "da3e2274a3dc8a5757078b20276a1a6a93084860",
            hermetic_candidate["reviewed_head_revision"],
        )
        self.assertEqual(
            "e9c1e69fee1ae815f62638db8b7263cb01b70389",
            hermetic_candidate["dev_integration_revision"],
        )
        self.assertEqual(53, hermetic_candidate["closeout_pull_request"])
        self.assertEqual(
            "7fe12635f7309e4fd709810dd192d43ff920592f",
            hermetic_candidate["closeout_dev_revision"],
        )
        self.assertEqual("29912502213", hermetic_candidate["closeout_dev_ci_run"])
        self.assertEqual(
            "29912502124", hermetic_candidate["closeout_dev_code_security_run"]
        )
        self.assertEqual(
            "not_triggered_truth_only_local_strict_pass",
            hermetic_candidate["closeout_dev_schema_check"],
        )
        self.assertEqual(
            "29912502140", hermetic_candidate["closeout_dev_security_policy_run"]
        )
        self.assertTrue(hermetic_candidate["exact_head_clean_reproduction"])
        self.assertEqual(48, hermetic_candidate["native_test_count"])
        self.assertEqual(375, hermetic_candidate["python_test_count"])
        self.assertEqual(279, hermetic_candidate["schema_count"])
        self.assertEqual(
            "eligible_for_human_verdict",
            hermetic_candidate["technical_disposition"],
        )
        self.assertEqual("unset", hermetic_candidate["human_verdict"])
        self.assertFalse(hermetic_candidate["public_command"])
        self.assertFalse(hermetic_candidate["product_permit_issuance"])
        self.assertFalse(hermetic_candidate["real_factorio_execution"])
        self.assertFalse(hermetic_candidate["authority_promotion"])
        self.assertFalse(hermetic_candidate["playability_promotion"])
        self.assertFalse(hermetic_candidate["canonical_main_promotion"])
        self.assertFalse(data["host_environment_program"]["blocks_real_play"])
        self.assertTrue(
            data["host_environment_program"]["installation_model_v2_reviewed_committed_clean"]
        )
        lifecycle = data["multi_version_install_lifecycle"]
        self.assertEqual(
            "gate1_read_only_model_complete_remaining_mutation_transferred",
            lifecycle["status"],
        )
        self.assertEqual("implemented_read_only_projection", lifecycle["installation_model_v2"])
        self.assertEqual(
            "implemented_evidence_bound_deterministic_plan_only",
            lifecycle["reconciliation_plan"],
        )
        self.assertFalse(lifecycle["reconciliation_apply"])
        self.assertFalse(lifecycle["umbrella_objective_complete"])
        self.assertEqual(
            "FACMAN-MANAGED-INSTALL-RECONCILIATION-01",
            lifecycle["remaining_lifecycle_work_unit"],
        )
        self.assertTrue(lifecycle["plan_identity_binds_current_evidence"])
        self.assertTrue(lifecycle["zero_write_proof"])
        gate2 = data["gate2_instance_spec_and_readiness_closeout"]
        self.assertEqual("accepted_reviewed_dev_integration", gate2["status"])
        self.assertEqual(39, gate2["implementation_pull_request"])
        self.assertEqual(40, gate2["reproduction_correction_pull_request"])
        self.assertEqual(
            "bbb46c5bfd10cd35fb965b23edc4951784f93ef4",
            gate2["final_dev_revision"],
        )
        self.assertTrue(gate2["exact_dev_clean_reproduction"])
        self.assertEqual(360, gate2["implementation_python_test_count"])
        self.assertEqual(361, gate2["final_python_test_count"])
        self.assertTrue(gate2["read_only_projection"])
        self.assertTrue(gate2["zero_write_proof"])
        self.assertFalse(gate2["preparation_available"])
        self.assertFalse(gate2["execution_available"])
        self.assertFalse(gate2["permit_issuance_authority"])
        self.assertFalse(gate2["authority_promotion"])
        self.assertFalse(gate2["canonical_main_promotion"])
        gate1 = data["gate1_installation_model_v2_readonly_closeout"]
        self.assertEqual("accepted_reviewed_dev_integration", gate1["status"])
        self.assertEqual(37, gate1["implementation_pull_request"])
        self.assertEqual(
            "c9ae60405d0b221faaba364be5f47e524649bb97",
            gate1["reviewed_head_revision"],
        )
        self.assertEqual(
            "6ec47046d1b1f4ab8bddfcc27bcec76a774ff305",
            gate1["dev_integration_revision"],
        )
        self.assertTrue(gate1["exact_dev_clean_reproduction"])
        self.assertTrue(gate1["plan_identity_binds_current_evidence"])
        self.assertTrue(gate1["zero_write_proof"])
        self.assertFalse(gate1["reconciliation_apply"])
        self.assertFalse(gate1["authority_promotion"])
        self.assertFalse(gate1["canonical_main_promotion"])
        gate0 = data["gate0_product_convergence_integration"]
        self.assertEqual("accepted_reviewed_dev_integration", gate0["status"])
        self.assertEqual(34, gate0["pull_request"])
        self.assertEqual(
            "61a7afe6718d3ca36b2c530b83890fcd37cc5c03",
            gate0["reviewed_head_revision"],
        )
        self.assertEqual(
            "62c2503110cdb89b9cc89f19a69903f214d33e3c",
            gate0["dev_integration_revision"],
        )
        self.assertTrue(gate0["exact_head_clean_reproduction"])
        self.assertTrue(gate0["exact_dev_clean_reproduction"])
        self.assertFalse(gate0["authority_promotion"])
        self.assertFalse(gate0["playability_promotion"])
        self.assertFalse(gate0["canonical_main_promotion"])
        self.assertFalse(gate0["signing"])
        self.assertFalse(gate0["publication"])
        self.assertEqual(
            {"instance_isolated", "hermetic"},
            {mode["id"] for mode in data["execution_modes"]},
        )
        self.assertEqual(
            "complete_machine_pass_canonically_promoted",
            data["m2_live_portable_setup"]["status"],
        )
        self.assertEqual("MachinePass", data["m2_live_portable_setup"]["technical_acceptance"])
        self.assertEqual(
            "not_required_for_synthetic_non_executable_lane",
            data["m2_live_portable_setup"]["human_review"],
        )
        self.assertEqual(
            "candidate_within_machine_accepted_policy_scope",
            data["m2_live_portable_setup"]["ordinary_live_apply"],
        )
        self.assertEqual(
            "FACMAN-HERMETIC-STANDALONE-PLAY-CANDIDATE-01",
            data["last_closed_work_unit"],
        )
        self.assertEqual("complete_fake_process_proof", data["execution_foundation"]["status"])
        self.assertFalse(data["execution_foundation"]["real_play_authority"])
        self.assertEqual("accepted_dev_integration_proof", data["m2_wu1_target_policy"]["status"])
        self.assertFalse(data["m2_wu1_target_policy"]["mutation_authority"])
        self.assertEqual("d96384bf8f48230256d35fa7015cbc7374e83319", data["m2_wu1_target_policy"]["facman_dev_integration_revision"])
        self.assertEqual("29318247825", data["m2_wu1_target_policy"]["facman_dev_ci_run"])
        m2_wu2 = data["m2_wu2_public_lifecycle"]
        self.assertEqual("accepted_dev_integration_proof", m2_wu2["status"])
        self.assertEqual(
            "316ee8efec5b962e6c2ed8419c0453c0c6062654",
            m2_wu2["facman_validation_remediation_revision"],
        )
        self.assertEqual(38, m2_wu2["native_test_count"])
        self.assertEqual(339, m2_wu2["python_test_count"])
        self.assertEqual(14, m2_wu2["required_windows_package_tests"])
        self.assertEqual(
            "747b4442cf228561de9fa15834bf78b0dad72f23",
            m2_wu2["facman_dev_integration_revision"],
        )
        self.assertEqual("29326004461", m2_wu2["facman_dev_ci_run"])
        self.assertEqual("29326004230", m2_wu2["facman_dev_code_security_run"])
        self.assertEqual("29326004219", m2_wu2["facman_dev_security_policy_run"])
        self.assertTrue(m2_wu2["plan_commands_read_only"])
        self.assertEqual("unavailable_pending_wu5", m2_wu2["recovery_apply"])
        self.assertEqual("pending", m2_wu2["operator_verdict"])
        self.assertFalse(m2_wu2["execution_authority"])
        m2_wu3 = data["m2_wu3_live_evidence"]
        self.assertEqual("accepted_dev_integration_proof", m2_wu3["status"])
        self.assertEqual(
            "fbbeb762f25921ae05945206fd0c004a52239c13",
            m2_wu3["universal_setup_main_revision"],
        )
        self.assertEqual("pending", m2_wu3["operator_verdict"])
        self.assertFalse(m2_wu3["automation_can_record_operator_verdict"])
        self.assertTrue(m2_wu3["setup_owned_evidence_write"])
        self.assertTrue(m2_wu3["plan_pre_snapshot"])
        self.assertTrue(m2_wu3["capture_recomputes_post_snapshot"])
        self.assertEqual(16, m2_wu3["facman_reviewed_pr"])
        self.assertEqual(
            "5f93f42f97089ae367e718d3466f4421abf43625",
            m2_wu3["facman_task_head_revision"],
        )
        self.assertEqual(
            m2_wu3["facman_task_tree_identity"],
            m2_wu3["facman_dev_tree_identity"],
        )
        self.assertEqual(
            "a8b298a35cd1587cea566886b5a3891153a2b7f2",
            m2_wu3["facman_dev_integration_revision"],
        )
        self.assertEqual("29332570822", m2_wu3["facman_dev_ci_run"])
        self.assertEqual("29332570777", m2_wu3["facman_dev_code_security_run"])
        self.assertEqual("29332570776", m2_wu3["facman_dev_security_policy_run"])
        self.assertEqual("unavailable_pending_operator_acceptance", m2_wu3["ordinary_live_apply"])
        self.assertFalse(m2_wu3["execution_authority"])
        self.assertEqual("none", m2_wu3["h1_inference"])
        m2_wu4 = data["m2_wu4_live_acceptance"]
        self.assertEqual("accepted_dev_integration_proof_pending_operator_verdict", m2_wu4["status"])
        self.assertEqual(18, m2_wu4["facman_reviewed_pr"])
        self.assertEqual("a286b5c42736e1a4189030a51e9b1e5c397552eb", m2_wu4["facman_task_head_revision"])
        self.assertEqual(m2_wu4["facman_task_tree"], m2_wu4["facman_dev_tree"])
        self.assertEqual("5563e3b8de4363d1d42cc2ba6f5829aed0c7405e", m2_wu4["facman_dev_integration_revision"])
        self.assertEqual("29337542209", m2_wu4["facman_dev_ci_run"])
        self.assertEqual("29337541636", m2_wu4["facman_dev_code_security_run"])
        self.assertEqual("29337541937", m2_wu4["facman_dev_security_policy_run"])
        self.assertEqual("9b8196437e41e45bd8d5a613246dabe5b8cdb968", m2_wu4["universal_setup_main_revision"])
        self.assertEqual("6209385f25db1824bcbb7ec599cf2152606be89b", m2_wu4["universal_setup_runner_revision"])
        self.assertEqual(4, m2_wu4["evidence_packet_count"])
        self.assertEqual(4, m2_wu4["journal_count"])
        self.assertEqual(5, m2_wu4["audit_event_count"])
        self.assertEqual(39, m2_wu4["native_test_count"])
        self.assertEqual(339, m2_wu4["python_test_count"])
        self.assertEqual(1, m2_wu4["python_opt_in_skip_count"])
        self.assertEqual(14, m2_wu4["required_windows_package_tests"])
        self.assertEqual(0, m2_wu4["required_windows_package_skips"])
        self.assertEqual(388, m2_wu4["package_tree_file_count"])
        self.assertEqual("expected_fail_observed", m2_wu4["damaged_owned_file_detection"])
        self.assertEqual("pass_old_root_retained", m2_wu4["same_volume_move"])
        self.assertEqual("not_attempted_no_second_authorized_volume", m2_wu4["cross_volume_move"])
        self.assertEqual("refused_and_retained", m2_wu4["foreign_content_uninstall"])
        self.assertEqual("retired", m2_wu4["final_lifecycle_status"])
        self.assertEqual("not_required", m2_wu4["final_recovery_status"])
        self.assertEqual("pending", m2_wu4["operator_verdict"])
        self.assertFalse(m2_wu4["automation_can_record_operator_verdict"])
        self.assertEqual("unavailable_pending_operator_acceptance", m2_wu4["ordinary_live_apply"])
        self.assertEqual("unavailable_pending_wu5", m2_wu4["recovery_apply"])
        self.assertFalse(m2_wu4["execution_authority"])
        self.assertEqual("none", m2_wu4["h1_inference"])
        m2_wu5 = data["m2_wu5_interruption_recovery"]
        self.assertEqual("accepted_dev_integration_proof_pending_operator_verdict", m2_wu5["status"])
        self.assertEqual(19, m2_wu5["facman_reviewed_pr"])
        self.assertEqual("a6cfe28c704df68025094f29be85f8961f745cd1", m2_wu5["facman_task_head_revision"])
        self.assertEqual(m2_wu5["facman_task_tree"], m2_wu5["facman_dev_tree"])
        self.assertEqual("f4b02ac022ee676ca5fdd5d8f31b44709a2c3277", m2_wu5["facman_dev_integration_revision"])
        self.assertEqual("29341098765", m2_wu5["facman_dev_ci_run"])
        self.assertEqual("29341101347", m2_wu5["facman_dev_code_security_run"])
        self.assertEqual("29341100659", m2_wu5["facman_dev_security_policy_run"])
        self.assertEqual("e1ce68e9593ae8d9a35cc0821b5e42c798524453", m2_wu5["universal_setup_main_revision"])
        self.assertEqual(11, m2_wu5["case_count"])
        self.assertEqual([1, 4, 3, 3], [m2_wu5["unchanged_count"], m2_wu5["rolled_back_count"], m2_wu5["completed_count"], m2_wu5["recovery_required_count"]])
        self.assertEqual(40, m2_wu5["native_test_count"])
        self.assertEqual(339, m2_wu5["python_test_count"])
        self.assertEqual(14, m2_wu5["required_windows_package_tests"])
        self.assertEqual(0, m2_wu5["required_windows_package_skips"])
        self.assertEqual(389, m2_wu5["package_tree_file_count"])
        self.assertEqual("exact_staged_rollback_only", m2_wu5["public_recovery_apply"])
        self.assertEqual("pending", m2_wu5["operator_verdict"])
        self.assertFalse(m2_wu5["automation_can_record_operator_verdict"])
        self.assertEqual("unavailable_pending_operator_acceptance", m2_wu5["ordinary_live_apply"])
        self.assertFalse(m2_wu5["execution_authority"])
        m2_wu6 = data["m2_wu6_launcher_handoff"]
        self.assertEqual("accepted_dev_integration_proof_pending_operator_verdict", m2_wu6["status"])
        self.assertEqual("f0b27c2e7f2117f9df0a98edb2264608ab75b664", m2_wu6["facman_task_head_revision"])
        self.assertEqual(m2_wu6["facman_task_tree"], m2_wu6["facman_dev_tree"])
        self.assertEqual("8c1ed53511332da2d9c2fbf04abb2d5e91c4df6c", m2_wu6["facman_dev_integration_revision"])
        self.assertEqual("29344174316", m2_wu6["facman_dev_ci_run"])
        self.assertEqual("29344174402", m2_wu6["facman_dev_codeql_run"])
        self.assertEqual("29344174517", m2_wu6["facman_dev_security_policy_run"])
        self.assertEqual(data["provider_pins"]["universal_launcher"]["revision"], m2_wu6["universal_launcher_main_revision"])
        self.assertEqual("1.3", m2_wu6["launcher_abi_version"])
        self.assertEqual("1.3", m2_wu6["facman_binding_abi_version"])
        self.assertTrue(m2_wu6["recovery_without_install_reference"])
        self.assertEqual("managed_install_recovery_required", m2_wu6["dependent_instance_status"])
        self.assertEqual("stale", m2_wu6["launch_plan_status"])
        self.assertFalse(m2_wu6["launcher_can_mutate_setup"])
        self.assertEqual("universal-setup", m2_wu6["setup_mutation_owner"])
        self.assertEqual("pending", m2_wu6["operator_verdict"])
        self.assertFalse(m2_wu6["automation_can_record_operator_verdict"])
        self.assertEqual("unavailable_pending_operator_acceptance", m2_wu6["ordinary_live_apply"])
        self.assertFalse(m2_wu6["execution_authority"])
        self.assertEqual("none", m2_wu6["h1_inference"])
        self.assertEqual(41, m2_wu6["native_test_count"])
        self.assertEqual(339, m2_wu6["python_test_count"])
        self.assertEqual(1, m2_wu6["python_opt_in_skip_count"])
        self.assertEqual(14, m2_wu6["required_windows_package_tests"])
        self.assertEqual(0, m2_wu6["required_windows_package_skips"])
        self.assertEqual(390, m2_wu6["package_tree_file_count"])
        m2_wu7 = data["m2_wu7_facman_live_portable_workflow"]
        self.assertEqual(
            "accepted_dev_integration_proof_pending_operator_verdict",
            m2_wu7["status"],
        )
        self.assertEqual("1b029ead969e3b68387fcbaef71458ba99f0c33e", m2_wu7["facman_task_head_revision"])
        self.assertEqual("a638e5d078a28751fa12ede205b48595986e5b0f", m2_wu7["facman_task_tree"])
        self.assertEqual(21, m2_wu7["facman_pull_request"])
        self.assertEqual("37c83c6538822a57bf96e03f03c48536f2b97e47", m2_wu7["facman_dev_integration_revision"])
        self.assertEqual(m2_wu7["facman_task_tree"], m2_wu7["facman_dev_tree"])
        self.assertEqual("29347961199", m2_wu7["facman_dev_ci_run"])
        self.assertEqual("29347961372", m2_wu7["facman_dev_codeql_run"])
        self.assertEqual("29347960097", m2_wu7["facman_dev_security_policy_run"])
        self.assertEqual("install_local.plan", m2_wu7["setup_command"])
        self.assertEqual("operator_acceptance", m2_wu7["target_class"])
        self.assertTrue(m2_wu7["plan_is_read_only"])
        self.assertTrue(m2_wu7["plan_binds_source_recipe_target_and_provider"])
        self.assertFalse(m2_wu7["apply_enabled"])
        self.assertEqual("live_target_acceptance_required", m2_wu7["apply_refusal"])
        self.assertEqual("pending", m2_wu7["operator_verdict"])
        self.assertFalse(m2_wu7["automation_can_record_operator_verdict"])
        self.assertFalse(m2_wu7["execution_authority"])
        self.assertEqual("none", m2_wu7["h1_inference"])
        m2_wu8 = data["m2_wu8_generated_frontend_workflow"]
        self.assertEqual(
            "accepted_dev_integration_proof_pending_operator_verdict",
            m2_wu8["status"],
        )
        self.assertEqual("facman.setup_workflow.v1", m2_wu8["workflow_schema"])
        self.assertEqual("991ff78c5cc349dfcd8400f585d319b830d2c922", m2_wu8["implementation_revision"])
        self.assertEqual(["cli", "tui", "winforms", "appkit"], m2_wu8["clients"])
        self.assertEqual("universal-setup", m2_wu8["policy_owner"])
        self.assertFalse(m2_wu8["frontend_policy"])
        self.assertEqual("APPLY", m2_wu8["confirmation_literal"])
        self.assertTrue(m2_wu8["recovery_required_is_distinct"])
        self.assertFalse(m2_wu8["apply_enabled"])
        self.assertEqual("live_target_acceptance_required", m2_wu8["apply_refusal"])
        self.assertEqual("pending", m2_wu8["operator_verdict"])
        self.assertFalse(m2_wu8["automation_can_record_operator_verdict"])
        self.assertFalse(m2_wu8["execution_authority"])
        self.assertEqual("none", m2_wu8["h1_inference"])
        self.assertEqual(14, m2_wu8["required_windows_package_tests"])
        self.assertEqual(0, m2_wu8["required_windows_package_skips"])
        self.assertEqual(392, m2_wu8["package_tree_file_count"])
        m2_wu9 = data["m2_wu9_cross_platform_adversarial_proof"]
        self.assertEqual(
            "accepted_dev_integration_proof_pending_operator_verdict",
            m2_wu9["status"],
        )
        self.assertEqual(["windows", "linux", "macos"], m2_wu9["required_platforms"])
        self.assertEqual([16, 15, 1], [m2_wu9["case_count"], m2_wu9["setup_owned_case_count"], m2_wu9["consumer_case_count"]])
        self.assertEqual("3f8489275077347c2918f3bb03614ec6431362ff", m2_wu9["universal_setup_main_revision"])
        self.assertEqual(m2_wu9["universal_setup_task_tree"], m2_wu9["universal_setup_main_tree"])
        self.assertTrue(m2_wu9["target_ancestor_identity_bound"])
        self.assertEqual([41, 344, 1], [m2_wu9["facman_native_test_count"], m2_wu9["facman_python_test_count"], m2_wu9["python_opt_in_skip_count"]])
        self.assertEqual([14, 0], [m2_wu9["required_windows_package_tests"], m2_wu9["required_windows_package_skips"]])
        self.assertEqual(395, m2_wu9["package_tree_file_count"])
        self.assertEqual("not_proven", m2_wu9["publisher_authenticity"])
        self.assertEqual(23, m2_wu9["facman_reviewed_pr"])
        self.assertEqual(m2_wu9["facman_task_tree"], m2_wu9["facman_dev_integration_tree"])
        self.assertEqual(
            ["29361218441", "29361218988", "29361218569", "29361219348"],
            [m2_wu9["dev_ci_run"], m2_wu9["dev_code_security_run"], m2_wu9["dev_security_policy_run"], m2_wu9["dev_schema_check_run"]],
        )
        self.assertEqual("pending", m2_wu9["operator_verdict"])
        self.assertFalse(m2_wu9["automation_can_record_operator_verdict"])
        self.assertFalse(m2_wu9["execution_authority"])
        m2_wu10 = data["m2_wu10_operator_live_target_verdict"]
        self.assertEqual("historical_machine_evidence_ready_pending_operator_verdict", m2_wu10["status"])
        self.assertEqual("D:\\FacMan-Live-Acceptance\\M2", m2_wu10["acceptance_root"])
        self.assertEqual("m2wu10-20260715-01", m2_wu10["run_id"])
        self.assertEqual(["Pass", "Fail", "Inconclusive"], m2_wu10["verdict_choices"])
        self.assertEqual([10, 4, 26, 14, 40105, 0], [
            m2_wu10["lifecycle_step_count"], m2_wu10["evidence_packet_count"],
            m2_wu10["retained_file_count"], m2_wu10["retained_directory_count"],
            m2_wu10["retained_total_bytes"], m2_wu10["retained_reparse_point_count"],
        ])
        self.assertEqual([5, "removed", "not_required"], [
            m2_wu10["audit_event_count"], m2_wu10["final_committed_closure"],
            m2_wu10["final_recovery_status"],
        ])
        self.assertEqual(11, m2_wu10["interruption_case_count"])
        self.assertEqual([41, 345, 1, 231], [
            m2_wu10["native_test_count"], m2_wu10["python_test_count"],
            m2_wu10["python_opt_in_skip_count"], m2_wu10["schema_count"],
        ])
        self.assertEqual("980d5b9e3113a673782d6efde74291b0c477f14b", m2_wu10["hosted_validation_revision"])
        self.assertEqual(25, m2_wu10["draft_pull_request"])
        self.assertEqual(
            ["29364492582", "29364492665", "29364491886", "29364492053",
             "29364494313", "29364495679", "29364495081", "29364494922"],
            [m2_wu10["task_push_ci_run"], m2_wu10["task_push_code_security_run"],
             m2_wu10["task_push_security_policy_run"], m2_wu10["task_push_schema_check_run"],
             m2_wu10["task_pr_ci_run"], m2_wu10["task_pr_code_security_run"],
             m2_wu10["task_pr_security_policy_run"], m2_wu10["task_pr_schema_check_run"]],
        )
        self.assertEqual("pending", m2_wu10["operator_verdict"])
        self.assertFalse(m2_wu10["automation_can_record_operator_verdict"])
        self.assertFalse(m2_wu10["execution_authority"])
        machine_policy = data["m2_wu10_automated_acceptance_policy"]
        self.assertEqual(
            "accepted_corrected_policy_with_bound_machine_pass",
            machine_policy["status"],
        )
        self.assertEqual(
            "MachinePass",
            machine_policy["technical_acceptance"],
        )
        self.assertEqual(
            "7a3f812ab0f81fb35e2e6104bd573d8832a44e59",
            machine_policy["accepted_policy_revision"],
        )
        self.assertEqual(
            "26eb7056984b42859e377c1ffd0ffb7c80488078",
            machine_policy["correction_revision"],
        )
        self.assertFalse(machine_policy["fresh_lifecycle_rerun_required"])
        self.assertFalse(machine_policy["fresh_interruption_rerun_required"])
        self.assertEqual(12, machine_policy["negative_control_count"])
        result_attempt = data["m2_wu10_automated_acceptance_result_attempt"]
        self.assertEqual("blocked_before_evidence_pass", result_attempt["status"])
        self.assertEqual("fail_closed", result_attempt["verifier_result"])
        self.assertFalse(result_attempt["observation_written"])
        self.assertFalse(result_attempt["machine_pass"])
        self.assertFalse(result_attempt["authority_promotion"])
        candidate = data["m2_wu10_machine_acceptance_candidate"]
        self.assertEqual(
            "hosted_validation_passed_bound_to_separate_machine_result",
            candidate["status"],
        )
        self.assertEqual("pass_complete_matrix", candidate["local_validation"])
        self.assertEqual("pass_exact_candidate_revision", candidate["hosted_validation"])
        self.assertEqual("EvidencePass", candidate["evidence_result"])
        self.assertFalse(candidate["machine_pass"])
        self.assertFalse(candidate["authority_promotion"])
        result = data["m2_wu10_machine_acceptance_result"]
        self.assertEqual("MachinePass", result["status"])
        self.assertEqual("candidate", result["local_managed_portable_setup"])
        self.assertFalse(result["run_execute"])
        self.assertEqual("none", result["h1_inference"])
        closeout = data["m2_closeout_candidate"]
        self.assertEqual(
            "accepted_public_integration_dev_synchronized",
            closeout["status"],
        )
        self.assertEqual(
            "5250db1d17ac330f5ae0b672ccc7466431a1e4a2",
            closeout["wu10_dev_merge_revision"],
        )
        self.assertEqual(
            "bd0642951a4a3abfb2cc1916c8b9c2c4e81d880f",
            closeout["canonical_main_revision"],
        )
        self.assertEqual(
            "ee54dc220ed5fd80a9f450988033c5e29599a326",
            closeout["shared_promoted_tree_identity"],
        )
        self.assertEqual("29569007275", closeout["exact_main_ci_run"])
        self.assertEqual("29569007270", closeout["exact_main_code_security_run"])
        self.assertEqual("29569007323", closeout["exact_main_schema_check_run"])
        self.assertEqual("29569007290", closeout["exact_main_security_policy_run"])
        self.assertEqual(
            "1678cb6d3c9545f09c4ae729054f68cf0fbc7bf2",
            closeout["public_integration_dev_revision"],
        )
        self.assertEqual(
            "51977de8120202958fc35776d284077b1fc027d3",
            closeout["dev_synchronization_revision"],
        )
        self.assertTrue(closeout["dev_synchronization_main_ancestor"])
        self.assertEqual("29573335555", closeout["dev_synchronization_ci_run"])
        self.assertEqual("29573335458", closeout["dev_synchronization_code_security_run"])
        self.assertEqual("29573335488", closeout["dev_synchronization_security_policy_run"])
        self.assertEqual("pass_complete_matrix", closeout["local_validation"])
        self.assertFalse(closeout["run_execute"])
        m3 = data["m3_existing_portable_adoption"]
        self.assertEqual(
            "authorized_backlog_after_playable_alpha",
            m3["status"],
        )
        self.assertEqual("read_only_and_plan_only", m3["scope"])
        self.assertTrue(m3["existing_portable_inspection"])
        self.assertTrue(m3["adoption_plan"])
        self.assertFalse(m3["adoption_apply"])
        self.assertFalse(m3["existing_installation_mutation"])
        self.assertFalse(m3["steam_adoption"])
        self.assertEqual("FACMAN-INSTANCE-CENTRIC-ALPHA-01", m3["resume_after"])
        self.assertEqual(
            "hermetic-standalone-play-verdict",
            data["current_checkpoint"],
        )
        self.assertEqual(
            "FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-01",
            data["active_work_unit"],
        )
        self.assertEqual(
            "FACMAN-HERMETIC-STANDALONE-PLAY-CANDIDATE-01",
            data["last_closed_work_unit"],
        )
        self.assertEqual("closed", data["r3_8_repair"]["status"])
        self.assertEqual(
            "f10aef03517a86a7c9d6afaf8b75c19549b6fa51",
            data["r3_8_repair"]["dev_integration_revision"],
        )
        self.assertEqual("unproven", data["r3_8_repair"]["standalone_manual_isolation"])
        self.assertFalse(data["r3_8_repair"]["authority_promotion"])
        integration = data["r3_8_public_integration"]
        self.assertEqual("accepted", integration["status"])
        self.assertEqual(
            "70d04edb77525ae43945a2199acda87eaf48a469",
            integration["shared_tree_identity"],
        )
        self.assertTrue(integration["main_dev_synchronized_at_proof"])
        self.assertFalse(integration["authority_promotion"])
        self.assertEqual(
            "2f13923a9cbdd60d47cab114ba1e280282259bb5",
            data["validation"]["accepted_revision"],
        )
        self.assertEqual(35, data["validation"]["native_test_count"])
        self.assertEqual(337, data["validation"]["python_test_count"])
        self.assertFalse(data["safe_beta"])
        self.assertEqual(
            "774628f442b0cd92ba7de14553f9bcd423aa3d9a",
            data["completed_wave"]["implementation_proof_revision"],
        )
        self.assertEqual(
            "7bd4425f0c35414f738159b45d8bec42edf70235",
            data["provider_pins"]["universal_launcher"]["revision"],
        )
        m1 = data["m1_managed_portable_install"]
        self.assertEqual("fixture_proven", m1["status"])
        self.assertEqual(
            "2f13923a9cbdd60d47cab114ba1e280282259bb5",
            m1["implementation_head_revision"],
        )
        self.assertEqual(
            "10b1caa915ed4ad5e934f625f3e1384ecc700eaa",
            m1["dev_integration_revision"],
        )
        self.assertEqual(
            "2bc4bf93b1a77c5c906fdc6d3f12b286dadc8ca7",
            m1["universal_setup_revision"],
        )
        self.assertEqual(
            "unavailable_pending_live_target_acceptance",
            m1["ordinary_setup_apply"],
        )
        self.assertFalse(m1["authority_promotion"])
        public_integration = data["m1_public_integration"]
        self.assertEqual("accepted", public_integration["status"])
        self.assertEqual(
            "73bec99916d509b0ab055a43562e93ef20a6b4b7",
            public_integration["canonical_main_revision"],
        )
        self.assertEqual(
            public_integration["dev_tree_identity"],
            public_integration["main_tree_identity"],
        )
        self.assertEqual("29310497458", public_integration["final_main_ci_run"])
        self.assertTrue(public_integration["main_dev_synchronized_at_proof"])
        self.assertFalse(public_integration["authority_promotion"])
        licenses = data["universal_repository_licenses"]
        self.assertEqual("accepted_mit", licenses["status"])
        self.assertEqual(
            "3f8489275077347c2918f3bb03614ec6431362ff",
            data["provider_pins"]["universal_setup"]["revision"],
        )
        self.assertEqual("MIT", licenses["spdx_license_expression"])
        self.assertFalse(licenses["publication_authority"])
        catalog = json.loads(
            (project_state.ROOT / "contracts/generated-index/command_catalog.v2.json").read_text(encoding="utf-8")
        )
        self.assertEqual(catalog["source_digest"], data["command_law"]["catalog_digest"])

    def test_platform_evidence_separates_proof_and_publication_status(self) -> None:
        data = project_state.collect()
        records = data["platforms"]
        self.assertTrue(records)
        for record in records:
            self.assertEqual("unpublished", record["publication_status"])
            self.assertIn(record["support_status"], {"candidate", "experimental", "unavailable"})
        appkit = next(record for record in records if record["id"] == "macos_legacy_appkit_x64")
        self.assertEqual("passed", appkit["compile_status"])
        self.assertEqual("not_proven", appkit["runtime_status"])

    def test_lifecycle_transitions_and_hashes_archived_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            policy = root / "contracts" / "policy"
            policy.mkdir(parents=True)
            source = project_state.ROOT / "contracts" / "policy" / "test_impact.v1.json"
            policy.joinpath("test_impact.v1.json").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            compacted = root / ".aide" / "queue" / "next" / "COMPACTED-EVIDENCE-ONLY"
            compacted.joinpath("evidence").mkdir(parents=True)
            path = aide_lifecycle.create(root, "TEST-LIFECYCLE-01", "Lifecycle proof", "Prove state transitions.", ["docs/"])
            self.assertEqual("planned", aide_lifecycle.state_for(path))
            self.assertEqual("active", aide_lifecycle.transition(root, "TEST-LIFECYCLE-01", "start"))
            active = root / ".aide" / "queue" / "active" / "TEST-LIFECYCLE-01"
            self.assertIn(
                ".aide/queue/active/TEST-LIFECYCLE-01/evidence/",
                active.joinpath("status.yaml").read_text(encoding="utf-8"),
            )
            for action, expected in (("verify", "verified"), ("review", "reviewed"), ("close", "closed")):
                self.assertEqual(expected, aide_lifecycle.transition(root, "TEST-LIFECYCLE-01", action))
            archived = aide_lifecycle.archive(root, "TEST-LIFECYCLE-01", "test-checkpoint")
            self.assertTrue(archived.is_dir())
            self.assertIn(
                ".aide/history/test-checkpoint/TEST-LIFECYCLE-01/evidence/",
                archived.joinpath("status.yaml").read_text(encoding="utf-8"),
            )
            index = json.loads((archived.parent / "index.json").read_text(encoding="utf-8"))
            self.assertTrue(index["immutable_task_records"])
            self.assertEqual("text_lf_v1", index["hash_canonicalization"])
            self.assertIn("task.yaml", index["tasks"][0]["files"])
            task_bytes = archived.joinpath("task.yaml").read_bytes()
            normalized = task_bytes.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            self.assertEqual(
                hashlib.sha256(normalized).hexdigest(),
                index["tasks"][0]["files"]["task.yaml"],
            )

    def test_queue_index_rejects_partially_materialized_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            partial = root / ".aide" / "queue" / "active" / "PARTIAL-RECORD"
            partial.mkdir(parents=True)
            partial.joinpath("task.yaml").write_text("id: PARTIAL-RECORD\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "incomplete mutable queue record"):
                aide_lifecycle.rebuild_queue_index(root)


if __name__ == "__main__":
    unittest.main()
