# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
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
        self.assertTrue((ROOT / "runtime" / "client" / "fl_command_client_cabi_execute.c").is_file())
        self.assertFalse((ROOT / "runtime" / "client" / "fl_command_client.c").exists())
        self.assertTrue((ROOT / "runtime" / "factorio" / "install_validation" / "README.md").is_file())
        self.assertTrue((ROOT / "runtime" / "factorio" / "modsets" / "README.md").is_file())
        self.assertFalse((ROOT / "runtime" / "factorio" / "c11").exists())
        self.assertFalse((ROOT / "runtime" / "factorio" / "cpp11").exists())

    def test_frontends_are_apps(self) -> None:
        for name in ["cli", "tui", "daemon", "gui"]:
            self.assertTrue((ROOT / "apps" / name).is_dir(), name)
        for name in [
            "windows/winforms",
            "windows/winui",
            "macos/appkit",
            "macos/swiftui",
            "linux/gtk",
            "linux/qt",
        ]:
            self.assertTrue((ROOT / "apps" / "gui" / name).is_dir(), name)
        for old_gui_root in ["win32", "winforms", "appkit", "gtk", "qt"]:
            self.assertFalse((ROOT / "apps" / old_gui_root).exists(), old_gui_root)
            self.assertFalse((ROOT / "apps" / "gui" / old_gui_root).exists(), old_gui_root)
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

    def test_contract_spine_exists_beyond_schemas(self) -> None:
        for path in [
            "contracts/abi/flb/README.md",
            "contracts/command/factorio/README.md",
            "contracts/result/README.md",
            "contracts/refusal/README.md",
            "contracts/diagnostic/README.md",
            "contracts/policy/README.md",
        ]:
            self.assertTrue((ROOT / path).is_file(), path)

    def test_launch_truth_inputs_are_fail_closed(self) -> None:
        launch_source = (
            ROOT
            / "runtime"
            / "factorio"
            / "launch"
            / "flb_factorio_launch_plan.cpp"
        ).read_text(encoding="utf-8")
        self.assertNotIn("std::getenv(", launch_source)
        self.assertIn("StableInputFile", launch_source)
        self.assertIn("launcher_reference_missing", launch_source)
        self.assertIn("launcher_install_not_active", launch_source)
        self.assertIn("launcher_install_unverified", launch_source)

        schema = json.loads(
            (
                ROOT
                / "contracts"
                / "schema"
                / "factorio"
                / "factorio_install_ref.v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        self.assertIn("lifecycle_status", schema["required"])
        self.assertEqual(
            {
                "active",
                "verification_failed",
                "recovery_required",
                "retired",
                "uninstalled",
                "missing",
                "unknown",
                "unsupported",
            },
            set(schema["properties"]["lifecycle_status"]["enum"]),
        )

    def test_candidate_storage_marker_is_workunit_neutral(self) -> None:
        candidate_source = (
            ROOT
            / "runtime"
            / "factorio"
            / "launch"
            / "flb_factorio_hermetic_candidate.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn("facman.candidate-artifacts.v1", candidate_source)
        self.assertNotIn(
            'marker, "FACMAN-HERMETIC-STANDALONE-PLAY-CANDIDATE-01',
            candidate_source,
        )

    def test_release_profiles_are_target_specific(self) -> None:
        for name in [
            "dev",
            "portable",
            "portable_cli",
            "windows_legacy_winforms",
            "windows_modern_winui",
            "macos_legacy_appkit",
            "macos_modern_swiftui",
            "linux_x11_gtk",
            "linux_wayland_qt",
        ]:
            self.assertTrue((ROOT / "release" / "profiles" / name / "README.md").is_file(), name)
        for vague in ["legacy", "modern"]:
            self.assertFalse((ROOT / "release" / "profiles" / vague).exists(), vague)

    def test_release_receipts_have_a_dedicated_namespace(self) -> None:
        self.assertTrue((ROOT / "release" / "receipts").is_dir())
        self.assertTrue(
            (
                ROOT
                / "release"
                / "receipts"
                / "facman-immutable-alpha-tag-ruleset-observation.v1.json"
            ).is_file()
        )


if __name__ == "__main__":
    unittest.main()
