# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import aide_target_truth_check


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

    def test_stale_python_prototype_claim_is_rejected(self) -> None:
        problems = aide_target_truth_check.validate_project_state_text(
            "apps/python_cli/` is the current runnable prototype"
        )
        self.assertTrue(any("stale claim" in problem for problem in problems), problems)

    def test_profile_evidence_authorities_exist(self) -> None:
        text = aide_target_truth_check.PROFILE.read_text(encoding="utf-8")
        self.assertEqual(aide_target_truth_check.validate_profile_text(text), [])

    def test_profile_rejects_stable_abi_and_rescheduled_windows_discovery(self) -> None:
        text = "C-compatible stable ABI\nadd real Windows read-only discovery"
        problems = aide_target_truth_check.validate_profile_text(text)
        self.assertTrue(any("stale target state" in problem for problem in problems), problems)

    def test_profile_and_project_state_require_r36_without_promoting_factorio(self) -> None:
        profile_problems = aide_target_truth_check.validate_profile_text(
            "phase: r3.2-registry-and-isolation-foundation"
        )
        self.assertTrue(
            any("r3.6-product-readiness-complete" in problem for problem in profile_problems),
            profile_problems,
        )
        state_problems = aide_target_truth_check.validate_project_state_text(
            "R3.5 is the architecture endpoint"
        )
        self.assertTrue(
            any("Real Factorio isolation remains operator-only" in problem for problem in state_problems),
            state_problems,
        )

    def test_roadmap_rejects_deferred_windows_discovery(self) -> None:
        text = "Real Steam VDF, Windows registry, macOS Spotlight, and Linux package-manager"
        problems = aide_target_truth_check.validate_roadmap_text(text)
        self.assertIn("roadmap still defers implemented Windows discovery", problems)

    def test_claim_ledger_rejects_stable_abi_promotion(self) -> None:
        problems = aide_target_truth_check.validate_claim_ledger_text("| Public C ABI is stable |")
        self.assertIn("claim ledger promotes the experimental ABI to stable", problems)

    def test_claim_ledger_rejects_corrected_registry_drift(self) -> None:
        problems = aide_target_truth_check.validate_claim_ledger_text(
            "command_graph.inspect` is still a duplicated static projection"
        )
        self.assertIn(
            "claim ledger still reports corrected registry introspection drift",
            problems,
        )

    def test_discovery_docs_require_completed_windows_provider_evidence(self) -> None:
        problems = aide_target_truth_check.validate_discovery_text("Windows discovery")
        self.assertTrue(any("Steam registry roots" in problem for problem in problems), problems)


if __name__ == "__main__":
    unittest.main()
