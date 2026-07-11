# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from native_cli import invoke

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"


def snapshot(root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))


class WorkspaceStoreTests(unittest.TestCase):
    def test_migration_inspect_and_plan_are_read_only_and_apply_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            before = snapshot(workspace)
            for operation in ("inspect", "plan"):
                code, stdout, stderr = invoke(
                    ["--workspace", tmp, "workspace", "migration", operation, "--json"]
                )
                self.assertEqual(code, 0, stderr)
                data = json.loads(stdout)
                self.assertEqual(data["command"], f"workspace.migration.{operation}")
                self.assertEqual(data["status"], "changes_detected")
                self.assertFalse(data["apply_enabled"])
                self.assertEqual(data["actions"][0]["kind"], "create_workspace_identity")
                self.assertEqual(snapshot(workspace), before)

            code, stdout, _stderr = invoke(
                ["--workspace", tmp, "workspace", "migration", "apply", "--json"]
            )
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout)["refusal"]["code"], "workspace_migration_apply_unproven")
            self.assertEqual(snapshot(workspace), before)

    def test_new_workspace_gets_stable_random_uuid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            manifest = json.loads((Path(tmp) / "workspace.v1.json").read_text(encoding="utf-8"))
            self.assertNotEqual(manifest["workspace_id"], "local")
            self.assertRegex(
                manifest["workspace_id"],
                re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"),
            )
            code, stdout, stderr = invoke(
                ["--workspace", tmp, "workspace", "migration", "inspect", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)["status"], "no_changes")

    def test_future_workspace_refuses_before_creating_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "workspace.v1.json").write_text(
                json.dumps(
                    {
                        "schema": "facman.factorio.workspace.v2",
                        "workspace_id": "future",
                        "layout_version": 2,
                    }
                ),
                encoding="utf-8",
            )
            before = snapshot(workspace)
            code, stdout, _stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture", "--json"]
            )
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout)["refusal"]["code"], "workspace_layout_future_or_unknown")
            self.assertEqual(snapshot(workspace), before)


if __name__ == "__main__":
    unittest.main()
