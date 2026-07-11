# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

from tools.validators.release import check_no_workspace_in_system_package

ROOT = Path(__file__).resolve().parents[2]


class SystemInstallLayoutTests(unittest.TestCase):
    def test_system_install_requires_elevation_and_user_workspaces(self) -> None:
        modes = load_toml(ROOT / "release/index/install_modes.v1.toml")
        system = modes["system"]
        self.assertTrue(system["admin_required"])
        self.assertTrue(system["updates_require_elevation"])
        self.assertFalse(system["workspace_under_install_dir_allowed"])
        self.assertTrue(system["setup_owned_files_only"])

    def test_system_packages_do_not_contain_workspace_roots(self) -> None:
        self.assertEqual(check_no_workspace_in_system_package.main(), 0)


def load_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


if __name__ == "__main__":
    unittest.main()
