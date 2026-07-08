from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class StructurePolicyTests(unittest.TestCase):
    def test_durable_roots_exist(self) -> None:
        for name in ["include", "source", "apps", "data", "schemas", "packaging", "tests", "tools"]:
            self.assertTrue((ROOT / name).is_dir(), name)

    def test_single_source_root(self) -> None:
        source_dirs = [path for path in ROOT.rglob("*") if path.is_dir() and path.name == "source"]
        self.assertEqual([ROOT / "source"], source_dirs)
        src_dirs = [path for path in ROOT.rglob("*") if path.is_dir() and path.name == "src"]
        self.assertEqual([], src_dirs)

    def test_factorio_assets_live_with_binding(self) -> None:
        self.assertTrue((ROOT / "data" / "factorio" / "product" / "factorio.product.toml").is_file())
        self.assertTrue((ROOT / "schemas" / "factorio" / "factorio_install_ref.v1.schema.json").is_file())
        self.assertFalse((ROOT / "product").exists())
        self.assertFalse((ROOT / "factorio").exists())

    def test_python_package_has_no_redundant_factorio_nesting(self) -> None:
        self.assertFalse((ROOT / "launcher").exists())
        self.assertFalse(
            (ROOT / "source" / "prototypes" / "python_launcher" / "factorio_launcher" / "factorio").exists()
        )

    def test_public_abi_prefixes_exist(self) -> None:
        self.assertTrue((ROOT / "include" / "usk" / "usk_api.h").is_file())
        self.assertTrue((ROOT / "include" / "ulk" / "ulk_api.h").is_file())
        self.assertTrue((ROOT / "include" / "flb" / "flb_api.h").is_file())

    def test_runtime_and_client_source_seams_exist(self) -> None:
        self.assertTrue((ROOT / "source" / "runtime" / "fl_runtime_locator.c").is_file())
        self.assertTrue((ROOT / "source" / "client" / "fl_command_client.c").is_file())

    def test_frontends_are_apps(self) -> None:
        for name in ["factorio_cli", "factorio_tui", "factorio_daemon", "winforms", "appkit", "gtk", "qt"]:
            self.assertTrue((ROOT / "apps" / name).is_dir(), name)
            self.assertTrue((ROOT / "source" / "apps" / name).is_dir(), name)
        for old_root in ["cli", "tui", "daemon", "gui", "universal", "src", "prototypes"]:
            self.assertFalse((ROOT / old_root).exists(), old_root)

    def test_schema_namespaces_are_versioned(self) -> None:
        for name in ["common", "usk", "ulk", "factorio", "packaging"]:
            self.assertTrue((ROOT / "schemas" / name).is_dir(), name)
        self.assertTrue((ROOT / "schemas" / "common" / "command_request.v1.schema.json").is_file())
        self.assertTrue((ROOT / "schemas" / "ulk" / "instance.v1.schema.json").is_file())
        self.assertTrue((ROOT / "schemas" / "factorio" / "factorio_instance.v1.schema.json").is_file())
        self.assertTrue((ROOT / "schemas" / "packaging" / "bundle_manifest.v1.schema.json").is_file())


if __name__ == "__main__":
    unittest.main()
