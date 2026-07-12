# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import r37_lifecycle_check


class R37LifecycleCheckTests(unittest.TestCase):
    def test_r37_lifecycle_check(self) -> None:
        self.assertEqual(0, r37_lifecycle_check.main())


if __name__ == "__main__":
    unittest.main()
