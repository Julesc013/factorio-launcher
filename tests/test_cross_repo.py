# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
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

    @unittest.skipUnless(
        HAS_SIBLINGS,
        "required_blocked: sibling repositories are not checked out",
    )
    def test_sibling_boundaries(self) -> None:
        self.assertEqual(cross_repo_check.main([]), 0)

    @unittest.skipUnless(
        HAS_SIBLINGS,
        "required_blocked: sibling repositories are not checked out",
    )
    def test_operation_outcome_projection_matches_pinned_launcher_contract(self) -> None:
        provider = json.loads(
            (
                cross_repo_check.UNIVERSAL_LAUNCHER
                / "contracts"
                / "schema"
                / "command"
                / "operation_outcome.v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        projection = json.loads(
            (
                cross_repo_check.ROOT
                / "contracts"
                / "schema"
                / "transport"
                / "transport_response.v2.schema.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            projection["properties"]["operation"]["properties"]["outcome"]["enum"],
            provider["properties"]["outcome"]["enum"],
        )


if __name__ == "__main__":
    unittest.main()
