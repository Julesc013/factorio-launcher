# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import preview_semantic_spine_check


class PreviewSemanticSpineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = preview_semantic_spine_check.load_json(
            preview_semantic_spine_check.FIXTURE
        )

    def test_canonical_characterization_and_fixture_are_valid(self) -> None:
        self.assertEqual(preview_semantic_spine_check.validate(), [])

    def test_revision_gap_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.fixture)
        invalid["steps"][5]["presentation_revision"] = 99
        self.assertIn(
            "walking skeleton revisions must be monotonic and gap-free",
            preview_semantic_spine_check.validate_fixture(invalid),
        )

    def test_effectful_action_requires_idempotency_and_operation_identity(self) -> None:
        invalid = copy.deepcopy(self.fixture)
        invalid["steps"][6]["action"]["idempotency_key"] = None
        invalid["steps"][6]["action"]["durable_operation_id"] = None
        problems = preview_semantic_spine_check.validate_fixture(invalid)
        self.assertTrue(any("lacks idempotency/operation identity" in item for item in problems))

    def test_real_execution_command_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.fixture)
        invalid["steps"][6]["action"]["command_id"] = "run.execute"
        self.assertTrue(
            any(
                "forbidden production command" in item
                for item in preview_semantic_spine_check.validate_fixture(invalid)
            )
        )

    def test_production_dispatch_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.fixture)
        invalid["steps"][0]["action"]["production_command_dispatched"] = True
        self.assertTrue(
            any(
                "fixture dispatched a production command" in item
                for item in preview_semantic_spine_check.validate_fixture(invalid)
            )
        )


if __name__ == "__main__":
    unittest.main()
