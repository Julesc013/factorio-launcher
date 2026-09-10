# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "release" / "index"
ARCHIVE = (
    ROOT / ".aide" / "history" / "facman-0-1-phase0-integrated-2026-09-03"
)


def load(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


class Phase0IntegrationCloseoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.closeout = load(INDEX / "phase0_integration_closeout.v1.toml")
        cls.identity = load(INDEX / "beta_repository_identity_decision.v1.toml")
        cls.manifest = load(INDEX / "repository_identity.v1.toml")

    def test_exact_two_pr_topology_and_merge_head_matrix_are_closed(self) -> None:
        self.assertEqual(
            self.closeout["canonical_dev"],
            "0d61feede2acd49bf54a4a7a1cd00bba3c867fb2",
        )
        self.assertEqual(
            self.closeout["canonical_dev_tree"],
            "5ff92f7ee668a900dfe26bbdcba2c061492358de",
        )
        self.assertEqual(
            [row["number"] for row in self.closeout["pull_request"]], [242, 243]
        )
        self.assertEqual(
            [row["merge_method"] for row in self.closeout["pull_request"]],
            ["merge_commit", "merge_commit"],
        )
        self.assertEqual(len(self.closeout["workflow"]), 5)
        self.assertEqual(
            {row["conclusion"] for row in self.closeout["workflow"]}, {"success"}
        )
        self.assertEqual(self.closeout["merge_head_success_count"], 12)
        self.assertEqual(self.closeout["merge_head_failure_count"], 0)

    def test_current_integration_does_not_inherit_candidate_qualification(self) -> None:
        boundary = self.closeout["qualification_boundary"]
        self.assertEqual(
            boundary["alpha5_candidate_revision"],
            "4683ecd9a1b9ead5eb84be152760d12583da0f0e",
        )
        self.assertEqual(
            boundary["alpha5_candidate_tree"],
            "c07938618bc0f533fd12756cba123f54b8592048",
        )
        self.assertNotEqual(
            boundary["alpha5_candidate_tree"], self.closeout["canonical_dev_tree"]
        )
        self.assertFalse(boundary["current_dev_inherits_candidate_qualification"])
        self.assertTrue(boundary["future_product_revision_requires_new_candidate_run"])

    def test_repository_identity_is_frozen_without_rename_authority(self) -> None:
        facman = next(
            row for row in self.manifest["repository"] if row["role"] == "facman"
        )
        for record in (facman, self.identity):
            self.assertEqual(record["canonical_slug"], "Julesc013/factorio-launcher")
            self.assertEqual(record["slug_status"], "frozen_for_0_1_release_train")
            self.assertEqual(
                record["freeze_through"],
                "0.1.0_publication_and_post_release_review",
            )
            self.assertFalse(record["rename_authorized"])
            self.assertEqual(record["future_slug_candidate"], "Julesc013/facman")
            self.assertFalse(record["future_slug_candidate_is_current_plan"])

    def test_integrated_workunits_are_archived_and_inactive(self) -> None:
        for task_id in self.closeout["integrated_work_units"]:
            self.assertTrue((ARCHIVE / task_id / "task.yaml").is_file())
            self.assertTrue((ARCHIVE / task_id / "status.yaml").is_file())
            self.assertFalse((ROOT / ".aide" / "queue" / "active" / task_id).exists())

    def test_every_external_authority_remains_closed(self) -> None:
        self.assertFalse(any(self.closeout["authority"].values()))
        self.assertFalse(any(self.identity["authority"].values()))


if __name__ == "__main__":
    unittest.main()
