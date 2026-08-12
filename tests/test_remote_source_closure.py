# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from tools import json_contract
from tools import remote_source_closure


class RemoteSourceClosureTests(unittest.TestCase):
    def test_v1_schema_remains_compatible_with_retained_v1_evidence(self) -> None:
        retained = json.loads(
            (
                remote_source_closure.ROOT
                / "docs/quality/evidence/source-closure/remote-source-closure.v1.json"
            ).read_text(encoding="utf-8")
        )

        remote_source_closure.validate_source_closure_report(
            retained,
            remote_source_closure.ROOT
            / "contracts/schema/release/remote_source_closure.v1.schema.json",
        )

    def test_hostile_git_environment_is_refused_and_child_environment_is_sanitized(self) -> None:
        for key in (
            "GIT_DIR",
            "GIT_OBJECT_DIRECTORY",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES",
            "GIT_CONFIG_COUNT",
            "GIT_REPLACE_REF_BASE",
            "SSH_ASKPASS",
        ):
            with self.subTest(key=key):
                with self.assertRaisesRegex(
                    remote_source_closure.ClosureFailure,
                    key,
                ):
                    remote_source_closure.assert_safe_git_environment({key: "hostile"})

        with patch.dict(
            remote_source_closure.os.environ,
            {"GIT_DIR": "hostile", "SSH_ASKPASS": "hostile"},
            clear=False,
        ):
            environment = remote_source_closure.sanitized_git_environment()
        self.assertNotIn("GIT_DIR", environment)
        self.assertNotIn("SSH_ASKPASS", environment)
        self.assertEqual(environment["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(environment["GIT_CONFIG_GLOBAL"], remote_source_closure.os.devnull)
        self.assertEqual(environment["GIT_ATTR_NOSYSTEM"], "1")
        self.assertEqual(environment["GIT_TERMINAL_PROMPT"], "0")

        for key in ("CMAKE_TOOLCHAIN_FILE", "CC", "CXXFLAGS", "CL", "PYTHONPATH"):
            with self.subTest(key=key), self.assertRaisesRegex(
                remote_source_closure.ClosureFailure,
                key,
            ):
                remote_source_closure.assert_safe_build_environment({key: "hostile"})

    def test_checked_spec_requires_https_canonical_ref_and_full_pin(self) -> None:
        accepted = remote_source_closure.checked_spec(
            remote_source_closure.SourceSpec(
                "factorio-launcher",
                remote_source_closure.FACTORIO_REMOTE,
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
                remote_source_closure.FACTORIO_REMOTE,
                "dev",
                "a" * 40,
            ),
            remote_source_closure.SourceSpec(
                "factorio-launcher",
                remote_source_closure.FACTORIO_REMOTE,
                "refs/heads/dev",
                "short",
            ),
            remote_source_closure.SourceSpec(
                "factorio-launcher",
                remote_source_closure.FACTORIO_REMOTE,
                "refs/heads/dev",
                "A" * 40,
            ),
            remote_source_closure.SourceSpec(
                "factorio-launcher",
                remote_source_closure.FACTORIO_REMOTE,
                "refs/heads/task//source-closure",
                "a" * 40,
            ),
            remote_source_closure.SourceSpec(
                "factorio-launcher",
                remote_source_closure.FACTORIO_REMOTE,
                "refs/heads/task/../source-closure",
                "a" * 40,
            ),
            remote_source_closure.SourceSpec(
                "factorio-launcher",
                remote_source_closure.FACTORIO_REMOTE,
                "refs/heads/task/source.lock",
                "a" * 40,
            ),
            remote_source_closure.SourceSpec(
                "factorio-launcher",
                "https://token@github.com/Julesc013/factorio-launcher.git",
                "refs/heads/dev",
                "a" * 40,
            ),
            remote_source_closure.SourceSpec(
                "factorio-launcher",
                remote_source_closure.FACTORIO_REMOTE + "?credential=secret",
                "refs/heads/dev",
                "a" * 40,
            ),
            remote_source_closure.SourceSpec(
                "factorio-launcher",
                "https://github.com/example/factorio-launcher.git",
                "refs/heads/dev",
                "a" * 40,
            ),
        ):
            with self.assertRaises(remote_source_closure.ClosureFailure):
                remote_source_closure.checked_spec(spec)

    def test_provider_specs_are_bound_to_workspace_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lock = Path(temporary) / "workspace_lock.v1.toml"
            lock.write_text(
                """
schema = "flaunch.workspace_lock.v1"

[[component]]
id = "universal_setup"
pin = "cccccccccccccccccccccccccccccccccccccccc"
tree = "dddddddddddddddddddddddddddddddddddddddd"
remote = "https://github.com/Julesc013/universal-setup.git"
required_ref = "refs/heads/main"
reachability = "required_for_source_closure"

[[component]]
id = "universal_launcher"
pin = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
tree = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
remote = "https://github.com/Julesc013/universal-launcher.git"
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
schema = "flaunch.workspace_lock.v1"

[[component]]
id = "universal_setup"
pin = "cccccccccccccccccccccccccccccccccccccccc"
tree = "dddddddddddddddddddddddddddddddddddddddd"
remote = "https://github.com/Julesc013/universal-setup.git"
required_ref = "refs/heads/main"
reachability = "required_for_source_closure"

[[component]]
id = "universal_launcher"
pin = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
tree = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
remote = "https://github.com/Julesc013/universal-launcher.git"
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

    def test_provider_specs_reject_duplicate_or_noncanonical_network_inputs(self) -> None:
        canonical = """
schema = "flaunch.workspace_lock.v1"

[[component]]
id = "universal_setup"
pin = "cccccccccccccccccccccccccccccccccccccccc"
tree = "dddddddddddddddddddddddddddddddddddddddd"
remote = "https://github.com/Julesc013/universal-setup.git"
required_ref = "refs/heads/main"
reachability = "required_for_source_closure"

[[component]]
id = "universal_launcher"
pin = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
tree = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
remote = "https://github.com/Julesc013/universal-launcher.git"
required_ref = "refs/heads/main"
reachability = "required_for_source_closure"
""".strip()
        with tempfile.TemporaryDirectory() as temporary:
            lock = Path(temporary) / "workspace_lock.v1.toml"
            for name, content, message in (
                (
                    "duplicate",
                    canonical
                    + "\n\n[[component]]\nid = \"universal_setup\"\n",
                    "duplicate component",
                ),
                (
                    "remote",
                    canonical.replace(
                        "https://github.com/Julesc013/universal-setup.git",
                        "https://evil.example/universal-setup.git",
                    ),
                    "remote is not canonical",
                ),
                (
                    "ref",
                    canonical.replace(
                        'required_ref = "refs/heads/main"',
                        'required_ref = "refs/heads/task/provider"',
                        1,
                    ),
                    "requires provider main",
                ),
            ):
                lock.write_text(content + "\n", encoding="utf-8")
                with self.subTest(name=name), self.assertRaisesRegex(
                    remote_source_closure.ClosureFailure,
                    message,
                ):
                    remote_source_closure.provider_specs_from_lock(lock)

    def test_clone_exact_uses_no_local_and_detached_pin(self) -> None:
        spec = remote_source_closure.SourceSpec(
            "factorio-launcher",
            remote_source_closure.FACTORIO_REMOTE,
            "refs/heads/dev",
            "a" * 40,
            "d" * 40,
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
                if args == ["rev-parse", spec.remote_tracking_ref]:
                    return spec.pin
                if args[:2] == ["status", "--porcelain=v1"]:
                    return ""
                raise AssertionError(args)

            with (
                patch.object(remote_source_closure, "run_checked", side_effect=fake_run),
                patch.object(remote_source_closure, "git_output", side_effect=fake_output),
                patch.object(remote_source_closure, "git_code", side_effect=[0, 0, 1]),
                patch.object(
                    remote_source_closure,
                    "inspect_git_isolation",
                    return_value={
                        "alternates": False,
                        "replace_refs": False,
                        "shallow": False,
                        "partial_clone": False,
                        "promisor": False,
                        "config_includes": False,
                        "unexpected_object_directories": False,
                        "hostile_git_environment": False,
                        "object_format": "sha1",
                    },
                ),
                patch.object(
                    remote_source_closure,
                    "line_ending_observation",
                    return_value={
                        "attributes_path": ".gitattributes",
                        "attributes_sha256": "1" * 64,
                        "tracked_eol_inventory_sha256": "2" * 64,
                        "core_autocrlf": "unset",
                    },
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

    def test_loaded_proof_code_must_equal_the_exact_facman_clone(self) -> None:
        loaded = {
            "tools/remote_source_closure.py": Path(remote_source_closure.__file__),
            "tools/json_contract.py": Path(json_contract.__file__),
            "tools/repro_workspace_smoke.py": Path(
                remote_source_closure.repro_workspace_smoke.__file__
            ),
            "tools/successor_play_route_definition_check.py": (
                remote_source_closure.ROOT
                / "tools/successor_play_route_definition_check.py"
            ),
        }
        with tempfile.TemporaryDirectory() as temporary:
            clone = Path(temporary)
            for relative, source in loaded.items():
                destination = clone / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(source.read_bytes())

            binding = remote_source_closure.verify_loaded_proof_code(clone)
            self.assertEqual(set(binding), set(loaded))
            self.assertTrue(all(row["identical"] for row in binding.values()))

            (clone / "tools/json_contract.py").write_text(
                "# stale proof helper\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                remote_source_closure.ClosureFailure,
                "loaded proof code differs",
            ):
                remote_source_closure.verify_loaded_proof_code(clone)

    def test_schema_validator_is_bound_to_the_exact_dependency_lock(self) -> None:
        binding = remote_source_closure.verify_jsonschema_dependency(
            remote_source_closure.ROOT
        )
        self.assertEqual(binding["name"], "jsonschema")
        self.assertEqual(binding["version"], "4.26.0")
        self.assertEqual(binding["dependency_count"], 6)
        self.assertEqual(len(binding["requirements_lock_sha256"]), 64)

        with tempfile.TemporaryDirectory() as temporary:
            clone = Path(temporary)
            (clone / "tools").mkdir()
            (clone / "tools/requirements-dev.lock").write_text(
                "jsonschema==0.0.0\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                remote_source_closure.ClosureFailure,
                "differ from the exact FacMan development lock",
            ):
                remote_source_closure.verify_jsonschema_dependency(clone)

    def test_exact_cloned_route_validator_passes_current_contracts(self) -> None:
        remote_source_closure.validate_cloned_route_contracts(
            remote_source_closure.ROOT
        )

    def test_unauthorized_successor_route_fails_before_provider_or_build_work(self) -> None:
        factorio = remote_source_closure.SourceSpec(
            "factorio-launcher",
            remote_source_closure.FACTORIO_REMOTE,
            "refs/heads/task/source-closure",
            "a" * 40,
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            clone_root = root / "clones"
            build_root = root / "build"
            archive = root / "factorio.zip"
            archive.write_bytes(b"not-read-before-authority")

            def fake_clone(
                spec: remote_source_closure.SourceSpec,
                destination: Path,
            ) -> dict[str, object]:
                destination.mkdir()
                return {"id": spec.repo_id, "pin": spec.pin}

            with (
                patch.dict(remote_source_closure.os.environ, {}, clear=True),
                patch.object(
                    remote_source_closure,
                    "clone_exact",
                    side_effect=fake_clone,
                ) as clone,
                patch.object(
                    remote_source_closure,
                    "verify_loaded_proof_code",
                    return_value={},
                ),
                patch.object(
                    remote_source_closure,
                    "verify_jsonschema_dependency",
                    return_value={},
                ),
                patch.object(
                    remote_source_closure,
                    "validate_cloned_route_contracts",
                ),
                patch.object(
                    remote_source_closure,
                    "selected_successor_route",
                    side_effect=remote_source_closure.ClosureFailure(
                        "successor source-closure execution is not authorized"
                    ),
                ),
                patch.object(
                    remote_source_closure,
                    "resolve_factorio_archive",
                ) as resolve_archive,
                patch.object(
                    remote_source_closure,
                    "provider_specs_from_lock",
                ) as providers,
                self.assertRaisesRegex(
                    remote_source_closure.ClosureFailure,
                    "not authorized",
                ),
            ):
                remote_source_closure.execute(
                    factorio,
                    clone_root=clone_root,
                    build_root=build_root,
                    factorio_archive=archive,
                )

        self.assertEqual(clone.call_count, 1)
        resolve_archive.assert_not_called()
        providers.assert_not_called()

    def test_factorio_archive_path_indirection_is_refused_after_authority(self) -> None:
        archive = Path("factorio.zip")
        with (
            patch.object(remote_source_closure.Path, "is_symlink", return_value=True),
            self.assertRaisesRegex(
                remote_source_closure.ClosureFailure,
                "path indirection",
            ),
        ):
            remote_source_closure.resolve_factorio_archive(archive)

    def test_authority_refusal_emits_no_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "report.json"
            with (
                patch.dict(remote_source_closure.os.environ, {}, clear=True),
                patch.object(
                    remote_source_closure,
                    "execute",
                    side_effect=remote_source_closure.ClosureFailure(
                        "successor source-closure execution is not authorized"
                    ),
                ),
                patch.object(remote_source_closure, "write_report") as write_report,
            ):
                result = remote_source_closure.main(
                    [
                        "--factorio-pin",
                        "a" * 40,
                        "--successor-route",
                        "--factorio-archive",
                        str(Path(temporary) / "factorio.zip"),
                        "--report",
                        str(report),
                    ]
                )
            report_created = report.exists()

        self.assertEqual(result, 1)
        self.assertFalse(report_created)
        write_report.assert_not_called()

    def test_existing_report_is_preserved_without_starting_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "report.json"
            report.write_text("operator-owned\n", encoding="utf-8")
            with (
                patch.dict(remote_source_closure.os.environ, {}, clear=True),
                patch.object(remote_source_closure, "execute") as execute,
            ):
                result = remote_source_closure.main(
                    [
                        "--factorio-pin",
                        "a" * 40,
                        "--report",
                        str(report),
                    ]
                )
            preserved = report.read_text(encoding="utf-8")

        self.assertEqual(result, 1)
        self.assertEqual(preserved, "operator-owned\n")
        execute.assert_not_called()

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

    def test_factorio_archive_is_observed_read_only_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "factorio-space-age_win_2.0.77.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr(
                    "Factorio_2.0.77/bin/x64/factorio.exe",
                    b"fixture-factorio-executable",
                )
            identity = remote_source_closure.observe_factorio_archive(
                archive,
                {
                    "selector": {
                        "factorio_version": "2.0.77",
                        "distribution": "standalone_non_steam",
                    }
                },
            )

        self.assertEqual(identity["version"], "2.0.77")
        self.assertTrue(identity["read_only_observation"])
        self.assertFalse(identity["executed"])
        self.assertEqual(
            identity["executable_sha256"],
            remote_source_closure.hashlib.sha256(
                b"fixture-factorio-executable"
            ).hexdigest(),
        )

    def test_factorio_archive_refuses_lookalike_and_excessive_expansion(self) -> None:
        definition = {
            "selector": {
                "factorio_version": "2.0.77",
                "distribution": "standalone_non_steam",
            }
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lookalike = root / "lookalike.zip"
            with zipfile.ZipFile(lookalike, "w") as package:
                package.writestr(
                    "prefix/Factorio_2.0.77/bin/x64/factorio.exe",
                    b"fixture",
                )
            with self.assertRaisesRegex(
                remote_source_closure.ClosureFailure,
                "exactly one expected",
            ):
                remote_source_closure.observe_factorio_archive(
                    lookalike,
                    definition,
                )

            symlink = root / "symlink.zip"
            link = zipfile.ZipInfo("Factorio_2.0.77/bin/x64/factorio.exe")
            link.create_system = 3
            link.external_attr = (
                remote_source_closure.stat.S_IFLNK | 0o777
            ) << 16
            with zipfile.ZipFile(symlink, "w") as package:
                package.writestr(link, b"elsewhere")
            with self.assertRaisesRegex(
                remote_source_closure.ClosureFailure,
                "regular file",
            ):
                remote_source_closure.observe_factorio_archive(
                    symlink,
                    definition,
                )

            expansion = root / "expansion.zip"
            with zipfile.ZipFile(
                expansion,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as package:
                package.writestr(
                    "Factorio_2.0.77/bin/x64/factorio.exe",
                    b"0" * (2 * 1024 * 1024),
                )
            with self.assertRaisesRegex(
                remote_source_closure.ClosureFailure,
                "compression-ratio budget",
            ):
                remote_source_closure.observe_factorio_archive(
                    expansion,
                    definition,
                )

    def test_successor_projection_binds_task_scope_and_false_authority(self) -> None:
        route_selection = authorized_route_selection_fixture()
        package = successor_package_fixture()
        repositories = successor_repository_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "factorio.zip"
            with zipfile.ZipFile(archive, "w") as factorio_zip:
                factorio_zip.writestr(
                    "Factorio_2.0.77/bin/x64/factorio.exe", b"fixture"
                )
            spec = remote_source_closure.SourceSpec(
                "factorio-launcher",
                remote_source_closure.FACTORIO_REMOTE,
                "refs/heads/task/source-closure",
                "a" * 40,
            )
            successor = remote_source_closure.build_successor_observation(
                remote_source_closure.ROOT,
                spec,
                repositories,
                package,
                archive,
                route_selection=route_selection,
            )
            wrong_tree = copy.deepcopy(repositories)
            wrong_tree[1]["tree"] = "0" * 40
            with self.assertRaisesRegex(
                remote_source_closure.ClosureFailure,
                "revisions or trees differ",
            ):
                remote_source_closure.build_successor_observation(
                    remote_source_closure.ROOT,
                    spec,
                    wrong_tree,
                    package,
                    archive,
                    route_selection=route_selection,
                )

        self.assertEqual(successor["closure_scope"], "task_ref_rehearsal")
        self.assertFalse(successor["canonical_gate_satisfied"])
        self.assertEqual(
            successor["status"], "task_ref_reconstruction_passed"
        )
        self.assertEqual(
            successor["source_closure_id"],
            "facman.successor-play.source-closure.02",
        )
        self.assertEqual(
            successor["route"]["definition_contract"],
            "release/index/successor_play_route.v2.toml",
        )
        self.assertTrue(all(value is False for value in successor["authority"].values()))
        self.assertEqual(len(successor["source_closure_digest"]), 64)

        schema = json_contract.load_schema(
            remote_source_closure.ROOT
            / "contracts/schema/release/remote_source_closure.v1.schema.json"
        )
        successor_schema = {
            "$schema": schema["$schema"],
            "$defs": schema["$defs"],
            **schema["$defs"]["successor"],
        }
        validator_type = remote_source_closure.validator_for(successor_schema)
        self.assertEqual(
            list(validator_type(successor_schema).iter_errors(successor)),
            [],
        )

    def test_current_route_refuses_evidence_run_while_deferred(self) -> None:
        with self.assertRaisesRegex(
            remote_source_closure.ClosureFailure,
            "not authorized",
        ):
            remote_source_closure.selected_successor_route(
                remote_source_closure.ROOT
            )
        selection = remote_source_closure.selected_successor_route(
            remote_source_closure.ROOT,
            require_execution_authority=False,
        )
        self.assertEqual(selection[4], "facman.successor-play.source-closure.02")

    def test_admission_fixture_requires_all_three_gates(self) -> None:
        for field, route_index in (
            ("new_evidence_execution_authorized", None),
            ("source_closure_execution_authorized", None),
            ("new_source_closure_evidence_allowed", 1),
        ):
            with self.subTest(field=field):
                index, definition, historical, providers = route_records_fixture()
                index = copy.deepcopy(index)
                index["new_evidence_execution_authorized"] = True
                index["source_closure_execution_authorized"] = True
                index["route"][1]["new_source_closure_evidence_allowed"] = True
                if route_index is None:
                    index[field] = False
                else:
                    index["route"][route_index][field] = False
                index["index_digest"] = remote_source_closure.canonical_digest(
                    {key: value for key, value in index.items() if key != "index_digest"}
                )
                with patch.object(
                    remote_source_closure.tomllib,
                    "load",
                    side_effect=[index, definition, historical, providers],
                ), self.assertRaisesRegex(
                    remote_source_closure.ClosureFailure,
                    "not authorized",
                ):
                    remote_source_closure.selected_successor_route(
                        remote_source_closure.ROOT
                    )

    def test_route_selection_rejects_open_or_inconsistent_records(self) -> None:
        index, definition, historical, providers = route_records_fixture()
        cases = []

        open_index = copy.deepcopy(index)
        open_index["unexpected"] = False
        open_index["index_digest"] = remote_source_closure.canonical_digest(
            {key: value for key, value in open_index.items() if key != "index_digest"}
        )
        cases.append(
            ("open index", open_index, definition, historical, providers, "open")
        )

        duplicate = copy.deepcopy(index)
        duplicate["route"][1]["route_id"] = duplicate["route"][0]["route_id"]
        duplicate["index_digest"] = remote_source_closure.canonical_digest(
            {key: value for key, value in duplicate.items() if key != "index_digest"}
        )
        cases.append(
            (
                "duplicate route",
                duplicate,
                definition,
                historical,
                providers,
                "duplicated",
            )
        )

        stale_historical = copy.deepcopy(historical)
        stale_historical["definition_digest"] = "0" * 64
        cases.append(
            (
                "historical digest",
                index,
                definition,
                stale_historical,
                providers,
                "historical successor route definition is invalid",
            )
        )

        for (
            name,
            selected_index,
            selected_definition,
            selected_historical,
            selected_providers,
            message,
        ) in cases:
            with self.subTest(name=name), patch.object(
                remote_source_closure.tomllib,
                "load",
                side_effect=[
                    selected_index,
                    selected_definition,
                    selected_historical,
                    selected_providers,
                ],
            ), self.assertRaisesRegex(remote_source_closure.ClosureFailure, message):
                remote_source_closure.selected_successor_route(
                    remote_source_closure.ROOT,
                    require_execution_authority=False,
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
                "replace_refs": False,
                "shallow": False,
                "partial_clone": False,
                "promisor": False,
                "config_includes": False,
                "unexpected_object_directories": False,
                "hostile_git_environment": False,
                "object_format": "sha1",
                "local_clone": False,
                "canonical_ref_contains_pin": True,
                "remote_ref_head": char * 40,
                "pin_equals_remote_ref_head": True,
                "line_endings": {
                    "attributes_path": ".gitattributes",
                    "attributes_sha256": "1" * 64,
                    "tracked_eol_inventory_sha256": "2" * 64,
                    "core_autocrlf": "unset",
                },
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
            "manifest": "manifest/package.v1.toml",
            "manifest_sha256": "3" * 64,
            "build_info_sha256": "4" * 64,
            "stage_manifest": "manifest/stage.v1.json",
            "stage_manifest_sha256": "5" * 64,
            "stage_digest": "6" * 64,
            "resolution_root_digest": "7" * 64,
            "source_observation_digest": "8" * 64,
            "runtime_metadata_sha256": "9" * 64,
            "runtime_metadata_digest": "a" * 64,
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
            proof_code={
                relative: {
                    "loaded_sha256": "b" * 64,
                    "cloned_sha256": "b" * 64,
                    "identical": True,
                }
                for relative in remote_source_closure.PROOF_CODE_RELATIVES
            },
            schema_validator={
                "name": "jsonschema",
                "version": "4.26.0",
                "dependency_count": 6,
                "requirements_lock_sha256": "c" * 64,
            },
        )
        remote_source_closure.validate_source_closure_report(
            report,
            remote_source_closure.ROOT
            / "contracts/schema/release/remote_source_closure.v1.schema.json",
        )
        self.assertEqual(
            report["proof_profile"],
            "facman.remote_source_closure.hardened.v2",
        )
        missing_binding = copy.deepcopy(report)
        del missing_binding["tooling"]["proof_code"]
        with self.assertRaisesRegex(
            remote_source_closure.ClosureFailure,
            "proof_code",
        ):
            remote_source_closure.validate_source_closure_report(
                missing_binding,
                remote_source_closure.ROOT
                / "contracts/schema/release/remote_source_closure.v1.schema.json",
            )
        self.assertTrue(report["clone_policy"]["git_core_longpaths"])


def ctest_record(label: str, count: int, *, extra: str = "") -> dict[str, object]:
    return {
        "label": label,
        "command": ["ctest"],
        "exit_code": 0,
        "output": f"{extra}\n100% tests passed, 0 tests failed out of {count}\n",
    }


def successor_package_fixture() -> dict[str, object]:
    return {
        "artifact": "facman.zip",
        "artifact_sha256": "1" * 64,
        "manifest_sha256": "2" * 64,
        "stage_manifest_sha256": "3" * 64,
        "resolution_root_digest": "4" * 64,
        "source_observation_digest": "5" * 64,
    }


def successor_repository_fixture() -> list[dict[str, object]]:
    return [
        {
            "id": "factorio-launcher",
            "pin": "a" * 40,
            "tree": "f" * 40,
            "pin_equals_remote_ref_head": True,
        },
        {
            "id": "universal-launcher",
            "pin": "1cafe4054297cc11e02458b83d230db0cd064471",
            "tree": "47018102de4b9fd20af9f77acd4e1e35e51590f3",
            "pin_equals_remote_ref_head": False,
        },
        {
            "id": "universal-setup",
            "pin": "32488fc13bd2439f9f6e52e83a97f6da345a7650",
            "tree": "12fe757b1fc2ae78768a8cf912d03835f46ca65b",
            "pin_equals_remote_ref_head": False,
        },
    ]


def route_records_fixture() -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    records = []
    for relative in (
        remote_source_closure.ROUTE_INDEX_RELATIVE,
        remote_source_closure.ACTIVE_ROUTE_RELATIVE,
        remote_source_closure.HISTORICAL_ROUTE_RELATIVE,
        Path("release/index/providers.lock.v2.toml"),
    ):
        with (remote_source_closure.ROOT / relative).open("rb") as handle:
            records.append(remote_source_closure.tomllib.load(handle))
    return tuple(records)  # type: ignore[return-value]


def authorized_route_selection_fixture() -> tuple[
    Path,
    dict[str, object],
    Path,
    dict[str, object],
    str,
]:
    index, definition, historical, providers = route_records_fixture()
    index = copy.deepcopy(index)
    index["new_evidence_execution_authorized"] = True
    index["source_closure_execution_authorized"] = True
    routes = index["route"]
    assert isinstance(routes, list)
    routes[1]["new_source_closure_evidence_allowed"] = True
    index["index_digest"] = remote_source_closure.canonical_digest(
        {key: value for key, value in index.items() if key != "index_digest"}
    )
    with patch.object(
        remote_source_closure.tomllib,
        "load",
        side_effect=[index, definition, historical, providers],
    ):
        return remote_source_closure.selected_successor_route(
            remote_source_closure.ROOT
        )


if __name__ == "__main__":
    unittest.main()
