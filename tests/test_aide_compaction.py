# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest
import json
import hashlib
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
            "m2_live_portable_setup",
            "m2_wu1_target_policy",
            "m2_wu2_public_lifecycle",
            "m2_wu3_live_evidence",
            "m2_wu4_live_acceptance",
            "m2_wu5_interruption_recovery",
            "m2_wu6_launcher_handoff",
            "m2_wu7_facman_live_portable_workflow",
            "m2_wu8_generated_frontend_workflow",
            "universal_repository_licenses",
            "next_authority_gate",
            "quarantined_capabilities", "claim_levels", "provider_pins", "platforms",
            "known_blockers", "current_checkpoint", "completed_wave", "command_law",
            "machine_protocol", "execution", "release", "validation", "safe_beta",
        ):
            self.assertIn(key, data)
        self.assertFalse(data["truth_boundaries"][2].startswith("Automated checks pass"))

    def test_m2_workflows_preserve_human_and_execution_gates(self) -> None:
        data = project_state.collect()
        self.assertEqual("m2-wu8-generated-frontend-workflow", data["current_checkpoint"])
        self.assertEqual("H1", data["next_authority_gate"])
        self.assertEqual("unavailable", data["execution"]["status"])
        self.assertEqual("Fail", data["execution"]["operator_verdict"])
        self.assertIsNone(data["active_work_unit"])
        self.assertEqual(
            "automated_live_lifecycle_complete_pending_operator_verdict",
            data["m2_live_portable_setup"]["status"],
        )
        self.assertEqual("pending", data["m2_live_portable_setup"]["operator_verdict"])
        self.assertEqual(
            "M2-WU8-GENERATED-FRONTEND-WORKFLOW-01",
            data["last_closed_work_unit"],
        )
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
        self.assertEqual(data["provider_pins"]["universal_setup"]["revision"], m2_wu5["universal_setup_main_revision"])
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
            "four_frontend_workflow_and_package_proven_pending_dev_integration_and_operator_verdict",
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
        self.assertEqual("m2-wu8-generated-frontend-workflow", data["current_checkpoint"])
        self.assertEqual("M2-WU8-GENERATED-FRONTEND-WORKFLOW-01", data["last_closed_work_unit"])
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
            "e1ce68e9593ae8d9a35cc0821b5e42c798524453",
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
