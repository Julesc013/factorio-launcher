from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.native_cli import invoke

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"


def tree_snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def vdf_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\")


def scan_with_providers(workspace: Path, **environment: str) -> dict:
    values = {
        "FACMAN_DISCOVERY_ROOTS": "",
        "FACMAN_DISCOVERY_DISABLE_DEFAULTS": "1",
        "FACMAN_STEAM_ROOTS": "",
        "FACMAN_STANDALONE_ROOTS": "",
        **environment,
    }
    with mock.patch.dict(os.environ, values):
        code, stdout, stderr = invoke(["--workspace", str(workspace), "installs", "scan", "--json"])
    if code != 0:
        raise AssertionError(stderr or stdout)
    return json.loads(stdout)


@unittest.skipUnless(os.name == "nt", "real Windows discovery providers")
class WindowsDiscoveryProviderTests(unittest.TestCase):
    def test_steam_vdf_discovery_is_stable_deduplicated_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman Steam Ω ") as tmp:
            root = Path(tmp)
            steam = root / "Steam"
            first_library = root / "Library Ω"
            second_library = root / "Missing executable library"
            valid = first_library / "steamapps" / "common" / "Factorio"
            invalid = second_library / "steamapps" / "common" / "Factorio"
            shutil.copytree(FIXTURE_INSTALL, valid)
            (invalid / "data" / "base").mkdir(parents=True)
            (invalid / "data" / "base" / "info.json").write_text(
                '{"name":"base","version":"2.0.77"}\n',
                encoding="utf-8",
            )
            (steam / "steamapps").mkdir(parents=True)
            (steam / "steamapps" / "libraryfolders.vdf").write_text(
                '"libraryfolders"\n{\n'
                f'  "0" {{ "path" "{vdf_path(first_library)}" }}\n'
                f'  "1" {{ "path" "{vdf_path(first_library)}" }}\n'
                f'  "2" "{vdf_path(second_library)}"\n'
                '}\n',
                encoding="utf-8",
            )
            before = tree_snapshot(root)
            workspace = root / "workspace"
            first = scan_with_providers(workspace, FACMAN_STEAM_ROOTS=str(steam))
            second = scan_with_providers(workspace, FACMAN_STEAM_ROOTS=str(steam))
            after = tree_snapshot(root)

            self.assertEqual(first, second)
            self.assertEqual(before, after)
            self.assertFalse(workspace.exists())
            self.assertEqual(first["candidate_count"], 2)
            self.assertEqual(first["structural_count"], 1)
            self.assertEqual(first["invalid_count"], 1)
            self.assertEqual([item["root"] for item in first["installs"]], sorted(item["root"] for item in first["installs"]))
            self.assertTrue(all(item["source"] == "steam" for item in first["installs"]))
            self.assertTrue(all(item["ownership"] == "foreign_owned" for item in first["installs"]))
            self.assertEqual(len({item["install_id"] for item in first["installs"]}), 2)
            self.assertTrue(all(item["safe_actions"] == {"repair": False, "uninstall": False} for item in first["installs"]))

    def test_malformed_vdf_falls_back_to_primary_steam_library(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            steam = root / "Steam"
            valid = steam / "steamapps" / "common" / "Factorio"
            shutil.copytree(FIXTURE_INSTALL, valid)
            (steam / "steamapps" / "libraryfolders.vdf").write_text(
                '"libraryfolders" { "1" { "path" "unterminated }',
                encoding="utf-8",
            )
            report = scan_with_providers(root / "workspace", FACMAN_STEAM_ROOTS=str(steam))
            self.assertEqual(report["candidate_count"], 1)
            self.assertEqual(report["installs"][0]["source"], "steam")
            self.assertEqual(report["installs"][0]["verification"]["status"], "structural")

    def test_standalone_provider_classifies_foreign_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            standalone = root / "Factorio Standalone Ω"
            shutil.copytree(FIXTURE_INSTALL, standalone)
            report = scan_with_providers(root / "workspace", FACMAN_STANDALONE_ROOTS=str(standalone))
            self.assertEqual(report["candidate_count"], 1)
            install = report["installs"][0]
            self.assertEqual(install["source"], "standalone")
            self.assertEqual(install["ownership"], "foreign_owned")
            self.assertFalse(install["setup_mutation_allowed"])

    def test_steam_provider_preserves_long_unicode_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman long path ") as tmp:
            root = Path(tmp)
            steam = root / "Steam"
            library = root / ("Library-Ω-" + "a" * 110) / ("nested-" + "b" * 110)
            install = library / "steamapps" / "common" / "Factorio"
            shutil.copytree(FIXTURE_INSTALL, install)
            (steam / "steamapps").mkdir(parents=True)
            (steam / "steamapps" / "libraryfolders.vdf").write_text(
                f'"libraryfolders" {{ "1" {{ "path" "{vdf_path(library)}" }} }}\n',
                encoding="utf-8",
            )

            report = scan_with_providers(root / "workspace", FACMAN_STEAM_ROOTS=str(steam))

            self.assertGreater(len(str(install)), 260)
            self.assertEqual(report["candidate_count"], 1)
            self.assertEqual(report["installs"][0]["root"], str(install))
            self.assertEqual(report["installs"][0]["verification"]["status"], "structural")

    def test_steam_provider_does_not_cross_a_junction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            steam = root / "Steam"
            external = root / "external-library"
            shutil.copytree(FIXTURE_INSTALL, external / "steamapps" / "common" / "Factorio")
            linked = root / "linked-library"
            completed = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(linked), str(external)],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
            (steam / "steamapps").mkdir(parents=True)
            (steam / "steamapps" / "libraryfolders.vdf").write_text(
                f'"libraryfolders" {{ "1" {{ "path" "{vdf_path(linked)}" }} }}\n',
                encoding="utf-8",
            )
            report = scan_with_providers(root / "workspace", FACMAN_STEAM_ROOTS=str(steam))
            self.assertEqual(report["candidate_count"], 0)


if __name__ == "__main__":
    unittest.main()
