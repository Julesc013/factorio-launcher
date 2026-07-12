# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.native_cli import invoke


class WorkspacePreferencesTests(unittest.TestCase):
    def test_schema_is_non_secret_and_unknown_field_closed(self) -> None:
        root = Path(__file__).resolve().parents[1]
        schema = json.loads(
            (root / "contracts/schema/facman/facman_preferences.v1.schema.json").read_text(encoding="utf-8")
        )
        self.assertFalse(schema["additionalProperties"])
        serialized = json.dumps(schema).lower()
        for forbidden in ("token", "password", "cookie", "credential", "script", "shell"):
            self.assertNotIn(forbidden, serialized)

    def test_cli_validate_is_read_only_and_rejects_secret_flags(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman preferences ") as temporary:
            workspace = Path(temporary) / "workspace"
            code, stdout, stderr = invoke([
                "--workspace", str(workspace), "preferences", "validate",
                "--transport", "direct", "--color", "never", "--page-size", "40",
                "--timeout-seconds", "90", "--json",
            ])
            self.assertEqual(0, code, stderr or stdout)
            report = json.loads(stdout)
            self.assertEqual("preferences.validate", report["command"])
            self.assertFalse(report["mutation_executed"])
            self.assertFalse(workspace.exists())
            code, _, _ = invoke([
                "--workspace", str(workspace), "preferences", "apply",
                "--account-token", "forbidden", "--json",
            ])
            self.assertEqual(2, code)
            self.assertFalse(workspace.exists())


if __name__ == "__main__":
    unittest.main()
