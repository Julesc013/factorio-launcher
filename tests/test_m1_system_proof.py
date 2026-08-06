# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest
from pathlib import Path

from tools import m1_system_proof_check


class M1SystemProofTests(unittest.TestCase):
    def test_three_repository_proof_remains_complete_and_bounded(self) -> None:
        self.assertEqual(m1_system_proof_check.main(), 0)

    def test_proof_validator_requires_normalized_launcher_and_source_only_setup(self) -> None:
        validator = Path(m1_system_proof_check.__file__).read_text(encoding="utf-8")
        self.assertIn('"${FACMAN_UNIVERSAL_LAUNCHER_TARGET}"', validator)
        self.assertIn('"FACMAN_PROVIDER_PRIVATE_SOURCE_TARGETS_AVAILABLE"', validator)
        self.assertIn('"usk_lifecycle_static"', validator)
        self.assertNotIn('        "ulk_static",', validator)


if __name__ == "__main__":
    unittest.main()
