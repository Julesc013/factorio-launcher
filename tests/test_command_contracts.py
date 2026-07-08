from __future__ import annotations

import unittest

from tools import command_contract_check


class CommandContractTests(unittest.TestCase):
    def test_command_contract_check(self) -> None:
        self.assertEqual(command_contract_check.main(), 0)


if __name__ == "__main__":
    unittest.main()
