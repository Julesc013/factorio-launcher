# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

from tools.validators.release import check_frontend_bundle_contents

ROOT = Path(__file__).resolve().parents[2]


class PackageFrontendContentsTests(unittest.TestCase):
    def test_frontend_bundle_validator(self) -> None:
        self.assertEqual(check_frontend_bundle_contents.main(), 0)

    def test_gui_lane_contains_only_functional_gui_and_cli(self) -> None:
        profile = load_toml(ROOT / "release/profiles/windows_legacy_winforms_x64/profile.toml")
        entrypoints = profile["entrypoints"]
        self.assertEqual(set(entrypoints), {"gui", "cli"})
        self.assertEqual(len(set(entrypoints.values())), 2)

    def test_tui_lanes_share_the_facman_cli_artifact(self) -> None:
        for profile_id in (
            "windows_portable_tui_x64",
            "linux_portable_tui_x64",
            "macos_portable_tui_x64",
            "portable_tui_x64",
        ):
            with self.subTest(profile=profile_id):
                profile = load_toml(ROOT / f"release/profiles/{profile_id}/profile.toml")
                entrypoints = profile["entrypoints"]
                self.assertEqual(entrypoints["cli"], entrypoints["tui"])
                self.assertIn(Path(entrypoints["cli"]).name, {"facman", "facman.exe"})


def load_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


if __name__ == "__main__":
    unittest.main()
