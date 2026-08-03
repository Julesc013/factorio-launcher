# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import json_contract
from tools import remote_source_closure


class RemoteSourceClosureTests(unittest.TestCase):
    def test_checked_spec_requires_https_canonical_ref_and_full_pin(self) -> None:
        accepted = remote_source_closure.checked_spec(
            remote_source_closure.SourceSpec(
                "factorio-launcher",
                "https://github.com/example/factorio-launcher.git",
                "refs/heads/dev",
                "a" * 40,
            )
        )
        self.assertEqual(accepted.branch, "dev")
        self.assertEqual(accepted.remote_tracking_ref, "refs/remotes/origin/dev")

        for spec in (
            remote_source_closure.SourceSpec(
                "factorio-launcher", "C:/local/repo", "refs/heads/dev", "a" * 40
            ),
            remote_source_closure.SourceSpec(
                "factorio-launcher",
                "https://github.com/example/repo.git",
                "dev",
                "a" * 40,
            ),
            remote_source_closure.SourceSpec(
                "factorio-launcher",
                "https://github.com/example/repo.git",
                "refs/heads/dev",
                "short",
            ),
            remote_source_closure.SourceSpec(
                "factorio-launcher",
                "https://github.com/example/repo.git",
                "refs/heads/dev",
                "A" * 40,
            ),
        ):
            with self.assertRaises(remote_source_closure.ClosureFailure):
                remote_source_closure.checked_spec(spec)

    def test_provider_specs_are_bound_to_workspace_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lock = Path(temporary) / "workspace_lock.v1.toml"
            lock.write_text(
                """
[[component]]
id = "universal_setup"
pin = "cccccccccccccccccccccccccccccccccccccccc"
remote = "https://github.com/example/universal-setup.git"
required_ref = "refs/heads/main"
reachability = "required_for_source_closure"

[[component]]
id = "universal_launcher"
pin = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
remote = "https://github.com/example/universal-launcher.git"
required_ref = "refs/heads/main"
reachability = "required_for_source_closure"
""".strip()
                + "\n",
                encoding="utf-8",
            )

            specs = remote_source_closure.provider_specs_from_lock(lock)

        self.assertEqual(
            [spec.repo_id for spec in specs],
            ["universal-setup", "universal-launcher"],
        )
        self.assertEqual(specs[0].pin, "c" * 40)
        self.assertEqual(specs[1].pin, "b" * 40)

    def test_provider_specs_reject_optional_source_closure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lock = Path(temporary) / "workspace_lock.v1.toml"
            lock.write_text(
                """
[[component]]
id = "universal_setup"
pin = "cccccccccccccccccccccccccccccccccccccccc"
remote = "https://github.com/example/universal-setup.git"
required_ref = "refs/heads/main"
reachability = "required_for_source_closure"

[[component]]
id = "universal_launcher"
pin = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
remote = "https://github.com/example/universal-launcher.git"
required_ref = "refs/heads/main"
reachability = "optional"
""".strip()
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                remote_source_closure.ClosureFailure,
                "source closure is not required",
            ):
                remote_source_closure.provider_specs_from_lock(lock)

    def test_clone_exact_uses_no_local_and_detached_pin(self) -> None:
        spec = remote_source_closure.SourceSpec(
            "factorio-launcher",
            "https://github.com/example/factorio-launcher.git",
            "refs/heads/dev",
            "a" * 40,
        )
        calls: list[list[str]] = []
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "factorio-launcher"

            def fake_run(
                command: list[str],
                cwd: Path,
                label: str,
            ) -> subprocess.CompletedProcess[str]:
                del cwd, label
                calls.append(command)
                if command[:4] == ["git", "-c", "core.longpaths=true", "clone"]:
                    destination.mkdir()
                return subprocess.CompletedProcess(command, 0, "", "")

            def fake_output(repo: Path, args: list[str]) -> str:
                del repo
                if args == ["remote", "get-url", "origin"]:
                    return spec.remote
                if args == ["rev-parse", "HEAD"]:
                    return spec.pin
                if args == ["rev-parse", "HEAD^{tree}"]:
                    return "d" * 40
                if args[:2] == ["status", "--porcelain=v1"]:
                    return ""
                raise AssertionError(args)

            with (
                patch.object(remote_source_closure, "run_checked", side_effect=fake_run),
                patch.object(remote_source_closure, "git_output", side_effect=fake_output),
                patch.object(remote_source_closure, "git_code", side_effect=[0, 0, 1]),
                patch.object(
                    remote_source_closure,
                    "git_path",
                    return_value=Path(temporary) / "missing-alternates",
                ),
            ):
                observation = remote_source_closure.clone_exact(spec, destination)

        self.assertEqual(
            calls[0][:4],
            ["git", "-c", "core.longpaths=true", "clone"],
        )
        self.assertIn("--no-local", calls[0])
        self.assertIn("--no-checkout", calls[0])
        self.assertEqual(
            calls[1],
            [
                "git",
                "-c",
                "core.longpaths=true",
                "checkout",
                "--detach",
                spec.pin,
            ],
        )
        self.assertTrue(observation["detached"])
        self.assertFalse(observation["local_clone"])

    def test_nonempty_roots_are_refused_without_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = root / "operator-owned.txt"
            marker.write_text("retain", encoding="utf-8")
            with self.assertRaises(remote_source_closure.ClosureFailure):
                remote_source_closure.require_empty_root(root, "clone")
            self.assertEqual(marker.read_text(encoding="utf-8"), "retain")

    def test_test_counts_and_installed_sdk_are_extracted_from_records(self) -> None:
        records: list[dict[str, object]] = [
            ctest_record("universal-launcher ctest", 4),
            ctest_record("universal-setup ctest", 14),
            ctest_record(
                "factorio-launcher ctest",
                52,
                extra="facman_installed_sdk_smoke",
            ),
            {
                "label": "factorio-launcher unittest",
                "command": ["python", "-m", "unittest"],
                "exit_code": 0,
                "output": "Ran 488 tests in 1.0s\n\nOK\n",
            },
        ]

        counts = remote_source_closure.test_counts(records)

        self.assertEqual(counts["factorio-launcher_native"], 52)
        self.assertEqual(counts["factorio-launcher_python"], 488)
        self.assertTrue(remote_source_closure.installed_sdk_passed(records))

    def test_required_package_proof_requires_explicit_zero_skip_result(self) -> None:
        self.assertEqual(
            remote_source_closure.windows_required_package_test_count(
                "required-package-proof: ok (14 tests, zero skips)\n"
            ),
            14,
        )
        with self.assertRaises(remote_source_closure.ClosureFailure):
            remote_source_closure.windows_required_package_test_count(
                "required-package-proof: ok (14 tests, one skip)\n"
            )

    def test_package_source_revisions_must_equal_exact_checkouts(self) -> None:
        repos = {
            "factorio-launcher": Path("factorio-launcher"),
            "universal-launcher": Path("universal-launcher"),
            "universal-setup": Path("universal-setup"),
        }
        revisions = {
            "factorio_launcher": "a" * 40,
            "universal_launcher": "b" * 40,
            "universal_setup": "c" * 40,
        }

        def fake_git_output(repo: Path, args: list[str]) -> str:
            self.assertEqual(args, ["rev-parse", "HEAD"])
            return {
                "factorio-launcher": "a" * 40,
                "universal-launcher": "b" * 40,
                "universal-setup": "c" * 40,
            }[repo.name]

        with patch.object(
            remote_source_closure,
            "git_output",
            side_effect=fake_git_output,
        ):
            self.assertEqual(
                remote_source_closure.exact_package_source_revisions(
                    repos,
                    {"source_revisions": revisions},
                ),
                revisions,
            )
            with self.assertRaisesRegex(
                remote_source_closure.ClosureFailure,
                "differ from the exact proof checkouts",
            ):
                remote_source_closure.exact_package_source_revisions(
                    repos,
                    {
                        "source_revisions": {
                            **revisions,
                            "universal_launcher": "d" * 40,
                        }
                    },
                )

    def test_generated_report_satisfies_source_closure_schema(self) -> None:
        records: list[dict[str, object]] = [
            ctest_record("universal-launcher ctest", 4),
            ctest_record("universal-setup ctest", 14),
            ctest_record(
                "factorio-launcher ctest",
                52,
                extra="facman_installed_sdk_smoke",
            ),
            {
                "label": "factorio-launcher unittest",
                "command": ["python", "-m", "unittest"],
                "exit_code": 0,
                "output": "Ran 488 tests in 1.0s\n\nOK\n",
            },
        ]
        records.extend(
            {
                "label": f"validation step {index}",
                "command": ["fixture", str(index)],
                "exit_code": 0,
                "output": "",
            }
            for index in range(14)
        )
        repositories = [
            {
                "id": repo_id,
                "remote": f"https://github.com/example/{repo_id}.git",
                "required_ref": "refs/heads/main",
                "pin": char * 40,
                "head": char * 40,
                "tree": tree * 40,
                "detached": True,
                "clean": True,
                "alternates": False,
                "local_clone": False,
                "canonical_ref_contains_pin": True,
            }
            for repo_id, char, tree in (
                ("factorio-launcher", "a", "d"),
                ("universal-launcher", "b", "e"),
                ("universal-setup", "c", "f"),
            )
        ]
        package = {
            "profile_id": "windows_portable_cli_x64",
            "package_file_count": 100,
            "artifact": "facman.zip",
            "artifact_size": 1000,
            "artifact_sha256": "1" * 64,
            "provenance": "facman.zip.provenance.v1.json",
            "provenance_sha256": "2" * 64,
            "runtime_smoke": "pass",
            "archive_runtime_smoke": "pass",
            "provenance_verification": "pass",
            "installed_sdk_proof": True,
            "required_package_tests": 14,
            "required_package_skips": 0,
            "source_revisions": {
                "factorio_launcher": "a" * 40,
                "universal_launcher": "b" * 40,
                "universal_setup": "c" * 40,
            },
            "toolchain": {"cmake": "fixture"},
            "signed": False,
            "published": False,
        }

        report = remote_source_closure.build_report(
            repositories,
            records,
            package,
            Path("local-clones"),
            Path("local-build"),
        )
        schema = json_contract.load_schema(
            remote_source_closure.ROOT
            / "contracts/schema/release/remote_source_closure.v1.schema.json"
        )

        self.assertEqual(json_contract.validate(report, schema), [])
        self.assertTrue(report["clone_policy"]["git_core_longpaths"])


def ctest_record(label: str, count: int, *, extra: str = "") -> dict[str, object]:
    return {
        "label": label,
        "command": ["ctest"],
        "exit_code": 0,
        "output": f"{extra}\n100% tests passed, 0 tests failed out of {count}\n",
    }


if __name__ == "__main__":
    unittest.main()
