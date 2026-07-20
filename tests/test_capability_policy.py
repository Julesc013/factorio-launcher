# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import unittest

from tools import capability_policy_check


class CapabilityPolicyTests(unittest.TestCase):
    def test_repository_policy_is_valid(self) -> None:
        self.assertEqual(capability_policy_check.main(), 0)

    def test_unknown_effect_and_command_fail_closed(self) -> None:
        policy = {
            "schema": "facman.capabilities.v1",
            "version": 1,
            "capability": [
                {
                    "id": capability_id,
                    "domain": "test",
                    "status": "available",
                    "required_effects": ["workspace_read"],
                    "commands": [],
                    "description": "test capability",
                }
                for capability_id in sorted(capability_policy_check.REQUIRED_CAPABILITIES)
            ],
        }
        policy["capability"][0]["required_effects"] = ["unknown.effect"]
        policy["capability"][0]["commands"] = ["unknown.command"]
        problems = capability_policy_check.validate(policy, {"workspace_read"}, set())
        self.assertTrue(any("unknown effects" in problem for problem in problems), problems)
        self.assertTrue(any("unknown commands" in problem for problem in problems), problems)

    def test_execution_contract_cannot_overclaim_real_play(self) -> None:
        policy = capability_policy_check.load_toml(capability_policy_check.POLICY)
        catalog = json.loads(capability_policy_check.CATALOG.read_text(encoding="utf-8"))
        self.assertEqual(capability_policy_check.validate_execution_foundation(policy, catalog), [])
        policy["capability"] = [dict(item) for item in policy["capability"]]
        next(item for item in policy["capability"] if item["id"] == "launch.execute.hermetic")["status"] = "available"
        problems = capability_policy_check.validate_execution_foundation(policy, catalog)
        self.assertTrue(any("hermetic" in problem for problem in problems), problems)


if __name__ == "__main__":
    unittest.main()
