# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from native_cli import invoke

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "factorio_installs"
GOLDEN_ROOT = ROOT / "tests" / "golden" / "discovery"


def tree_snapshot(root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        snapshot[path.relative_to(root).as_posix()] = digest
    return snapshot


def run_json(args: list[str]) -> tuple[int, dict, str]:
    code, stdout, stderr = invoke(args)
    if stdout:
        return code, json.loads(stdout), stderr
    return code, {}, stderr


def report_summary(report: dict) -> dict:
    installs = report["installs"]
    assert len(installs) == 1
    install = installs[0]
    summary = {
        "schema": report["schema"],
        "command": report["command"],
        "read_only": report["read_only"],
        "candidate_count": report["candidate_count"],
        "structural_count": report["structural_count"],
        "invalid_count": report["invalid_count"],
        "install": {
            "candidate_id": install["candidate_id"],
            "source": install["source"],
            "ownership": install["ownership"],
            "platform": install["platform"],
            "capabilities": install["capabilities"],
            "executable_path_kind": install["executable_path_kind"],
            "app_dir_kind": install["app_dir_kind"],
            "validation_status": install["verification"]["status"],
            "setup_mutation_allowed": install["setup_mutation_allowed"],
        },
    }
    if "refusal" in install:
        summary["install"]["refusal"] = install["refusal"]
    return summary


class DiscoveryFixtureTests(unittest.TestCase):
    def test_fixture_goldens_match_cli_scan_reports(self) -> None:
        for golden_path in sorted(GOLDEN_ROOT.glob("*.json")):
            fixture_id = golden_path.name.split(".")[0]
            with self.subTest(fixture=fixture_id):
                code, report, stderr = run_json([
                    "installs",
                    "scan",
                    "--path",
                    str(FIXTURE_ROOT / fixture_id),
                    "--json",
                ])
                self.assertEqual(code, 0, stderr)
                expected = json.loads(golden_path.read_text(encoding="utf-8"))
                self.assertEqual(report_summary(report), expected)

    def test_fixture_root_scan_is_read_only_and_classifies_all_candidates(self) -> None:
        before = tree_snapshot(FIXTURE_ROOT)
        code, report, stderr = run_json([
            "installs",
            "scan",
            "--search-root",
            str(FIXTURE_ROOT),
            "--json",
        ])
        after = tree_snapshot(FIXTURE_ROOT)

        self.assertEqual(code, 0, stderr)
        self.assertEqual(before, after)
        self.assertEqual(report["candidate_count"], 10)
        self.assertEqual(report["structural_count"], 8)
        self.assertEqual(report["invalid_count"], 2)
        by_candidate = {install["candidate_id"]: install for install in report["installs"]}
        self.assertEqual(by_candidate["windows_steam"]["ownership"], "foreign_owned")
        self.assertEqual(by_candidate["linux_package_foreign"]["source"], "os_package")
        self.assertEqual(by_candidate["linux_headless"]["capabilities"], ["headless_server"])
        self.assertEqual(by_candidate["invalid"]["refusal"]["code"], "invalid_factorio_install")
        self.assertTrue(all(not install["setup_mutation_allowed"] for install in report["installs"]))

    def test_import_preserves_source_tree_and_operator_install_id(self) -> None:
        fixture = FIXTURE_ROOT / "windows_portable"
        before = tree_snapshot(fixture)
        with tempfile.TemporaryDirectory() as tmp:
            code, imported, stderr = run_json([
                "--workspace",
                tmp,
                "installs",
                "import",
                str(fixture),
                "--id",
                "portable-fixture",
                "--json",
            ])
            after = tree_snapshot(fixture)
            self.assertEqual(code, 0, stderr)
            self.assertEqual(imported["install_id"], "portable-fixture")
            self.assertEqual(imported["candidate_id"], "windows_portable")
            self.assertEqual(imported["ownership"], "portable")
            self.assertFalse(imported["setup_mutation_allowed"])

            code, inspected, stderr = run_json([
                "--workspace",
                tmp,
                "installs",
                "inspect",
                "portable-fixture",
                "--json",
            ])

        self.assertEqual(before, after)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(inspected["install_id"], "portable-fixture")
        self.assertNotEqual(inspected["ownership"], "managed")

    def test_invalid_fixture_import_does_not_create_install_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _stdout, _stderr = invoke([
                "--workspace",
                tmp,
                "installs",
                "import",
                str(FIXTURE_ROOT / "invalid"),
                "--id",
                "invalid-fixture",
                "--json",
            ])
            refs = list((Path(tmp) / "installs" / "refs").glob("*.json"))

        self.assertEqual(code, 1)
        self.assertFalse(refs)

    def test_foreign_owned_fixtures_refuse_repair_and_uninstall(self) -> None:
        fixture = FIXTURE_ROOT / "windows_steam"
        before = tree_snapshot(fixture)
        with tempfile.TemporaryDirectory() as tmp:
            code, imported, stderr = run_json([
                "--workspace",
                tmp,
                "installs",
                "import",
                str(fixture),
                "--id",
                "steam-fixture",
                "--json",
            ])
            self.assertEqual(code, 0, stderr)
            self.assertEqual(imported["ownership"], "foreign_owned")

            code, repair, _stderr = run_json([
                "--workspace",
                tmp,
                "installs",
                "repair",
                "steam-fixture",
                "--json",
            ])
            self.assertEqual(code, 1)
            self.assertEqual(repair["refusal"]["code"], "ownership_denied")
            self.assertFalse(repair["mutates_install"])

            code, uninstall, _stderr = run_json([
                "--workspace",
                tmp,
                "installs",
                "uninstall",
                "steam-fixture",
                "--json",
            ])
            self.assertEqual(code, 1)
            self.assertEqual(uninstall["refusal"]["code"], "ownership_denied")
            self.assertFalse(uninstall["mutates_install"])

        after = tree_snapshot(fixture)
        self.assertEqual(before, after)

    def test_doctor_reports_invalid_explicit_candidates_without_mutation(self) -> None:
        before = tree_snapshot(FIXTURE_ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            code, report, stderr = run_json([
                "--workspace",
                tmp,
                "doctor",
                "--search-root",
                str(FIXTURE_ROOT),
                "--json",
            ])
        after = tree_snapshot(FIXTURE_ROOT)

        self.assertEqual(code, 0, stderr)
        self.assertEqual(before, after)
        self.assertEqual(report["schema"], "factorio.diagnostic_report.v1")
        self.assertEqual(report["command"], "doctor.run")
        self.assertEqual(report["discovery"]["invalid_count"], 2)
        checks = {check["id"]: check["status"] for check in report["checks"]}
        self.assertEqual(checks["discovery_candidates"], "warning")
        self.assertIn("invalid Factorio install candidates found", report["warnings"])


if __name__ == "__main__":
    unittest.main()
