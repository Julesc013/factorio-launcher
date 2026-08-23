# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import alpha_release_source_check


class AlphaReleaseSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source, self.prospective = alpha_release_source_check.load()

    def validate(self, source: dict | None = None, prospective: dict | None = None) -> list[str]:
        return alpha_release_source_check.validate(
            source if source is not None else copy.deepcopy(self.source),
            prospective if prospective is not None else copy.deepcopy(self.prospective),
        )

    def test_allocated_release_source_is_exact_and_non_authorizing(self) -> None:
        self.assertEqual(self.validate(), [])
        self.assertEqual(self.source["version"], "0.1.0-alpha.1")
        self.assertEqual(self.source["channel"], "alpha")
        self.assertFalse(any(self.source["authority"].values()))
        self.assertFalse(self.prospective["human_receipt_required"])

    def test_verified_source_remains_valid_until_reviewed_closeout(self) -> None:
        task = alpha_release_source_check.WORK_UNIT.read_text(encoding="utf-8")
        self.assertIn("status: verified_pending_closeout", task)
        self.assertNotIn(
            "alpha.1 release-source WorkUnit is neither active nor verified pending closeout",
            self.validate(),
        )

    def test_precursor_filename_cannot_be_relabelled(self) -> None:
        changed = copy.deepcopy(self.source)
        changed["package"]["filename"] = (
            "facman-0.1.0-alpha.0-dev.contract-windows-winforms-x86_64-technical-preview.zip"
        )
        problems = self.validate(source=changed)
        self.assertTrue(any("schema rejection" in item for item in problems), problems)
        self.assertTrue(any("canonical package filename" in item for item in problems), problems)

    def test_human_receipt_cannot_be_promoted_to_an_alpha_gate(self) -> None:
        changed = copy.deepcopy(self.source)
        changed["qualification"]["human_receipt"] = "required_before_publication"
        problems = self.validate(source=changed)
        self.assertTrue(any("schema rejection" in item for item in problems), problems)

    def test_prospective_ledger_cannot_drop_route_or_publication_gates(self) -> None:
        changed = copy.deepcopy(self.prospective)
        changed["pending_gates"].remove("real_play_route")
        problems = self.validate(prospective=changed)
        self.assertTrue(any("uncompleted alpha gate" in item for item in problems), problems)

    def test_release_source_cannot_grant_publication(self) -> None:
        changed = copy.deepcopy(self.source)
        changed["authority"]["publication"] = True
        problems = self.validate(source=changed)
        self.assertTrue(any("grants authority" in item for item in problems), problems)


if __name__ == "__main__":
    unittest.main()
