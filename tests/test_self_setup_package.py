# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "self_setup_package", ROOT / "tools/self_setup_package.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class SelfSetupPackageTests(unittest.TestCase):
    def portable(self, path: Path, extra: str | None = None) -> None:
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("bin/facman.exe", b"cli")
            archive.writestr("bin/FacMan.WinForms.exe", b"gui")
            archive.writestr("contracts/example.json", b"{}\n")
            if extra is not None:
                archive.writestr(extra, b"bad")

    def build(self, root: Path, output_name: str) -> tuple[dict[str, object], Path]:
        portable = root / "FacMan-0.1.0-alpha.2-windows-x64-portable.zip"
        setup = root / "FacManSetup.exe"
        output = root / output_name
        self.portable(portable)
        setup.write_bytes(b"MZ synthetic setup")
        record = MODULE.build(
            portable,
            setup,
            output,
            version="0.1.0-alpha.2",
            facman_revision="a" * 40,
            usk_revision="b" * 40,
            dirty=False,
        )
        return record, output

    def test_build_is_deterministic_and_versioned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, first_root = self.build(root, "first")
            second, second_root = self.build(root, "second")
            first_payload = first_root / first["payload"]["filename"]
            second_payload = second_root / second["payload"]["filename"]
            self.assertEqual(first_payload.read_bytes(), second_payload.read_bytes())
            self.assertEqual(first["payload"]["sha256"], second["payload"]["sha256"])
            with zipfile.ZipFile(first_payload) as archive:
                names = set(archive.namelist())
                self.assertIn(
                    "facman/generations/0.1.0-alpha.2/bin/FacMan.WinForms.exe", names
                )
                self.assertIn("facman/maintenance/FacManSetup.exe", names)
                activation = json.loads(
                    archive.read("facman/state/current-generation.v1.json")
                )
            self.assertEqual(activation["version"], "0.1.0-alpha.2")
            self.assertFalse(activation["automatic_update"])
            self.assertTrue(activation["workspace_preserved"])

    def test_traversal_and_case_collision_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            setup = root / "FacManSetup.exe"
            setup.write_bytes(b"MZ")
            for extra in ("../escape", "BIN/FACMAN.EXE"):
                portable = root / "portable.zip"
                self.portable(portable, extra)
                with self.assertRaises(ValueError):
                    MODULE.build(
                        portable,
                        setup,
                        root / ("out-" + extra.replace("/", "-")),
                        version="0.1.0-alpha.2",
                        facman_revision="a" * 40,
                        usk_revision="b" * 40,
                        dirty=False,
                    )


if __name__ == "__main__":
    unittest.main()
