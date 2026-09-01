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
