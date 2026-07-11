# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import frontend_contract_check


class FrontendContractTests(unittest.TestCase):
    def test_frontend_contract_check(self) -> None:
        self.assertEqual(frontend_contract_check.main(), 0)


if __name__ == "__main__":
    unittest.main()
