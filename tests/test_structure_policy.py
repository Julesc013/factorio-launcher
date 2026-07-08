from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class StructurePolicyTests(unittest.TestCase):
    def test_durable_roots_exist(self) -> None:
        for name in ["universal", "factorio", "cli", "tui", "daemon", "gui", "launcher", "schemas"]:
            self.assertTrue((ROOT / name).is_dir(), name)

    def test_factorio_assets_live_with_binding(self) -> None:
        self.assertTrue((ROOT / "factorio" / "product" / "factorio.product.toml").is_file())
        self.assertTrue((ROOT / "factorio" / "schemas" / "factorio-install-ref.schema.json").is_file())
        self.assertFalse((ROOT / "product").exists())

    def test_python_package_has_no_redundant_factorio_nesting(self) -> None:
        self.assertFalse((ROOT / "launcher" / "factorio_launcher" / "factorio").exists())


if __name__ == "__main__":
    unittest.main()

