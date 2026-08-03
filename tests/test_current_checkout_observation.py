# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import current_checkout_observation


class CurrentCheckoutObservationTests(unittest.TestCase):
    def git(self, root: Path, *args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return completed.stdout.strip()

    def initialize_repository(self, root: Path, *, content: str = "truth\n") -> str:
        root.mkdir(parents=True)
        self.git(root, "init", "-b", "main")
        self.git(root, "config", "user.name", "FacMan Test")
        self.git(root, "config", "user.email", "facman-test@example.invalid")
        self.git(root, "config", "core.autocrlf", "false")
        root.joinpath("truth.txt").write_text(content, encoding="utf-8")
        self.git(root, "add", "truth.txt")
        self.git(root, "commit", "-m", "test truth")
        return self.git(root, "rev-parse", "HEAD")

    def initialize_provider(
        self,
        temporary: Path,
        component_id: str,
        abi_versions: dict[str, tuple[int, int]],
        *,
        pin_after_push: bool = False,
    ) -> tuple[Path, Path, str]:
        root = temporary / component_id
        self.initialize_repository(root)
        for abi_id, (major, minor) in abi_versions.items():
            header = root / "include" / abi_id / f"{abi_id}_types.h"
            header.parent.mkdir(parents=True)
            prefix = abi_id.upper()
            header.write_text(
                f"#define {prefix}_API_VERSION_MAJOR {major}\n"
                f"#define {prefix}_API_VERSION_MINOR {minor}\n",
                encoding="utf-8",
            )
        self.git(root, "add", "include")
        self.git(root, "commit", "-m", "declare provider ABIs")

        remote = temporary / "remotes" / f"{component_id}.git"
        remote.parent.mkdir(parents=True, exist_ok=True)
        remote.mkdir()
        self.git(remote, "init", "--bare")
        self.git(root, "remote", "add", "origin", str(remote.resolve()))
        self.git(root, "push", "-u", "origin", "main")

        if pin_after_push:
            root.joinpath("post-push.txt").write_text("not on origin/main\n", encoding="utf-8")
            self.git(root, "add", "post-push.txt")
            self.git(root, "commit", "-m", "unpublished pin")
        return root, remote, self.git(root, "rev-parse", "HEAD")

    def write_workspace_lock(
        self,
        path: Path,
        providers: list[tuple[str, Path, str]],
    ) -> None:
        lines = [
            'schema = "flaunch.workspace_lock.v1"',
            'id = "test_workspace_lock_v1"',
            '',
        ]
        for component_id, remote, pin in providers:
            source = component_id.replace("_", "-")
            lines.extend(
                [
                    "[[component]]",
                    f"id = {json.dumps(component_id)}",
                    f"source = {json.dumps(source)}",
                    f"pin = {json.dumps(pin)}",
                    f"path = {json.dumps('../' + source)}",
                    f"remote = {json.dumps(str(remote.resolve()))}",
                    'required_ref = "refs/heads/main"',
                    'reachability = "required_for_source_closure"',
                    "",
                ]
            )
        path.write_text("\n".join(lines), encoding="utf-8")

    def build_fixture(
        self,
        temporary: Path,
        *,
        unreachable_launcher_pin: bool = False,
    ) -> tuple[Path, Path, dict[str, Path], str]:
        facman = temporary / "factorio-launcher"
        facman_head = self.initialize_repository(facman)
        launcher, launcher_remote, launcher_pin = self.initialize_provider(
            temporary,
            "universal_launcher",
            {"ulk": (1, 6), "ulu": (1, 0)},
            pin_after_push=unreachable_launcher_pin,
        )
        setup, setup_remote, setup_pin = self.initialize_provider(
            temporary,
            "universal_setup",
            {"usk": (1, 0), "usu": (1, 0)},
        )
        lock = temporary / "workspace_lock.v1.toml"
        self.write_workspace_lock(
            lock,
            [
                ("universal_launcher", launcher_remote, launcher_pin),
                ("universal_setup", setup_remote, setup_pin),
            ],
        )
        return (
            facman,
            lock,
            {
                "universal_launcher": launcher,
                "universal_setup": setup,
            },
            facman_head,
        )

    def test_observation_binds_exact_checkout_provider_pins_and_abis(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temporary:
            temporary = Path(raw_temporary)
            facman, lock, provider_roots, facman_head = self.build_fixture(temporary)
            observation = current_checkout_observation.collect_observation(
                facman,
                lock,
                provider_roots,
                expected_source_sha=facman_head,
                observed_at_utc="2026-08-03T00:00:00Z",
            )

        self.assertEqual(
            observation["schema"], "facman.current_checkout_observation.v1"
        )
        self.assertEqual(observation["git_ownership_mode"], "owner_verified")
        self.assertEqual(
            observation["result"],
            {"status": "pass", "problem_count": 0, "problems": []},
        )
        self.assertEqual(observation["source"]["head"], facman_head)
        self.assertEqual(observation["source"]["branch"], "main")
        self.assertFalse(observation["source"]["dirty"])
        self.assertTrue(observation["source"]["expected_ci_sha_match"])

        providers = {provider["id"]: provider for provider in observation["providers"]}
        self.assertEqual(set(providers), {"universal_launcher", "universal_setup"})
        for provider in providers.values():
            self.assertEqual(provider["status"], "pass")
            self.assertTrue(provider["pin_checkout"])
            self.assertTrue(provider["pin_object_present"])
            self.assertTrue(provider["remote_matches_lock"])
            self.assertTrue(provider["pin_reachable_from_canonical_ref"])
            self.assertEqual(provider["canonical_remote_ref"], "refs/remotes/origin/main")
        self.assertEqual(
            [
                (item["id"], item["version"])
                for item in providers["universal_launcher"]["abi_versions"]
            ],
            [("ulk", "1.6"), ("ulu", "1.0")],
        )
        self.assertEqual(
            [
                (item["id"], item["version"])
                for item in providers["universal_setup"]["abi_versions"]
            ],
            [("usk", "1.0"), ("usu", "1.0")],
        )

    def test_expected_sha_mismatch_and_dirty_checkout_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temporary:
            temporary = Path(raw_temporary)
            facman, lock, provider_roots, _ = self.build_fixture(temporary)
            facman.joinpath("dirty.txt").write_text("dirty\n", encoding="utf-8")
            observation = current_checkout_observation.collect_observation(
                facman,
                lock,
                provider_roots,
                expected_source_sha="0" * 40,
                observed_at_utc="2026-08-03T00:00:00Z",
            )

        self.assertEqual(observation["result"]["status"], "fail")
        self.assertFalse(observation["source"]["expected_ci_sha_match"])
        self.assertTrue(observation["source"]["dirty"])
        self.assertIn(
            "factorio-launcher: checkout HEAD does not match expected CI SHA",
            observation["result"]["problems"],
        )
        self.assertIn(
            "factorio-launcher: checkout is dirty",
            observation["result"]["problems"],
        )

    def test_inherited_git_redirection_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temporary:
            temporary = Path(raw_temporary)
            facman, lock, provider_roots, facman_head = self.build_fixture(temporary)
            poisoned_git_dir = provider_roots["universal_setup"] / ".git"
            with mock.patch.dict(
                "os.environ",
                {
                    "GIT_DIR": str(poisoned_git_dir),
                    "GIT_WORK_TREE": str(provider_roots["universal_setup"]),
                    "GIT_NO_REPLACE_OBJECTS": "0",
                },
            ):
                observation = current_checkout_observation.collect_observation(
                    facman,
                    lock,
                    provider_roots,
                    expected_source_sha=facman_head,
                    observed_at_utc="2026-08-03T00:00:00Z",
                )

        self.assertEqual(observation["result"]["status"], "pass")
        self.assertEqual(observation["source"]["head"], facman_head)

    def test_inherited_alternate_index_and_object_stores_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temporary:
            temporary = Path(raw_temporary)
            facman, lock, provider_roots, facman_head = self.build_fixture(temporary)
            alternate_index = temporary / "alternate.index"
            alternate_index.write_bytes(facman.joinpath(".git", "index").read_bytes())
            facman.joinpath("truth.txt").write_text("hidden by alternate index\n", encoding="utf-8")
            alternate_environment = os.environ.copy()
            alternate_environment["GIT_INDEX_FILE"] = str(alternate_index)
            subprocess.run(
                ["git", "add", "truth.txt"],
                cwd=facman,
                env=alternate_environment,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            injected_objects = temporary / "injected-objects"
            injected_objects.mkdir()
            with mock.patch.dict(
                "os.environ",
                {
                    "GIT_INDEX_FILE": str(alternate_index),
                    "GIT_OBJECT_DIRECTORY": str(injected_objects),
                    "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(
                        provider_roots["universal_setup"] / ".git" / "objects"
                    ),
                },
            ):
                observation = current_checkout_observation.collect_observation(
                    facman,
                    lock,
                    provider_roots,
                    expected_source_sha=facman_head,
                    observed_at_utc="2026-08-03T00:00:00Z",
                )

        self.assertEqual(observation["source"]["head"], facman_head)
        self.assertTrue(observation["source"]["dirty"])
        self.assertTrue(observation["source"]["index_flags_clean"])
        self.assertIn(
            "factorio-launcher: checkout is dirty",
            observation["result"]["problems"],
        )

    def test_replace_refs_cannot_change_pinned_abi_identity(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temporary:
            temporary = Path(raw_temporary)
            facman, lock, provider_roots, facman_head = self.build_fixture(temporary)
            launcher = provider_roots["universal_launcher"]
            pin = self.git(launcher, "rev-parse", "HEAD")
            header = launcher / "include" / "ulk" / "ulk_types.h"
            header.write_text(
                "#define ULK_API_VERSION_MAJOR 9\n"
                "#define ULK_API_VERSION_MINOR 9\n",
                encoding="utf-8",
            )
            self.git(launcher, "add", "include/ulk/ulk_types.h")
            replacement_tree = self.git(launcher, "write-tree")
            replacement_commit = self.git(
                launcher,
                "commit-tree",
                replacement_tree,
                "-m",
                "hostile replacement",
            )
            self.git(launcher, "reset", "--hard", pin)
            self.git(launcher, "replace", pin, replacement_commit)
            replaced_header = self.git(
                launcher,
                "show",
                f"{pin}:include/ulk/ulk_types.h",
            )
            self.assertIn("API_VERSION_MAJOR 9", replaced_header)

            observation = current_checkout_observation.collect_observation(
                facman,
                lock,
                provider_roots,
                expected_source_sha=facman_head,
                observed_at_utc="2026-08-03T00:00:00Z",
            )

        launcher_observation = next(
            provider
            for provider in observation["providers"]
            if provider["id"] == "universal_launcher"
        )
        versions = {
            abi["id"]: abi["version"]
            for abi in launcher_observation["abi_versions"]
        }
        self.assertEqual(observation["result"]["status"], "pass")
        self.assertEqual(versions["ulk"], "1.6")

    def test_git_line_ending_policy_is_explicit_for_each_platform(self) -> None:
        completed = subprocess.CompletedProcess([], 0, "", "")
        root = Path.cwd()
        for platform, expected in (
            ("nt", "core.autocrlf=true"),
            ("posix", "core.autocrlf=input"),
        ):
            with self.subTest(platform=platform), mock.patch.object(
                current_checkout_observation.os,
                "name",
                platform,
            ), mock.patch.object(
                current_checkout_observation.subprocess,
                "run",
                return_value=completed,
            ) as run:
                current_checkout_observation._run_git(root, "status")
                command = run.call_args.args[0]
                self.assertIn(expected, command)

    def test_remote_credentials_are_ignored_and_redacted(self) -> None:
        credentialed = (
            "https://token:secret@example.invalid/org/repository.git?access=secret"
        )
        public = "https://example.invalid/org/repository.git"
        self.assertEqual(
            current_checkout_observation._normalize_remote(credentialed, Path.cwd()),
            current_checkout_observation._normalize_remote(public, Path.cwd()),
        )
        redacted = current_checkout_observation._redact_remote(credentialed)
        self.assertEqual(redacted, public)
        self.assertNotIn("token", redacted)
        self.assertNotIn("secret", redacted)

    def test_provider_pin_must_be_reachable_from_canonical_origin_main(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temporary:
            temporary = Path(raw_temporary)
            facman, lock, provider_roots, facman_head = self.build_fixture(
                temporary, unreachable_launcher_pin=True
            )
            observation = current_checkout_observation.collect_observation(
                facman,
                lock,
                provider_roots,
                expected_source_sha=facman_head,
                observed_at_utc="2026-08-03T00:00:00Z",
            )

        launcher = next(
            provider
            for provider in observation["providers"]
            if provider["id"] == "universal_launcher"
        )
        self.assertTrue(launcher["pin_checkout"])
        self.assertFalse(launcher["pin_reachable_from_canonical_ref"])
        self.assertEqual(launcher["status"], "fail")
        self.assertIn(
            "provider universal_launcher: locked pin is not reachable from canonical origin/main",
            observation["result"]["problems"],
        )

    def test_missing_canonical_remote_ref_is_unknown_and_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temporary:
            temporary = Path(raw_temporary)
            facman, lock, provider_roots, facman_head = self.build_fixture(temporary)
            launcher = provider_roots["universal_launcher"]
            self.git(launcher, "update-ref", "-d", "refs/remotes/origin/main")
            observation = current_checkout_observation.collect_observation(
                facman,
                lock,
                provider_roots,
                expected_source_sha=facman_head,
                observed_at_utc="2026-08-03T00:00:00Z",
            )

        launcher_observation = next(
            provider
            for provider in observation["providers"]
            if provider["id"] == "universal_launcher"
        )
        self.assertIsNone(launcher_observation["canonical_remote_head"])
        self.assertIsNone(
            launcher_observation["pin_reachable_from_canonical_ref"]
        )
        self.assertEqual(launcher_observation["status"], "fail")
        self.assertIn(
            "provider universal_launcher: canonical remote-tracking ref is unavailable",
            observation["result"]["problems"],
        )

    def test_abi_identity_comes_from_pin_and_special_index_flags_fail(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temporary:
            temporary = Path(raw_temporary)
            facman, lock, provider_roots, facman_head = self.build_fixture(temporary)
            launcher = provider_roots["universal_launcher"]
            header = launcher / "include" / "ulk" / "ulk_types.h"
            self.git(
                launcher,
                "update-index",
                "--assume-unchanged",
                "include/ulk/ulk_types.h",
            )
            header.write_text(
                "#define ULK_API_VERSION_MAJOR 9\n"
                "#define ULK_API_VERSION_MINOR 9\n",
                encoding="utf-8",
            )
            observation = current_checkout_observation.collect_observation(
                facman,
                lock,
                provider_roots,
                expected_source_sha=facman_head,
                observed_at_utc="2026-08-03T00:00:00Z",
            )

        launcher_observation = next(
            provider
            for provider in observation["providers"]
            if provider["id"] == "universal_launcher"
        )
        versions = {
            abi["id"]: abi["version"]
            for abi in launcher_observation["abi_versions"]
        }
        self.assertEqual(versions["ulk"], "1.6")
        self.assertFalse(launcher_observation["checkout"]["index_flags_clean"])
        self.assertEqual(launcher_observation["status"], "fail")
        self.assertIn(
            "provider universal_launcher: index contains assume-unchanged, "
            "skip-worktree, or nonstandard entries",
            observation["result"]["problems"],
        )

    def test_duplicate_provider_components_fail_provider_and_overall_status(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temporary:
            temporary = Path(raw_temporary)
            facman, lock, provider_roots, facman_head = self.build_fixture(temporary)
            lock_text = lock.read_text(encoding="utf-8")
            first_component = lock_text.split("[[component]]", 2)[1]
            first_component = first_component.rsplit("[[component]]", 1)[0]
            lock.write_text(
                lock_text + "[[component]]" + first_component,
                encoding="utf-8",
            )
            observation = current_checkout_observation.collect_observation(
                facman,
                lock,
                provider_roots,
                expected_source_sha=facman_head,
                observed_at_utc="2026-08-03T00:00:00Z",
            )

        duplicate_problem = (
            "workspace lock contains duplicate provider universal_launcher"
        )
        self.assertEqual(observation["result"]["status"], "fail")
        self.assertIn(duplicate_problem, observation["result"]["problems"])
        duplicate_providers = [
            provider
            for provider in observation["providers"]
            if provider["id"] == "universal_launcher"
        ]
        self.assertEqual(len(duplicate_providers), 2)
        self.assertTrue(
            all(provider["status"] == "fail" for provider in duplicate_providers)
        )

    def test_missing_passed_provider_root_is_reported_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temporary:
            temporary = Path(raw_temporary)
            facman, lock, provider_roots, facman_head = self.build_fixture(temporary)
            provider_roots["universal_launcher"] = temporary / "missing-launcher"
            observation = current_checkout_observation.collect_observation(
                facman,
                lock,
                provider_roots,
                expected_source_sha=facman_head,
                observed_at_utc="2026-08-03T00:00:00Z",
            )

        self.assertEqual(observation["result"]["status"], "fail")
        self.assertIn(
            "provider universal_launcher: repository root does not exist: "
            + str(provider_roots["universal_launcher"].resolve()),
            observation["result"]["problems"],
        )

    def test_cli_writes_canonical_json_and_markdown_outside_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temporary:
            temporary = Path(raw_temporary)
            facman, lock, provider_roots, facman_head = self.build_fixture(temporary)
            observed_roots = [facman, *provider_roots.values()]
            indexes_before = {
                root: root.joinpath(".git", "index").read_bytes()
                for root in observed_roots
            }
            output = temporary / "observation"
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
                io.StringIO()
            ):
                result = current_checkout_observation.main(
                    [
                        "--repository-root",
                        str(facman),
                        "--workspace-lock",
                        str(lock),
                        "--provider-root",
                        f"universal_launcher={provider_roots['universal_launcher']}",
                        "--provider-root",
                        f"universal_setup={provider_roots['universal_setup']}",
                        "--expected-source-sha",
                        facman_head,
                        "--output-dir",
                        str(output),
                    ]
                )
            json_path = output / "current-checkout-observation.v1.json"
            markdown_path = output / "current-checkout-observation.v1.md"
            json_text = json_path.read_text(encoding="utf-8")
            machine = json.loads(json_text)
            human = markdown_path.read_text(encoding="utf-8")

            failed_output = temporary / "failed-observation"
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
                io.StringIO()
            ):
                failed_result = current_checkout_observation.main(
                    [
                        "--repository-root",
                        str(facman),
                        "--workspace-lock",
                        str(lock),
                        "--provider-root",
                        f"universal_launcher={provider_roots['universal_launcher']}",
                        "--provider-root",
                        f"universal_setup={provider_roots['universal_setup']}",
                        "--expected-source-sha",
                        "0" * 40,
                        "--output-dir",
                        str(failed_output),
                    ]
                )
            failed_machine = json.loads(
                failed_output.joinpath(
                    "current-checkout-observation.v1.json"
                ).read_text(encoding="utf-8")
            )
            failed_markdown_exists = failed_output.joinpath(
                "current-checkout-observation.v1.md"
            ).is_file()
            indexes_after = {
                root: root.joinpath(".git", "index").read_bytes()
                for root in observed_roots
            }
            statuses_after = {
                root: self.git(root, "status", "--porcelain=v1")
                for root in observed_roots
            }

        self.assertEqual(result, 0)
        self.assertEqual(machine["result"]["status"], "pass")
        self.assertIn(machine["source"]["head"], human)
        self.assertIn(machine["providers"][0]["pin"], human)
        self.assertEqual(
            current_checkout_observation.canonical_json(machine),
            json_text,
        )
        self.assertEqual(failed_result, 1)
        self.assertEqual(failed_machine["result"]["status"], "fail")
        self.assertTrue(failed_markdown_exists)
        self.assertEqual(indexes_after, indexes_before)
        self.assertEqual(statuses_after, {root: "" for root in observed_roots})

    def test_cli_refuses_output_inside_any_observed_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temporary:
            temporary = Path(raw_temporary)
            facman, lock, provider_roots, facman_head = self.build_fixture(temporary)
            output = provider_roots["universal_launcher"] / "observation"
            stderr = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
                stderr
            ):
                result = current_checkout_observation.main(
                    [
                        "--repository-root",
                        str(facman),
                        "--workspace-lock",
                        str(lock),
                        "--provider-root",
                        f"universal_launcher={provider_roots['universal_launcher']}",
                        "--provider-root",
                        f"universal_setup={provider_roots['universal_setup']}",
                        "--expected-source-sha",
                        facman_head,
                        "--output-dir",
                        str(output),
                    ]
                )
            output_exists = output.exists()

        self.assertEqual(result, 2)
        self.assertFalse(output_exists)
        self.assertIn(
            "--output-dir must be outside every observed source/provider checkout",
            stderr.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
