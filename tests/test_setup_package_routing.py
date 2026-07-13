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
        self.assertIn("c43d390efe0db17480f9d0262827659b4ae242dd", lock)
        self.assertIn("2bc4bf93b1a77c5c906fdc6d3f12b286dadc8ca7", lock)


if __name__ == "__main__":
    unittest.main()
