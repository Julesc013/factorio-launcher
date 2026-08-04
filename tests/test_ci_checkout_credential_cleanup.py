# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tools import ci_checkout_credential_cleanup as cleanup


CREDENTIAL = "git-credentials-454ffcf9-7c35-40d3-88a6-53b1328f86dd.config"


class CheckoutCredentialCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name)
        self.repository = self.root / "repository"
        self.runner_temp = self.root / "runner-temp"
        self.repository.mkdir()
        self.runner_temp.mkdir()
        self.credential = self.runner_temp / CREDENTIAL
        self.credential.write_text("temporary test credential\n", encoding="utf-8")
        self.run_git("init")

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def run_git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.repository,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def add_include(self, key: str, value: str) -> None:
        self.run_git("config", "--local", "--add", key, value)

    def test_no_includes_is_a_safe_noop(self) -> None:
        self.assertEqual(cleanup.cleanup(self.repository, self.runner_temp), 0)

    def test_exact_runner_temp_and_compatibility_aliases_are_removed(self) -> None:
        values = [str(self.credential), f"/github/runner_temp/{CREDENTIAL}"]
        for index, value in enumerate(values):
            self.add_include(
                f"includeIf.gitdir:C:/a/repository/{index}/.git.path",
                value,
            )
        self.assertEqual(cleanup.cleanup(self.repository, self.runner_temp), 2)
        self.assertEqual(cleanup._include_entries(self.repository), [])

    def test_deleted_checkout_credential_file_leaves_a_removable_bounded_path(self) -> None:
        key = "includeIf.gitdir:C:/a/repository/.git.path"
        self.add_include(key, str(self.credential))
        self.credential.unlink()
        self.assertEqual(cleanup.cleanup(self.repository, self.runner_temp), 1)
        self.assertEqual(cleanup._include_entries(self.repository), [])

    def test_unexpected_include_is_refused_without_mutation(self) -> None:
        unexpected = self.root / "outside.config"
        unexpected.write_text("untrusted\n", encoding="utf-8")
        key = "includeIf.gitdir:C:/a/repository/.git.path"
        self.add_include(key, str(unexpected))
        with self.assertRaisesRegex(cleanup.CleanupFailure, "non-checkout Git include value"):
            cleanup.cleanup(self.repository, self.runner_temp)
        remaining = cleanup._include_entries(self.repository)
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0][0].casefold(), key.casefold())
        self.assertEqual(remaining[0][1], str(unexpected))

    def test_alias_without_verified_runner_temp_file_is_refused(self) -> None:
        key = "includeIf.gitdir:/github/workspace/.git.path"
        self.add_include(key, f"/github/runner_temp/{CREDENTIAL}")
        with self.assertRaisesRegex(cleanup.CleanupFailure, "lack a verified"):
            cleanup.cleanup(self.repository, self.runner_temp)
        self.assertEqual(len(cleanup._include_entries(self.repository)), 1)


if __name__ == "__main__":
    unittest.main()
