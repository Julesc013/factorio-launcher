# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest
from pathlib import Path

from tools import language_runtime_policy_check


class LanguageRuntimePolicyTests(unittest.TestCase):
    def test_language_runtime_policy_check(self) -> None:
        self.assertEqual(language_runtime_policy_check.main(), 0)

    def test_only_repository_build_outputs_are_excluded(self) -> None:
        root = Path("X:/facman")
        self.assertTrue(
            language_runtime_policy_check.is_repository_build_output(
                root / "build" / "nested-worktree" / "apps" / "shell.cs", root
            )
        )
        self.assertFalse(
            language_runtime_policy_check.is_repository_build_output(
                root / "runtime" / "build" / "source.cpp", root
            )
        )
        self.assertFalse(
            language_runtime_policy_check.is_repository_build_output(
                Path("X:/other/build/source.cpp"), root
            )
        )


if __name__ == "__main__":
    unittest.main()
