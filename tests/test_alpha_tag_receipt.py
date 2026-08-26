# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools import alpha_tag_receipt


class AlphaTagReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = {
            "schema": "facman.alpha_tag_plan.v1",
            "eligible": True,
            "tag": "v0.1.0-alpha.1",
            "version": "0.1.0-alpha.1",
            "source_revision": "1" * 40,
            "source_tree": "2" * 40,
            "candidate_sha256": "3" * 64,
            "tag_ruleset_ids": [9876],
            "annotation": "FacMan 0.1.0-alpha.1",
            "publication": False,
            "signing": False,
        }

    def make(self, plan: dict | None = None) -> dict:
        return alpha_tag_receipt.make_receipt(
            plan if plan is not None else self.plan,
            tag_object_sha="4" * 40,
            eligibility_sha256="5" * 64,
            github_run_id="12345",
            created_at="2026-08-27T00:00:00Z",
        )

    def test_receipt_is_closed_and_non_publication(self) -> None:
        receipt = self.make()
        self.assertEqual(receipt["schema"], "facman.alpha_tag_receipt.v1")
        self.assertFalse(receipt["publication"])
        self.assertFalse(receipt["signing"])
        self.assertEqual(receipt["tag_ruleset_ids"], [9876])

    def test_authorizing_plan_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.plan)
        invalid["publication"] = True
        with self.assertRaisesRegex(ValueError, "publication must be False"):
            self.make(invalid)

    def test_mismatched_version_and_tag_are_rejected(self) -> None:
        invalid = copy.deepcopy(self.plan)
        invalid["version"] = "0.1.0-alpha.2"
        with self.assertRaisesRegex(ValueError, "version does not match"):
            self.make(invalid)

    def test_cli_refuses_to_overwrite_a_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = root / "plan.json"
            output = root / "receipt.json"
            plan.write_text(json.dumps(self.plan), encoding="utf-8")
            output.write_text("preserve", encoding="utf-8")
            result = alpha_tag_receipt.main(
                [
                    "--plan", str(plan),
                    "--tag-object-sha", "4" * 40,
                    "--eligibility-sha256", "5" * 64,
                    "--github-run-id", "12345",
                    "--created-at", "2026-08-27T00:00:00Z",
                    "--output", str(output),
                ]
            )
            self.assertEqual(result, 1)
            self.assertEqual(output.read_text(encoding="utf-8"), "preserve")


if __name__ == "__main__":
    unittest.main()
