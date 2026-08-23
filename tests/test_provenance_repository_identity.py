# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import provenance_build


class ProvenanceRepositoryIdentityTests(unittest.TestCase):
    def test_current_sbom_follows_canonical_slug_and_preserves_versioned_contract(self) -> None:
        old_schema = (
            provenance_build.ROOT
            / "contracts/schema/release/spdx_document.v2.3.schema.json"
        ).read_text(encoding="utf-8")
        current_schema = provenance_build.SPDX_SCHEMA.read_text(encoding="utf-8")
        self.assertIn("Julesc013/factorio-launcher/spdx/", old_schema)
        self.assertNotIn("Julesc013/facman/spdx/", old_schema)
        self.assertIn("Julesc013/factorio-launcher/spdx/", current_schema)
        self.assertNotIn("Julesc013/facman/spdx/", current_schema)


if __name__ == "__main__":
    unittest.main()
