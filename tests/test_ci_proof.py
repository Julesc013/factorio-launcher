# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import ci_proof_check


class CiProofTests(unittest.TestCase):
    def test_ci_workflows_reproduce_the_claimed_proof(self) -> None:
        self.assertEqual(ci_proof_check.validate(), [])

    def test_required_package_runner_is_fail_closed(self) -> None:
        text = (ci_proof_check.ROOT / "tools" / "required_package_proof.py").read_text(encoding="utf-8")
        self.assertIn("if result.skipped:", text)
        self.assertIn('source checkout must be clean', text)


if __name__ == "__main__":
    unittest.main()
