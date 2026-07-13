# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import release_structure_check


class ReleaseStructureTests(unittest.TestCase):
    def test_release_structure_check(self) -> None:
        self.assertEqual(release_structure_check.main(), 0)


if __name__ == "__main__":
    unittest.main()
