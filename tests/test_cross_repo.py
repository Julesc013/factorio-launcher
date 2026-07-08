from __future__ import annotations

import unittest
from pathlib import Path

from tools import cross_repo_check

ROOT = Path(__file__).resolve().parents[1]
HAS_SIBLINGS = (ROOT.parent / "universal-setup").is_dir() and (ROOT.parent / "universal-launcher").is_dir()


class CrossRepoTests(unittest.TestCase):
    def test_product_only_boundaries(self) -> None:
        self.assertEqual(cross_repo_check.main(["--product-only"]), 0)

    @unittest.skipUnless(HAS_SIBLINGS, "sibling repositories are not checked out")
    def test_sibling_boundaries(self) -> None:
        self.assertEqual(cross_repo_check.main([]), 0)


if __name__ == "__main__":
    unittest.main()
