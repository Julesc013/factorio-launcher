from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

from tools.validators.release import check_frontend_bundle_contents

ROOT = Path(__file__).resolve().parents[2]


class PackageFrontendContentsTests(unittest.TestCase):
    def test_frontend_bundle_validator(self) -> None:
        self.assertEqual(check_frontend_bundle_contents.main(), 0)

    def test_gui_lane_contains_cli_tui_daemon_and_gui(self) -> None:
        profile = load_toml(ROOT / "release/profiles/windows_legacy_winforms_x64/profile.toml")
        entrypoints = profile["entrypoints"]
        self.assertEqual(set(entrypoints), {"gui", "cli", "tui", "daemon"})
        self.assertEqual(len(set(entrypoints.values())), 4)


def load_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


if __name__ == "__main__":
    unittest.main()
