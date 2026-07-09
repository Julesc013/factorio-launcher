from __future__ import annotations

import unittest
from pathlib import Path

from tools import package_check, package_layout_check, package_manifest_check, package_skeleton_check

ROOT = Path(__file__).resolve().parents[1]


class PackageManifestTests(unittest.TestCase):
    def test_package_check(self) -> None:
        self.assertEqual(package_check.main(), 0)

    def test_package_layout_check(self) -> None:
        self.assertEqual(package_layout_check.main(), 0)

    def test_package_manifest_check(self) -> None:
        self.assertEqual(package_manifest_check.main(), 0)

    def test_package_skeleton_check(self) -> None:
        self.assertEqual(package_skeleton_check.main([]), 0)

    def test_platform_manifests_exist(self) -> None:
        expected = [
            "release/packaging/windows/facman_portable.v1.toml",
            "release/packaging/windows/facman_installer.v1.toml",
            "release/packaging/windows/facman_single_exe.v1.toml",
            "release/packaging/macos/facman_app.v1.toml",
            "release/packaging/macos/legacy_x86_64.v1.toml",
            "release/packaging/macos/modern_universal.v1.toml",
            "release/packaging/linux/appimage.v1.toml",
            "release/packaging/linux/legacy_cli_tarball.v1.toml",
            "release/index/package_manifest.v1.toml",
            "release/index/release_index.v1.toml",
            "release/index/support_matrix.v1.toml",
        ]
        for relative in expected:
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_packaging_schema_namespace_exists(self) -> None:
        self.assertTrue(
            (ROOT / "contracts" / "schema" / "release" / "packaging" / "bundle_manifest.v1.schema.json").is_file()
        )
        self.assertTrue((ROOT / "contracts" / "schema" / "release" / "package_manifest.v1.schema.json").is_file())


if __name__ == "__main__":
    unittest.main()
