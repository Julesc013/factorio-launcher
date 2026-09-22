# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import hashlib
import os
import subprocess
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from tools import development_layout
from tools import self_maintenance_candidate as candidate
from tests.integration import facman_self_setup_lifecycle as lifecycle


class SelfMaintenanceCandidateTests(unittest.TestCase):
    def test_candidate_payload_capacity_binds_exact_fixture_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "candidate.zip"
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("facman/bin/facman.exe", b"facman\n")
                archive.writestr("facman/release/" + "x" * 40, b"record\n")
            capacity = candidate.candidate_payload_path_capacity(
                package, root / "maintenance-transition"
            )
            self.assertEqual(
                candidate.WINDOWS_PROVIDER_FILE_LIMIT,
                capacity["limit_utf16_units"],
            )
            self.assertEqual("release/" + "x" * 40, capacity["relative_path"])
            self.assertGreaterEqual(capacity["headroom_utf16_units"], 0)

            with self.assertRaisesRegex(ValueError, "provider file limit"):
                candidate.candidate_payload_path_capacity(
                    package, root / ("overlong-" + "y" * 300)
                )

    def test_candidate_payload_capacity_refuses_noncanonical_members(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "candidate.zip"
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("other/bin/facman.exe", b"facman\n")
            with self.assertRaisesRegex(ValueError, "noncanonical payload path"):
                candidate.candidate_payload_path_capacity(package, root / "fixture")

    def test_predecessor_checkout_is_a_disjoint_task_root_sibling(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            task_root = parent / "owned-task"
            task_root.mkdir()
            checkout, output = candidate.predecessor_roots(task_root, "a" * 40)
            self.assertEqual(task_root / "self-maintenance-baseline-source", output)
            self.assertEqual(parent, checkout.parent)
            self.assertFalse(checkout.is_relative_to(task_root))
            self.assertFalse(task_root.is_relative_to(checkout))
            self.assertIn(".owned-task.predecessor.aaaaaaaaaaaa", checkout.name)

    def test_predecessor_environment_rebinds_inherited_candidate_task_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate_task = development_layout.ensure_task_root(
                root / "candidate-task", candidate.ROOT, "candidate-test",
            )
            source = root / "predecessor-source"
            source.mkdir()
            output = candidate_task / "predecessor-output"
            launcher = root / "universal-launcher"
            setup = root / "universal-setup"

            predecessor_revision = "a" * 40
            with mock.patch.dict(
                os.environ,
                {
                    "FACMAN_TASK_ROOT": str(candidate_task),
                    "GITHUB_SHA": "b" * 40,
                    "FACMAN_CI_SOURCE_SHA": "c" * 40,
                },
                clear=False,
            ):
                with self.assertRaisesRegex(ValueError, "repository_key"):
                    development_layout.ensure_task_root(
                        development_layout.default_task_root(source),
                        source,
                        development_layout.current_task_id(source),
                    )
                environment = candidate.predecessor_environment(
                    source, output, launcher, setup, predecessor_revision,
                )

            self.assertEqual(str(output.resolve()), environment["FACMAN_TASK_ROOT"])
            self.assertEqual(str(launcher), environment["FLAUNCH_UNIVERSAL_LAUNCHER_ROOT"])
            self.assertEqual(str(setup), environment["FLAUNCH_UNIVERSAL_SETUP_ROOT"])
            self.assertEqual(str(source), environment["PYTHONPATH"])
            self.assertEqual(
                predecessor_revision, environment["FACMAN_CI_SOURCE_SHA"],
            )
            self.assertEqual("b" * 40, environment["GITHUB_SHA"])
            self.assertEqual(
                str(output / "winforms-product" / "Release"),
                environment["FACMAN_WINFORMS_OUTPUT_ROOT"],
            )
            audit_environment = candidate.predecessor_audit_environment(environment)
            self.assertIsNot(environment, audit_environment)
            self.assertEqual(str(candidate.ROOT), audit_environment["PYTHONPATH"])
            self.assertEqual(
                predecessor_revision, audit_environment["FACMAN_CI_SOURCE_SHA"],
            )
            self.assertEqual(str(source), environment["PYTHONPATH"])
            marker = development_layout.read_marker(output, source)
            self.assertEqual(
                development_layout.repository_key(source), marker["repository_key"],
            )
            self.assertEqual(
                development_layout.current_task_id(source), marker["task_id"],
            )
            with mock.patch.dict(os.environ, environment, clear=False):
                self.assertEqual(
                    output.resolve(),
                    development_layout.ensure_task_root(
                        development_layout.default_task_root(source),
                        source,
                        development_layout.current_task_id(source),
                    ),
                )
            with self.assertRaisesRegex(ValueError, "repository_key"):
                development_layout.read_marker(output, candidate.ROOT)

    def test_predecessor_winforms_uses_its_checkout_and_owned_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "predecessor-source"
            output = root / "predecessor-output"
            source.mkdir()
            output.mkdir()
            environment = {"PYTHONPATH": str(source)}
            executable = output / "winforms-product/Release/FacMan.exe"

            def build(command: list[str], **kwargs: object) -> None:
                self.assertEqual(candidate.sys.executable, command[0])
                self.assertEqual("-c", command[1])
                self.assertIn("from tools import winforms_build", command[2])
                self.assertEqual(str(output), command[3])
                self.assertEqual(source, kwargs["cwd"])
                self.assertIs(environment, kwargs["env"])
                executable.parent.mkdir(parents=True)
                executable.write_bytes(b"predecessor WinForms")

            with mock.patch.object(candidate, "run", side_effect=build) as invoked:
                result = candidate.build_predecessor_winforms(
                    source, output, environment, deadline=time.monotonic() + 30,
                )

            self.assertEqual(executable, result)
            invoked.assert_called_once()

    def test_clone_clean_detached_materializes_long_path_and_persists_setting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bare = root / "source.git"
            subprocess.run(["git", "init", "--bare", str(bare)], check=True)
            payload = b"long path checkout \x00payload\n"
            blob = subprocess.run(
                ["git", "hash-object", "-w", "--stdin"], cwd=bare,
                input=payload, check=True, capture_output=True,
            ).stdout.decode("ascii").strip()
            target_relative = Path(*(["segment" + str(index).zfill(2) + "x" * 24
                                       for index in range(10)] + ["payload.bin"]))
            self.assertGreater(len(str(root / "checkout" / target_relative)), 260)
            tree = subprocess.run(
                ["git", "mktree"], cwd=bare,
                input=f"100644 blob {blob}\tpayload.bin\n".encode("ascii"),
                check=True, capture_output=True,
            ).stdout.decode("ascii").strip()
            for segment in reversed(target_relative.parts[:-1]):
                tree = subprocess.run(
                    ["git", "mktree"], cwd=bare,
                    input=f"040000 tree {tree}\t{segment}\n".encode("ascii"),
                    check=True, capture_output=True,
                ).stdout.decode("ascii").strip()
            environment = {
                **os.environ,
                "GIT_AUTHOR_NAME": "FacMan Test",
                "GIT_AUTHOR_EMAIL": "test@example.invalid",
                "GIT_COMMITTER_NAME": "FacMan Test",
                "GIT_COMMITTER_EMAIL": "test@example.invalid",
            }
            revision = subprocess.run(
                ["git", "commit-tree", tree, "-m", "long path fixture"], cwd=bare,
                env=environment, check=True, capture_output=True,
            ).stdout.decode("ascii").strip()
            subprocess.run(
                ["git", "update-ref", "refs/heads/main", revision], cwd=bare,
                check=True,
            )

            checkout = root / "checkout"
            candidate.clone_clean_detached(
                bare, checkout, revision, deadline=time.monotonic() + 30,
            )

            self.assertEqual(revision, candidate.head_revision(
                cwd=checkout, deadline=time.monotonic() + 30,
            ))
            self.assertNotEqual(0, subprocess.run(
                ["git", "symbolic-ref", "--quiet", "HEAD"], cwd=checkout,
                check=False,
            ).returncode)
            self.assertEqual("", candidate.capture(
                candidate.git_command("status", "--porcelain=v1", "--untracked-files=all"),
                cwd=checkout, deadline=time.monotonic() + 30,
            ))
            self.assertEqual(payload, (checkout / target_relative).read_bytes())
            self.assertEqual("", subprocess.run(
                ["git", "status", "--porcelain=v1", "--untracked-files=all"],
                cwd=checkout, check=True, text=True, capture_output=True,
            ).stdout)
            self.assertEqual("true", subprocess.run(
                ["git", "config", "--get", "core.longpaths"], cwd=checkout,
                check=True, text=True, capture_output=True,
            ).stdout.strip())

    def overlay(
        self, root: Path, *, version: str, source: str,
        current_source: str | None = None, current_provider: str | None = None,
    ) -> tuple[Path, Path]:
        package = root / f"{version}.exe"
        portable = root / f"FacMan-{version}-windows-x64-portable.zip"
        portable.write_bytes(b"portable package")
        current_source = current_source or source
        provider = "a" * 40
        current_provider = current_provider or provider
        with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("facman/state/self-maintenance-package.v1.json", json.dumps({
                "schema": "facman.self_maintenance_package.v1",
                "product_id": "facman",
                "product_version": version,
                "generation_relative_path": f"generations/{version}",
                "facman_source_revision": source,
                "universal_setup_revision": provider,
                "setup_protocol": "facman.self_maintenance.v1",
                "package_layout": "versioned_generation_with_maintenance_v1",
                "entrypoints": {
                    "gui_relative_path": "FacMan.exe",
                    "cli_relative_path": "bin/facman.exe",
                    "maintenance_relative_path": "maintenance/FacManSetup.exe",
                },
                "automatic_update": False,
            }))
            archive.writestr("facman/state/current-generation.v1.json", json.dumps({
                "schema": "facman.current_generation.v1",
                "product_id": "facman",
                "version": version,
                "generation": f"generations/{version}",
                "portable_package": portable.name,
                "portable_sha256": candidate.sha256_file(portable),
                "facman_source_revision": current_source,
                "universal_setup_revision": current_provider,
                "workspace_preserved": True,
                "automatic_update": False,
            }))
        return package, portable

    def test_identity_requires_matching_maintained_package_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = "b" * 40
            package, portable = self.overlay(root, version="0.1.0-alpha.6", source=source)
            identity = candidate.identity_from_overlay(package, portable)
            self.assertEqual("0.1.0-alpha.6", identity["version"])
            self.assertEqual(source, identity["source_revision"])

    def test_setup_overlay_digest_binds_only_the_materialized_zip_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package, _ = self.overlay(
                root, version="0.1.0-alpha.6", source="b" * 40,
            )
            expected = candidate.sha256_file(package)
            prefixed = root / "FacMan-0.1.0-alpha.6-windows-x64-setup.exe"
            prefixed.write_bytes(b"MZ\x00bounded bootstrap\n" + package.read_bytes())

            self.assertEqual(expected, candidate.setup_overlay_sha256(package))
            self.assertEqual(expected, candidate.setup_overlay_sha256(prefixed))

            prefixed.write_bytes(prefixed.read_bytes() + b"foreign trailing byte")
            with self.assertRaisesRegex(ValueError, "ZIP end record"):
                candidate.setup_overlay_sha256(prefixed)

    def test_identity_refuses_cross_record_source_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package, _ = self.overlay(Path(temporary), version="0.1.0-alpha.6", source="b" * 40,
                                      current_source="c" * 40)
            with self.assertRaisesRegex(ValueError, "inconsistent"):
                candidate.identity_from_overlay(package)

    def test_identity_refuses_provider_and_portable_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package, portable = self.overlay(
                root, version="0.1.0-alpha.6", source="b" * 40,
                current_provider="c" * 40,
            )
            with self.assertRaisesRegex(ValueError, "inconsistent"):
                candidate.identity_from_overlay(package, portable)
            package, portable = self.overlay(
                root, version="0.1.0-alpha.7", source="b" * 40,
            )
            portable.write_bytes(b"substituted")
            with self.assertRaisesRegex(ValueError, "does not bind"):
                candidate.identity_from_overlay(package, portable)

    def test_predecessor_identity_preserves_produced_name_and_retained_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = "b" * 40
            package, portable = self.overlay(
                root, version="0.1.0-alpha.5", source=source,
            )
            retained_setup = candidate.copy_evidence(
                package, root / "windows-self-maintenance-baseline-setup.exe",
            )
            retained_portable = candidate.copy_evidence(
                portable, root / "windows-self-maintenance-baseline-portable.zip",
            )
            predecessor = {
                "setup": package,
                "portable": portable,
                "staged": {
                    "setup": retained_setup,
                    "portable": retained_portable,
                },
            }

            identity = candidate.identity_from_predecessor_outputs(predecessor)
            self.assertEqual(portable.name, identity["portable_name"])
            self.assertEqual(source, identity["source_revision"])

            Path(str(retained_portable["path"])).write_bytes(b"changed evidence")
            with self.assertRaisesRegex(ValueError, "predecessor portable differ"):
                candidate.identity_from_predecessor_outputs(predecessor)

    def test_semver_gate_accepts_alpha_successor_and_refuses_same_or_reverse(self) -> None:
        self.assertLess(candidate.semver_order("0.1.0-alpha.5", "0.1.0-alpha.6"), 0)
        self.assertEqual(0, candidate.semver_order("0.1.0-alpha.6", "0.1.0-alpha.6"))
        self.assertGreater(candidate.semver_order("0.1.0-alpha.6", "0.1.0-alpha.5"), 0)

    def test_semver_gate_refuses_noncanonical_versions(self) -> None:
        for value in ("01.0.0", "1.0.0-alpha..1", "1.0.0-alpha_1", "1.0.0+"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "invalid semantic"):
                candidate.semver_order(value, "1.0.0")

    def test_transition_receipt_recomputes_generation_install_and_physical_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            coordinator = root / "setup-coordinator.v1"
            generations = coordinator / "generations"
            activations = coordinator / "activations"
            generations.mkdir(parents=True)
            activations.mkdir()
            logical = root / "Programs/FacMan"
            state = root / "SetupState"
            identity = {
                "version": "0.1.0-alpha.6",
                "source_revision": "c" * 40,
                "provider_revision": "d" * 40,
            }
            package_sha256 = "e" * 64
            generation_id = lifecycle.generation_identity(identity, package_sha256)
            self.assertEqual(
                "705e6baf722b4f67c79003bf2750defbb541d6a417831c63fce7deb2bf232682",
                generation_id,
            )
            if os.name == "nt":
                self.assertEqual(
                    Path(
                        r"C:\fixture\Programs\FacMan.generation."
                        "5cfb56740435960b80efdf167a18f350b85465917c153cd8e081d391c532dfcd"
                    ),
                    lifecycle.physical_generation_root(
                        Path(r"C:\fixture\Programs\FacMan"), generation_id
                    ),
                )
            generation = lifecycle.expected_generation_record(
                identity, package_sha256, logical, state, root, legacy=False,
            )
            physical = Path(str(generation["install_root"]))
            source_identity = {
                "version": "0.1.0-alpha.5",
                "source_revision": "b" * 40,
                "provider_revision": "d" * 40,
            }
            source_package_sha256 = "a" * 64
            source_generation = lifecycle.expected_generation_record(
                source_identity, source_package_sha256, logical, state, root,
                legacy=True,
            )
            source_generation_id = str(source_generation["generation_id"])
            source_generation_path = (
                generations / f"generation.{source_generation_id}.v1.json"
            )
            source_generation_path.write_text(
                json.dumps(source_generation) + "\n", encoding="utf-8"
            )
            operation_id = "maint.update.legacy.candidate"
            migration_name = "activation.migration.legacy.v1.json"
            migration = {
                "schema": "facman.self_activation.v1",
                "product_id": "facman",
                "operation": "migration",
                "operation_id": "migration.legacy",
                "generation_id": source_generation_id,
                "previous": {"name": "", "sha256": ""},
            }
            migration_path = activations / migration_name
            migration_path.write_text(json.dumps(migration) + "\n", encoding="utf-8")
            activation = {
                "schema": "facman.self_activation.v1",
                "product_id": "facman",
                "operation": "update",
                "operation_id": operation_id,
                "source_generation_id": source_generation_id,
                "target_generation_id": generation_id,
                "previous": {
                    "name": migration_name,
                    "sha256": lifecycle.sha256_path(migration_path),
                },
            }
            activation_path = activations / f"activation.{operation_id}.v1.json"
            activation_path.write_text(json.dumps(activation) + "\n", encoding="utf-8")
            generation_path = generations / f"generation.{generation_id}.v1.json"
            if os.name == "nt":
                generation = dict(generation)
                generation["gui"] = (
                    str(physical / "generations") + "/" + identity["version"]
                    + "\\FacMan.exe"
                )
                generation["maintenance_launcher"] = (
                    str(physical / "maintenance") + "/FacManSetup.exe"
                )
            generation_path.write_text(json.dumps(generation) + "\n", encoding="utf-8")
            response = {
                "schema": "facman.self_maintenance_cli.v1",
                "status": "ok",
                "operation": "update",
                "phase": "completed",
                "operation_id": operation_id,
                "generation_id": generation_id,
                "product_version": identity["version"],
                "install_id": generation["install_id"],
                "install_root": str(physical),
                "generation_record": str(generation_path),
                "activation_record": str(activation_path),
            }
            receipt = lifecycle.require_transition_receipt(
                response, "update", identity, package_sha256,
                logical, state, root, None,
                migration_source=(source_identity, source_package_sha256),
            )
            self.assertEqual(physical, receipt["install_root"])
            self.assertEqual(source_generation, receipt["retained_legacy"])

            downgrade_id = "maint.downgrade.candidate.legacy"
            downgrade_activation = {
                "schema": "facman.self_activation.v1",
                "product_id": "facman",
                "operation": "downgrade",
                "operation_id": downgrade_id,
                "source_generation_id": generation_id,
                "target_generation_id": source_generation_id,
                "previous": {
                    "name": activation_path.name,
                    "sha256": lifecycle.sha256_path(activation_path),
                },
            }
            downgrade_activation_path = (
                activations / f"activation.{downgrade_id}.v1.json"
            )
            downgrade_activation_path.write_text(
                json.dumps(downgrade_activation) + "\n", encoding="utf-8"
            )
            downgrade_response = {
                **response,
                "operation": "downgrade",
                "operation_id": downgrade_id,
                "generation_id": source_generation_id,
                "product_version": source_identity["version"],
                "install_id": "facman.self",
                "install_root": str(logical),
                "generation_record": str(source_generation_path),
                "activation_record": str(downgrade_activation_path),
            }
            downgrade_receipt = lifecycle.require_transition_receipt(
                downgrade_response, "downgrade", source_identity,
                source_package_sha256, logical, state, root,
                receipt["activation"], retained_legacy=source_generation,
            )
            self.assertEqual(logical, downgrade_receipt["install_root"])
            substituted_legacy = dict(source_generation, logical_root=str(
                root / "Programs/FacMan-B"
            ))
            with self.assertRaisesRegex(AssertionError, "retained predecessor"):
                lifecycle.require_transition_receipt(
                    downgrade_response, "downgrade", source_identity,
                    source_package_sha256, logical, state, root,
                    receipt["activation"], retained_legacy=substituted_legacy,
                )

            physical_a = lifecycle.expected_generation_record(
                source_identity, source_package_sha256, logical, state, root,
                legacy=False,
            )
            source_generation_path.write_text(
                json.dumps(physical_a) + "\n", encoding="utf-8"
            )
            physical_a_response = {
                **downgrade_response,
                "install_id": physical_a["install_id"],
                "install_root": physical_a["install_root"],
            }
            with self.assertRaisesRegex(AssertionError, "retained legacy target"):
                lifecycle.require_transition_receipt(
                    physical_a_response, "downgrade", source_identity,
                    source_package_sha256, logical, state, root,
                    receipt["activation"], retained_legacy=source_generation,
                )
            source_generation_path.write_text(
                json.dumps(source_generation) + "\n", encoding="utf-8"
            )

            invalid_generation = dict(response, generation_id="f" * 64)
            with self.assertRaisesRegex(AssertionError, "independently invalid"):
                lifecycle.require_transition_receipt(
                    invalid_generation, "update", identity, package_sha256,
                    logical, state, root, None,
                    migration_source=(source_identity, source_package_sha256),
                )

            invalid_install = dict(response, install_id="facman.self.generation." + "f" * 64)
            with self.assertRaisesRegex(AssertionError, "install id"):
                lifecycle.require_transition_receipt(
                    invalid_install, "update", identity, package_sha256,
                    logical, state, root, None,
                    migration_source=(source_identity, source_package_sha256),
                )

            generation["logical_root"] = str(root / "Programs/FacMan-B")
            generation_path.write_text(json.dumps(generation) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "target package/root"):
                lifecycle.require_transition_receipt(
                    response, "update", identity, package_sha256,
                    logical, state, root, None,
                    migration_source=(source_identity, source_package_sha256),
                )

    def test_shell_assertion_binds_physical_root_and_exact_retained_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            logical = root / "Programs/FacMan"
            state = root / "SetupState"
            physical = root / ("FacMan.generation." + "9" * 64)
            version = "0.1.0-alpha.6"
            sources = state / "repair-sources"
            sources.mkdir(parents=True)
            retained: set[str] = set()
            active_sha = ""
            for index, payload in enumerate((b"baseline", b"candidate")):
                digest = hashlib.sha256(payload).hexdigest()
                source = sources / f"{digest}.zip"
                launcher = sources / f"{digest}.FacManSetup.exe"
                receipt = sources / f"{digest}.maintenance.v1"
                source.write_bytes(payload)
                launcher.write_bytes(b"launcher-" + payload)
                receipt.write_bytes((
                    "facman-repair-source-receipt-v1\n"
                    f"source_sha256={digest}\n"
                    f"launcher_sha256={lifecycle.sha256_path(launcher)}\n"
                ).encode("utf-8"))
                retained.add(digest)
                if index == 1:
                    active_sha = digest
            active_source = sources / f"{active_sha}.zip"
            maintenance = sources / f"{active_sha}.FacManSetup.exe"
            generation = physical / "generations" / version
            gui = generation / "FacMan.exe"
            uninstall = (
                f'"{maintenance}" uninstall --root "{physical}" --state-root "{state}" '
                f'--acceptance-root "{root}" --yes --noninteractive --shell-integration'
            )
            modify = (
                f'"{maintenance}" repair --package "{active_source}" --root "{physical}" '
                f'--state-root "{state}" --acceptance-root "{root}" '
                f'--yes --noninteractive --shell-integration'
            )
            expected = {
                "DisplayName": ("FacMan", 1),
                "DisplayVersion": (version, 1),
                "Publisher": ("Jules C", 1),
                "InstallLocation": (str(physical), 1),
                "DisplayIcon": (f'"{gui}"', 1),
                "UninstallString": (uninstall, 1),
                "QuietUninstallString": (uninstall + " --json", 1),
                "ModifyPath": (modify, 1),
                "NoModify": (1, 4),
                "NoRepair": (0, 4),
            }
            registry = {
                "state": "present", "view": "64-bit", "subkeys": [],
                "values": [
                    {"name": name, "value": value, "type": kind}
                    for name, (value, kind) in expected.items()
                ],
            }
            shortcut = {
                "state": "present",
                "fields": {
                    "target": str(generation / "FacMan.exe"),
                    "working_directory": str(generation),
                    "arguments": "",
                },
            }
            lifecycle.assert_owned_native(
                shortcut, registry, logical, state, root, version, "candidate update",
                active_root=physical, active_package_sha256=active_sha,
                retained_package_sha256s=retained,
            )
            receipt = sources / f"{active_sha}.maintenance.v1"
            for retained_path in (active_source, maintenance, receipt):
                linked = sources / (retained_path.name + ".linked")
                os.link(retained_path, linked)
                try:
                    with self.assertRaisesRegex(AssertionError, "single-link"):
                        lifecycle.assert_owned_native(
                            shortcut, registry, logical, state, root, version,
                            "linked retained source", active_root=physical,
                            active_package_sha256=active_sha,
                            retained_package_sha256s=retained,
                        )
                finally:
                    linked.unlink()

            launcher_bytes = maintenance.read_bytes()
            external_launcher = root / "substituted-launcher.exe"
            external_launcher.write_bytes(launcher_bytes)
            maintenance.unlink()
            try:
                try:
                    os.symlink(external_launcher, maintenance)
                except OSError:
                    maintenance.write_bytes(launcher_bytes)
                else:
                    with self.assertRaisesRegex(AssertionError, "plain regular file"):
                        lifecycle.assert_owned_native(
                            shortcut, registry, logical, state, root, version,
                            "linked retained launcher", active_root=physical,
                            active_package_sha256=active_sha,
                            retained_package_sha256s=retained,
                        )
                    maintenance.unlink()
                    maintenance.write_bytes(launcher_bytes)
            finally:
                if not maintenance.exists():
                    maintenance.write_bytes(launcher_bytes)

    def test_task_marker_is_stably_read_validated_and_single_link(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_root = development_layout.ensure_task_root(
                Path(temporary) / "owned-task", candidate.ROOT,
                "self-maintenance-candidate-marker-test",
            )
            marker = task_root / development_layout.MARKER_NAME
            observed = candidate.read_task_marker(task_root)
            self.assertEqual(str(task_root), observed["canonical_path"])

            hardlink = task_root / "marker-hardlink.json"
            os.link(marker, hardlink)
            try:
                with self.assertRaisesRegex(ValueError, "single-link"):
                    candidate.read_task_marker(task_root)
            finally:
                hardlink.unlink()

            original = marker.read_bytes()
            target = task_root / "marker-target.json"
            target.write_bytes(original)
            marker.unlink()
            try:
                try:
                    os.symlink(target, marker)
                except OSError:
                    marker.write_bytes(original)
                else:
                    with self.assertRaises((ValueError, OSError)):
                        candidate.read_task_marker(task_root)
                    marker.unlink()
                    marker.write_bytes(original)
            finally:
                if not marker.exists():
                    marker.write_bytes(original)

            payload = json.loads(original)
            payload["canonical_path"] = str(task_root / "substitution")
            marker.write_text(json.dumps(payload) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "path mismatch"):
                candidate.read_task_marker(task_root)

    def test_baseline_staging_retains_produced_inputs_when_gate_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            produced = root / "produced"
            evidence = root / "evidence"
            produced.mkdir()
            evidence.mkdir()
            artifacts: dict[str, dict[str, object]] = {}
            gates = {"payload_equivalence": "not_started"}
            for name, content in (
                ("checkout", b"checkout receipt\n"),
                ("source", b"source receipt\n"),
                ("portable", b"portable package\n"),
                ("setup", b"setup package\n"),
            ):
                source = produced / name
                source.write_bytes(content)
                artifacts[name] = candidate.copy_evidence(
                    source, evidence / name,
                )
                candidate.write_baseline_staging(evidence, artifacts, gates)
            gates["payload_equivalence"] = "failed"
            receipt = candidate.write_baseline_staging(evidence, artifacts, gates)
            observed = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertEqual("produced_unqualified", observed["status"])
            self.assertEqual("failed", observed["gates"]["payload_equivalence"])
            self.assertEqual(set(artifacts), set(observed["artifacts"]))
            for record in observed["artifacts"].values():
                path = Path(str(record["path"]))
                self.assertTrue(path.is_file())
                self.assertEqual(record["sha256"], candidate.sha256_file(path))

            source_text = (candidate.ROOT / "tools/self_maintenance_candidate.py").read_text(
                encoding="utf-8"
            )
            gate_call = source_text.index('str(ROOT / "tools/package_contract_tck.py")')
            self.assertLess(source_text.index('staged["portable"]'), gate_call)
            self.assertLess(source_text.index('staged["setup"]'), gate_call)
            self.assertIn("cwd=ROOT, env=auditor_environment", source_text)
