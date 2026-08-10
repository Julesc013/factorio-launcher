# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import tomllib
import unittest

from tools import branch_policy_check


class BranchPolicyTests(unittest.TestCase):
    def test_canonical_policy_is_valid(self) -> None:
        self.assertEqual(branch_policy_check.check(), [])

    def test_consumer_pins_to_dev_are_forbidden(self) -> None:
        with branch_policy_check.POLICY.open("rb") as handle:
            policy = tomllib.load(handle)
        invalid = copy.deepcopy(policy)
        invalid["invariants"]["consumer_pins_may_reference_dev"] = True
        self.assertIn(
            "branch policy invariants.consumer_pins_may_reference_dev must be False",
            branch_policy_check.check_data(invalid),
        )

    def test_automation_cannot_merge_its_own_change(self) -> None:
        with branch_policy_check.POLICY.open("rb") as handle:
            policy = tomllib.load(handle)
        invalid = copy.deepcopy(policy)
        invalid["automation_authority"]["self_merge"] = True
        self.assertIn(
            "branch policy automation_authority.self_merge must be False",
            branch_policy_check.check_data(invalid),
        )

    def test_delegated_development_is_ratified_but_inactive(self) -> None:
        with branch_policy_check.POLICY.open("rb") as handle:
            policy = tomllib.load(handle)
        delegated = policy["delegated_development"]
        self.assertEqual(
            delegated["required_logical_roles"],
            ["control", "implementation", "assurance"],
        )
        self.assertFalse(delegated["protected_dev_merge_active"])
        self.assertFalse(delegated["autonomous_alpha_tagging_active"])
        self.assertTrue(delegated["beta_rc_stable_human_authority"])
        self.assertFalse(delegated["d4_delegation_allowed"])
        self.assertEqual(
            policy["branches"]["currently_active_release_tags_from"],
            "main",
        )
        self.assertEqual(
            policy["branches"]["future_alpha_exception_requires"],
            "FACMAN-AUTONOMOUS-ALPHA-DELEGATION-01",
        )

    def test_delegation_cannot_waive_red_gates_or_activate_itself(self) -> None:
        with branch_policy_check.POLICY.open("rb") as handle:
            policy = tomllib.load(handle)
        invalid = copy.deepcopy(policy)
        invalid["delegated_development"]["red_gate_waiver"] = True
        invalid["delegated_development"]["protected_dev_merge_active"] = True
        problems = branch_policy_check.check_data(invalid)
        self.assertIn(
            "branch policy delegated_development.red_gate_waiver must be False",
            problems,
        )
        self.assertIn(
            "branch policy delegated_development.protected_dev_merge_active must be False",
            problems,
        )


if __name__ == "__main__":
    unittest.main()
