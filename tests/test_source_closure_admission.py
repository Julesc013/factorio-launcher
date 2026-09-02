# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import source_closure_admission_check as admission_check
from tools import successor_play_route_definition_check as route_check


class SourceClosureAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.index = route_check.load_route_index()
        self.plan = admission_check.load_toml(admission_check.PLAN)
        self.project = admission_check.load_toml(admission_check.PROJECT_STATUS)
        self.current = admission_check.load_toml(admission_check.CURRENT_STATE)

    def admission_candidate(self) -> dict[str, object]:
        candidate = copy.deepcopy(self.index)
        candidate["new_evidence_execution_authorized"] = True
        candidate["source_closure_execution_authorized"] = True
        candidate["route"][1]["new_source_closure_evidence_allowed"] = True
        candidate["index_digest"] = route_check.index_digest(candidate)
        return candidate

    def test_deferred_state_is_exact_and_non_product_authorizing(self) -> None:
        self.assertEqual([], admission_check.validate_index(self.index))

    def test_deferred_state_rejects_each_temporary_gate(self) -> None:
        cases = [
            ("new_evidence_execution_authorized", None),
            ("source_closure_execution_authorized", None),
            ("new_source_closure_evidence_allowed", 1),
        ]
        for field, route_index in cases:
            with self.subTest(field=field):
                changed = copy.deepcopy(self.index)
                if route_index is None:
                    changed[field] = True
                else:
                    changed["route"][route_index][field] = True
                changed["index_digest"] = route_check.index_digest(changed)
                self.assertNotEqual([], admission_check.validate_index(changed))

    def test_integrated_admission_candidate_is_exact(self) -> None:
        self.assertEqual(
            [],
            admission_check.validate_integrated_admission(
                self.admission_candidate()
            ),
        )

    def test_integrated_admission_requires_all_three_gates(self) -> None:
        cases = [
            ("new_evidence_execution_authorized", None),
            ("source_closure_execution_authorized", None),
            ("new_source_closure_evidence_allowed", 1),
        ]
        for field, route_index in cases:
            with self.subTest(field=field):
                changed = self.admission_candidate()
                if route_index is None:
                    changed[field] = False
                else:
                    changed["route"][route_index][field] = False
                changed["index_digest"] = route_check.index_digest(changed)
                self.assertNotEqual(
                    [],
                    admission_check.validate_integrated_admission(changed),
                )

    def test_qualification_gate_cannot_open(self) -> None:
        changed = copy.deepcopy(self.index)
        changed["route"][1]["new_qualification_evidence_allowed"] = True
        changed["index_digest"] = route_check.index_digest(changed)
        problems = admission_check.validate_index(changed)
        self.assertTrue(any("qualification" in item for item in problems))

    def test_route_capability_cannot_open(self) -> None:
        changed = copy.deepcopy(self.index)
        changed["route_capability_authorized"] = True
        changed["index_digest"] = route_check.index_digest(changed)
        problems = admission_check.validate_index(changed)
        self.assertTrue(any("route_capability" in item for item in problems))

    def test_historical_route_cannot_receive_evidence(self) -> None:
        changed = copy.deepcopy(self.index)
        changed["route"][0]["new_source_closure_evidence_allowed"] = True
        changed["index_digest"] = route_check.index_digest(changed)
        problems = admission_check.validate_index(changed)
        self.assertTrue(any("historical route" in item for item in problems))

    def test_plan_binds_reconciliation_and_superseded_admission(self) -> None:
        self.assertEqual([], admission_check.validate_plan(self.plan))

    def test_adopted_ulk_cannot_retain_a_stale_promotion_blocker(self) -> None:
        changed = copy.deepcopy(self.plan)
        item = admission_check.workunit(changed, admission_check.ADOPTION_WORK_UNIT)
        assert item is not None
        item["blockers"] = ["stale promotion blocker"]
        problems = admission_check.validate_plan(changed)
        self.assertTrue(any("complete FacMan ULK adoption" in problem for problem in problems))

    def test_plan_rejects_a_different_task_branch(self) -> None:
        changed = copy.deepcopy(self.plan)
        item = admission_check.workunit(changed, admission_check.ADMISSION_WORK_UNIT)
        assert item is not None
        item["branch"] = "task/not-the-admitted-branch"
        problems = admission_check.validate_plan(changed)
        self.assertTrue(any("branch" in problem for problem in problems))

    def test_plan_rejects_more_than_one_task_ref_run(self) -> None:
        changed = copy.deepcopy(self.plan)
        item = admission_check.workunit(changed, admission_check.ADMISSION_WORK_UNIT)
        assert item is not None
        item["task_ref_run_limit"] = 2
        problems = admission_check.validate_plan(changed)
        self.assertTrue(any("task_ref_run_limit" in problem for problem in problems))

    def test_source_closure_and_qualification_remain_inactive(self) -> None:
        changed = copy.deepcopy(self.plan)
        source = admission_check.workunit(
            changed, admission_check.SOURCE_CLOSURE_WORK_UNIT
        )
        assert source is not None
        source["status"] = "active"
        problems = admission_check.validate_plan(changed)
        self.assertTrue(any("source-closure WorkUnit" in problem for problem in problems))

    def test_aide_queue_accepts_the_current_post_integration_workunit(self) -> None:
        self.assertEqual([], admission_check.validate_queue())

    def test_task_scope_forbids_every_immutable_input(self) -> None:
        self.assertEqual([], admission_check.validate_task_scope())

    def test_project_and_generated_truth_select_reconciliation(self) -> None:
        self.assertEqual(
            [], admission_check.validate_project_truth(self.project, self.current)
        )

    def test_project_truth_rejects_product_execution(self) -> None:
        changed = copy.deepcopy(self.project)
        changed["provider_convergence"]["factorio_execution"] = True
        problems = admission_check.validate_project_truth(changed, self.current)
        self.assertTrue(any("factorio_execution" in item for item in problems))

    def test_alpha5_truth_binds_promoted_main_without_opening_source_closure(self) -> None:
        self.assertEqual(
            "facman_0_1_0_alpha_5_promotion_candidate_closeout",
            self.project["product"]["phase"],
        )
        self.assertTrue(self.project["product"]["canonical_main_promotion"])
        self.assertEqual(
            self.project["qualification_source_revision"],
            "a7a518dbfe2a6d54da7b9c84fbd318300265e31d",
        )
        self.assertEqual(
            self.project["qualification_integration_revision"],
            "43af71f8231c5a1b843636df7fd0ab8a6040d25c",
        )
        changed = copy.deepcopy(self.project)
        changed["product"]["canonical_main_promotion"] = False
        problems = admission_check.validate_project_truth(changed, self.current)
        self.assertTrue(any("canonical main promotion truth" in item for item in problems))

    def test_alpha5_tree_equality_cannot_extend_revision_qualification(self) -> None:
        changed = copy.deepcopy(self.project)
        changed["alpha5_beta_readiness"][
            "synchronized_tree_extends_revision_qualification"
        ] = True
        changed["alpha5_beta_readiness"][
            "closeout_revision_candidate_qualified"
        ] = True
        problems = admission_check.validate_project_truth(changed, self.current)
        self.assertTrue(
            any(
                "alpha.5 boundary synchronized_tree_extends_revision_qualification"
                in item
                for item in problems
            )
        )
        self.assertTrue(
            any(
                "alpha.5 boundary closeout_revision_candidate_qualified" in item
                for item in problems
            )
        )

    def test_unrecognized_phase_cannot_inherit_alpha5_lifecycle(self) -> None:
        changed = copy.deepcopy(self.project)
        changed["product"]["phase"] = "unreviewed_future_phase"
        problems = admission_check.validate_project_truth(changed, self.current)
        self.assertTrue(any("active WorkUnit" in item for item in problems))

    def test_proof_engine_and_all_other_inputs_remain_exact(self) -> None:
        self.assertEqual([], admission_check.validate_immutable_inputs())


if __name__ == "__main__":
    unittest.main()
