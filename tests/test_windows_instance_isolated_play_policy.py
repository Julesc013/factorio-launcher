# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import windows_instance_isolated_play_policy_check as policy_check


class WindowsInstanceIsolatedPlayPolicyTests(unittest.TestCase):
    def test_repository_policy_is_valid_and_digest_bound(self) -> None:
        policy = policy_check.load_policy()
        self.assertEqual(policy_check.validate_policy(policy), [])
        self.assertEqual(
            policy["policy_digest"],
            policy_check.canonical_policy_digest(policy),
        )

    def test_canonical_digest_ignores_object_insertion_order(self) -> None:
        policy = policy_check.load_policy()
        reordered = dict(reversed(list(policy.items())))
        self.assertEqual(
            policy_check.canonical_policy_digest(policy),
            policy_check.canonical_policy_digest(reordered),
        )

    def test_hermetic_or_whole_host_overclaim_is_refused(self) -> None:
        policy = copy.deepcopy(policy_check.load_policy())
        policy["claim"]["enforced_sandbox_claimed"] = True
        policy["claim"]["whole_host_immutability_claimed"] = True
        problems = policy_check.validate_policy(policy)
        self.assertTrue(any("instance-isolated claim" in item for item in problems), problems)

    def test_instance_string_prefix_authority_is_refused(self) -> None:
        policy = copy.deepcopy(policy_check.load_policy())
        resource = policy["writable_resources"][0]
        resource["logical_selector"] = "E:\\Temporary\\FacMan\\instance"
        resource["string_prefix_authority"] = True
        problems = policy_check.validate_policy(policy)
        self.assertTrue(any("string-prefix authority" in item for item in problems), problems)
        self.assertTrue(any("cannot be a path" in item for item in problems), problems)

    def test_reparse_and_ancestor_escape_cannot_be_enabled(self) -> None:
        policy = copy.deepcopy(policy_check.load_policy())
        policy["writable_resources"][0]["reparse_policy"] = "follow_links"
        problems = policy_check.validate_policy(policy)
        self.assertTrue(any("reparse" in item for item in problems), problems)

    def test_external_effects_are_not_permit_resources(self) -> None:
        policy = copy.deepcopy(policy_check.load_policy())
        disclosure = policy["external_effect_disclosures"][0]
        disclosure["permit_authorized"] = True
        disclosure["permit_effects"] = ["workspace_write"]
        problems = policy_check.validate_policy(policy)
        self.assertTrue(any("never permit resources" in item for item in problems), problems)

    def test_nvidia_or_directinput_cannot_be_whitelisted(self) -> None:
        for marker in ("NVIDIA", "DirectInput"):
            with self.subTest(marker=marker):
                policy = copy.deepcopy(policy_check.load_policy())
                policy["external_effect_disclosures"][0]["user_disclosure"] += marker
                problems = policy_check.validate_policy(policy)
                self.assertTrue(
                    any("cannot be frozen" in item for item in problems),
                    problems,
                )

    def test_bam_disclosure_is_exact(self) -> None:
        policy = copy.deepcopy(policy_check.load_policy())
        disclosure = policy["external_effect_disclosures"][0]
        disclosure["target_selector"] = "HKLM\\SYSTEM\\*"
        disclosure["value_selector"] = "*"
        problems = policy_check.validate_policy(policy)
        self.assertTrue(any("broad or wildcarded" in item for item in problems), problems)
        self.assertTrue(any("BAM disclosure must bind" in item for item in problems), problems)

    def test_protected_installation_write_cannot_be_disclosed(self) -> None:
        policy = copy.deepcopy(policy_check.load_policy())
        selected = next(
            item
            for item in policy["protected_resources"]
            if item["resource_id"] == "installation.selected"
        )
        selected["mutation_disposition"] = "allowed"
        problems = policy_check.validate_policy(policy)
        self.assertTrue(any("protected mutation must be Fail" in item for item in problems), problems)

    def test_unresolved_effect_cannot_pass(self) -> None:
        policy = copy.deepcopy(policy_check.load_policy())
        unresolved = next(
            item
            for item in policy["effect_dispositions"]
            if item["classification"] == "unresolved"
        )
        unresolved["pass_eligible"] = True
        unresolved["verdict_impact"] = "allowed"
        problems = policy_check.validate_policy(policy)
        self.assertTrue(any("disposition semantics changed" in item for item in problems), problems)

    def test_observation_gap_cannot_be_waived(self) -> None:
        policy = copy.deepcopy(policy_check.load_policy())
        policy["observation_scopes"][0]["gap_disposition"] = "Pass"
        problems = policy_check.validate_policy(policy)
        self.assertTrue(any("observation gap" in item for item in problems), problems)

    def test_missing_file_completion_is_a_required_negative_control(self) -> None:
        policy = copy.deepcopy(policy_check.load_policy())
        policy["automated_negative_controls"].remove("missing_fileio_op_end")
        problems = policy_check.validate_policy(policy)
        self.assertTrue(any("negative controls" in item for item in problems), problems)

    def test_artifact_owners_are_disjoint(self) -> None:
        policy = copy.deepcopy(policy_check.load_policy())
        runtime = next(
            item
            for item in policy["writable_resources"]
            if item["resource_id"] == "operation.candidate_artifacts"
        )
        runtime["artifact_owner"] = "observer"
        problems = policy_check.validate_policy(policy)
        self.assertTrue(any("runtime-owned" in item for item in problems), problems)
        self.assertTrue(any("must be disjoint" in item for item in problems), problems)

    def test_policy_or_verdict_cannot_grant_authority(self) -> None:
        policy = copy.deepcopy(policy_check.load_policy())
        policy["authority_boundary"]["process_execution"] = True
        policy["verdict_criteria"][0]["grants_authority"] = True
        problems = policy_check.validate_policy(policy)
        self.assertTrue(any("promotes forbidden authority" in item for item in problems), problems)
        self.assertTrue(any("grants no authority" in item for item in problems), problems)

    def test_retained_inventory_reconciles_exactly(self) -> None:
        policy = copy.deepcopy(policy_check.load_policy())
        inventory = next(
            item
            for item in policy["evidence_inventory"]
            if item["inventory_id"] == "verdict03.unresolved_file_targets"
        )
        inventory["effect_count"] = 5
        problems = policy_check.validate_policy(policy)
        self.assertTrue(any("effect count" in item for item in problems), problems)
        self.assertTrue(any("reconcile to 611" in item for item in problems), problems)


if __name__ == "__main__":
    unittest.main()
