# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import discovery_golden_check


class DiscoveryGoldenTests(unittest.TestCase):
    def test_discovery_report_goldens_are_contract_shaped(self) -> None:
        self.assertEqual(discovery_golden_check.main(), 0)


if __name__ == "__main__":
    unittest.main()
