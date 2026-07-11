# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import refusal_contract_check


class RefusalContractTests(unittest.TestCase):
    def test_refusal_code_registry_covers_goldens(self) -> None:
        self.assertEqual(refusal_contract_check.main(), 0)


if __name__ == "__main__":
    unittest.main()
