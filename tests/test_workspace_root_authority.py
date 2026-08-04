# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import workspace_root_authority_check


class WorkspaceRootAuthorityTests(unittest.TestCase):
    def test_root_authority_is_explicit_stable_and_fail_closed(self) -> None:
        self.assertEqual([], workspace_root_authority_check.validate())


if __name__ == "__main__":
    unittest.main()
