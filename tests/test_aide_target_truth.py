# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest
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

    def test_contributor_summary_names_current_product_sequence(self) -> None:
        state = project_state.collect()
        text = project_state.summary(state)
        self.assertIn(
            "phase: same_binary_tui_parity_01 "
            "(ulk_session_adopted_authoritative_last_run_tui_parity_closeout_active)",
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
            "(same_binary_tui_parity_closeout_active_no_factorio_execution_authority)",
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


if __name__ == "__main__":
    unittest.main()
