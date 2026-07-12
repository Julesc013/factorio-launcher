# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from native_cli import invoke
from tools import json_contract


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"
SIMPLE = ROOT / "tests" / "fixtures" / "factorio_mods" / "valid_simple" / "simple_mod_1.0.0.zip"
OPTIONAL = ROOT / "tests" / "fixtures" / "factorio_mods" / "valid_optional_deps" / "optional_deps_1.0.0.zip"
SCHEMA_ROOT = ROOT / "contracts" / "schema" / "factorio"


def call(workspace: Path, *args: str, success: bool = True) -> dict:
    code, stdout, stderr = invoke(["--workspace", str(workspace), *args, "--json"])
    if success and code != 0:
        raise AssertionError(stderr or stdout)
    if not success and code == 0:
        raise AssertionError(f"command unexpectedly succeeded: {stdout}")
    return json.loads(stdout or stderr)


def assert_schema(test: unittest.TestCase, value: dict, name: str) -> None:
    schema = json_contract.load_schema(SCHEMA_ROOT / name)
    test.assertEqual([], json_contract.validate(value, schema), name)


def setup(workspace: Path, install: Path = FIXTURE_INSTALL) -> Path:
    call(workspace, "installs", "import", str(install), "--id", "fixture")
    call(workspace, "instances", "create", "Main", "--id", "main", "--install", "fixture")
    return workspace / "instances" / "main"


class LocalModInventoryTests(unittest.TestCase):
    def test_managed_inventory_has_stable_archives_dependencies_and_references(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman mod inventory ") as value:
            workspace = Path(value)
            instance = setup(workspace)
            simple = instance / "mods" / SIMPLE.name
            optional = instance / "mods" / OPTIONAL.name
            shutil.copyfile(SIMPLE, simple)
            shutil.copyfile(OPTIONAL, optional)
            before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (simple, optional)}
            call(workspace, "modsets", "lock", "main")

            inventory = call(workspace, "mods", "list")
            assert_schema(self, inventory, "factorio_mod_inventory.v1.schema.json")
            self.assertTrue(inventory["managed_roots_complete"])
            self.assertFalse(inventory["recursive_scan"])
            self.assertFalse(inventory["portal_access"])
            self.assertFalse(inventory["source_mutation"])
            records = {(item["name"], item["version"]): item for item in inventory["records"]}
            self.assertIn(("base", "2.0.77"), records)
            self.assertTrue(records[("base", "2.0.77")]["virtual_package"])
            simple_record = records[("simple_mod", "1.0.0")]
            optional_record = records[("optional_deps", "1.0.0")]
            self.assertRegex(simple_record["sha1"], r"^[0-9a-f]{40}$")
            self.assertRegex(simple_record["sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(simple_record["archive_size"], 0)
            self.assertGreater(simple_record["expanded_size"], 0)
            self.assertEqual("pass", simple_record["archive_policy_result"])
            self.assertEqual(["main"], simple_record["instance_references"])
            self.assertTrue(simple_record["lock_references"])
            self.assertEqual(["optional_mod", "load_order_hint"], [item["name"] for item in optional_record["optional_dependencies"]])
            self.assertEqual(["load_order_hint"], [item["name"] for item in optional_record["hidden_optional_dependencies"]])

            verified = call(workspace, "mods", "verify", simple_record["sha256"])
            explained = call(workspace, "mods", "explain", "optional_deps@1.0.0")
            inspected = call(workspace, "mods", "inspect", SIMPLE.name)
            for result in (verified, explained, inspected):
                assert_schema(self, result, "factorio_mod_inventory_record.v1.schema.json")
                self.assertFalse(result["portal_access"])
                self.assertFalse(result["source_mutation"])
            self.assertTrue(verified["stable_identity_verified"])
            self.assertEqual(before, {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (simple, optional)})

    def test_explicit_roots_are_nonrecursive_and_builtins_come_from_install_metadata(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman inventory roots ") as value:
            root = Path(value)
            workspace = root / "workspace"
            install = root / "install"
            shutil.copytree(FIXTURE_INSTALL, install)
            quality = install / "data" / "quality"
            quality.mkdir()
            (quality / "info.json").write_text(
                '{"name":"quality","version":"2.0.77","title":"Quality"}\n', encoding="utf-8"
            )
            setup(workspace, install)
            external = root / "external"
            nested = external / "nested"
            nested.mkdir(parents=True)
            shutil.copyfile(SIMPLE, external / SIMPLE.name)
            shutil.copyfile(OPTIONAL, nested / OPTIONAL.name)

            indexed = call(workspace, "mods", "index", "--root", str(external))
            assert_schema(self, indexed, "factorio_mod_inventory.v1.schema.json")
            names = [item["name"] for item in indexed["records"]]
            self.assertIn("simple_mod", names)
            self.assertNotIn("optional_deps", names)
            self.assertIn("quality", names)
            quality_record = next(item for item in indexed["records"] if item["name"] == "quality")
            self.assertTrue(quality_record["virtual_package"])
            self.assertEqual("builtin_info_json", quality_record["metadata_source"])
            refused = call(workspace, "mods", "index", "--root", "relative-root", success=False)
            self.assertEqual("inventory_root_unsafe", refused["refusal"]["code"])


if __name__ == "__main__":
    unittest.main()
