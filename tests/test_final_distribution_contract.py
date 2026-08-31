# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_toml(relative: str) -> dict:
    with (ROOT / relative).open("rb") as handle:
        return tomllib.load(handle)


class FinalDistributionContractTests(unittest.TestCase):
    def test_contract_binds_exact_alpha_3_cross_platform_artifacts(self) -> None:
        record = load_toml("release/index/final_distribution.v1.toml")
        version = load_toml("release/index/version.v2.toml")
        self.assertEqual(record["version"], version["semver"])
        self.assertEqual(record["canonical_version"], version["canonical_version"])
        self.assertEqual(record["channel"], "alpha")
        self.assertEqual(
            record["classification"],
            "unsigned_private_draft_cross_platform_manual_test_candidate",
        )
        self.assertEqual(record["platform"], "windows_macos_linux")
        self.assertEqual(record["architecture"], "x64")
        artifacts = record["artifact"]
        self.assertEqual(
            [item["id"] for item in artifacts],
            [
                "windows_x64_portable",
                "windows_x64_setup",
                "macos_x64_portable",
                "macos_x64_setup",
                "linux_x64_portable",
                "linux_x64_setup",
                "checksums",
                "evidence",
            ],
        )
        self.assertEqual(
            [item["filename"] for item in artifacts],
            [
                "FacMan-0.1.0-alpha.3-windows-x64-portable.zip",
                "FacMan-0.1.0-alpha.3-windows-x64-setup.exe",
                "FacMan-0.1.0-alpha.3-macos-x64-portable.zip",
                "FacMan-0.1.0-alpha.3-macos-x64-setup.pkg",
                "FacMan-0.1.0-alpha.3-linux-x64-portable.tar.zst",
                "FacMan-0.1.0-alpha.3-linux-x64-setup.run",
                "FacMan-0.1.0-alpha.3-SHA256SUMS.txt",
                "FacMan-0.1.0-alpha.3-evidence.zip",
            ],
        )

    def test_contract_binds_qualified_families_and_redacted_evidence(self) -> None:
        record = load_toml("release/index/final_distribution.v1.toml")
        qualification = record["factorio_qualification"]
        self.assertEqual(qualification["families"], ["F100", "F110", "F200", "F210"])
        self.assertEqual(
            qualification["exact_versions"],
            ["1.0.0", "1.1.110", "2.0.77", "2.1.14"],
        )
        self.assertTrue(qualification["installation_trees_unchanged"])
        for key in ("corpus", "matrix"):
            path = ROOT / qualification[key]
            self.assertTrue(path.is_file())
            payload = json.loads(path.read_text(encoding="utf-8"))
            rendered = json.dumps(payload)
            self.assertNotIn("D:\\\\Games", rendered)

    def test_contract_keeps_every_external_authority_false(self) -> None:
        record = load_toml("release/index/final_distribution.v1.toml")
        self.assertEqual(
            record["support_claim"],
            "windows_manual_test_candidate_macos_linux_experimental_preview",
        )
        self.assertTrue(record["verification"]["clean_exact_source_required"])
        self.assertFalse(record["verification"]["source_dirty_allowed"])
        self.assertTrue(record["authority"])
        self.assertTrue(all(value is False for value in record["authority"].values()))

    def test_release_index_exposes_the_contract(self) -> None:
        index = load_toml("release/index/release_index.v1.toml")
        self.assertEqual(
            index["final_distribution"],
            "release/index/final_distribution.v1.toml",
        )


if __name__ == "__main__":
    unittest.main()
