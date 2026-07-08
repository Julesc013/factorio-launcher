from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from tools import cross_repo_check

HAS_SIBLINGS = cross_repo_check.UNIVERSAL_SETUP.is_dir() and cross_repo_check.UNIVERSAL_LAUNCHER.is_dir()


class CrossRepoTests(unittest.TestCase):
    def test_repo_locator_prefers_portable_overrides(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "FLAUNCH_UNIVERSAL_SETUP_ROOT": "X:/deps/setup",
                "FLAUNCH_UNIVERSAL_ROOT": "Y:/universal",
                "FLAUNCH_WORKSPACE_ROOT": "Z:/workspace",
            },
        ):
            candidates = cross_repo_check.candidate_roots("universal-setup")

        self.assertEqual(
            candidates[:4],
            [
                Path("X:/deps/setup"),
                Path("Y:/universal") / "universal-setup",
                Path("Z:/workspace") / "Universal" / "universal-setup",
                Path("Z:/workspace") / "universal-setup",
            ],
        )
        self.assertIn(cross_repo_check.ROOT / "external" / "universal-setup", candidates)

    def test_product_only_boundaries(self) -> None:
        self.assertEqual(cross_repo_check.main(["--product-only"]), 0)

    @unittest.skipUnless(HAS_SIBLINGS, "sibling repositories are not checked out")
    def test_sibling_boundaries(self) -> None:
        self.assertEqual(cross_repo_check.main([]), 0)


if __name__ == "__main__":
    unittest.main()
