# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Alpha2ReleaseAssetContractTests(unittest.TestCase):
    def setUp(self) -> None:
        with (ROOT / "release/index/alpha2_release_source.v1.toml").open("rb") as source:
            self.record = tomllib.load(source)

    def test_inventory_is_exact_unique_and_versioned(self) -> None:
        assets = self.record["inventory"]["assets"]
        self.assertEqual(len(assets), self.record["asset_count"])
        self.assertEqual(len(assets), len(set(name.casefold() for name in assets)))
        self.assertTrue(all("0.1.0-alpha.2" in name for name in assets))
        self.assertEqual(assets[-1], "facman-0.1.0-alpha.2-checksums.txt")

    def test_five_downloadable_artifacts_are_in_inventory(self) -> None:
        artifacts = self.record["artifact"]
        self.assertEqual(len(artifacts), 5)
        inventory = set(self.record["inventory"]["assets"])
        self.assertTrue(all(item["filename"] in inventory for item in artifacts))
        self.assertEqual(
            [item["profile"] for item in artifacts[-2:]],
            ["windows_x64_per_user_self_setup"] * 2,
        )

    def test_external_authority_remains_closed(self) -> None:
        self.assertEqual(self.record["release_kind"], "private_draft_prerelease")
        self.assertTrue(all(value is False for value in self.record["authority"].values()))


if __name__ == "__main__":
    unittest.main()
