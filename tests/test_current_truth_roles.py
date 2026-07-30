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

MAIN = "133da925af13d475c959a336e0b0eec0427a0381"
DEV = "f0b9bac022e428fb19db27a2e320941c9e193899"
PROMOTION_SOURCE = "29f1a97410cb999f7691d5daa1f4b2afa82f0149"
QUALIFICATION_SOURCE = "2c393acf838dd432d37f8acce50d01f91bfd28ca"
REVALIDATION = "FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-02"
REPAIR = "FACMAN-OBSERVER-SELF-TEST-IMPORT-CLOSURE-01"
QUALIFICATION_04 = "FACMAN-WINDOWS-INSTANCE-ISOLATED-CANDIDATE-QUALIFICATION-04"


def load_toml(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


class CurrentTruthRoleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.status = load_toml(STATUS_PATH)
        self.current = load_toml(CURRENT_STATE_PATH)
        self.plan = load_toml(PLAN_PATH)

    def test_current_branch_roles_are_exact_and_distinct(self) -> None:
        self.assertEqual(self.status["canonical_main_revision"], MAIN)
        self.assertEqual(self.status["planning_promotion_revision"], MAIN)
        self.assertEqual(self.status["current_dev_revision"], DEV)
        self.assertEqual(self.status["dev_synchronization_revision"], DEV)
        self.assertEqual(self.status["truth_closeout_revision"], DEV)
        self.assertEqual(self.status["observed_branch_head"], DEV)
        self.assertEqual(self.status["promotion_source_revision"], PROMOTION_SOURCE)
        self.assertNotEqual(
            self.status["current_dev_revision"],
            self.status["qualification_source_revision"],
        )

    def test_generated_current_state_exposes_each_revision_role(self) -> None:
        revisions = self.current["revisions"]
        self.assertEqual(revisions["canonical_main"], MAIN)
        self.assertEqual(revisions["planning_promotion"], MAIN)
        self.assertEqual(revisions["observed_dev"], DEV)
        self.assertEqual(revisions["dev_synchronization"], DEV)
        self.assertEqual(revisions["truth_closeout"], DEV)
        self.assertEqual(revisions["promotion_source"], PROMOTION_SOURCE)
        self.assertEqual(revisions["qualification_source"], QUALIFICATION_SOURCE)

    def test_plan_observes_qualification_04_stage_handoff_repair(self) -> None:
        gate = next(item for item in self.plan["gate"] if item["status"] == "active")
        self.assertEqual(gate["external_ref"], QUALIFICATION_04)
        self.assertEqual(gate["stage"], "stage_handoff_binding_filename_repair")
        self.assertEqual(gate["owner"], "Jules")
        self.assertFalse(gate["operator_assignment_required"])

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
            "pass_superseded_by_stage_binding_filename_defect",
        )
        self.assertTrue(qualification_04["qualification_generated"])
        self.assertEqual(
            qualification_04["qualification_disposition"],
            "superseded_before_stage",
        )
        self.assertEqual(
            qualification_04["qualification_digest"],
            "b6d1e7b030a17cf5279d363c341a8405526363217c96928d78d199d6a073363b",
        )
        self.assertFalse(qualification_04["stage_started"])
        self.assertEqual(
            qualification_04["stage_handoff_defect"],
            "v3_binding_would_be_staged_under_historical_v2_filename",
        )
        self.assertEqual(
            qualification_04["stage_handoff_target_filename"],
            "qualification-binding.v3.json",
        )
        self.assertFalse(qualification_04["historical_v2_filename_emitted"])
        self.assertFalse(qualification_04["authority_promotion"])
        closeout = self.status["canonical_plan_and_truth_closeout"]
        self.assertEqual(closeout["external_gate"], REVALIDATION)
        self.assertEqual(closeout["external_gate_stage"], "staged_not_prepared")
        self.assertEqual(closeout["operator"], "unassigned")
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
