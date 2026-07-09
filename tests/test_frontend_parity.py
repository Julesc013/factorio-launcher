from __future__ import annotations

import unittest

from tools import frontend_parity_check


class FrontendParityTests(unittest.TestCase):
    def test_frontend_parity_check(self) -> None:
        self.assertEqual(frontend_parity_check.main(), 0)


if __name__ == "__main__":
    unittest.main()
