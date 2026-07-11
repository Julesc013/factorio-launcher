# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import refusal_golden_check


class RefusalGoldenTests(unittest.TestCase):
    def test_refusal_goldens_use_common_refusal_contract(self) -> None:
        self.assertEqual(refusal_golden_check.main(), 0)


if __name__ == "__main__":
    unittest.main()
