# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import unittest

from tools import remote_source_closure, remote_source_closure_v2


class RemoteSourceClosureV2Tests(unittest.TestCase):
    def test_v1_engine_and_schema_remain_immutable(self) -> None:
        self.assertEqual(
            remote_source_closure.FACTORIO_REMOTE,
            "https://github.com/Julesc013/factorio-launcher.git",
        )
        schema = json.loads(
            (
                remote_source_closure.ROOT
                / "contracts/schema/release/remote_source_closure.v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(schema["$id"], "facman.remote_source_closure.v1")

    def test_v2_selects_canonical_remote_and_rejects_redirect_as_final(self) -> None:
        self.assertEqual(
            remote_source_closure_v2.FACTORIO_REMOTE,
            "https://github.com/Julesc013/facman.git",
        )
        legacy = "https://github.com/Julesc013/factorio-launcher.git"
        self.assertEqual(
            remote_source_closure_v2.classify_factorio_remote(legacy),
            "legacy_redirect",
        )
        with self.assertRaisesRegex(
            remote_source_closure_v2.ClosureFailure,
            "canonical repository",
        ):
            remote_source_closure_v2.checked_spec(
                remote_source_closure_v2.SourceSpec(
                    "factorio-launcher", legacy, "refs/heads/dev", "a" * 40
                )
            )

    def test_v2_binds_stable_role_and_numeric_repository_id(self) -> None:
        identity = remote_source_closure_v2.FACMAN_IDENTITY
        self.assertEqual(identity.role, "facman")
        self.assertEqual(identity.github_repository_id, 1293124404)
        self.assertEqual(identity.canonical_slug, "Julesc013/facman")


if __name__ == "__main__":
    unittest.main()
