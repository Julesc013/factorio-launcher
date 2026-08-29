# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest
from unittest import mock

from tools import alpha_publication_gate


class AlphaPublicationGateTests(unittest.TestCase):
    def test_qualification_preflight_is_green_and_non_authorizing(self) -> None:
        self.assertEqual(alpha_publication_gate.validate_source(), [])

    def test_publication_is_refused_while_authority_is_closed(self) -> None:
        problems = alpha_publication_gate.validate_publish(
            control_source_revision="0" * 40,
            product_source_revision="0" * 40,
            asset_root=alpha_publication_gate.ROOT / "does-not-exist",
            human_alpha_receipt_sha256="0" * 64,
            route_receipt_sha256="0" * 64,
            publication_authority_sha256="0" * 64,
        )
        self.assertTrue(
            any("route capability is not integrated" in item for item in problems),
            problems,
        )
        self.assertTrue(any("route promotion is not integrated" in item for item in problems))
        self.assertTrue(any("downloaded exact asset directory" in item for item in problems))

    def test_product_and_control_revisions_are_independently_checked(self) -> None:
        source = alpha_publication_gate._toml(alpha_publication_gate.SOURCE_PATH)
        product = source["source"]["product_revision"]
        with mock.patch.object(
            alpha_publication_gate,
            "_git",
            side_effect=["1" * 40, ""],
        ):
            problems = alpha_publication_gate.validate_source("1" * 40, product)
        self.assertEqual(problems, [])

        problems = alpha_publication_gate.validate_source(
            product_source_revision="f" * 40
        )
        self.assertTrue(any("frozen alpha.1 product" in item for item in problems), problems)

    def test_invocation_authority_cannot_enable_signing_or_tag_creation(self) -> None:
        authority = {
            "schema": "facman.alpha_publication_authority.v1",
            "version": "0.1.0-alpha.1",
            "tag": "v0.1.0-alpha.1",
            "product_source_revision": "1" * 40,
            "product_source_tree": "2" * 40,
            "control_source_revision": "3" * 40,
            "control_source_tree": "4" * 40,
            "package_sha256": "5" * 64,
            "human_alpha_receipt_sha256": "6" * 64,
            "route_receipt_sha256": "7" * 64,
            "route_index_digest": "8" * 64,
            "decision": "authorize_exact_alpha_publication_once",
            "approved_by": "Jules",
            "approved_at": "2026-08-30T00:00:00Z",
            "release_policy": {
                "support": "unsupported",
                "signing": "unsigned",
                "prerelease": True,
                "publisher_authenticity_claimed": False,
            },
            "authority": {
                "tag_creation": False,
                "publication": True,
                "signing": False,
                "support_promotion": False,
                "route_promotion": False,
            },
        }
        self.assertEqual(
            alpha_publication_gate._schema_problems(
                authority,
                alpha_publication_gate.PUBLICATION_AUTHORITY_SCHEMA,
                "publication authority receipt",
            ),
            [],
        )
        changed = copy.deepcopy(authority)
        changed["authority"]["tag_creation"] = True
        changed["authority"]["signing"] = True
        problems = alpha_publication_gate._schema_problems(
            changed,
            alpha_publication_gate.PUBLICATION_AUTHORITY_SCHEMA,
            "publication authority receipt",
        )
        self.assertEqual(len(problems), 2)


if __name__ == "__main__":
    unittest.main()
