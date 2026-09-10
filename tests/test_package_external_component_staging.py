# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.package import pipeline


class PackageExternalComponentStagingTests(unittest.TestCase):
    def test_winforms_resolver_refuses_debug_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            debug = root / "apps" / "gui" / "windows" / "winforms" / "bin" / "Debug"
            debug.mkdir(parents=True)
            (debug / "FacMan.WinForms.exe").write_bytes(b"debug")
            with mock.patch.dict(
                os.environ, {"FACMAN_WINFORMS_OUTPUT_ROOT": ""}
            ), mock.patch.object(pipeline, "ROOT", root):
                with self.assertRaisesRegex(ValueError, "missing built artifact"):
                    pipeline.resolve_source_target(
                        "apps/gui/windows/winforms", root / "native"
                    )

    def test_winforms_resolver_selects_only_release_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release = root / "apps" / "gui" / "windows" / "winforms" / "bin" / "Release"
            release.mkdir(parents=True)
            expected = release / "FacMan.WinForms.exe"
            expected.write_bytes(b"release")
            with mock.patch.dict(
                os.environ, {"FACMAN_WINFORMS_OUTPUT_ROOT": ""}
            ), mock.patch.object(pipeline, "ROOT", root):
                self.assertEqual(
                    pipeline.resolve_source_target(
                        "apps/gui/windows/winforms", root / "native"
                    ),
                    expected,
                )

    def test_winforms_artifact_is_staged_into_installed_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "built" / "FacMan.WinForms.exe"
            source.parent.mkdir()
            source.write_bytes(b"winforms fixture")
            install_root = root / "installed"
            bundle = {
                "components": [
                    {
                        "source_target": "apps/gui/windows/winforms",
                        "destination": "bin/FacMan.WinForms.exe",
                    },
                    {
                        "source_target": "facman_cli",
                        "destination": "bin/facman.exe",
                    },
                ]
            }

            with mock.patch.object(pipeline, "resolve_source_target", return_value=source) as resolve:
                pipeline.stage_external_components(install_root, root / "native", bundle)

            self.assertEqual(
                (install_root / "bin" / "FacMan.WinForms.exe").read_bytes(),
                b"winforms fixture",
            )
            resolve.assert_called_once_with("apps/gui/windows/winforms", root / "native")
            self.assertFalse((install_root / "bin" / "facman.exe").exists())

    def test_external_stage_to_package_preserves_gui_and_cli_identity(self) -> None:
        for destination in ("FacMan.exe", "bin/FacMan.WinForms.exe"):
            with self.subTest(destination=destination), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                built = root / "built" / "FacMan.exe"
                built.parent.mkdir()
                built.write_bytes(b"managed GUI fixture")
                installed = root / "installed"
                (installed / "bin").mkdir(parents=True)
                # This is the same CLI file on Windows. On a case-sensitive
                # host both spellings deliberately expose the old alias lookup.
                (installed / "bin" / "facman.exe").write_bytes(b"native CLI fixture")
                (installed / "bin" / "FacMan.exe").write_bytes(b"native CLI fixture")
                bundle = {"components": [
                    {"source_target": "apps/gui/windows/winforms",
                     "destination": destination, "runtime_role": "runtime_required"},
                    {"source_target": "facman_cli",
                     "destination": "bin/facman.exe", "runtime_role": "runtime_required"},
                ]}
                with mock.patch.object(pipeline, "resolve_source_target", return_value=built):
                    pipeline.stage_external_components(installed, root / "native", bundle)
                self.assertEqual((installed / destination).read_bytes(), built.read_bytes())
                package = root / "package"
                pipeline.copy_bundle_components(package, installed, bundle)
                self.assertEqual((package / destination).read_bytes(), b"managed GUI fixture")
                self.assertEqual((package / "bin/facman.exe").read_bytes(), b"native CLI fixture")
                self.assertNotEqual((package / destination).read_bytes(),
                                    (package / "bin/facman.exe").read_bytes())

    def test_missing_exact_external_stage_cannot_fall_back_to_other_binary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = root / "installed"
            (installed / "bin").mkdir(parents=True)
            (installed / "bin/FacMan.exe").write_bytes(b"native CLI fixture")
            (installed / "bin/FacMan.WinForms.exe").write_bytes(b"stale GUI fixture")
            bundle = {"components": [{
                "source_target": "apps/gui/windows/winforms",
                "destination": "FacMan.exe",
                "runtime_role": "runtime_required",
            }]}
            with self.assertRaisesRegex(ValueError, "missing source file"):
                pipeline.copy_bundle_components(root / "package", installed, bundle)
            self.assertFalse((root / "package/FacMan.exe").exists())

    def test_generic_component_lookup_cannot_resolve_a_gui_from_cli_alias(self) -> None:
        from tools.package import components
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bin").mkdir()
            (root / "bin/FacMan.exe").write_bytes(b"native CLI fixture")
            with self.assertRaisesRegex(ValueError, "missing component target"):
                components.resolve(root, "apps/gui/windows/winforms")

    def test_component_resolver_rejects_escaping_external_destination(self) -> None:
        from tools.package import components
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for destination in ("../outside.exe", "/absolute.exe", "C:/absolute.exe",
                                "bin\\\\FacMan.exe"):
                with self.subTest(destination=destination):
                    with self.assertRaisesRegex(ValueError, "relative and portable"):
                        components.resolve(root, "apps/gui/windows/winforms",
                                           destination=destination)

    def test_external_component_requires_a_safe_destination(self) -> None:
        bundle = {
            "components": [
                {
                    "source_target": "apps/gui/windows/winforms",
                    "destination": "../outside.exe",
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "must not escape package root"):
                pipeline.stage_external_components(root / "installed", root / "native", bundle)


if __name__ == "__main__":
    unittest.main()
