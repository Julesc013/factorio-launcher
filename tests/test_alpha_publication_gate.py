# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import alpha_publication_gate


class AlphaPublicationGateTests(unittest.TestCase):
    def test_qualification_preflight_is_green_and_non_authorizing(self) -> None:
        self.assertEqual(alpha_publication_gate.validate_source(), [])

    def test_publication_is_refused_while_authority_is_closed(self) -> None:
        problems = alpha_publication_gate.validate_publish(
            source_revision="0" * 40,
            asset_root=alpha_publication_gate.ROOT / "does-not-exist",
            route_receipt_sha256="0" * 64,
            publication_authority_sha256="0" * 64,
        )
        self.assertTrue(
            any("GitHub prerelease publication is inactive" in item for item in problems),
            problems,
        )
        self.assertTrue(any("downloaded exact asset directory" in item for item in problems))


if __name__ == "__main__":
    unittest.main()
