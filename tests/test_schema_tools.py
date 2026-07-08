from __future__ import annotations

import unittest

from tools import schema_validate, security_policy_check


class ToolTests(unittest.TestCase):
    def test_schema_validate(self) -> None:
        self.assertEqual(schema_validate.main(), 0)

    def test_security_policy_check(self) -> None:
        self.assertEqual(security_policy_check.main(), 0)


if __name__ == "__main__":
    unittest.main()

