# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import release_identity_coherence_check


class ReleaseIdentityCoherenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = release_identity_coherence_check.load_records()

    def test_current_release_identity_is_coherent(self) -> None:
        self.assertEqual(
            release_identity_coherence_check.validate_records(copy.deepcopy(self.records)),
            set(),
        )
        self.assertEqual(release_identity_coherence_check.validate_source_bindings(), set())
        self.assertEqual(release_identity_coherence_check.detect_misnumbered_identity(), set())

    def test_rejects_version_package_and_authority_drift(self) -> None:
        changed = copy.deepcopy(self.records)
        changed["version"]["semver"] = "4.0.0"
        changed["distribution"]["artifact"][0]["filename"] = "facman-4.0.0.zip"
        changed["distribution"]["authority"]["publication"] = True
        changed["candidate_closeout"]["authority"]["publication"] = True
        changed["current"]["product"]["safe_beta"] = True
        problems = release_identity_coherence_check.validate_records(changed)
        self.assertTrue(any(problem.startswith("version.semver") for problem in problems))
        self.assertTrue(any(problem.startswith("distribution.packages") for problem in problems))
        self.assertTrue(any(problem.startswith("distribution.authority") for problem in problems))
        self.assertTrue(
            any(problem.startswith("candidate_closeout.authority") for problem in problems)
        )
        self.assertTrue(any(problem.startswith("current.product.safe_beta") for problem in problems))

    def test_alpha5_candidate_identity_is_revision_exact_and_non_circular(self) -> None:
        records = self.records
        train = records["train"]
        self.assertEqual(
            train["release_source_revision"],
            release_identity_coherence_check.MAIN_REVISION,
        )
        self.assertEqual(
            train["release_source_tree"],
            release_identity_coherence_check.SOURCE_TREE,
        )
        self.assertFalse(train["release_source_is_closeout_revision"])
        self.assertFalse(train["release_source_is_dev_sync_revision"])
        receipt = records["candidate_closeout"]
        self.assertEqual(
            receipt["candidate"]["head_sha"],
            release_identity_coherence_check.MAIN_REVISION,
        )
        self.assertEqual(
            receipt["revision_topology"]["dev_sync_revision"],
            release_identity_coherence_check.DEV_REVISION,
        )
        self.assertNotEqual(
            receipt["candidate"]["head_sha"],
            receipt["revision_topology"]["dev_sync_revision"],
        )
        self.assertFalse(
            receipt["non_circular"]["closeout_revision_candidate_qualified"]
        )
        self.assertFalse(
            receipt["non_circular"][
                "synchronized_tree_extends_revision_qualification"
            ]
        )
        self.assertTrue(
            receipt["non_circular"]["future_revision_requires_new_candidate_run"]
        )

    def test_tree_equality_cannot_requalify_the_synchronized_revision(self) -> None:
        changed = copy.deepcopy(self.records)
        changed["candidate_closeout"]["non_circular"][
            "synchronized_tree_extends_revision_qualification"
        ] = True
        changed["status"]["alpha5_beta_readiness"][
            "closeout_revision_candidate_qualified"
        ] = True
        problems = release_identity_coherence_check.validate_records(changed)
        self.assertTrue(
            any(
                problem.startswith(
                    "candidate_closeout.non_circular."
                    "synchronized_tree_extends_revision_qualification"
                )
                for problem in problems
            )
        )
        self.assertTrue(
            any(
                problem.startswith(
                    "status.alpha5_beta_readiness."
                    "closeout_revision_candidate_qualified"
                )
                for problem in problems
            )
        )

    def test_closeout_lifecycle_may_only_advance_to_verified_pending_closeout(self) -> None:
        advanced = copy.deepcopy(self.records)
        closeout = next(
            item
            for item in advanced["plan"]["workunit"]
            if item["id"] == release_identity_coherence_check.ACTIVE_WORK_UNIT
        )
        closeout["status"] = "verified_pending_closeout"
        self.assertEqual(
            release_identity_coherence_check.validate_records(advanced), set()
        )

        invalid = copy.deepcopy(self.records)
        closeout = next(
            item
            for item in invalid["plan"]["workunit"]
            if item["id"] == release_identity_coherence_check.ACTIVE_WORK_UNIT
        )
        closeout["status"] = "complete"
        problems = release_identity_coherence_check.validate_records(invalid)
        self.assertTrue(
            any(problem.startswith("plan.alpha5_closeout_workunit.status") for problem in problems)
        )

    def test_only_explicit_containment_lines_may_retain_old_identity(self) -> None:
        check = release_identity_coherence_check.misnumbered_line_is_allowed
        self.assertTrue(
            check(
                "release/index/plan.v1.toml",
                'depends_on = ["FACMAN-4.0.0-MISNUMBERING-CONTAINMENT-01"]',
            )
        )
        self.assertFalse(
            check("README.md", "Current package: facman-4.0.0-windows.zip")
        )
        self.assertTrue(
            check(
                "docs/release/history/facman-4.0.0-misnumbered-internal-candidate.md",
                "Historical FacMan 4.0.0 internal candidate",
            )
        )


if __name__ == "__main__":
    unittest.main()
