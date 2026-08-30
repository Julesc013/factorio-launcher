# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

from copy import deepcopy
import unittest

from tools import alpha1_publication_preparation_closeout_check


class Alpha1PublicationPreparationCloseoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.closeout = alpha1_publication_preparation_closeout_check.load()

    def validate(self, value: dict | None = None) -> list[str]:
        return alpha1_publication_preparation_closeout_check.validate(
            value if value is not None else deepcopy(self.closeout)
        )

    def test_exact_closeout_binds_integration_and_keeps_later_gates_closed(self) -> None:
        self.assertEqual(self.validate(), [])
        self.assertEqual(self.closeout["gate_state"]["g1_tag"], "complete")
        self.assertEqual(self.closeout["gate_state"]["g2_human_alpha"], "pending")
        self.assertFalse(any(self.closeout["authority"].values()))

    def test_merge_identity_drift_is_rejected(self) -> None:
        changed = deepcopy(self.closeout)
        changed["integration"]["merge_revision"] = "0" * 40
        problems = self.validate(changed)
        self.assertTrue(any("merge_revision" in item for item in problems), problems)

    def test_failed_workflow_is_rejected(self) -> None:
        changed = deepcopy(self.closeout)
        changed["post_merge_workflow"][0]["conclusion"] = "failure"
        problems = self.validate(changed)
        self.assertTrue(any("conclusion" in item for item in problems), problems)

    def test_unassigned_human_cannot_be_relabelled_as_pass(self) -> None:
        changed = deepcopy(self.closeout)
        changed["next_gate"]["human_result"] = "Pass"
        problems = self.validate(changed)
        self.assertTrue(any("human_result" in item for item in problems), problems)

    def test_closeout_cannot_grant_publication_or_execution(self) -> None:
        changed = deepcopy(self.closeout)
        changed["authority"]["publication"] = True
        changed["authority"]["factorio_execution"] = True
        problems = self.validate(changed)
        self.assertTrue(any("authority" in item for item in problems), problems)


if __name__ == "__main__":
    unittest.main()
