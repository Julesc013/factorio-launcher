# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.native_cli import invoke
from tools import workspace_resolver_check


class WorkspaceResolverTests(unittest.TestCase):
    def test_every_frontend_uses_the_shared_resolution_law(self) -> None:
        self.assertEqual([], workspace_resolver_check.validate())

    def test_cli_runtime_preserves_explicit_primary_and_compatibility_precedence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman resolver ") as temporary:
            root = Path(temporary)
            explicit = root / "explicit"
            primary = root / "primary"
            compatibility = root / "compatibility"
            env = os.environ.copy()
            env["FACMAN_WORKSPACE"] = str(primary)
            env["FACTORIO_LAUNCHER_WORKSPACE"] = str(compatibility)

            report = self.invoke_paths([], env)
            self.assertEqual(str(primary), report["observations"]["root"])
            report = self.invoke_paths(["--workspace", str(explicit)], env)
            self.assertEqual(str(explicit), report["observations"]["root"])

            env.pop("FACMAN_WORKSPACE")
            report = self.invoke_paths([], env)
            self.assertEqual(str(compatibility), report["observations"]["root"])
            self.assertFalse(explicit.exists())
            self.assertFalse(primary.exists())
            self.assertFalse(compatibility.exists())

    def invoke_paths(self, prefix: list[str], env: dict[str, str]) -> dict:
        code, stdout, stderr = invoke([*prefix, "workspace", "paths", "--json"], env=env)
        self.assertEqual(0, code, stderr or stdout)
        return json.loads(stdout)


if __name__ == "__main__":
    unittest.main()
