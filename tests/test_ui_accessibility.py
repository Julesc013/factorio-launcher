# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import ui_accessibility_check


class UiAccessibilityTests(unittest.TestCase):
    def test_ui_accessibility_check(self) -> None:
        self.assertEqual(ui_accessibility_check.main(), 0)


if __name__ == "__main__":
    unittest.main()
