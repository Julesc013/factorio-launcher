from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class UninstallPreservesWorkspaceTests(unittest.TestCase):
    def test_all_install_modes_preserve_workspace(self) -> None:
        modes = load_toml(ROOT / "release/index/install_modes.v1.toml")
        for mode in ["portable", "user", "system"]:
            self.assertTrue(modes[mode]["uninstall_preserves_workspace"], mode)

    def test_product_policy_preserves_workspace_by_default(self) -> None:
        product = load_toml(ROOT / "release/index/product_manifest.v1.toml")
        workspace_policy = product["workspace_policy"]
        self.assertFalse(workspace_policy["install_directory_is_workspace"])
        self.assertTrue(workspace_policy["uninstall_preserves_workspace_by_default"])


def load_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


if __name__ == "__main__":
    unittest.main()
