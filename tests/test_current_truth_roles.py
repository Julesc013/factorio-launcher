# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


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

MAIN = "b70be10696855628c6d2948eb016c8424912e14e"
REVIEWED_DEV_CHECKPOINT = "d4171a9beca18a63692819c7b7eedbaaae48d04a"
PROMOTION_SOURCE = MAIN
QUALIFICATION_SOURCE = "2c393acf838dd432d37f8acce50d01f91bfd28ca"
ULK_MAIN = "09f0639ab6529fba2f2aa22e9bf68e5eebed0553"
ULK_DEV = "2e77e15c8bcdeb833a0a45aab3421886b72cc70c"
ULK_PIN = "1cafe4054297cc11e02458b83d230db0cd064471"
USK_MAIN = "32488fc13bd2439f9f6e52e83a97f6da345a7650"
USK_DEV = "6dc48673d54fb27ac4e8949da6f43275d36c9622"
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
            self.status["current_dev_revision"], REVIEWED_DEV_CHECKPOINT
        )
        self.assertEqual(
            self.status["dev_synchronization_revision"], REVIEWED_DEV_CHECKPOINT
        )
        self.assertEqual(
            self.status["truth_closeout_revision"], REVIEWED_DEV_CHECKPOINT
        )
        self.assertEqual(
            self.status["observed_branch_head"], REVIEWED_DEV_CHECKPOINT
        )
        self.assertEqual(self.status["promotion_source_revision"], PROMOTION_SOURCE)
        self.assertNotEqual(
            self.status["current_dev_revision"],
            self.status["qualification_source_revision"],
        )

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
        self.assertEqual(revisions["observed_dev"], REVIEWED_DEV_CHECKPOINT)
        self.assertEqual(
            revisions["dev_synchronization"], REVIEWED_DEV_CHECKPOINT
        )
        self.assertEqual(revisions["truth_closeout"], REVIEWED_DEV_CHECKPOINT)
        self.assertEqual(revisions["promotion_source"], PROMOTION_SOURCE)
        self.assertEqual(revisions["qualification_source"], QUALIFICATION_SOURCE)
        providers = self.current["provider_convergence"]
        self.assertEqual(providers["universal_launcher_main_revision"], ULK_MAIN)
        self.assertEqual(providers["universal_launcher_dev_revision"], ULK_DEV)
        self.assertEqual(providers["universal_launcher_consumed_pin"], ULK_PIN)
        self.assertEqual(providers["universal_setup_main_revision"], USK_MAIN)
        self.assertEqual(providers["universal_setup_dev_revision"], USK_DEV)
        self.assertEqual(providers["universal_setup_consumed_pin"], USK_PIN)
        self.assertTrue(providers["provider_promotions_complete"])
        self.assertTrue(providers["provider_pins_reconciled"])
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
            "accepted_dev_integration",
        )
        self.assertEqual(providers["accepted_play_routes"], 0)
        self.assertEqual(providers["observed_player_journeys"], 0)
        self.assertFalse(providers["factorio_execution"])
        self.assertFalse(providers["signing"])
        self.assertFalse(providers["publication"])

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
