# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import factorio_2_1_14_route_packet_check as packet_check


class Factorio2114RoutePacketTests(unittest.TestCase):
    def setUp(self) -> None:
        self.packet = packet_check.load_packet()
        self.template = packet_check.load_human_template()

    def test_canonical_candidate_binding_is_valid_and_non_authorizing(self) -> None:
        self.assertEqual([], packet_check.validate(self.packet, self.template))
        self.assertTrue(self.packet["active_route_unchanged"])
        self.assertFalse(self.packet["release_evidence_created"])
        self.assertFalse(self.packet["route_index_mutation"])
        self.assertTrue(all(value is False for value in self.packet["authority"].values()))

    def test_packet_digest_is_deterministic(self) -> None:
        self.assertEqual(self.packet["packet_digest"], packet_check.packet_digest(self.packet))

    def test_candidate_identity_drift_is_rejected(self) -> None:
        changed = copy.deepcopy(self.packet)
        changed["future_bindings"]["source_revision"] = "1" * 40
        changed["packet_digest"] = packet_check.packet_digest(changed)
        problems = packet_check.validate(changed, self.template)
        self.assertTrue(any("candidate-bound route identities" in item for item in problems))
        self.assertTrue(any("schema rejection" in item for item in problems))

    def test_authority_activation_is_rejected(self) -> None:
        changed = copy.deepcopy(self.packet)
        changed["authority"]["factorio_execution"] = True
        changed["packet_digest"] = packet_check.packet_digest(changed)
        problems = packet_check.validate(changed, self.template)
        self.assertTrue(any("opens authority" in item for item in problems))
        self.assertTrue(any("schema rejection" in item for item in problems))

    def test_historical_evidence_identity_reuse_is_rejected(self) -> None:
        changed = copy.deepcopy(self.packet)
        changed["evidence_identity"][1]["id"] = "facman.successor-play.source-closure.02"
        changed["packet_digest"] = packet_check.packet_digest(changed)
        problems = packet_check.validate(changed, self.template)
        self.assertTrue(any("reuse" in item for item in problems))
        self.assertTrue(any("schema rejection" in item for item in problems))

    def test_policy_cannot_be_frozen_with_invented_identity(self) -> None:
        changed = copy.deepcopy(self.packet)
        changed["policy_scaffold"]["contract_path"] = (
            "contracts/policy/factorio/windows_instance_isolated_play_2_1_14_windows_x64.v1.toml"
        )
        changed["policy_scaffold"]["policy_digest"] = "1" * 64
        changed["packet_digest"] = packet_check.packet_digest(changed)
        problems = packet_check.validate(changed, self.template)
        self.assertTrue(any("policy identity was invented" in item for item in problems))

    def test_action_checklist_cannot_execute_itself(self) -> None:
        changed = copy.deepcopy(self.packet)
        changed["action"][6]["execution_allowed"] = True
        changed["packet_digest"] = packet_check.packet_digest(changed)
        problems = packet_check.validate(changed, self.template)
        self.assertTrue(any("may not execute" in item for item in problems))

    def test_human_template_remains_inconclusive_until_filled(self) -> None:
        changed = copy.deepcopy(self.template)
        changed["result"] = "Pass"
        changed["journeys"][0]["result"] = "Pass"
        problems = packet_check.validate(self.packet, changed)
        self.assertTrue(any("template result must remain Inconclusive" in item for item in problems))
        self.assertTrue(any("template journeys must remain Inconclusive" in item for item in problems))

    def test_human_template_cannot_consume_reserved_verdict_identity(self) -> None:
        changed = copy.deepcopy(self.template)
        changed["receipt_id"] = "facman.successor-play.human-verdict.03"
        problems = packet_check.validate(self.packet, changed)
        self.assertTrue(any("receipt identity must remain unassigned" in item for item in problems))

    def test_human_template_requires_exact_candidate_binding(self) -> None:
        changed = copy.deepcopy(self.template)
        changed["candidate"]["package_sha256"] = "1" * 64
        problems = packet_check.validate(self.packet, changed)
        self.assertTrue(any("exact alpha.1 binding" in item for item in problems))


if __name__ == "__main__":
    unittest.main()
