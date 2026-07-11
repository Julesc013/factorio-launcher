# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SetupPackageRoutingTests(unittest.TestCase):
    def test_facman_package_verify_routes_through_canonical_usk_command(self) -> None:
        cli = (ROOT / "apps" / "cli" / "command_dispatch.cpp").read_text(encoding="utf-8")
        setup = (
            ROOT / "runtime" / "factorio" / "application" / "handlers" / "setup.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn('call(options, "setup.operation", operation_payload("package.verify"))', cli)
        self.assertNotIn("usk/usk_api.h", cli)
        self.assertIn('setup_execute("package.verify"', setup)
        self.assertIn("usk.package_verify_request.v1", setup)

    def test_workspace_lock_pins_integrated_universal_revisions(self) -> None:
        lock = (ROOT / "release" / "index" / "workspace_lock.v1.toml").read_text(
            encoding="utf-8"
        )
        self.assertIn("80a848375227dc858865874ef594c4b466877241", lock)
        self.assertIn("4855e4f5dd23ae5dfa0d7f23a61ffbf46e1439d2", lock)


if __name__ == "__main__":
    unittest.main()
