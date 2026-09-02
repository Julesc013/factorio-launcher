# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from tools import alpha5_final_candidate_closeout_check as closeout


class Alpha5FinalCandidateCloseoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.receipt = closeout.load_toml(closeout.RECEIPT)
        cls.values = {
            "release_index": closeout.load_toml(closeout.RELEASE_INDEX),
            "current_state": closeout.load_toml(closeout.CURRENT_STATE),
            "project": closeout.load_toml(closeout.PROJECT),
            "plan": closeout.load_toml(closeout.PLAN),
            "version_train": closeout.load_toml(closeout.VERSION_TRAIN),
            "readiness": closeout.load_toml(closeout.READINESS),
            "support_matrix": closeout.load_toml(closeout.SUPPORT_MATRIX),
            "package_producers": closeout.load_toml(closeout.PACKAGE_PRODUCERS),
            "profile_lifecycle": closeout.load_toml(closeout.PROFILE_LIFECYCLE),
            "final_distribution": closeout.load_toml(closeout.FINAL_DISTRIBUTION),
        }

    def test_canonical_receipt_and_repository_bindings_are_valid(self) -> None:
        self.assertEqual(closeout.check(), [])

    def test_final_hosted_run_and_authority_axes_cannot_drift(self) -> None:
        changed = copy.deepcopy(self.receipt)
        changed["candidate"]["workflow_run"] = closeout.OLD_RUN
        changed["axes"]["published"] = True
        problems = closeout.validate_receipt(changed)
        self.assertTrue(any("workflow_run" in problem for problem in problems), problems)
        self.assertTrue(any("published" in problem for problem in problems), problems)

    def test_newer_completed_candidate_cannot_leave_current_truth_stale(self) -> None:
        changed = copy.deepcopy(self.values)
        changed["current_state"]["alpha5_exact_candidate"]["run"] = closeout.OLD_RUN
        changed["readiness"]["exact_candidate"]["source_revision"] = closeout.OLD_MAIN
        problems = closeout.current_binding_problems(changed)
        self.assertTrue(any("compact current candidate run" in problem for problem in problems), problems)
        self.assertTrue(any("source_revision" in problem for problem in problems), problems)

    def test_integrated_workunit_cannot_remain_active(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            active = Path(temporary)
            (active / closeout.OLD_CLOSEOUT).mkdir()
            problems = closeout.lifecycle_problems(
                self.values["plan"],
                self.values["package_producers"],
                self.values["profile_lifecycle"],
                active,
            )
        self.assertTrue(any("remains active" in problem for problem in problems), problems)

    def test_expired_producer_exception_cannot_be_release_active(self) -> None:
        lifecycle = copy.deepcopy(self.values["profile_lifecycle"])
        plan = copy.deepcopy(self.values["plan"])
        plan["workunit"].append(
            {"id": "FACMAN-PACKAGE-PRODUCER-CONVERGENCE-01", "status": "complete"}
        )
        assignments = {
            row["profile_id"]: row for row in lifecycle["assignment"]
        }
        assignments["windows_portable_cli_x64"]["lifecycle"] = "active"
        problems = closeout.lifecycle_problems(
            plan,
            self.values["package_producers"],
            lifecycle,
            Path(tempfile.gettempdir()) / "facman-no-active-queue",
        )
        self.assertTrue(
            any("expired producer exception remains release-active" in problem for problem in problems),
            problems,
        )

    def test_historical_distribution_cannot_present_as_current(self) -> None:
        changed = copy.deepcopy(self.values["final_distribution"])
        changed["current_candidate"] = True
        problems = closeout.historical_role_problems(changed)
        self.assertTrue(any("presents itself as current" in problem for problem in problems), problems)

    def test_bundle_validation_is_closed_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            problems = closeout.validate_bundle_root(self.receipt, Path(temporary))
        self.assertIn("candidate custody root is not the exact closed inventory", problems)


if __name__ == "__main__":
    unittest.main()
