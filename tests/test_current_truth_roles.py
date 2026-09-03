# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

from copy import deepcopy
import tomllib
import unittest
from pathlib import Path

from tools import project_state


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "release" / "index" / "project_status.v2.toml"
CURRENT_STATE_PATH = ROOT / "release" / "index" / "current_state.v1.toml"
PLAN_PATH = ROOT / "release" / "index" / "plan.v1.toml"
OPERATOR_DESIGNATION_PATH = (
    ROOT
    / ".aide"
    / "history"
    / "windows-instance-isolated-play-revalidation-04-superseded-before-observer-self-test"
    / "FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-04"
    / "evidence"
    / "operator-designation.md"
)
SUSPENSION_PATH = OPERATOR_DESIGNATION_PATH.with_name(
    "superseded-before-observer.md"
)

MAIN = "4683ecd9a1b9ead5eb84be152760d12583da0f0e"
REVIEWED_DEV_CHECKPOINT = "0d61feede2acd49bf54a4a7a1cd00bba3c867fb2"
REVIEWED_DEV_TREE = "5ff92f7ee668a900dfe26bbdcba2c061492358de"
CANDIDATE_INTEGRATION = "488994a81ddb5eb54d541ef3a48b64ca83f67d4a"
CANDIDATE_TREE = "c07938618bc0f533fd12756cba123f54b8592048"
PROMOTION_SOURCE = MAIN
QUALIFICATION_SOURCE = "2c393acf838dd432d37f8acce50d01f91bfd28ca"
CURRENT_QUALIFICATION_SOURCE = MAIN
ULK_MAIN = "5479939ca5cbc9ee0f901608a92012778b4752ae"
ULK_DEV = "5c2b6eb8ead53db863103a5190fa4fa130f64d42"
ULK_PIN = ULK_MAIN
USK_MAIN = "d2a2aae7e61c47035c92334b0522143b4fea3880"
USK_DEV = "d7057ee397fd172863d4ed31aaf7cc6dcf57b961"
USK_PIN = USK_MAIN
REVALIDATION_02 = "FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-02"
REVALIDATION_03 = "FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-03"
REVALIDATION_04 = "FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-04"
REPAIR = "FACMAN-OBSERVER-SELF-TEST-IMPORT-CLOSURE-01"
QUALIFICATION_04 = "FACMAN-WINDOWS-INSTANCE-ISOLATED-CANDIDATE-QUALIFICATION-04"
ROUTE_BINDING_REPAIR = "FACMAN-INSTANCE-ISOLATED-OBSERVER-ROUTE-BINDING-01"
QUALIFICATION_05 = "FACMAN-WINDOWS-INSTANCE-ISOLATED-CANDIDATE-QUALIFICATION-05"


