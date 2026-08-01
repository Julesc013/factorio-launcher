# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from tools import build_winforms_c1_portable, facman_winforms_c1_check


class FacManWinFormsC1ShellTests(unittest.TestCase):
    def test_complete_bounded_shell_contract(self) -> None:
        self.assertEqual(facman_winforms_c1_check.main(), 0)

    def test_optional_cli_is_packaged_beside_shell(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            shell = root / "FacMan.WinForms.exe"
            cli = root / "facman.exe"
            shell.write_bytes(b"shell")
            cli.write_bytes(b"cli")
            output = build_winforms_c1_portable.build(shell, root / "prototype.zip", cli)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.read("bin/facman.exe"), b"cli")
                notice = archive.read("PROTOTYPE-NOTICE.txt").decode("utf-8")
                self.assertIn("no live Play authority", notice)
                self.assertIn("unsigned, unpublished", notice)


if __name__ == "__main__":
    unittest.main()
