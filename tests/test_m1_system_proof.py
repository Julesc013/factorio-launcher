# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import m1_system_proof_check


class M1SystemProofTests(unittest.TestCase):
    def test_three_repository_proof_remains_complete_and_bounded(self) -> None:
        self.assertEqual(m1_system_proof_check.main(), 0)


if __name__ == "__main__":
    unittest.main()
