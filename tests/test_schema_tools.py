# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import package_check, schema_validate, security_policy_check, strict_check, structure_policy_check


class ToolTests(unittest.TestCase):
    def test_schema_validate(self) -> None:
        self.assertEqual(schema_validate.main(), 0)

    def test_structure_policy_check(self) -> None:
        self.assertEqual(structure_policy_check.main(), 0)

    def test_security_policy_check(self) -> None:
        self.assertEqual(security_policy_check.main(), 0)

    def test_package_check(self) -> None:
        self.assertEqual(package_check.main(), 0)

    def test_strict_check(self) -> None:
        self.assertEqual(strict_check.main(), 0)


if __name__ == "__main__":
    unittest.main()
