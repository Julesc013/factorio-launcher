# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import code_security_check


class CodeSecurityTests(unittest.TestCase):
    def test_codeql_is_separate_versioned_code_security_evidence(self) -> None:
        self.assertEqual(code_security_check.validate(), [])


if __name__ == "__main__":
    unittest.main()
