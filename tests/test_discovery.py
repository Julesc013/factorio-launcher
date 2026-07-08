from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from native_cli import invoke

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"


class DiscoveryTests(unittest.TestCase):
    def test_fake_install_is_structural(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture", "--json"]
            )
        self.assertEqual(code, 0, stderr)
        install = json.loads(stdout)
        self.assertEqual(install["install_id"], "fixture")
        self.assertEqual(install["verification"]["status"], "structural")
        self.assertEqual(install["version"], "2.0.77")
        self.assertIn("fixture_stub", install["capabilities"])


if __name__ == "__main__":
    unittest.main()
