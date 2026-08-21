# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_repro_workspace_smoke import make_repo
from tools import repro_workspace_smoke_v2


class ReproWorkspaceSmokeV2Tests(unittest.TestCase):
    def test_workspace_root_resolves_canonical_facman_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            facman = make_repo(workspace / "facman", "factorio-launcher")
            make_repo(workspace / "universal-setup", "universal-setup")
            make_repo(workspace / "universal-launcher", "universal-launcher")
            with patch.dict("os.environ", {}, clear=True):
                repos = repro_workspace_smoke_v2.resolve_workspace_repos(
                    workspace_root=workspace
                )
        self.assertEqual(repos["factorio-launcher"], facman.resolve(strict=False))

    def test_explicit_facman_root_accepts_either_workspace_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            for name in ("facman", "factorio-launcher"):
                root = make_repo(workspace / name, "factorio-launcher")
                with self.subTest(name=name):
                    repos = repro_workspace_smoke_v2.resolve_workspace_repos(
                        facman_root=root
                    )
                    self.assertEqual(
                        repos["factorio-launcher"], root.resolve(strict=False)
                    )


if __name__ == "__main__":
    unittest.main()
