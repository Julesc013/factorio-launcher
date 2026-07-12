# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from native_cli import invoke
from tools import json_contract


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"
SCHEMA_ROOT = ROOT / "contracts" / "schema" / "factorio"


def invoke_json(workspace: Path, *args: str, success: bool = True) -> dict:
    code, stdout, stderr = invoke(["--workspace", str(workspace), *args, "--json"])
    if success and code != 0:
        raise AssertionError(stderr or stdout)
    if not success and code == 0:
        raise AssertionError(f"command unexpectedly succeeded: {stdout}")
    return json.loads(stdout or stderr)


def assert_schema(test: unittest.TestCase, value: dict, name: str) -> None:
    schema = json_contract.load_schema(SCHEMA_ROOT / name)
    test.assertEqual([], json_contract.validate(value, schema), name)


def create_instance(workspace: Path) -> Path:
    invoke_json(workspace, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture")
    invoke_json(workspace, "instances", "create", "Main", "--id", "main", "--install", "fixture")
    return workspace / "instances" / "main"


class ProfileTemplateTests(unittest.TestCase):
    def test_shipped_template_and_existing_gui_instance_remain_compatible(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman templates ") as value:
            workspace = Path(value)
            create_instance(workspace)
            listed = invoke_json(workspace, "templates", "list")
            inspected = invoke_json(workspace, "templates", "inspect", "vanilla")
            validated = invoke_json(workspace, "templates", "validate", "vanilla")
            assert_schema(self, listed, "factorio_instance_templates.v1.schema.json")
            assert_schema(self, inspected, "factorio_instance_template.v1.schema.json")
            assert_schema(self, validated, "factorio_instance_template_validation.v1.schema.json")
            self.assertEqual(["vanilla"], listed["templates"])
            self.assertTrue(all(inspected["forbidden_capabilities"].values()))
            self.assertNotIn('"executable":', json.dumps(inspected).lower())

            preview = invoke_json(workspace, "launch", "plan", "main")
            self.assertEqual("gui", preview["profile_id"])
            self.assertEqual("gui", preview["mode"])
            self.assertEqual("--config", preview["args"][0])
            self.assertEqual("--mod-directory", preview["args"][2])

    def test_profile_lifecycle_plan_apply_and_safe_argument_boundary(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman profiles ") as value:
            workspace = Path(value)
            instance = create_instance(workspace)
            before = (instance / "instance.v1.json").read_bytes()

            created = invoke_json(
                workspace, "profiles", "create", "quiet", "--audio", "disabled",
                "--graphics-quality", "low", "--arg", "--low-vram",
            )
            assert_schema(self, created, "factorio_launch_profile_report.v1.schema.json")
            profile_path = workspace / "profiles" / "quiet" / "profile.v1.json"
            document = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertEqual("factorio.launch_profile.v1", document["schema"])
            assert_schema(self, document, "factorio_launch_profile.v1.schema.json")
            self.assertFalse(document["portability"]["machine_local_paths"])
            self.assertFalse(document["portability"]["credentials"])
            self.assertNotIn(str(workspace), profile_path.read_text(encoding="utf-8"))

            refused = invoke_json(workspace, "profiles", "create", "unsafe", "--arg", "--config", success=False)
            self.assertEqual("profile_arguments_invalid", refused["refusal"]["code"])
            self.assertFalse((workspace / "profiles" / "unsafe").exists())

            planned = invoke_json(
                workspace, "profiles", "plan", "main", "quiet",
                "--window-mode", "fullscreen", "--arg", "--disable-audio",
            )
            assert_schema(self, planned, "factorio_effective_profile.v1.schema.json")
            self.assertFalse(planned["mutation_executed"])
            self.assertFalse(planned["execution_enabled"])
            self.assertEqual(before, (instance / "instance.v1.json").read_bytes())

            applied = invoke_json(
                workspace, "profiles", "apply", "main", "quiet",
                "--window-mode", "fullscreen", "--arg", "--disable-audio",
            )
            assert_schema(self, applied, "factorio_effective_profile.v1.schema.json")
            self.assertTrue(applied["mutation_executed"])
            self.assertEqual("quiet", json.loads((instance / "instance.v1.json").read_text(encoding="utf-8"))["profile"])
            overrides = json.loads((instance / "instance-overrides.v1.json").read_text(encoding="utf-8"))
            self.assertEqual("factorio.instance_overrides.v1", overrides["schema"])
            assert_schema(self, overrides, "factorio_instance_overrides.v1.schema.json")
            self.assertTrue(any((workspace / "backups" / "profiles").rglob("instance.v1.json")))

            preview = invoke_json(workspace, "launch", "plan", "main")
            self.assertEqual("quiet", preview["profile_id"])
            self.assertEqual(["--config", "--mod-directory"], [preview["args"][0], preview["args"][2]])
            self.assertIn("--low-vram", preview["args"])
            self.assertIn("--disable-audio", preview["args"])
            self.assertEqual(1, preview["args"].count("--config"))
            self.assertEqual(1, preview["args"].count("--mod-directory"))

            cloned = invoke_json(workspace, "profiles", "clone", "quiet", "archivable")
            assert_schema(self, cloned, "factorio_launch_profile_report.v1.schema.json")
            difference = invoke_json(workspace, "profiles", "diff", "gui", "quiet")
            assert_schema(self, difference, "factorio_launch_profile_diff.v1.schema.json")
            self.assertEqual({"audio", "graphics_quality", "additional_arguments"}, {
                item["field"] for item in difference["differences"]
            })
            archived = invoke_json(workspace, "profiles", "archive", "archivable")
            assert_schema(self, archived, "factorio_launch_profile_archive.v1.schema.json")
            self.assertFalse(archived["permanent_delete"])
            self.assertFalse((workspace / "profiles" / "archivable").exists())
            self.assertEqual(1, len(list((workspace / "trash" / "profiles").rglob("profile.v1.json"))))


if __name__ == "__main__":
    unittest.main()
