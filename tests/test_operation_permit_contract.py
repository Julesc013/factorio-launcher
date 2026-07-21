# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import operation_permit_check


class OperationPermitContractTests(unittest.TestCase):
    def test_permit_contract_and_no_authority_boundary(self) -> None:
        self.assertEqual(operation_permit_check.main(), 0)


if __name__ == "__main__":
    unittest.main()
