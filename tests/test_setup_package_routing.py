# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SetupPackageRoutingTests(unittest.TestCase):
    def test_legacy_package_verify_routes_through_canonical_usk_command(self) -> None:
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

    def test_canonical_v2_package_verify_routes_through_native_exact_closure(self) -> None:
        setup = (
            ROOT / "runtime" / "factorio" / "application" / "handlers" / "setup.cpp"
        ).read_text(encoding="utf-8")
        stage_branch = setup.index('root / "manifest" / "stage.v1.json"')
        legacy_branch = setup.index('root / "manifest" / "package.v1.toml"')
        self.assertLess(stage_branch, legacy_branch)
        self.assertIn("facman::package::inspect_runtime_package()", setup)
        self.assertIn(
            'facman::package::inspect_package(root, root / "bin" / "facman.exe")',
            setup,
        )
        self.assertIn('output.add_string("authenticity", "not_proven_unsigned")', setup)

    def test_workspace_lock_pins_integrated_universal_revisions(self) -> None:
        lock = (ROOT / "release" / "index" / "workspace_lock.v1.toml").read_text(
            encoding="utf-8"
        )
        self.assertIn("5479939ca5cbc9ee0f901608a92012778b4752ae", lock)
        self.assertIn("d2a2aae7e61c47035c92334b0522143b4fea3880", lock)


if __name__ == "__main__":
    unittest.main()
