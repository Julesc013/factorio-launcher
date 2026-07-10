from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SetupPackageRoutingTests(unittest.TestCase):
    def test_facman_package_verify_routes_through_canonical_usk_command(self) -> None:
        source = (ROOT / "apps" / "cli" / "command_dispatch.cpp").read_text(encoding="utf-8")
        start = source.index("int command_package(")
        end = source.index("\nint command_product(", start)
        command = source[start:end]
        self.assertIn('setup_command_response_json("package.verify"', command)
        self.assertNotIn("fl_runtime_verify_package", command)
        self.assertIn("usk.package_verify_request.v1", command)

    def test_workspace_lock_pins_the_proven_usk_verifier_revision(self) -> None:
        lock = (ROOT / "release" / "index" / "workspace_lock.v1.toml").read_text(
            encoding="utf-8"
        )
        self.assertIn("b98d40bf23b5df598333fa94367a93c612e09f17", lock)


if __name__ == "__main__":
    unittest.main()
