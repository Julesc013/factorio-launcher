# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import package_contract_tck, resource_pack


class PackageContractTckTests(unittest.TestCase):
    def test_canonical_product_profiles_use_one_resource_pack(self) -> None:
        for profile in package_contract_tck.PRODUCT_PROFILES:
            self.assertEqual([], package_contract_tck.profile_problems(profile))

    def test_windows_product_stage_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary)
            (stage / "FacMan.exe").write_bytes(b"gui")
            (stage / "bin").mkdir()
            (stage / "bin/facman.exe").write_bytes(b"terminal")
            resource_pack.build(resource_pack.ROOT, stage / "facman.resources")
            self.assertEqual(
                [], package_contract_tck.stage_problems(stage, "windows_product_x64")
            )
            (stage / "bin/facman-tui.exe").write_bytes(b"legacy")
            (stage / "contracts/schema").mkdir(parents=True)
            problems = package_contract_tck.stage_problems(stage, "windows_product_x64")
            self.assertTrue(any("forbidden public executable" in item for item in problems))
            self.assertTrue(any("non-product root" in item for item in problems))


if __name__ == "__main__":
    unittest.main()
