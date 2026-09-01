# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import dev, verify_dependency_revisions, workspace_config
from tools.package import pipeline
from tools.validators.release import check_workspace_lock


class DependencyRevisionEnforcementTests(unittest.TestCase):
    def test_current_sibling_revisions_match_the_workspace_lock(self) -> None:
        self.assertEqual(verify_dependency_revisions.verify(), [])

    def test_explicit_repository_paths_take_precedence(self) -> None:
        component = {
            "id": "universal_launcher",
            "pin": "a" * 40,
            "path": "../universal-launcher",
            "source": "universal-launcher",
        }
        with tempfile.TemporaryDirectory() as tmp:
            explicit = Path(tmp)
            explicit.joinpath(".git").mkdir()
            self.assertEqual(
                verify_dependency_revisions.resolve_repo_path(
                    component, {"universal_launcher": explicit}
                ),
                explicit.resolve(),
            )

    def test_detached_worktree_git_file_is_a_repository_candidate(self) -> None:
        component = {
            "id": "universal_launcher",
            "pin": "a" * 40,
            "path": "../universal-launcher",
            "source": "universal-launcher",
        }
        with tempfile.TemporaryDirectory() as tmp:
            worktree = Path(tmp)
            worktree.joinpath(".git").write_text(
                "gitdir: C:/fixture/repository/.git/worktrees/proof\n",
                encoding="utf-8",
            )
            self.assertEqual(
                verify_dependency_revisions.resolve_repo_path(
                    component, {"universal_launcher": worktree}
                ),
                worktree.resolve(),
            )

    def test_release_lock_validator_uses_configured_worktree(self) -> None:
        component = {
            "id": "universal_setup",
            "pin": "a" * 40,
            "path": "../universal-setup",
            "source": "universal-setup",
        }
        with tempfile.TemporaryDirectory() as tmp:
            worktree = Path(tmp)
            worktree.joinpath(".git").write_text(
                "gitdir: C:/fixture/repository/.git/worktrees/proof\n",
                encoding="utf-8",
            )
            with patch.dict(
                "os.environ",
                {"FLAUNCH_UNIVERSAL_SETUP_ROOT": str(worktree)},
                clear=True,
            ):
                self.assertEqual(
                    check_workspace_lock.resolve_repo_path(component),
                    worktree.resolve(),
                )

    def test_default_verification_reports_drift_without_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launcher = root / "launcher"
            setup = root / "setup"
            launcher.joinpath(".git").mkdir(parents=True)
            setup.joinpath(".git").mkdir(parents=True)
            with (
                patch.object(
                    verify_dependency_revisions,
                    "git_output",
                    return_value="0" * 40,
                ),
                patch.object(verify_dependency_revisions, "run_git") as run_git,
            ):
                problems = verify_dependency_revisions.verify(
                    repository_paths={
                        "universal_launcher": launcher,
                        "universal_setup": setup,
                    }
                )
        self.assertEqual(len(problems), 2)
        self.assertTrue(all("expected" in problem for problem in problems))
        run_git.assert_not_called()

    def test_default_verification_does_not_contact_remotes(self) -> None:
        pin = "a" * 40
        component = {
            "id": "universal_launcher",
            "pin": pin,
            "path": "../universal-launcher",
            "source": "universal-launcher",
            "remote": "https://github.com/example/universal-launcher.git",
            "required_ref": "refs/heads/main",
            "reachability": "required_for_source_closure",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath(".git").mkdir()
            with (
                patch.object(
                    verify_dependency_revisions._common,
                    "load_toml",
                    return_value={"component": [component]},
                ),
                patch.object(
                    verify_dependency_revisions,
                    "git_output",
                    side_effect=[pin, ""],
                ),
                patch.object(
                    verify_dependency_revisions,
                    "remote_component_problems",
                ) as remote_check,
            ):
                problems = verify_dependency_revisions.verify(
                    repository_paths={"universal_launcher": root}
                )
        self.assertEqual(problems, [])
        remote_check.assert_not_called()

    def test_remote_verification_is_explicit(self) -> None:
        pin = "a" * 40
        component = {
            "id": "universal_launcher",
            "pin": pin,
            "path": "../universal-launcher",
            "source": "universal-launcher",
            "remote": "https://github.com/example/universal-launcher.git",
            "required_ref": "refs/heads/main",
            "reachability": "required_for_source_closure",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath(".git").mkdir()
            with (
                patch.object(
                    verify_dependency_revisions._common,
                    "load_toml",
                    return_value={"component": [component]},
                ),
                patch.object(
                    verify_dependency_revisions,
                    "git_output",
                    side_effect=[pin, ""],
                ),
                patch.object(
                    verify_dependency_revisions,
                    "remote_component_problems",
                    return_value=[],
                ) as remote_check,
            ):
                problems = verify_dependency_revisions.verify(
                    remote=True,
                    repository_paths={"universal_launcher": root},
                )
        self.assertEqual(problems, [])
        remote_check.assert_called_once()

    def test_remote_verification_rejects_missing_policy(self) -> None:
        problems = verify_dependency_revisions.remote_component_problems(
            Path("workspace_lock.toml"),
            {
                "id": "universal_launcher",
                "pin": "a" * 40,
                "path": "../universal-launcher",
                "source": "universal-launcher",
                "remote": "",
                "required_ref": "",
                "reachability": "",
            },
        )
        self.assertEqual(len(problems), 3)

    def test_workspace_doctor_refuses_a_pin_mismatch(self) -> None:
        repos = {
            "universal-setup": Path("X:/setup"),
            "universal-launcher": Path("X:/launcher"),
        }
        with (
            patch.object(workspace_config, "resolved_repos", return_value=repos),
            patch.object(workspace_config, "missing_repos", return_value=[]),
            patch.object(
                verify_dependency_revisions,
                "verify",
                return_value=["universal_launcher mismatch"],
            ),
        ):
            self.assertEqual(workspace_config.main(["doctor"]), 1)

    def test_package_preflight_refuses_before_output_mutation(self) -> None:
        with patch.object(
            verify_dependency_revisions,
            "verify",
            return_value=["universal_setup mismatch"],
        ):
            with self.assertRaisesRegex(
                ValueError, "requires exact Universal dependency revisions"
            ):
                pipeline.require_pinned_dependency_revisions()

    def test_verify_all_checks_pins_before_running_tests(self) -> None:
        source = Path(dev.__file__).read_text(encoding="utf-8")
        pin = 'run([sys.executable, "tools/verify_dependency_revisions.py"], env=exact_environment)'
        full = 'mode="full"'
        self.assertLess(source.index(pin), source.index(full))


if __name__ == "__main__":
    unittest.main()
