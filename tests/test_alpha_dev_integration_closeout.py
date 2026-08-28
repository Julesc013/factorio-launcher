# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import alpha_dev_integration_closeout_check as closeout


class AlphaDevIntegrationCloseoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.receipt = closeout.load()

    def test_exact_protected_merge_receipt_passes(self) -> None:
        self.assertEqual(closeout.validate(self.receipt), [])

    def test_synthetic_or_non_merge_identity_is_rejected(self) -> None:
        changed = copy.deepcopy(self.receipt)
        changed["merge_method"] = "squash"
        changed["dev_merge_tree"] = "0" * 40
        problems = closeout.validate(changed)
        self.assertTrue(any("merge_method" in item for item in problems))
        self.assertTrue(any("dev_merge_tree" in item for item in problems))

    def test_incomplete_workflow_or_open_authority_is_rejected(self) -> None:
        changed = copy.deepcopy(self.receipt)
        changed["workflow"][0]["conclusion"] = "failure"
        changed["authority"]["tagging"] = True
        problems = closeout.validate(changed)
        self.assertTrue(any("workflow is not completed successfully" in item for item in problems))
        self.assertTrue(any("authority" in item for item in problems))


if __name__ == "__main__":
    unittest.main()
