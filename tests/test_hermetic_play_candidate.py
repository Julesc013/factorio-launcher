# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import json
import unittest

from tools import hermetic_play_candidate_check, json_contract


class HermeticPlayCandidateTests(unittest.TestCase):
    def test_repository_candidate_boundary_is_valid(self) -> None:
        self.assertEqual(hermetic_play_candidate_check.check(), [])

    def test_packet_schema_cannot_record_verdict_or_authority(self) -> None:
        path = (
            hermetic_play_candidate_check.ROOT
            / "contracts/schema/factorio/factorio_play_candidate_evidence_packet.v1.schema.json"
        )
        schema = json.loads(path.read_text(encoding="utf-8"))
        properties = schema["properties"]
        self.assertEqual(properties["human_verdict"]["const"], "unset")
        self.assertIs(properties["grants_authority"]["const"], False)
        self.assertIs(properties["product_route_available"]["const"], False)
        self.assertNotEqual(
            json_contract.validate("Pass", properties["human_verdict"]), []
        )
        self.assertNotEqual(
            json_contract.validate(True, properties["grants_authority"]), []
        )

    def test_policy_digest_mutation_is_detectable(self) -> None:
        path = (
            hermetic_play_candidate_check.ROOT
            / "contracts/schema/factorio/factorio_hermetic_play_candidate_plan.v1.schema.json"
        )
        schema = json.loads(path.read_text(encoding="utf-8"))
        core = schema["$defs"]["plan_core"]["properties"]
        self.assertEqual(
            core["policy_digest"]["const"],
            hermetic_play_candidate_check.EXPECTED_DIGEST,
        )
        mutated = copy.deepcopy(core["policy_digest"])
        self.assertNotEqual(json_contract.validate("0" * 64, mutated), [])

    def test_observation_gap_set_is_closed(self) -> None:
        path = (
            hermetic_play_candidate_check.ROOT
            / "contracts/schema/factorio/factorio_play_candidate_observation.v1.schema.json"
        )
        schema = json.loads(path.read_text(encoding="utf-8"))
        gaps = schema["$defs"]["gap_state"]
        self.assertIs(gaps["additionalProperties"], False)
        self.assertEqual(set(gaps["required"]), set(gaps["properties"]))

    def test_no_public_play_or_issuer_command_exists(self) -> None:
        catalog = json.loads(
            (
                hermetic_play_candidate_check.ROOT
                / "contracts/generated-index/command_catalog.v2.json"
            ).read_text(encoding="utf-8")
        )
        command_ids = {command["command_id"] for command in catalog["commands"]}
        self.assertTrue(
            command_ids.isdisjoint(
                {"instance.play", "instances.play", "permit.issue", "permits.issue"}
            )
        )


if __name__ == "__main__":
    unittest.main()
