from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from tools import package_build, package_runtime_smoke

ROOT = Path(__file__).resolve().parents[2]
BUILD_ROOT = ROOT / "build" / "native-smoke"
SECRET_CORPUS = ROOT / "tests" / "fixtures" / "redaction" / "secrets_corpus.v1.json"


class BuiltPackageArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not BUILD_ROOT.exists():
            raise unittest.SkipTest("native smoke build has not been created")
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out_root = Path(cls._tmp.name) / "packages"
        cls.portable_cli = build_or_skip(cls, "portable_cli_x64")
        cls.portable_tui = build_or_skip(cls, "portable_tui_x64")

    @classmethod
    def tearDownClass(cls) -> None:
        tmp = getattr(cls, "_tmp", None)
        if tmp is not None:
            tmp.cleanup()

    def test_portable_cli_runtime_smoke_runs_from_package_root(self) -> None:
        report = package_runtime_smoke.smoke_package(self.portable_cli)
        self.assertEqual(report["schema"], "facman.package_runtime_smoke.v1")
        self.assertEqual(report["product_id"], "factorio")
        self.assertTrue(report["contracts_found"])
        self.assertTrue(report["content_found"])
        self.assertFalse(report["python_runtime"])

    def test_portable_cli_contains_required_package_layout(self) -> None:
        required = [
            "bin/facman",
            "contracts/schema",
            "content/factorio",
            "docs",
            "licenses/LICENSE",
            "licenses/THIRD_PARTY_NOTICES.md",
            "release",
            "manifest/package.v1.toml",
            "manifest/build_info.v1.json",
            "manifest/components.v1.json",
            "manifest/hashes.sha256",
        ]
        for relative in required:
            self.assertTrue((self.portable_cli / relative).exists(), relative)

    def test_portable_tui_contains_tui_entrypoint_and_smokes_cli(self) -> None:
        self.assertTrue((self.portable_tui / "bin" / "facman-tui").exists())
        report = package_runtime_smoke.smoke_package(self.portable_tui)
        self.assertEqual(report["product_id"], "factorio")

    def test_hash_manifest_covers_all_package_files_except_itself(self) -> None:
        hashed = hash_manifest_destinations(self.portable_cli)
        expected = {
            path.relative_to(self.portable_cli).as_posix()
            for path in self.portable_cli.rglob("*")
            if path.is_file()
            and path.relative_to(self.portable_cli).as_posix() != "manifest/hashes.sha256"
            and not path.name.endswith(".sig")
        }
        self.assertEqual(hashed, expected)
        self.assertIn("manifest/components.v1.json", hashed)

    def test_component_manifest_records_profile_components(self) -> None:
        data = json.loads((self.portable_cli / "manifest" / "components.v1.json").read_text(encoding="utf-8"))
        destinations = {component["destination"] for component in data["components"]}
        self.assertIn("bin/facman", destinations)
        self.assertIn("lib/ulk", destinations)
        self.assertIn("lib/usk", destinations)
        self.assertIn("lib/flb_factorio", destinations)
        self.assertTrue(any(destination.startswith("contracts/schema/") for destination in destinations))
        self.assertTrue(any(destination.startswith("content/factorio/") for destination in destinations))

    def test_package_excludes_python_runtime_files(self) -> None:
        for root in [self.portable_cli, self.portable_tui]:
            leaked = [
                path.relative_to(root).as_posix()
                for path in root.rglob("*")
                if path.name in {"python", "python3", "python.exe", "__pycache__"}
                or path.suffix in {".py", ".pyc", ".pyo"}
            ]
            self.assertEqual(leaked, [])

    def test_package_excludes_forbidden_factorio_payloads_and_secret_markers(self) -> None:
        forbidden_names = ["factorio.exe", "Factorio.app", "steamapps", "mod_portal_credentials"]
        for root in [self.portable_cli, self.portable_tui]:
            relative_paths = [path.relative_to(root).as_posix() for path in root.rglob("*")]
            for marker in forbidden_names:
                self.assertFalse(
                    any(marker.lower() in relative.lower() for relative in relative_paths),
                    marker,
                )
            package_text = read_text_payload(root)
            for secret in secret_values():
                self.assertNotIn(secret, package_text)

    def test_text_manifests_do_not_leak_source_tree_absolute_paths(self) -> None:
        forbidden = str(ROOT.resolve())
        for root in [self.portable_cli, self.portable_tui]:
            for path in text_payloads(root):
                self.assertNotIn(forbidden, path.read_text(encoding="utf-8"))


class BuiltPackageOutputOwnershipTests(unittest.TestCase):
    def test_builder_refuses_unowned_output_root_before_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "unowned"
            root.mkdir()
            valuable = root / "operator-data.txt"
            valuable.write_text("preserve\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unowned output root"):
                package_build.build_profile(
                    profile_id="portable_cli_x64",
                    out_root=root,
                    build_root=Path(tmp) / "missing-build",
                    dist_root=None,
                )
            self.assertEqual(valuable.read_text(encoding="utf-8"), "preserve\n")


@unittest.skipIf(os.name != "nt", "WinForms package layout proof is Windows-only")
class BuiltWindowsPackageArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not BUILD_ROOT.exists():
            raise unittest.SkipTest("native smoke build has not been created")
        if not (ROOT / "apps" / "gui" / "windows" / "winforms" / "bin" / "Debug" / "FacMan.WinForms.exe").is_file():
            raise unittest.SkipTest("WinForms shell has not been built")
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out_root = Path(cls._tmp.name) / "packages"
        cls.package_root = build_or_skip(cls, "windows_legacy_winforms_x64")

    @classmethod
    def tearDownClass(cls) -> None:
        tmp = getattr(cls, "_tmp", None)
        if tmp is not None:
            tmp.cleanup()

    def test_windows_package_contains_legacy_frontends_and_dlls(self) -> None:
        required = [
            "bin/FacMan.WinForms.exe",
            "bin/facman.exe",
            "bin/facman-tui.exe",
            "bin/facmand.exe",
            "bin/ulk.dll",
            "bin/usk.dll",
            "bin/flb_factorio.dll",
            "contracts/schema",
            "content/factorio",
        ]
        for relative in required:
            self.assertTrue((self.package_root / relative).exists(), relative)

    def test_windows_package_cli_smokes_from_package_root(self) -> None:
        report = package_runtime_smoke.smoke_package(self.package_root)
        self.assertEqual(report["product_id"], "factorio")


def build_or_skip(test_case: unittest.TestCase, profile_id: str) -> Path:
    try:
        return package_build.build_profile(
            profile_id=profile_id,
            out_root=test_case.out_root,
            build_root=BUILD_ROOT,
            dist_root=None,
        )
    except ValueError as exc:
        test_case.skipTest(str(exc))


def hash_manifest_destinations(root: Path) -> set[str]:
    destinations: set[str] = set()
    for line in (root / "manifest" / "hashes.sha256").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        _, destination = line.split("  ", 1)
        destinations.add(destination)
    return destinations


def text_payloads(root: Path) -> list[Path]:
    suffixes = {".json", ".md", ".toml", ".txt", ".sha256"}
    return [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in suffixes]


def read_text_payload(root: Path) -> str:
    return "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in text_payloads(root))


def secret_values() -> list[str]:
    if not SECRET_CORPUS.is_file():
        return []
    data = json.loads(SECRET_CORPUS.read_text(encoding="utf-8"))
    return [str(value) for value in data.get("values", [])]


if __name__ == "__main__":
    unittest.main()
