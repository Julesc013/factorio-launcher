# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import alpha1_tag_truth_closeout_check as closeout


class Alpha1TagTruthCloseoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.receipt = closeout.load(closeout.RECEIPT)

    def test_exact_sealed_tag_truth_passes(self) -> None:
        self.assertEqual(closeout.validate_receipt(copy.deepcopy(self.receipt)), [])

    def test_product_tag_or_package_drift_is_rejected(self) -> None:
        changed = copy.deepcopy(self.receipt)
        changed["frozen_product"]["source_revision"] = "0" * 40
        changed["tag"]["object_sha"] = "1" * 40
        changed["package"][0]["sha256"] = "2" * 64
        problems = closeout.validate_receipt(changed)
        self.assertTrue(any("source_revision" in item for item in problems))
        self.assertTrue(any("object_sha" in item for item in problems))
        self.assertTrue(any("package set" in item for item in problems))

    def test_incomplete_workflow_or_open_authority_is_rejected(self) -> None:
        changed = copy.deepcopy(self.receipt)
        changed["route_v5"]["workflow"][0]["conclusion"] = "failure"
        changed["authority"]["publication"] = True
        problems = closeout.validate_receipt(changed)
        self.assertTrue(any("not successful" in item for item in problems))
        self.assertTrue(any("authority" in item for item in problems))

    def test_human_and_publication_boundaries_cannot_be_overstated(self) -> None:
        changed = copy.deepcopy(self.receipt)
        changed["human"]["result"] = "Pass"
        changed["release_state"]["public_alpha"] = True
        problems = closeout.validate_receipt(changed)
        self.assertTrue(any("human.result" in item for item in problems))
        self.assertTrue(any("release state" in item for item in problems))

    def test_later_closeout_is_allowed_when_alpha3_truth_remains_exact(self) -> None:
        route = closeout.load(closeout.ROUTE)
        project = closeout.load(closeout.PROJECT)
        plan = closeout.load(closeout.PLAN)
        project["last_closed_work_unit"] = "FACMAN-LATER-CLOSEOUT-01"
        self.assertEqual(
            [],
            closeout.validate_repository_bindings(self.receipt, route, project, plan),
        )

    def test_alpha3_distribution_drift_is_rejected(self) -> None:
        route = closeout.load(closeout.ROUTE)
        project = closeout.load(closeout.PROJECT)
        plan = closeout.load(closeout.PLAN)
        project["alpha3_distribution"]["public_release"] = True
        problems = closeout.validate_repository_bindings(self.receipt, route, project, plan)
        self.assertTrue(any("alpha.3 distribution public_release" in item for item in problems))


if __name__ == "__main__":
    unittest.main()
