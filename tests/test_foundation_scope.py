# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

import unittest

from tools import foundation_scope_check


class FoundationScopeTests(unittest.TestCase):
    def test_scope_is_closed_and_non_authorizing(self) -> None:
        self.assertEqual([], foundation_scope_check.detect())


if __name__ == "__main__":
    unittest.main()
