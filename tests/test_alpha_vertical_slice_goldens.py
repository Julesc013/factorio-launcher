# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import alpha_vertical_slice_check


class AlphaVerticalSliceGoldenTests(unittest.TestCase):
    def test_alpha_vertical_slice_goldens_are_present(self) -> None:
        self.assertEqual(alpha_vertical_slice_check.main(), 0)


if __name__ == "__main__":
    unittest.main()
