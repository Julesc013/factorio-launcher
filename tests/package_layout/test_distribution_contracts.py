from __future__ import annotations

import unittest
from pathlib import Path

from tools import package_manifest_check

ROOT = Path(__file__).resolve().parents[2]


class DistributionContractTests(unittest.TestCase):
    def test_first_release_profiles_exist(self) -> None:
        expected = [
            "release/profiles/windows_legacy_winforms_x64/profile.toml",
            "release/profiles/macos_legacy_appkit_x64/profile.toml",
            "release/profiles/linux_x11_gtk_x64/profile.toml",
            "release/profiles/portable_cli_x64/profile.toml",
            "release/profiles/portable_tui_x64/profile.toml",
        ]
        for relative in expected:
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_distribution_contract_validator(self) -> None:
        self.assertEqual(package_manifest_check.main(), 0)


if __name__ == "__main__":
    unittest.main()
