# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import (
    macos_self_setup,
    package_contract_tck,
    platform_product_bundle,
    resource_pack,
)
from tools.package import profile as package_profile


class PackageContractTckTests(unittest.TestCase):
    @staticmethod
    def identity(
        path: str, data: bytes, mode: int = 0o644
    ) -> package_contract_tck.FileIdentity:
        return package_contract_tck.FileIdentity(
            path=path,
            size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            mode=mode,
        )

    def test_canonical_product_profiles_use_one_resource_pack(self) -> None:
        for profile in package_contract_tck.PRODUCT_PROFILES:
            self.assertEqual([], package_contract_tck.profile_problems(profile))

    def test_profile_lifecycle_and_producer_models_are_truthful(self) -> None:
        self.assertEqual([], package_contract_tck.lifecycle_problems())
        self.assertEqual([], package_contract_tck.producer_model_problems())

    def test_producer_model_rejects_candidate_receipt_or_source_drift(self) -> None:
        policy_path = (
            package_contract_tck.ROOT
            / "release/index/package_producers.v1.toml"
        )
        original_loader = package_contract_tck.load_toml
        baseline = original_loader(policy_path)
        cases = {
            "receipt": ("payload_equivalence_receipt", "release/index/wrong.toml"),
            "revision": ("payload_equivalence_source_revision", "0" * 40),
            "tree": ("payload_equivalence_source_tree", "1" * 40),
            "run": ("payload_equivalence_candidate_run", 1),
            "authority": ("payload_equivalence_authority", "release_qualified"),
        }
        for label, (field, value) in cases.items():
            with self.subTest(label=label):
                changed = copy.deepcopy(baseline)
                setup = next(
                    item
                    for item in changed["producer"]
                    if item["id"] == "platform_self_setup"
                )
                setup[field] = value

                def substituted(path: Path) -> dict[str, object]:
                    return changed if path == policy_path else original_loader(path)

                with patch.object(
                    package_contract_tck, "load_toml", side_effect=substituted
                ):
                    self.assertTrue(package_contract_tck.producer_model_problems())

    def test_qualified_install_mode_requires_sealed_evidence(self) -> None:
        lifecycle_path = (
            package_contract_tck.ROOT
            / "release/profiles/profile_lifecycle.v1.toml"
        )
        lifecycle = copy.deepcopy(package_contract_tck.load_toml(lifecycle_path))
        windows = next(
            item
            for item in lifecycle["assignment"]
            if item["profile_id"] == "windows_product_x64"
        )
        windows["install_mode_claims"]["system"] = "qualified"
        original_toml = package_profile._toml

        def substituted(path: Path) -> dict[str, object]:
            if path == lifecycle_path:
                return lifecycle
            return original_toml(path)

        with patch.object(package_profile, "_toml", side_effect=substituted):
            problems = package_profile.lifecycle_problems(package_contract_tck.ROOT)
        self.assertTrue(any("lacks sealed evidence" in item for item in problems))

    def test_macos_product_uses_non_colliding_internal_cli_and_public_shim(self) -> None:
        profile = package_contract_tck.load_toml(
            package_contract_tck.ROOT
            / "release/profiles/macos_product_x64/profile.toml"
        )
        entrypoints = profile["entrypoints"]
        self.assertNotEqual(entrypoints["gui"].casefold(), entrypoints["cli"].casefold())
        self.assertEqual("FacMan.app/Contents/Helpers/facman", entrypoints["cli"])
        self.assertEqual(
            '#!/bin/sh\nexec "/Applications/FacMan.app/Contents/Helpers/facman" "$@"\n',
            macos_self_setup.terminal_shim(),
        )

    def test_macos_setup_refuses_an_app_without_the_internal_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            app = Path(temporary) / "FacMan.app"
            gui = app / "Contents/MacOS/FacMan"
            gui.parent.mkdir(parents=True)
            gui.write_bytes(b"gui")
            with self.assertRaisesRegex(ValueError, "required executable"):
                macos_self_setup.validate_app_payload(app)
            cli = app / "Contents/Helpers/facman"
            cli.parent.mkdir(parents=True)
            cli.write_bytes(b"cli")
            macos_self_setup.validate_app_payload(app)

    def test_macos_installer_version_tracks_release_order_and_package_revision(self) -> None:
        version = macos_self_setup.native_package_version
        ordered = [
            version("0.1.0-alpha.5", "0"),
            version("0.1.0-alpha.6", "0"),
            version("0.1.0-beta.1", "0"),
            version("0.1.0-rc.1", "0"),
            version("0.1.0", "0"),
            version("0.1.1-alpha.1", "0"),
        ]
        numeric = [tuple(map(int, item.split("."))) for item in ordered]
        self.assertEqual(numeric, sorted(numeric))
        self.assertEqual(len(numeric), len(set(numeric)))
        self.assertEqual("0.1.10600", version("0.1.0-alpha.6", "0"))
        self.assertEqual("0.1.10601", version("0.1.0-alpha.6", "1"))
        for product, revision in (
            ("0.1.0-preview.1", "0"),
            ("0.1.0-alpha.100", "0"),
            ("0.1.0", "100"),
            ("0.1.0", "01"),
        ):
            with self.subTest(product=product, revision=revision), self.assertRaises(ValueError):
                version(product, revision)

    def test_macos_installer_package_info_matches_canonical_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            info = root / "PackageInfo"
            evidence = root / "evidence.json"
            record = {
                "schema": "facman.macos_self_setup.v1",
                "version": "0.1.0-alpha.6",
                "package_version": "0.1.10600",
                "setup": {"identifier": macos_self_setup.PACKAGE_IDENTIFIER},
            }
            evidence.write_text(json.dumps(record), encoding="utf-8")
            info.write_text(
                '<pkg-info identifier="io.github.julesc013.facman" version="0.1.10600"/>',
                encoding="utf-8",
            )
            with patch.object(
                macos_self_setup,
                "version_truth",
                return_value={"semver": "0.1.0-alpha.6", "package_revision": "0"},
            ):
                macos_self_setup.verify_package_info(info, evidence)
                info.write_text('<pkg-info identifier="io.github.julesc013.facman" version="0.1.0"/>', encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "Installer package identity"):
                    macos_self_setup.verify_package_info(info, evidence)

    def test_macos_setup_builder_checks_its_produced_package_info(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = root / "FacMan.app"
            for relative in ("Contents/MacOS/FacMan", "Contents/Helpers/facman"):
                executable = app / relative
                executable.parent.mkdir(parents=True, exist_ok=True)
                executable.write_bytes(b"facman")
            observed: list[str] = []
            native_version = "0.1.10600"

            def fake_run(arguments: list[str], **kwargs: object) -> None:
                observed.append(arguments[0])
                if arguments[0] == "pkgbuild":
                    Path(arguments[-1]).write_bytes(b"package")
                elif arguments[0] == "xar":
                    (Path(str(kwargs["cwd"])) / "PackageInfo").write_text(
                        f'<pkg-info identifier="io.github.julesc013.facman" version="{native_version}"/>',
                        encoding="utf-8",
                    )

            with (
                patch.object(macos_self_setup, "version_truth", return_value={
                    "semver": "0.1.0-alpha.6", "package_revision": "0"}),
                patch.object(macos_self_setup, "git", return_value="a" * 40),
                patch.object(macos_self_setup.subprocess, "run", side_effect=fake_run),
            ):
                record = macos_self_setup.build(app, root / "out", root / "evidence.json")
                self.assertEqual(["pkgbuild", "xar"], observed)
                self.assertEqual("0.1.10600", record["package_version"])
                native_version = "0.1.0"
                with self.assertRaisesRegex(ValueError, "Installer package identity"):
                    macos_self_setup.build(app, root / "out", root / "evidence.json")
                self.assertFalse((root / "out/FacMan-0.1.0-alpha.6-macos-x64-setup.pkg").exists())

    def test_macos_product_builder_places_cli_in_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            terminal = root / "terminal"
            (terminal / "bin").mkdir(parents=True)
            (terminal / "bin/facman").write_bytes(b"cli")
            for directory in ("licenses", "docs", "manifest"):
                path = terminal / directory
                path.mkdir()
                (path / "marker").write_bytes(directory.encode())
            (terminal / "facman.resources").write_bytes(b"resources")
            gui = root / "gui"
            executable = gui / "Contents/MacOS/FacMan"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"gui")
            stage = root / "stage"
            with (
                patch.object(platform_product_bundle, "version_truth", return_value="0.1.0-test"),
                patch.object(platform_product_bundle, "write_manifest", return_value={}) as manifest,
                patch.object(platform_product_bundle, "deterministic_zip"),
                patch.object(platform_product_bundle, "finish_evidence", return_value={}),
            ):
                platform_product_bundle.build_macos(
                    terminal,
                    gui,
                    stage,
                    root / "dist",
                    root / "evidence.json",
                )
            self.assertTrue(
                (stage / "FacMan.app/Contents/Helpers/facman").is_file()
            )
            self.assertEqual(
                ["FacMan"],
                [path.name for path in (stage / "FacMan.app/Contents/MacOS").iterdir()],
            )
            self.assertEqual(
                "FacMan.app/Contents/Helpers/facman",
                manifest.call_args.kwargs["cli"],
            )

    def test_windows_product_stage_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary)
            (stage / "FacMan.exe").write_bytes(b"gui")
            (stage / "bin").mkdir()
            (stage / "bin/facman.exe").write_bytes(b"terminal")
            resource_pack.build(resource_pack.ROOT, stage / "facman.resources")
            self.assertEqual(
                [], package_contract_tck.stage_problems(stage, "windows_product_x64")
            )
            (stage / "bin/facman-tui.exe").write_bytes(b"legacy")
            (stage / "contracts/schema").mkdir(parents=True)
            problems = package_contract_tck.stage_problems(stage, "windows_product_x64")
            self.assertTrue(any("forbidden public executable" in item for item in problems))
            self.assertTrue(any("non-product root" in item for item in problems))

    def test_all_setup_adapters_preserve_canonical_runtime_content(self) -> None:
        cases = {
            "windows_setup_overlay_v1": {
                "version": "0.1.0-alpha.4",
                "stage": [self.identity("FacMan.exe", b"gui"), self.identity("bin/facman.exe", b"cli")],
                "payload": [
                    self.identity("facman/generations/0.1.0-alpha.4/FacMan.exe", b"gui"),
                    self.identity("facman/generations/0.1.0-alpha.4/bin/facman.exe", b"cli"),
                    self.identity("facman/maintenance/FacManSetup.exe", b"setup"),
                    self.identity("facman/state/current-generation.v1.json", b"state"),
                    self.identity(
                        "facman/state/self-maintenance-package.v1.json",
                        b"maintenance",
                    ),
                ],
            },
            "macos_pkg_root_v1": {
                "version": "",
                "stage": [
                    self.identity("FacMan.app/Contents/MacOS/FacMan", b"gui"),
                    self.identity("FacMan.app/Contents/Helpers/facman", b"cli"),
                ],
                "payload": [
                    self.identity("Applications/FacMan.app/Contents/MacOS/FacMan", b"gui"),
                    self.identity("Applications/FacMan.app/Contents/Helpers/facman", b"cli"),
                    self.identity(
                        "usr/local/bin/facman",
                        macos_self_setup.terminal_shim().encode(),
                        0o755,
                    ),
                ],
            },
            "linux_run_embedded_archive_v1": {
                "version": "",
                "stage": [
                    self.identity("FacMan-0.1.0-alpha.4/FacMan", b"gui"),
                    self.identity("FacMan-0.1.0-alpha.4/facman", b"cli"),
                ],
                "payload": [
                    self.identity("FacMan-0.1.0-alpha.4/FacMan", b"gui"),
                    self.identity("FacMan-0.1.0-alpha.4/facman", b"cli"),
                ],
            },
        }
        for adapter, case in cases.items():
            with self.subTest(adapter=adapter):
                receipt = package_contract_tck.payload_equivalence_receipt(
                    case["stage"],
                    case["payload"],
                    adapter_id=adapter,
                    version=case["version"],
                )
                self.assertEqual("pass", receipt["status"])
                self.assertEqual([], receipt["problems"])
                self.assertEqual(
                    receipt["canonical_stage_digest"],
                    receipt["payload_runtime_digest"],
                )
                self.assertEqual(
                    "contract_test_only_no_release_qualification",
                    receipt["authority"],
                )

    def test_payload_equivalence_rejects_missing_modified_and_unowned_files(self) -> None:
        stage = [self.identity("FacMan", b"gui"), self.identity("facman", b"cli")]
        payload = [
            self.identity("FacMan", b"changed"),
            self.identity("unowned.txt", b"foreign"),
        ]
        receipt = package_contract_tck.payload_equivalence_receipt(
            stage,
            payload,
            adapter_id="linux_run_embedded_archive_v1",
        )
        self.assertEqual("fail", receipt["status"])
        self.assertTrue(any("content differs" in item for item in receipt["problems"]))
        self.assertTrue(any("missing canonical file" in item for item in receipt["problems"]))
        self.assertTrue(any("unowned extra file" in item for item in receipt["problems"]))

    def test_posix_payload_equivalence_includes_executable_modes(self) -> None:
        stage = [self.identity("facman", b"cli", 0o755)]
        payload = [self.identity("facman", b"cli", 0o644)]
        receipt = package_contract_tck.payload_equivalence_receipt(
            stage,
            payload,
            adapter_id="linux_run_embedded_archive_v1",
        )
        self.assertEqual("fail", receipt["status"])
        self.assertTrue(any("POSIX mode differs" in item for item in receipt["problems"]))
        self.assertNotEqual(
            receipt["canonical_stage_digest"],
            receipt["payload_runtime_digest"],
        )

    def test_macos_adapter_rejects_a_redirected_or_non_executable_public_shim(self) -> None:
        stage = [self.identity("FacMan.app/Contents/MacOS/FacMan", b"gui")]
        payload = [
            self.identity("Applications/FacMan.app/Contents/MacOS/FacMan", b"gui"),
            self.identity("usr/local/bin/facman", b"#!/bin/sh\nexec /tmp/other\n"),
        ]
        receipt = package_contract_tck.payload_equivalence_receipt(
            stage,
            payload,
            adapter_id="macos_pkg_root_v1",
        )
        self.assertEqual("fail", receipt["status"])
        self.assertTrue(
            any("adapter-owned content differs" in item for item in receipt["problems"])
        )
        self.assertTrue(
            any("adapter-owned file is not executable" in item for item in receipt["problems"])
        )

    def test_payload_equivalence_rejects_unsafe_and_case_colliding_paths(self) -> None:
        stage = [self.identity("FacMan.exe", b"gui")]
        payload = [
            self.identity("facman/generations/0.1/FacMan.exe", b"gui"),
            self.identity("FACMAN/GENERATIONS/0.1/facman.exe", b"other"),
            self.identity("../escape", b"bad"),
            self.identity("facman/maintenance/FacManSetup.exe", b"setup"),
            self.identity("facman/state/current-generation.v1.json", b"state"),
            self.identity(
                "facman/state/self-maintenance-package.v1.json",
                b"maintenance",
            ),
        ]
        receipt = package_contract_tck.payload_equivalence_receipt(
            stage,
            payload,
            adapter_id="windows_setup_overlay_v1",
            version="0.1",
        )
        self.assertEqual("fail", receipt["status"])
        self.assertTrue(any("path collision" in item for item in receipt["problems"]))
        self.assertTrue(any("unsafe inventory path" in item for item in receipt["problems"]))

    def test_windows_adapter_requires_a_safe_version(self) -> None:
        receipt = package_contract_tck.payload_equivalence_receipt(
            [self.identity("FacMan.exe", b"gui")],
            [],
            adapter_id="windows_setup_overlay_v1",
            version="../escape",
        )
        self.assertEqual("fail", receipt["status"])
        self.assertTrue(any("unsafe character" in item for item in receipt["problems"]))


if __name__ == "__main__":
    unittest.main()
