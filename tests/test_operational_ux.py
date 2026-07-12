# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import operational_ux_check


class OperationalUxTests(unittest.TestCase):
    def test_operational_ux_contract_check(self) -> None:
        self.assertEqual(operational_ux_check.main(), 0)


if __name__ == "__main__":
    unittest.main()
