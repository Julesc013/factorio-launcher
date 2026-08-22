# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import repository_identity


class RepositoryIdentityTests(unittest.TestCase):
    def test_manifest_preserves_roles_ids_aliases_and_canonical_remote(self) -> None:
        identities = repository_identity.load()
        facman = identities["facman"]
        self.assertEqual(facman.github_repository_id, 1293124404)
        self.assertEqual(facman.canonical_slug, "Julesc013/factorio-launcher")
        self.assertEqual(
            facman.canonical_https_remote,
            "https://github.com/Julesc013/factorio-launcher.git",
        )
        self.assertEqual(facman.product_name, "FacMan")
        self.assertEqual(facman.preferred_future_slug, "Julesc013/facman")
        self.assertEqual(
            facman.preferred_future_https_remote,
            "https://github.com/Julesc013/facman.git",
        )
        self.assertEqual(
            facman.rename_status,
            "deferred_pending_beta_brand_validation",
        )
        self.assertEqual(facman.classifies_slug("Julesc013/factorio-launcher"), "canonical")
        self.assertEqual(
            facman.classifies_remote("https://github.com/Julesc013/factorio-launcher.git"),
            "canonical",
        )
        self.assertEqual(
            facman.classifies_remote("https://github.com/Julesc013/factorio-launcher"),
            "canonical",
        )
        self.assertEqual(
            facman.classifies_remote("git@github.com:Julesc013/facman.git"),
            "deferred_future",
        )
        self.assertIsNone(
            facman.classifies_remote("https://example.invalid/Julesc013/facman.git")
        )
        self.assertEqual(facman.workspace_names, ("factorio-launcher", "facman"))
        self.assertEqual(identities["universal_launcher"].github_repository_id, 1293260879)
        self.assertEqual(identities["universal_setup"].github_repository_id, 1282727988)

    def test_canonical_and_future_slugs_cannot_be_conflated(self) -> None:
        source = repository_identity.MANIFEST.read_text(encoding="utf-8").replace(
            'preferred_future_slug = "Julesc013/facman"',
            'preferred_future_slug = "Julesc013/factorio-launcher"',
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "identity.toml"
            path.write_text(source, encoding="utf-8")
            problems = repository_identity.validate(path)
        self.assertTrue(any("distinct" in problem for problem in problems), problems)


if __name__ == "__main__":
    unittest.main()
