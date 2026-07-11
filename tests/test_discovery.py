# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from native_cli import invoke

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"
FIXTURE_PORTABLE = ROOT / "tests" / "fixtures" / "fake_portable_install"
FIXTURE_HEADLESS = ROOT / "tests" / "fixtures" / "fake_headless_install"
FIXTURE_STEAM = ROOT / "tests" / "fixtures" / "fake_steam_library"
FIXTURE_MACOS = ROOT / "tests" / "fixtures" / "fake_macos_app"


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

    def test_scan_classifies_fixture_install_families_without_registering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            invalid = Path(tmp) / "not_factorio"
            invalid.mkdir()
            code, stdout, stderr = invoke(
                [
                    "--workspace",
                    tmp,
                    "installs",
                    "scan",
                    "--json",
                    "--path",
                    str(FIXTURE_INSTALL),
                    "--path",
                    str(FIXTURE_PORTABLE),
                    "--path",
                    str(FIXTURE_HEADLESS),
                    "--path",
                    str(FIXTURE_STEAM),
                    "--path",
                    str(FIXTURE_MACOS),
                    "--path",
                    str(invalid),
                ]
            )
            install_root = Path(tmp) / "installs"
            registered = list((install_root / "refs").glob("*.json"))
            registered += list((install_root / "installed_state").glob("*.json"))

        self.assertEqual(code, 0, stderr)
        report = json.loads(stdout)
        self.assertEqual(report["schema"], "factorio.discovery_report.v1")
        self.assertEqual(report["command"], "installs.scan")
        self.assertEqual(report["read_only"], True)
        installs = report["installs"]
        self.assertEqual(report["candidate_count"], len(installs))
        self.assertFalse(registered)

        structural = [install for install in installs if install["verification"]["status"] == "structural"]
        self.assertEqual(report["structural_count"], len(structural))
        by_source = {install["source"]: install for install in structural}
        self.assertEqual(by_source["manual"]["ownership"], "imported")
        self.assertEqual(by_source["portable"]["ownership"], "portable")
        self.assertEqual(by_source["steam"]["ownership"], "foreign_owned")
        self.assertEqual(by_source["headless"]["ownership"], "imported")
        self.assertEqual(by_source["app_bundle"]["platform"], "macos")
        self.assertEqual(by_source["manual"]["discovery"]["read_only"], True)

        invalid_candidates = [install for install in installs if install["verification"]["status"] == "invalid"]
        self.assertEqual(report["invalid_count"], len(invalid_candidates))
        self.assertTrue(invalid_candidates)

    def test_imported_install_can_be_inspected_by_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture"]
            )
            self.assertEqual(code, 0, stderr)

            code, stdout, stderr = invoke(["--workspace", tmp, "installs", "inspect", "fixture", "--json"])

        self.assertEqual(code, 0, stderr)
        install = json.loads(stdout)
        self.assertEqual(install["install_id"], "fixture")
        self.assertEqual(install["verification"]["status"], "structural")
        self.assertEqual(install["safe_actions"], {"repair": False, "uninstall": False})

    def test_legacy_install_refs_remain_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "legacy-fixture"]
            )
            self.assertEqual(code, 0, stderr)

            canonical = workspace / "installs" / "refs" / "legacy-fixture.json"
            legacy = workspace / "installs" / "installed_state" / "legacy-fixture.json"
            legacy.parent.mkdir(parents=True)
            legacy.write_text(canonical.read_text(encoding="utf-8"), encoding="utf-8")
            canonical.unlink()

            code, stdout, stderr = invoke(["--workspace", tmp, "installs", "inspect", "legacy-fixture", "--json"])
            self.assertEqual(code, 0, stderr)
            install = json.loads(stdout)
            self.assertEqual(install["install_id"], "legacy-fixture")

            code, stdout, stderr = invoke(["--workspace", tmp, "installs", "list", "--json"])
            self.assertEqual(code, 0, stderr)
            listed = json.loads(stdout)
            self.assertEqual([item["install_id"] for item in listed], ["legacy-fixture"])

            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "instances", "create", "Legacy Fixture", "--install", "legacy-fixture"]
            )
            self.assertEqual(code, 0, stderr)


if __name__ == "__main__":
    unittest.main()
