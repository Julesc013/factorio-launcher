# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tools import ci_checkout_credential_scrub


class CiCheckoutCredentialScrubTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.runner_temp = self.root / "runner-temp"
        self.repo.mkdir()
        self.runner_temp.mkdir()
        self.run_git("init")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.repo,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def credential_file(
        self, *, outside: bool = False, identifier: str = "12345678"
    ) -> Path:
        root = self.root if outside else self.runner_temp
        path = root / f"git-credentials-{identifier}-1234-1234-1234-123456789abc.config"
        path.write_text(
            '[http "https://github.com/"]\n\textraheader = fake\n',
            encoding="utf-8",
        )
        return path

    def checkout_keys(self) -> tuple[str, str]:
        git_dir = str((self.repo / ".git").resolve()).replace("\\", "/")
        return (
            f"includeIf.gitdir:{git_dir}.path",
            f"includeIf.gitdir:{git_dir}/worktrees/*.path",
        )

    def configure_checkout_pair(self, value: Path) -> tuple[str, str]:
        keys = self.checkout_keys()
        for key in keys:
            self.run_git("config", "--local", key, str(value))
        return keys

    def include_keys(self) -> list[str]:
        completed = subprocess.run(
            [
                "git",
                "config",
                "--local",
                "--no-includes",
                "--name-only",
                "--get-regexp",
                ".*",
            ],
            cwd=self.repo,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return [
            key
            for key in completed.stdout.splitlines()
            if key.casefold() == "include.path"
            or (
                key.casefold().startswith("includeif.")
                and key.casefold().endswith(".path")
            )
        ]

    def test_exact_checkout_pair_is_removed_without_reading_ordinary_config(self) -> None:
        self.run_git("config", "--local", "facman.sentinel", "preserved")
        self.configure_checkout_pair(self.credential_file())

        removed = ci_checkout_credential_scrub.scrub_checkout_credentials(
            self.repo, self.runner_temp
        )

        self.assertEqual(removed, 2)
        self.assertEqual(self.include_keys(), [])
        self.assertEqual(
            self.run_git("config", "--local", "--get", "facman.sentinel").stdout.strip(),
            "preserved",
        )

    def test_no_include_state_is_a_safe_noop(self) -> None:
        self.assertEqual(
            ci_checkout_credential_scrub.scrub_checkout_credentials(
                self.repo, self.runner_temp
            ),
            0,
        )

    def test_arbitrary_include_fails_before_any_include_is_removed(self) -> None:
        credential = self.credential_file()
        self.configure_checkout_pair(credential)
        arbitrary = self.root / "arbitrary.config"
        arbitrary.write_text("[facman]\n\thostile = true\n", encoding="utf-8")
        self.run_git("config", "--local", "include.path", str(arbitrary))

        with self.assertRaisesRegex(ValueError, "exact checkout-owned credential pair"):
            ci_checkout_credential_scrub.scrub_checkout_credentials(
                self.repo, self.runner_temp
            )

        self.assertEqual(len(self.include_keys()), 3)

    def test_partial_checkout_pair_fails_closed(self) -> None:
        key = self.checkout_keys()[0]
        self.run_git("config", "--local", key, str(self.credential_file()))

        with self.assertRaisesRegex(ValueError, "exact checkout-owned credential pair"):
            ci_checkout_credential_scrub.scrub_checkout_credentials(
                self.repo, self.runner_temp
            )

        self.assertEqual(len(self.include_keys()), 1)

    def test_divergent_checkout_credential_values_fail_closed(self) -> None:
        keys = self.checkout_keys()
        self.run_git(
            "config", "--local", keys[0], str(self.credential_file())
        )
        self.run_git(
            "config",
            "--local",
            keys[1],
            str(self.credential_file(identifier="87654321")),
        )

        with self.assertRaisesRegex(ValueError, "share one credential file"):
            ci_checkout_credential_scrub.scrub_checkout_credentials(
                self.repo, self.runner_temp
            )

        self.assertEqual(len(self.include_keys()), 2)

    def test_credential_outside_runner_temp_fails_closed(self) -> None:
        self.configure_checkout_pair(self.credential_file(outside=True))

        with self.assertRaisesRegex(ValueError, "within runner temp"):
            ci_checkout_credential_scrub.scrub_checkout_credentials(
                self.repo, self.runner_temp
            )

        self.assertEqual(len(self.include_keys()), 2)

    def test_missing_credential_file_fails_closed(self) -> None:
        missing = self.runner_temp / (
            "git-credentials-12345678-1234-1234-1234-123456789abc.config"
        )
        self.configure_checkout_pair(missing)

        with self.assertRaises(FileNotFoundError):
            ci_checkout_credential_scrub.scrub_checkout_credentials(
                self.repo, self.runner_temp
            )

        self.assertEqual(len(self.include_keys()), 2)

    def test_empty_credential_file_fails_closed(self) -> None:
        credential = self.runner_temp / (
            "git-credentials-12345678-1234-1234-1234-123456789abc.config"
        )
        credential.touch()
        self.configure_checkout_pair(credential)

        with self.assertRaisesRegex(ValueError, "invalid size"):
            ci_checkout_credential_scrub.scrub_checkout_credentials(
                self.repo, self.runner_temp
            )

        self.assertEqual(len(self.include_keys()), 2)

    def test_oversized_credential_file_fails_closed(self) -> None:
        credential = self.runner_temp / (
            "git-credentials-12345678-1234-1234-1234-123456789abc.config"
        )
        credential.write_text(
            "[facman]\n\tvalue = "
            + "x" * ci_checkout_credential_scrub.MAX_CREDENTIAL_FILE_BYTES,
            encoding="utf-8",
        )
        self.configure_checkout_pair(credential)

        with self.assertRaisesRegex(ValueError, "invalid size"):
            ci_checkout_credential_scrub.scrub_checkout_credentials(
                self.repo, self.runner_temp
            )

        self.assertEqual(len(self.include_keys()), 2)

    def test_wrong_credential_file_name_fails_closed(self) -> None:
        credential = self.runner_temp / "checkout-auth.config"
        credential.write_text("[facman]\n\tvalue = true\n", encoding="utf-8")
        self.configure_checkout_pair(credential)

        with self.assertRaisesRegex(ValueError, "unexpected file name"):
            ci_checkout_credential_scrub.scrub_checkout_credentials(
                self.repo, self.runner_temp
            )

        self.assertEqual(len(self.include_keys()), 2)

    def test_relative_credential_path_fails_closed(self) -> None:
        relative = Path(
            "git-credentials-12345678-1234-1234-1234-123456789abc.config"
        )
        self.configure_checkout_pair(relative)

        with self.assertRaisesRegex(ValueError, "absolute path"):
            ci_checkout_credential_scrub.scrub_checkout_credentials(
                self.repo, self.runner_temp
            )

        self.assertEqual(len(self.include_keys()), 2)


if __name__ == "__main__":
    unittest.main()
