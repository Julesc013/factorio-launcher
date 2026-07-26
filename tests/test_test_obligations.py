# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import test_architecture_check, test_obligations


class TestObligationTests(unittest.TestCase):
    def test_all_source_skip_reasons_use_the_reviewed_vocabulary(self) -> None:
        policy = test_obligations.load_policy()
        self.assertEqual(
            [],
            test_architecture_check.skip_policy_problems(set(policy["classes"])),
        )

    def test_classification_is_exact_and_unknown_fails_closed(self) -> None:
        policy = test_obligations.load_policy()
        self.assertEqual(
            "required_blocked",
            test_obligations.classify(
                "required_blocked: sibling repositories are missing",
                policy,
            ),
        )
        self.assertEqual(
            "not_applicable",
            test_obligations.classify("not_applicable: Windows-only", policy),
        )
        self.assertEqual("unknown", test_obligations.classify("legacy reason", policy))
        self.assertEqual("unknown", test_obligations.classify("optionalish: no", policy))

    def test_promotion_profile_requires_zero_required_skips(self) -> None:
        policy = test_obligations.load_policy()
        self.assertEqual(
            0,
            policy["profiles"]["promotion"]["required_skip_limit"],
        )
        self.assertEqual(0, policy["unknown_skip_limit"])


if __name__ == "__main__":
    unittest.main()
