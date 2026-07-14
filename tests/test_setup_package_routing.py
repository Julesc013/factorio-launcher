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
        gateway = (
            ROOT / "runtime" / "factorio" / "application" / "setup_gateway.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn('call(options, "package.verify")', cli)
        self.assertNotIn('call(options, "setup.operation"', cli)
        self.assertNotIn("usk/usk_api.h", cli)
        self.assertNotIn("usk/usk_api.h", setup)
        self.assertIn("context.setup().verify_package", setup)
        self.assertIn('execute_setup("package.verify"', gateway)
        self.assertIn("usk.package_verify_request.v1", gateway)
        self.assertIn("request.version", gateway)
        self.assertIn("facman::platform::path_to_utf8(request.archive)", gateway)
        self.assertNotIn("request.archive.string()", gateway)

    def test_workspace_lock_pins_integrated_universal_revisions(self) -> None:
        lock = (ROOT / "release" / "index" / "workspace_lock.v1.toml").read_text(
            encoding="utf-8"
        )
        self.assertIn("6d41e07b76cd19b2a7630835e05ac3aa125d57b8", lock)
        self.assertIn("264bb1939a67231878313155157abd0f83d24c13", lock)


if __name__ == "__main__":
    unittest.main()
