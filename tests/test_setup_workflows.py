# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import setup_workflow_check


class SetupWorkflowTests(unittest.TestCase):
    def test_generated_setup_workflows_remain_explicit_and_guarded(self) -> None:
        self.assertEqual(setup_workflow_check.main(), 0)


if __name__ == "__main__":
    unittest.main()
