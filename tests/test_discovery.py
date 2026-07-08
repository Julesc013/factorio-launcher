from __future__ import annotations

import unittest
from pathlib import Path

from factorio_launcher.discovery.detect_install import inspect_install

ROOT = Path(__file__).resolve().parents[1]


class DiscoveryTests(unittest.TestCase):
    def test_fake_install_is_structural(self) -> None:
        install = inspect_install(ROOT / "tests" / "fixtures" / "fake_factorio_install", install_id="fixture")
        self.assertEqual(install["install_id"], "fixture")
        self.assertEqual(install["verification"]["status"], "structural")
        self.assertEqual(install["version"], "2.0.77")
        self.assertIn("fixture_stub", install["capabilities"])


if __name__ == "__main__":
    unittest.main()
