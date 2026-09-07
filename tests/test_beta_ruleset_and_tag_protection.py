# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DECISION = ROOT / "release/index/beta_ruleset_and_tag_protection.v1.toml"
OBSERVATION = ROOT / (
    "release/receipts/"
    "facman-beta-ruleset-and-tag-protection-observation.v1.json"
)
CLEANUP = ROOT / "release/receipts/facman-phase0-workspace-cleanup.v1.json"


class BetaRulesetAndTagProtectionTests(unittest.TestCase):
    def setUp(self) -> None:
        with DECISION.open("rb") as handle:
            self.decision = tomllib.load(handle)
        self.observation = json.loads(OBSERVATION.read_text(encoding="utf-8"))
        self.cleanup = json.loads(CLEANUP.read_text(encoding="utf-8"))

    def test_report_is_exact_and_non_mutating(self) -> None:
        self.assertEqual(
            self.decision["status"], "report_complete_settings_unchanged"
        )
        self.assertEqual(self.decision["repository_id"], 1293124404)
        self.assertFalse(self.decision["github_settings_changed"])
        self.assertFalse(self.decision["recommendation_applied"])
        self.assertFalse(
            self.observation["derived"][
                "github_settings_changed_by_this_work_unit"
            ]
        )
        self.assertFalse(
            any(self.decision["authority"].values()),
            self.decision["authority"],
        )

    def test_observed_machine_enforcement_is_not_programme_authority(self) -> None:
        branch, alpha = self.observation["rulesets"]
        self.assertEqual(branch["id"], 20445007)
        self.assertEqual(branch["included_refs"], ["refs/heads/main", "refs/heads/dev"])
        self.assertEqual(branch["rules"]["required_approving_review_count"], 0)
        self.assertTrue(branch["rules"]["required_review_thread_resolution"])
        self.assertTrue(branch["rules"]["strict_required_status_checks_policy"])
        self.assertEqual(len(branch["rules"]["required_status_checks"]), 11)
        self.assertEqual(branch["bypass_actors"], [])
        self.assertEqual(alpha["id"], 21787868)
        self.assertEqual(alpha["included_refs"], ["refs/tags/v0.1.0-alpha.*"])
        self.assertTrue(alpha["rules"]["update_denied"])
        self.assertFalse(
            self.decision["policy_reconciliation"]["implementation_author_self_approval"]
        )
        self.assertFalse(self.decision["policy_reconciliation"]["self_merge"])

    def test_beta_proposal_is_complete_without_deadlocking_review_policy(self) -> None:
        branch = self.decision["recommended_branch_ruleset"]
        self.assertEqual(
            branch["included_refs"],
            ["refs/heads/main", "refs/heads/dev", "refs/heads/release/0.1"],
        )
        self.assertEqual(branch["allowed_merge_methods"], ["merge"])
        self.assertTrue(branch["require_resolved_conversations"])
        self.assertTrue(branch["strict_required_status_checks"])
        self.assertEqual(
            branch["review_count_policy"],
            "do_not_raise_without_an_eligible_independent_reviewer",
        )
        patterns = self.decision["recommended_tag_ruleset"]["immutable_patterns"]
        for pattern in (
            "refs/tags/v0.1.0-alpha.*",
            "refs/tags/v0.1.0-beta.*",
            "refs/tags/v0.1.0-rc.*",
            "refs/tags/v0.*",
            "refs/tags/v1.*",
        ):
            self.assertIn(pattern, patterns)

    def test_cleanup_receipt_balances_and_keeps_exact_history_reachable(self) -> None:
        roots = self.cleanup["removed_marker_owned_roots"]
        self.assertEqual(
            sum(item["bytes"] for item in roots),
            self.cleanup["totals"]["bytes_reclaimed"],
        )
        self.assertEqual(
            sum(item["files"] for item in roots),
            self.cleanup["totals"]["files_removed"],
        )
        self.assertEqual(self.cleanup["totals"]["task_roots_remaining"], 0)
        self.assertTrue(
            self.cleanup["preconditions"]["exact_task_heads_reachable_from_dev"]
        )
        self.assertTrue(
            all(item["local_deleted"] for item in self.cleanup["retired_branches"])
        )
        self.assertTrue(
            all(item["remote_deleted"] for item in self.cleanup["retired_branches"])
        )


if __name__ == "__main__":
    unittest.main()
