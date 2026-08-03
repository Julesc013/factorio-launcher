# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import winforms_transport_hardening_check


class WinFormsTransportHardeningTests(unittest.TestCase):
    def test_source_contract_and_windows_behavior_matrix(self) -> None:
        self.assertEqual(winforms_transport_hardening_check.main(), 0)


if __name__ == "__main__":
    unittest.main()
