# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools import branding_asset_check

ROOT = Path(__file__).resolve().parents[1]


class BrandingAssetTests(unittest.TestCase):
    def test_exact_assets_and_platform_wiring(self) -> None:
        self.assertEqual(branding_asset_check.main(), 0)

    def test_manifest_keeps_human_and_public_authority_closed(self) -> None:
        manifest = json.loads(branding_asset_check.MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "provisional_human_review_required")
        self.assertFalse(manifest["source"]["official_brand_asset"])
        self.assertIn("public_brand_and_trademark_judgment", manifest["human_review_required"])
        self.assertIn("production_signing", manifest["authority_exclusions"])
        self.assertIn("public_release_or_support_activation", manifest["authority_exclusions"])

    def test_png_parser_rejects_trailing_bytes_and_crc_drift(self) -> None:
        source = (ROOT / "content/factorio/ui/branding/master/facman-provisional.png").read_bytes()
        self.assertEqual(branding_asset_check.png_dimensions(source), (1254, 1254))
        with self.assertRaises(ValueError):
            branding_asset_check.png_dimensions(source + b"trailing")
        corrupted = bytearray(source)
        corrupted[-8] ^= 1
        with self.assertRaises(ValueError):
            branding_asset_check.png_dimensions(bytes(corrupted))

    def test_multiplatform_container_size_sets_are_exact(self) -> None:
        ico = (ROOT / "apps/gui/windows/winforms/branding/FacMan.ico").read_bytes()
        icns = (ROOT / "apps/gui/macos/appkit/branding/FacMan.icns").read_bytes()
        self.assertEqual(branding_asset_check.ico_sizes(ico), branding_asset_check.ICO_SIZES)
        self.assertEqual(
            branding_asset_check.icns_sizes(icns),
            tuple(branding_asset_check.ICNS_TYPES.values()),
        )


if __name__ == "__main__":
    unittest.main()
