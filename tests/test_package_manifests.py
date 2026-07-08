from __future__ import annotations

import unittest
from pathlib import Path

from tools import package_check

ROOT = Path(__file__).resolve().parents[1]


class PackageManifestTests(unittest.TestCase):
    def test_package_check(self) -> None:
        self.assertEqual(package_check.main(), 0)

    def test_platform_manifests_exist(self) -> None:
        expected = [
            "packaging/windows/flaunch_portable.v1.toml",
            "packaging/windows/flaunch_installer.v1.toml",
            "packaging/windows/flaunch_single_exe.v1.toml",
            "packaging/macos/flaunch_app.v1.toml",
            "packaging/macos/legacy_x86_64.v1.toml",
            "packaging/macos/modern_universal.v1.toml",
            "packaging/linux/appimage.v1.toml",
            "packaging/linux/legacy_cli_tarball.v1.toml",
        ]
        for relative in expected:
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_packaging_schema_namespace_exists(self) -> None:
        self.assertTrue((ROOT / "schemas" / "packaging" / "bundle_manifest.v1.schema.json").is_file())


if __name__ == "__main__":
    unittest.main()
