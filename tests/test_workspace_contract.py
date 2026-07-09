from __future__ import annotations

import unittest

from tools import workspace_contract_check


class WorkspaceContractTests(unittest.TestCase):
    def test_workspace_contract_check(self) -> None:
        self.assertEqual(workspace_contract_check.main(), 0)


if __name__ == "__main__":
    unittest.main()
