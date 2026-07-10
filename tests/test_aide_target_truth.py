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


if __name__ == "__main__":
    unittest.main()
