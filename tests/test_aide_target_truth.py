# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from tools import aide_target_truth_check, project_state


class AideTargetTruthTests(unittest.TestCase):
    def test_repository_target_truth_is_current(self) -> None:
        self.assertEqual(aide_target_truth_check.main(), 0)

    def test_retired_root_authority_is_rejected(self) -> None:
        text = """\
roots:
  source:
    authority: implementation
    canonical: true
"""
        problems = aide_target_truth_check.validate_root_authority_text(text)
        self.assertTrue(any("retired root" in problem for problem in problems), problems)

    def test_canonical_status_fields_are_compared_as_data(self) -> None:
        stale = {
            "schema": "facman.project_status.v2",
            "completed_wave": "r3.6",
            "next_authority_gate": "H1",
            "safe_beta": False,
            "execution": {"status": "unavailable", "operator_verdict": "Fail", "proof": "evidence.json"},
        }
        problems = project_state.validate_status(stale)
        self.assertTrue(any("completed M2 technical wave" in problem for problem in problems), problems)

    def test_profile_evidence_authorities_exist(self) -> None:
        text = aide_target_truth_check.PROFILE.read_text(encoding="utf-8")
        self.assertEqual(aide_target_truth_check.validate_profile_text(text), [])
        self.assertIn("phase: provider-canonical-conformance", text)
        self.assertIn("completed provider-input, semantic, and production-capable SDK", text)
        self.assertIn("installed static, installed shared", text)
        self.assertIn("FACMAN-PROVIDER-PIN-RECONCILIATION-01", text)
        self.assertIn("align source, package, ABI, contract, build, TCK", text)
        self.assertIn("menu as the default", text)
        self.assertNotIn("portable WorldSpec", text)

    def test_profile_rejects_stable_abi_and_stale_phase(self) -> None:
        text = """\
current_focus:
  phase: r3.6-product-readiness-complete
  quarantined_capabilities:
    - run.execute
native_direction:
  public_abi: C-compatible stable ABI
"""
        problems = aide_target_truth_check.validate_profile_text(text)
        self.assertTrue(any("profile phase" in problem for problem in problems), problems)
        self.assertTrue(any("stable ABI" in problem for problem in problems), problems)

    def test_provider_canonical_conformance_is_an_exact_supported_phase(self) -> None:
        current = aide_target_truth_check.PROFILE.read_text(encoding="utf-8")
        self.assertEqual(aide_target_truth_check.validate_profile_text(current), [])
        misspelled = current.replace(
            "phase: provider-canonical-conformance",
            "phase: provider-canonical-conformanc",
        )
        problems = aide_target_truth_check.validate_profile_text(misspelled)
        self.assertTrue(any("profile phase" in problem for problem in problems), problems)

    def test_generated_project_state_matches_canonical_inputs(self) -> None:
        self.assertEqual(project_state.validate(), [])

    def test_execution_truth_projects_the_single_active_plan_as_current_work(self) -> None:
        plan = {
            "last_reviewed": "2026-08-05",
            "workunit": [
                {
                    "id": "FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-01",
                    "status": "active",
                }
            ],
        }
        with patch.object(project_state, "load_toml", return_value=plan):
            truth = project_state.execution_truth(
                {
                    "current_checkpoint": "c1-backend-identity-01",
                    "truth_closeout_revision": "a" * 40,
                },
                {"current": "FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-01"},
            )
        self.assertEqual(
            truth["current_active_workunit"]["value"],
            "FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-01",
        )
        self.assertEqual(
            truth["next_dependency_ready_workunit"]["value"],
            "FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-01",
        )

    def test_execution_truth_allows_bounded_concurrent_verified_work(self) -> None:
        plan = {
            "last_reviewed": "2026-08-26",
            "wip_limit": 3,
            "workunit": [
                {"id": "ROUTE-01", "status": "verified_pending_closeout"},
                {"id": "CONTRACT-01", "status": "verified_pending_closeout"},
            ],
        }
        with patch.object(project_state, "load_toml", return_value=plan):
            truth = project_state.execution_truth(
                {
                    "active_work_unit": "ROUTE-01",
                    "current_checkpoint": "route-01",
                    "truth_closeout_revision": "a" * 40,
                },
                {"current": None},
            )
        self.assertEqual(truth["current_active_workunit"]["value"], "ROUTE-01")
        self.assertEqual(
            truth["next_dependency_ready_workunit"]["value"], "ROUTE-01"
        )

    def test_execution_truth_rejects_work_above_the_plan_wip_limit(self) -> None:
        plan = {
            "last_reviewed": "2026-08-26",
            "wip_limit": 1,
            "workunit": [
                {"id": "ROUTE-01", "status": "verified_pending_closeout"},
                {"id": "CONTRACT-01", "status": "verified_pending_closeout"},
            ],
        }
        with patch.object(project_state, "load_toml", return_value=plan):
            with self.assertRaisesRegex(ValueError, "WIP limit"):
                project_state.execution_truth(
                    {
                        "active_work_unit": "ROUTE-01",
                        "current_checkpoint": "route-01",
                        "truth_closeout_revision": "a" * 40,
                    },
                    {"current": None},
                )

    def test_contributor_summary_names_current_product_sequence(self) -> None:
        state = project_state.collect()
        text = project_state.summary(state)
        self.assertIn(
            "phase: facman_0_1_alpha6_workspace_migration_recovery "
            "(alpha6_workspace_migration_recovery_active_beta_gates_pending)",
            text,
        )
        self.assertIn(
            "active_work_unit: "
            + (
                state["execution_truth"]["current_active_workunit"]["value"]
                or "none"
            ),
            text,
        )
        self.assertIn(
            "next_dependency_ready_workunit: "
            + state["execution_truth"]["next_dependency_ready_workunit"]["value"],
            text,
        )
        self.assertIn(
            "execution: unavailable "
            "(alpha6_workspace_migration_recovery_active_"
            "exact_play_route_unaccepted)",
            text,
        )
        self.assertIn(
            "alpha5_candidate: 4683ecd9a1b9ead5eb84be152760d12583da0f0e "
            "run=33603385303/1 future_revision_requires_new_run=true",
            text,
        )
        self.assertIn("instance_isolated=unproven", text)
        self.assertIn("hermetic=unproven", text)
        self.assertIn("Gate 4A hermetic Play policy", text)
        self.assertIn("Gate 4B hermetic Play candidate: eligible_for_human_verdict", text)
        self.assertIn(
            "Instance-isolated Play candidate: eligible_for_human_verdict",
            text,
        )

    def test_current_roadmap_uses_the_alpha6_to_beta1_dependency_chain(self) -> None:
        text = project_state.roadmap_status(project_state.collect())
        for work_unit in (
            "FACMAN-0.1-ALPHA6-WORKSPACE-MIGRATION-RECOVERY-01",
            "FACMAN-0.1-ALPHA6-MANAGED-INSTALL-LIFECYCLE-01",
            "FACMAN-0.1-ALPHA7-CONTENT-WORLD-ROUTES-01",
            "FACMAN-0.1-ALPHA7-PLAY-FRONTEND-CONVERGENCE-01",
            "FACMAN-0.1-FEATURE-FREEZE-01",
            "FACMAN-0.1-BETA1-EXACT-RELEASE-01",
        ):
            self.assertIn(work_unit, text)
        self.assertNotIn("FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-01", text)

    def test_claim_ledger_rejects_stable_abi_promotion(self) -> None:
        problems = aide_target_truth_check.validate_claim_ledger_text(
            "| Public C ABI is stable | proven | none | none |"
        )
        self.assertIn("claim ledger promotes the experimental ABI to stable", problems)

    def test_claim_ledger_requires_structured_current_rows(self) -> None:
        problems = aide_target_truth_check.validate_claim_ledger_text("| Claim | Level | Proof | Limitation |")
        self.assertTrue(any("structured row" in problem for problem in problems), problems)

    def test_discovery_docs_reject_deferred_windows_provider(self) -> None:
        text = "Real Steam VDF, Windows registry, macOS Spotlight, and Linux package-manager"
        problems = aide_target_truth_check.validate_discovery_text(text)
        self.assertIn("discovery documentation defers the implemented Windows provider", problems)


class ConcurrentQueueTruthTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / ".aide" / "history").mkdir(parents=True)
        (self.root / "release" / "index").mkdir(parents=True)

    def task(self, identifier: str, state: str = "active_automated", lane: str = "active") -> None:
        folder = self.root / ".aide" / "queue" / lane / identifier
        folder.mkdir(parents=True)
        common = f"status: {state}\nlifecycle_state: {state}\n"
        (folder / "task.yaml").write_text(f"id: {identifier}\ntitle: Worker\n" + common)
        (folder / "status.yaml").write_text(f"task_id: {identifier}\n" + common)

    def plan(self, primary: str | None = "Z-CONTROL", limit: int = 4,
             gates: int = 0, programme: bool = True) -> Path:
        lines = [f"wip_limit = {limit}", 'last_reviewed = "2026-09-06"']
        if programme:
            lines.extend(['[execution_programme]', 'id = "PROGRAMME"'])
            if primary is not None:
                lines.append(f'primary_workunit = "{primary}"')
        for identifier in ("A-WORKER", "Z-CONTROL"):
            lines.extend(['[[workunit]]', f'id = "{identifier}"', 'status = "active"'])
        for number in range(gates):
            lines.extend(['[[gate]]', f'id = "GATE-{number}"', 'status = "active"'])
        path = self.root / "release" / "index" / "plan.v1.toml"
        path.write_text("\n".join(lines) + "\n")
        return path

    def test_programme_selects_primary_and_exposes_every_worker(self) -> None:
        self.task("A-WORKER")
        self.task("Z-CONTROL", "awaiting_operator")
        plan_path = self.plan()
        queue = project_state.queue_state(self.root)
        self.assertEqual(queue["current"], "Z-CONTROL")
        self.assertEqual(queue["active_workunits"], ["A-WORKER", "Z-CONTROL"])
        status = {"active_work_unit": "A-WORKER", "current_checkpoint": "historical",
                  "truth_closeout_revision": "a" * 40}
        with patch.object(project_state, "PLAN_PATH", plan_path):
            truth = project_state.execution_truth(status, queue)
        self.assertEqual(truth["current_active_workunit"]["value"], "Z-CONTROL")
        self.assertEqual(truth["current_active_workunits"]["value"], ["A-WORKER", "Z-CONTROL"])
        self.assertEqual(truth["reviewed_product_checkpoint"]["as_of_revision"], "a" * 40)
        self.assertEqual(status["active_work_unit"], "A-WORKER")

    def test_concurrent_programme_never_selects_an_implicit_primary(self) -> None:
        self.task("A-WORKER")
        self.task("Z-CONTROL")
        self.plan(primary=None)
        with self.assertRaisesRegex(ValueError, "primary_workunit"):
            project_state.queue_state(self.root)
        self.plan(primary="CLOSED-OR-UNKNOWN")
        with self.assertRaisesRegex(ValueError, "active plan WorkUnit"):
            project_state.queue_state(self.root)

    def test_unknown_queue_worker_is_refused(self) -> None:
        self.task("A-WORKER")
        self.task("Z-CONTROL")
        self.task("UNADMITTED")
        self.plan()
        with self.assertRaisesRegex(ValueError, "not active in the canonical plan"):
            project_state.queue_state(self.root)

    def test_completed_plan_work_cannot_remain_active_in_the_queue(self) -> None:
        self.task("A-WORKER")
        self.task("Z-CONTROL")
        path = self.plan()
        path.write_text(path.read_text().replace('id = "A-WORKER"\nstatus = "active"',
                                                'id = "A-WORKER"\nstatus = "complete"'))
        with self.assertRaisesRegex(ValueError, "not active in the canonical plan"):
            project_state.queue_state(self.root)

    def test_programme_refuses_missing_active_queue_membership(self) -> None:
        self.task("A-WORKER")
        self.plan()
        with self.assertRaisesRegex(ValueError, "membership differs"):
            project_state.queue_state(self.root)

    def test_external_gates_consume_the_existing_wip_limit(self) -> None:
        self.task("A-WORKER")
        self.task("Z-CONTROL")
        self.plan(limit=4, gates=2)
        self.assertEqual(project_state.queue_state(self.root)["current"], "Z-CONTROL")
        self.plan(limit=4, gates=3)
        with self.assertRaisesRegex(ValueError, "WIP limit including gates: 5 > 4"):
            project_state.queue_state(self.root)

    def test_active_worker_cannot_hide_in_the_next_lane(self) -> None:
        self.task("A-WORKER", lane="next")
        with self.assertRaisesRegex(ValueError, "active lane"):
            project_state.queue_state(self.root)

    def test_legacy_single_worker_without_a_plan_is_compatible(self) -> None:
        self.task("LEGACY", "active")
        queue = project_state.queue_state(self.root)
        self.assertEqual(queue["current"], "LEGACY")
        self.assertEqual(queue["active_workunits"], ["LEGACY"])

    def test_legacy_multiple_workers_need_explicit_historical_selection(self) -> None:
        self.task("A-WORKER")
        self.task("Z-CONTROL")
        self.plan(programme=False)
        with self.assertRaisesRegex(ValueError, "explicit primary"):
            project_state.queue_state(self.root)
        (self.root / "release" / "index" / "project_status.v2.toml").write_text(
            'active_work_unit = "Z-CONTROL"\n')
        self.assertEqual(project_state.queue_state(self.root)["current"], "Z-CONTROL")

    def test_current_programme_preserves_historical_checkpoint_fields(self) -> None:
        data = project_state.collect()
        status = project_state.load_toml(project_state.STATUS_PATH)
        plan = project_state.load_toml(project_state.PLAN_PATH)
        self.assertEqual(data["active_work_unit"], status["active_work_unit"])
        self.assertEqual(data["execution_truth"]["current_active_workunit"]["value"],
                         plan["execution_programme"]["primary_workunit"])
        self.assertEqual(set(data["queue"]["active_workunits"]),
                         set(project_state.plan_active_workunits(plan)))
        self.assertEqual(data["execution_truth"]["reviewed_product_checkpoint"]["as_of_revision"],
                         status["truth_closeout_revision"])


if __name__ == "__main__":
    unittest.main()
