# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import m2_wu9_adversarial_check


class M2Wu9AdversarialProofTests(unittest.TestCase):
    def test_complete_cross_repository_corpus_is_bound_and_fail_closed(self) -> None:
        self.assertEqual(0, m2_wu9_adversarial_check.main())


if __name__ == "__main__":
    unittest.main()
