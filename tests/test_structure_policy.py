from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class StructurePolicyTests(unittest.TestCase):
    def test_durable_roots_exist(self) -> None:
        for name in ["include", "runtime", "apps", "content", "contracts", "release", "tests", "tools"]:
            self.assertTrue((ROOT / name).is_dir(), name)

    def test_source_and_src_are_retired(self) -> None:
        source_dirs = [path for path in ROOT.rglob("*") if path.is_dir() and path.name == "source"]
        self.assertEqual([], source_dirs)
        src_dirs = [path for path in ROOT.rglob("*") if path.is_dir() and path.name == "src"]
        self.assertEqual([], src_dirs)

    def test_factorio_assets_live_with_binding(self) -> None:
        self.assertTrue((ROOT / "content" / "factorio" / "product" / "factorio.product.toml").is_file())
        self.assertTrue((ROOT / "contracts" / "schema" / "factorio" / "factorio_install_ref.v1.schema.json").is_file())
        self.assertFalse((ROOT / "product").exists())
        self.assertFalse((ROOT / "factorio").exists())

    def test_python_is_not_a_product_runtime(self) -> None:
        self.assertFalse((ROOT / "launcher").exists())
        self.assertFalse((ROOT / "apps" / "python_cli").exists())
        self.assertFalse((ROOT / "pyproject.toml").exists())

    def test_public_abi_prefixes_exist(self) -> None:
        self.assertTrue((ROOT / "include" / "flb" / "flb_api.h").is_file())
        self.assertFalse((ROOT / "include" / "usk").exists())
        self.assertFalse((ROOT / "include" / "ulk").exists())

    def test_runtime_and_client_source_seams_exist(self) -> None:
        self.assertTrue((ROOT / "runtime" / "package" / "fl_runtime_locator.c").is_file())
        self.assertTrue((ROOT / "runtime" / "client" / "fl_command_client.c").is_file())

    def test_frontends_are_apps(self) -> None:
        for name in ["cli", "tui", "daemon", "gui"]:
            self.assertTrue((ROOT / "apps" / name).is_dir(), name)
        for name in ["win32", "appkit", "gtk", "qt"]:
            self.assertTrue((ROOT / "apps" / "gui" / name).is_dir(), name)
        for old_gui_root in ["winforms", "appkit", "gtk", "qt"]:
            self.assertFalse((ROOT / "apps" / old_gui_root).exists(), old_gui_root)
        for old_root in ["gui", "universal", "src", "source", "prototypes"]:
            self.assertFalse((ROOT / old_root).exists(), old_root)

    def test_schema_namespaces_are_versioned(self) -> None:
        for name in ["common", "factorio", "release"]:
            self.assertTrue((ROOT / "contracts" / "schema" / name).is_dir(), name)
        self.assertTrue((ROOT / "contracts" / "schema" / "common" / "command_request.v1.schema.json").is_file())
        self.assertTrue((ROOT / "contracts" / "schema" / "factorio" / "factorio_instance.v1.schema.json").is_file())
        self.assertTrue(
            (ROOT / "contracts" / "schema" / "release" / "packaging" / "bundle_manifest.v1.schema.json").is_file()
        )


if __name__ == "__main__":
    unittest.main()