def load_toml(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


class CurrentTruthRoleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.status = load_toml(STATUS_PATH)
        self.current = load_toml(CURRENT_STATE_PATH)
        self.plan = load_toml(PLAN_PATH)

    def test_reviewed_checkpoint_roles_are_exact_and_distinct(self) -> None:
        self.assertEqual(
            self.status["revision_snapshot_kind"], "reviewed_checkpoint_truth"
        )
        self.assertEqual(
            self.status["live_checkout_observation_tool"],
            "tools/current_checkout_observation.py",
        )
        self.assertEqual(self.status["canonical_main_revision"], MAIN)
        self.assertEqual(self.status["planning_promotion_revision"], MAIN)
        self.assertEqual(
            self.status["reviewed_dev_checkpoint_revision"], REVIEWED_DEV_CHECKPOINT
        )
        self.assertEqual(
            self.status["reviewed_dev_checkpoint_tree"], REVIEWED_DEV_TREE
        )
        self.assertEqual(
            self.status["dev_synchronization_revision"], REVIEWED_DEV_CHECKPOINT
        )
        self.assertEqual(
            self.status["truth_closeout_revision"], REVIEWED_DEV_CHECKPOINT
        )
        self.assertNotIn("current_dev_revision", self.status)
        self.assertNotIn("observed_branch_head", self.status)
        self.assertEqual(self.status["promotion_source_revision"], PROMOTION_SOURCE)
        self.assertEqual(self.status["qualification_source_revision"], MAIN)
        self.assertEqual(self.status["qualification_evidence_revision"], MAIN)
        self.assertEqual(
            self.status["qualification_integration_revision"],
            CANDIDATE_INTEGRATION,
        )
        self.assertNotEqual(REVIEWED_DEV_CHECKPOINT, MAIN)

    def test_generated_current_state_exposes_each_revision_role(self) -> None:
        snapshot = self.current["revision_snapshot"]
        self.assertEqual(snapshot["kind"], "reviewed_checkpoint_truth")
        self.assertEqual(
            snapshot["live_checkout_claim"], "generated_after_checkout_not_tracked"
        )
        self.assertEqual(
            snapshot["live_checkout_observation_tool"],
            "tools/current_checkout_observation.py",
        )
        revisions = self.current["revisions"]
        self.assertEqual(revisions["canonical_main"], MAIN)
        self.assertEqual(revisions["planning_promotion"], MAIN)
        self.assertEqual(revisions["reviewed_dev_checkpoint"], REVIEWED_DEV_CHECKPOINT)
        self.assertEqual(revisions["reviewed_dev_checkpoint_tree"], REVIEWED_DEV_TREE)
        self.assertNotIn("observed_dev", revisions)
        self.assertNotIn("observed_branch_head", revisions)
        self.assertEqual(
            revisions["dev_synchronization"], REVIEWED_DEV_CHECKPOINT
        )
        self.assertEqual(revisions["truth_closeout"], REVIEWED_DEV_CHECKPOINT)
        self.assertEqual(revisions["promotion_source"], PROMOTION_SOURCE)
        self.assertEqual(
            revisions["qualification_source"], CURRENT_QUALIFICATION_SOURCE
        )
        self.assertEqual(revisions["qualification_evidence"], MAIN)
        self.assertEqual(
            revisions["qualification_integration"], CANDIDATE_INTEGRATION
        )
        alpha5 = self.current["alpha5_exact_candidate"]
        self.assertEqual(alpha5["source_revision"], MAIN)
        self.assertEqual(alpha5["source_tree"], CANDIDATE_TREE)
        self.assertEqual(alpha5["run"], 33603385303)
        self.assertEqual(alpha5["attempt"], 1)
        self.assertFalse(alpha5["candidate_source_is_closeout_revision"])
        self.assertFalse(alpha5["candidate_source_is_dev_sync_revision"])
        self.assertFalse(alpha5["closeout_revision_candidate_qualified"])
        self.assertFalse(
            alpha5["synchronized_tree_extends_revision_qualification"]
        )
        self.assertFalse(
            alpha5["current_main_after_closeout_qualified_by_this_receipt"]
        )
        self.assertTrue(alpha5["future_revision_requires_new_candidate_run"])
        self.assertFalse(alpha5["beta_ready"])
        self.assertFalse(alpha5["factorio_execution"])
        self.assertFalse(alpha5["publication"])
        providers = self.current["provider_convergence"]
        self.assertEqual(providers["universal_launcher_main_revision"], ULK_MAIN)
        self.assertEqual(providers["universal_launcher_dev_revision"], ULK_DEV)
        self.assertEqual(providers["universal_launcher_consumed_pin"], ULK_PIN)
        self.assertEqual(providers["universal_setup_main_revision"], USK_MAIN)
        self.assertEqual(providers["universal_setup_dev_revision"], USK_DEV)
        self.assertEqual(providers["universal_setup_consumed_pin"], USK_PIN)
        self.assertTrue(providers["provider_promotions_complete"])
        self.assertTrue(providers["provider_pins_reconciled"])
        journey = self.current["journey_convergence"]
        self.assertEqual(
            journey["truth_closeout"], "complete_incorporated_by_protected_dev_pr_163"
        )
        self.assertEqual(
            journey["fake_session_bridge"], "complete_integrated_pr_154_and_incorporated_stack"
        )
        self.assertEqual(
            journey["presentation_action_binding"], "complete_cross_frontend_candidate_stack"
        )
        self.assertEqual(journey["ulk_last_run_authority"], "complete_canonical")
        self.assertEqual(
            journey["winforms_presentation_adoption"],
            "complete_integrated_engineering_qualified",
        )
        self.assertFalse(journey["real_factorio_execution"])
        candidate = self.current["technical_preview_candidate"]
        self.assertEqual(candidate["required_capability_rows"], 29)
        self.assertEqual(
            candidate["package_qualification_status"],
            "pass_exact_source_three_root_non_authorizing",
        )
        self.assertEqual(candidate["package_reproducibility_roots"], 3)
        self.assertEqual(
            candidate["package_qualification_source_revision"],
            "0df94467637836a364f684a43b887d8133ed4388",
        )
        self.assertEqual(
            candidate["package_archive_sha256"],
            "4d878d3dc2c1420360301b4af95669fc2fbf90cb569fe60febc8edc88a5fc870",
        )
        self.assertEqual(
            candidate["package_native_verifier"],
            "pass_intact_and_refuse_drift_3_of_3",
        )
        self.assertFalse(candidate["human_accessibility_receipt"])
        self.assertFalse(candidate["publication"])
        self.assertEqual(
            providers["source_closure_state"],
            "deferred_external",
        )
        self.assertEqual(providers["source_closure_status"], "deferred_external")
        self.assertEqual(providers["source_closure_result"], "not_run")
        self.assertEqual(providers["current_valid_evidence"], [])
        self.assertEqual(
            providers["source_closure_blockers"],
            ["qualified_clean_windows_host_and_private_read_only_archive_not_yet_bound"],
        )
        self.assertEqual(
            providers["route_index_contract"],
            "release/index/successor_play_route.index.v1.toml",
        )
        self.assertEqual(
            providers["historical_route_contract"],
            "release/index/successor_play_route.v1.toml",
        )
        self.assertEqual(
            providers["active_route_contract"],
            "release/index/successor_play_route.v2.toml",
        )
        self.assertEqual(
            providers["active_route_id"],
            "facman.play.windows-x64.factorio-2.0.77.standalone.menu.instance-isolated.successor.v2",
        )
        self.assertEqual(
            providers["active_route_integration"],
            "invalidated_by_protected_provider_package_adoption",
        )
        self.assertEqual(providers["accepted_play_routes"], 0)
        self.assertEqual(providers["observed_player_journeys"], 0)
        self.assertFalse(providers["factorio_execution"])
        self.assertFalse(providers["signing"])
        self.assertFalse(providers["publication"])

    def test_candidate_package_truth_refuses_digest_and_authority_drift(self) -> None:
        self.assertEqual(project_state.validate_status(self.status), [])

        digest_drift = deepcopy(self.status)
        digest_drift["technical_preview_candidate"]["package_archive_sha256"] = (
            "0" * 64
        )
        problems = project_state.validate_status(digest_drift)
        self.assertTrue(
            any("package_archive_sha256" in problem for problem in problems),
            problems,
        )

        authority_drift = deepcopy(self.status)
        authority_drift["technical_preview_candidate"]["publication"] = True
        problems = project_state.validate_status(authority_drift)
        self.assertIn(
            "technical preview candidate must keep publication false",
            problems,
        )

    def test_plan_observes_suspended_revalidation_04(self) -> None:
        gate = next(
            item for item in self.plan["gate"]
            if item["external_ref"] == REVALIDATION_04
        )
        self.assertEqual(gate["status"], "blocked")
        self.assertEqual(gate["external_ref"], REVALIDATION_04)
        self.assertEqual(gate["stage"], "superseded_before_observer_self_test")
        self.assertIn(".aide/history/", gate["source"])
        self.assertEqual(gate["owner"], "Jules")
        self.assertFalse(gate["operator_assignment_required"])
        self.assertEqual(gate["gate_scope"], "authority_only")
        self.assertEqual(
            gate["blocks"],
            [
                "FACMAN-EXACT-PLAY-ROUTE-CAPABILITY-01",
                "FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-ROUTE-PROMOTION-01",
                "C1-LIVE-PLAY-ACCEPTANCE-01",
            ],
        )

    def test_revalidation_04_operator_designation_is_bounded(self) -> None:
        designation = OPERATOR_DESIGNATION_PATH.read_text(encoding="utf-8")
        self.assertIn("I, Jules, designate myself", designation)
        self.assertIn(
            "eaea8e2bbc03268f49f0fa8c077e329edae317c3757ef42a628a05da06cf1788",
            designation,
        )
        self.assertIn(
            "060bbeaea354bc39a9601208e89b8a2fe066cdeef0ffffb2e0174514838e4249",
            designation,
        )
        self.assertIn("It does not authorize:", designation)
        self.assertIn("Factorio execution", designation)
        self.assertIn("route promotion", designation)
        suspension = SUSPENSION_PATH.read_text(encoding="utf-8")
        self.assertIn("owner-directed lifecycle disposition", suspension)
        self.assertIn("blocked_by_pending_file_rename", suspension)
        self.assertIn("observer self-test             not started", suspension)
        self.assertIn("no multi-repository convergence", suspension)

    def test_candidate_and_authority_bindings_remain_unpromoted(self) -> None:
        qualification = self.status[
            "windows_instance_isolated_candidate_qualification_03"
        ]
        self.assertEqual(qualification["candidate_source_revision"], QUALIFICATION_SOURCE)
        self.assertEqual(
            qualification["qualification_digest"],
            "99aee276b2968e493f7830ee0cf949efbcd4b0d843e0e93abe8729f13454d210",
        )
        revalidation = self.status["windows_instance_isolated_play_revalidation_02"]
        self.assertEqual(
            revalidation["staged_candidate_digest"],
            "f7ef4783dd153b1445ec3cd9882134fc0ccb14a19fe3494186b7fe95b721de9d",
        )
        self.assertEqual(revalidation["status"], "superseded_before_prepare")
        self.assertEqual(revalidation["observer_self_test"], "not_started")
        self.assertEqual(revalidation["observer_evidence"], "none")
        self.assertFalse(revalidation["coordinator_prepare"])
        self.assertFalse(revalidation["factorio_execution"])
        repair = self.status["observer_self_test_import_closure_01"]
        self.assertEqual(repair["work_unit"], REPAIR)
        self.assertEqual(repair["status"], "accepted_hosted_dev_integration")
        self.assertTrue(repair["fresh_qualification_required"])
        self.assertFalse(repair["observer_capture"])
        self.assertFalse(repair["authority_promotion"])
        qualification_04 = self.status[
            "windows_instance_isolated_candidate_qualification_04"
        ]
        self.assertEqual(qualification_04["work_unit"], QUALIFICATION_04)
        self.assertEqual(
            qualification_04["producer_work_unit_binding"],
            QUALIFICATION_04,
        )
        self.assertTrue(qualification_04["producer_binding_integrated"])
        self.assertEqual(
            qualification_04["producer_dev_integration_revision"],
            "569883a86c50ca203ccbecec6d37216f22f7c6a0",
        )
        self.assertEqual(
            qualification_04["remote_source_closure"],
            "pass_exact_repaired_composition",
        )
        self.assertTrue(qualification_04["qualification_generated"])
        self.assertEqual(
            qualification_04["qualification_disposition"],
            "accepted_for_revalidation_03_stage",
        )
        self.assertEqual(
            qualification_04["qualification_digest"],
            "49732ad3a785a1341f642b9cfd99c01a78bbb199f6a3ef8b88b8a7acd79d9868",
        )
        self.assertTrue(qualification_04["stage_started"])
        self.assertEqual(
            qualification_04["stage_handoff_repair_dev_integration_revision"],
            "ab159b8ced48ecbaaa1d8f37bb1b4687c6b4c679",
        )
        self.assertEqual(
            qualification_04["stage_handoff_target_filename"],
            "qualification-binding.v3.json",
        )
        self.assertFalse(qualification_04["historical_v2_filename_emitted"])
        self.assertFalse(qualification_04["authority_promotion"])
        revalidation_03 = self.status[
            "windows_instance_isolated_play_revalidation_03"
        ]
        self.assertEqual(revalidation_03["work_unit"], REVALIDATION_03)
        self.assertEqual(
            revalidation_03["status"],
            "superseded_before_observer_self_test",
        )
        self.assertEqual(
            revalidation_03["qualification_digest"],
            "49732ad3a785a1341f642b9cfd99c01a78bbb199f6a3ef8b88b8a7acd79d9868",
        )
        self.assertEqual(
            revalidation_03["staged_candidate_digest"],
            "b2e8335fa372e8f796af939e426a0cc3c7f98a68497e8fe9326e8b7f1da5a35c",
        )
        self.assertEqual(
            revalidation_03["staged_qualification_filename"],
            "qualification-binding.v3.json",
        )
        self.assertFalse(revalidation_03["historical_v2_binding_exists"])
        self.assertEqual(revalidation_03["operator"], "Jules")
        self.assertFalse(revalidation_03["operator_assignment_required"])
        self.assertEqual(
            revalidation_03["operator_designation"],
            "accepted_for_revalidation_03_only",
        )
        self.assertFalse(revalidation_03["coordinator_prepare"])
        self.assertFalse(revalidation_03["observer_capture"])
        self.assertFalse(revalidation_03["factorio_execution"])
        self.assertFalse(revalidation_03["authority_promotion"])
        route_repair = self.status[
            "instance_isolated_observer_route_binding_01"
        ]
        self.assertEqual(route_repair["work_unit"], ROUTE_BINDING_REPAIR)
        self.assertEqual(
            route_repair["next_work_unit"],
            "FACMAN-WINDOWS-INSTANCE-ISOLATED-CANDIDATE-QUALIFICATION-05",
        )
        self.assertEqual(
            route_repair["successor_revalidation"],
            "FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-04",
        )
        self.assertFalse(route_repair["wpr_execution"])
        self.assertFalse(route_repair["factorio_execution"])
        self.assertFalse(route_repair["authority_promotion"])
        qualification_05 = self.status[
            "windows_instance_isolated_candidate_qualification_05"
        ]
        self.assertEqual(qualification_05["work_unit"], QUALIFICATION_05)
        self.assertEqual(
            qualification_05["remote_source_closure_facman_revision"],
            "8f495d63b412a3af5a22305d9d8b424efd4303d2",
        )
        self.assertEqual(
            qualification_05["qualification_digest"],
            "eaea8e2bbc03268f49f0fa8c077e329edae317c3757ef42a628a05da06cf1788",
        )
        self.assertFalse(qualification_05["factorio_execution"])
        self.assertFalse(qualification_05["authority_promotion"])
        revalidation_04 = self.status[
            "windows_instance_isolated_play_revalidation_04"
        ]
        self.assertEqual(revalidation_04["work_unit"], REVALIDATION_04)
        self.assertEqual(
            revalidation_04["status"],
            "superseded_before_observer_self_test",
        )
        self.assertEqual(revalidation_04["lifecycle"], "superseded_archived")
        self.assertEqual(
            revalidation_04["admission"], "blocked_by_pending_file_rename"
        )
        self.assertEqual(
            revalidation_04["stage_disposition"],
            "preserved_external_superseded_before_observer",
        )
        self.assertEqual(
            revalidation_04["staged_candidate_digest"],
            "060bbeaea354bc39a9601208e89b8a2fe066cdeef0ffffb2e0174514838e4249",
        )
        self.assertEqual(
            revalidation_04["staged_qualification_filename"],
            "qualification-binding.v4.json",
        )
        self.assertEqual(revalidation_04["operator"], "Jules")
        self.assertFalse(revalidation_04["operator_assignment_required"])
        self.assertEqual(
            revalidation_04["operator_designation"],
            "accepted_for_revalidation_04_only",
        )
        self.assertFalse(revalidation_04["coordinator_prepare"])
        self.assertEqual(revalidation_04["observer_self_test"], "not_started")
        self.assertFalse(revalidation_04["factorio_execution"])
        self.assertFalse(revalidation_04["authority_promotion"])
        closeout = self.status["canonical_plan_and_truth_closeout"]
        self.assertEqual(
            closeout["status"],
            "phase0_integrations_closed",
        )
        self.assertEqual(closeout["promotion_source_revision"], PROMOTION_SOURCE)
        self.assertEqual(closeout["canonical_main_revision"], MAIN)
        self.assertEqual(
            closeout["dev_synchronization_revision"], REVIEWED_DEV_CHECKPOINT
        )
        self.assertEqual(closeout["candidate_source_tree"], CANDIDATE_TREE)
        self.assertEqual(closeout["dev_synchronization_tree"], REVIEWED_DEV_TREE)
        self.assertFalse(closeout["trees_equal"])
        self.assertEqual(closeout["candidate_run"], 33603385303)
        self.assertFalse(closeout["candidate_source_is_closeout_revision"])
        self.assertFalse(closeout["closeout_revision_candidate_qualified"])
        self.assertFalse(
            closeout["synchronized_tree_extends_revision_qualification"]
        )
        self.assertTrue(closeout["future_revision_requires_new_candidate_run"])
        self.assertEqual(closeout["external_gate"], REVALIDATION_04)
        self.assertEqual(closeout["external_gate_stage"], "staged_not_prepared")
        self.assertEqual(closeout["operator"], "Jules")
        self.assertEqual(closeout["human_verdict"], "unset")
        for field in (
            "prepare_authorized",
            "factorio_execution",
            "observer_capture",
            "permit_issuance",
            "route_promotion",
            "setup_mutation",
            "credential_authority",
            "network_authority",
            "signing",
            "publication",
        ):
            self.assertFalse(closeout[field], field)


if __name__ == "__main__":
    unittest.main()
