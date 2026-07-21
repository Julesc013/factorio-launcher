# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import hermetic_play_policy_check


class HermeticPlayPolicyTests(unittest.TestCase):
    def test_repository_policy_is_valid_and_digest_bound(self) -> None:
        policy = hermetic_play_policy_check.load_policy()
        self.assertEqual(hermetic_play_policy_check.validate_policy(policy), [])
        self.assertEqual(
            policy["policy_digest"],
            hermetic_play_policy_check.canonical_policy_digest(policy),
        )

    def test_canonical_digest_ignores_object_insertion_order(self) -> None:
        policy = hermetic_play_policy_check.load_policy()
        reordered = dict(reversed(list(policy.items())))
        self.assertEqual(
            hermetic_play_policy_check.canonical_policy_digest(policy),
            hermetic_play_policy_check.canonical_policy_digest(reordered),
        )

    def test_candidate_mutation_invalidates_policy(self) -> None:
        policy = copy.deepcopy(hermetic_play_policy_check.load_policy())
        policy["candidate"]["factorio_version"] = "2.1.10"
        problems = hermetic_play_policy_check.validate_policy(policy)
        self.assertTrue(any("digest mismatch" in item for item in problems), problems)
        self.assertTrue(any("candidate selector" in item for item in problems), problems)

    def test_broad_workspace_prefix_is_refused(self) -> None:
        policy = copy.deepcopy(hermetic_play_policy_check.load_policy())
        policy["writable_roots"][0]["selector"] = "{workspace_root}"
        problems = hermetic_play_policy_check.validate_policy(policy)
        self.assertTrue(any("broad, wildcard, or parent" in item for item in problems), problems)

    def test_whole_host_overclaim_is_refused(self) -> None:
        policy = copy.deepcopy(hermetic_play_policy_check.load_policy())
        policy["claim"]["whole_host_immutability_claimed"] = True
        problems = hermetic_play_policy_check.validate_policy(policy)
        self.assertTrue(any("whole-host" in item for item in problems), problems)

    def test_observer_gap_cannot_be_waived(self) -> None:
        policy = copy.deepcopy(hermetic_play_policy_check.load_policy())
        policy["observation_scopes"][0]["gap_disposition"] = "Pass"
        problems = hermetic_play_policy_check.validate_policy(policy)
        self.assertTrue(any("observation gap" in item for item in problems), problems)

    def test_verdict_and_policy_cannot_grant_authority(self) -> None:
        policy = copy.deepcopy(hermetic_play_policy_check.load_policy())
        policy["verdict_criteria"][0]["grants_authority"] = True
        policy["authority_boundary"]["process_execution"] = True
        problems = hermetic_play_policy_check.validate_policy(policy)
        self.assertTrue(any("verdict record cannot grant authority" in item for item in problems), problems)
        self.assertTrue(any("promotes forbidden authority" in item for item in problems), problems)

    def test_missing_exact_resource_is_refused(self) -> None:
        policy = copy.deepcopy(hermetic_play_policy_check.load_policy())
        policy["writable_roots"].pop()
        problems = hermetic_play_policy_check.validate_policy(policy)
        self.assertTrue(any("writable resource set" in item for item in problems), problems)


if __name__ == "__main__":
    unittest.main()
