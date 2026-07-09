from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class UserInstallLayoutTests(unittest.TestCase):
    def test_user_install_uses_user_state(self) -> None:
        modes = load_toml(ROOT / "release/index/install_modes.v1.toml")
        user = modes["user"]
        self.assertFalse(user["admin_required"])
        self.assertFalse(user["system_registration_required"])
        self.assertEqual(user["state_location"], "user_application_data")
        self.assertFalse(user["workspace_under_install_dir_allowed"])
        self.assertTrue(user["per_user_update_repair_uninstall"])


def load_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


if __name__ == "__main__":
    unittest.main()
