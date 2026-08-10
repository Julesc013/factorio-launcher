# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import tomllib
import unittest

from tools import successor_play_route_definition_check as route_check


class SuccessorPlayRouteDefinitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.v1 = route_check.load_definition()
        self.v2 = route_check.load_v2_definition()
        self.index = route_check.load_route_index()

    def test_canonical_v1_is_preserved_byte_for_byte(self) -> None:
        self.assertEqual([], route_check.validate_v1_file())
        self.assertEqual([], route_check.validate(self.v1))

    def test_canonical_v2_and_route_index_admit_only_source_closure(self) -> None:
        self.assertEqual([], route_check.validate_v2(self.v2))
        self.assertEqual([], route_check.validate_route_index(self.index))

    def test_route_index_binds_exact_source_closure_admission(self) -> None:
        self.assertEqual(
            "one_integrated_current_definition_no_product_authority",
            self.index["selection_status"],
        )
        self.assertEqual(
            "c197b5c977bbc442adfba454f12103b8f93f5e39",
            self.index["current_route_integration_revision"],
        )
        self.assertEqual(
            "312c4d2383b60f8780bc320b005fca997d615dd6",
            self.index["current_route_integration_tree"],
        )
        self.assertEqual(129, self.index["current_route_integration_pull_request"])
        self.assertTrue(self.index["new_evidence_execution_authorized"])
        self.assertTrue(self.index["source_closure_execution_authorized"])
        self.assertTrue(self.index["route"][1]["new_source_closure_evidence_allowed"])
        self.assertFalse(self.index["route"][1]["new_qualification_evidence_allowed"])
        self.assertFalse(self.index["route_capability_authorized"])
        self.assertFalse(self.index["route_promotion_authorized"])

    def test_route_index_rejects_stale_integration_identity(self) -> None:
        changed = copy.deepcopy(self.index)
        changed["current_route_integration_revision"] = "0" * 40
        changed["index_digest"] = route_check.index_digest(changed)
        problems = route_check.validate_route_index(changed, check_views=False)
        self.assertTrue(
            any("current_route_integration_revision" in item for item in problems)
        )

    def test_route_v1_byte_mutation_is_rejected(self) -> None:
        payload = route_check.V1_DEFINITION.read_bytes() + b"\n"
        problems = route_check.validate_v1_bytes(payload)
        self.assertTrue(any("immutable route v1 SHA-256 drifted" in item for item in problems))

    def test_route_v1_hash_mismatch_in_index_is_rejected(self) -> None:
        changed = copy.deepcopy(self.index)
        changed["route"][0]["sha256"] = "0" * 64
        problems = route_check.validate_route_index(changed, check_views=False)
        self.assertTrue(any("preserve and supersede v1 exactly" in item for item in problems))

    def test_duplicate_route_id_is_rejected(self) -> None:
        changed = copy.deepcopy(self.v2)
        changed["route_id"] = route_check.EXPECTED_V1_ROUTE_ID
        changed["definition_digest"] = route_check.definition_digest(changed)
        problems = route_check.validate_v2(changed)
        self.assertIn("successor route v2 ID drifted or duplicates another route", problems)

    def test_predecessor_dot_01_identity_reuse_is_rejected(self) -> None:
        changed = copy.deepcopy(self.v2)
        changed["evidence_identity"][7]["id"] = "facman.successor-play.launch-1.operation.01"
        changed["definition_digest"] = route_check.definition_digest(changed)
        problems = route_check.validate_v2(changed)
        self.assertTrue(any("fresh .02 family" in item for item in problems))
        self.assertTrue(any("reuses a predecessor or .01" in item for item in problems))

    def test_route_v2_old_provider_pin_is_rejected(self) -> None:
        changed = copy.deepcopy(self.v2)
        changed["provider_pins"]["universal_launcher"] = route_check.EXPECTED_V1_PROVIDER_PINS[
            "universal_launcher"
        ]
        changed["definition_digest"] = route_check.definition_digest(changed)
        problems = route_check.validate_v2(changed)
        self.assertIn(
            "successor route v2 does not bind the exact reconciled provider locks",
            problems,
        )

    def test_route_v2_wrong_lock_digest_is_rejected(self) -> None:
        changed = copy.deepcopy(self.v2)
        changed["provider_pins"]["provider_lock_sha256"] = "0" * 64
        changed["definition_digest"] = route_check.definition_digest(changed)
        problems = route_check.validate_v2(changed)
        self.assertIn(
            "successor route v2 does not bind the exact reconciled provider locks",
            problems,
        )

    def test_route_v2_stale_base_revision_and_tree_are_rejected(self) -> None:
        changed = copy.deepcopy(self.v2)
        changed["base_revision"] = "0" * 40
        changed["base_tree"] = "1" * 40
        changed["definition_digest"] = route_check.definition_digest(changed)
        problems = route_check.validate_v2(changed)
        self.assertTrue(any("stale or unauthorized base revision" in item for item in problems))
        self.assertTrue(any("stale or unauthorized base tree" in item for item in problems))

    def test_new_evidence_targeting_superseded_v1_is_rejected(self) -> None:
        problems = route_check.validate_evidence_target(
            route_check.EXPECTED_V1_ROUTE_ID,
            ["facman.successor-play.source-closure.01"],
            self.index,
        )
        self.assertTrue(any("may not target superseded" in item for item in problems))
        self.assertTrue(any("reuses a superseded .01" in item for item in problems))

    def test_mixed_v1_v2_evidence_chain_is_rejected(self) -> None:
        problems = route_check.validate_evidence_target(
            route_check.EXPECTED_V2_ROUTE_ID,
            [
                "facman.successor-play.source-closure.01",
                "facman.successor-play.source-closure.02",
            ],
            self.index,
        )
        self.assertIn("mixed v1/v2 evidence chains are forbidden", problems)

    def test_any_authority_field_set_true_is_rejected(self) -> None:
        changed = copy.deepcopy(self.v2)
        changed["authority"]["factorio_execution"] = True
        changed["definition_digest"] = route_check.definition_digest(changed)
        problems = route_check.validate_v2(changed)
        self.assertTrue(any("opens authority" in item for item in problems))

    def test_source_or_candidate_identity_cannot_be_filled_during_definition(self) -> None:
        changed = copy.deepcopy(self.v2)
        changed["future_bindings"]["source_revision"] = "1" * 40
        changed["definition_digest"] = route_check.definition_digest(changed)
        problems = route_check.validate_v2(changed)
        self.assertIn(
            "successor route v2 assigns or opens future source/candidate bindings",
            problems,
        )

    def test_unknown_field_and_unsupported_enum_are_rejected(self) -> None:
        changed = copy.deepcopy(self.v2)
        changed["unknown_authority_surface"] = False
        changed["definition_status"] = "release_authorized"
        changed["definition_digest"] = route_check.definition_digest(changed)
        problems = route_check.validate_v2(changed)
        self.assertIn("successor route v2 top-level contract is incomplete or open", problems)
        self.assertIn("successor route v2 definition status is unsupported", problems)

    def test_generated_current_views_must_match_route_index(self) -> None:
        current = tomllib.loads(
            route_check.CURRENT_STATE.read_text(encoding="utf-8")
        )
        project = tomllib.loads(
            route_check.PROJECT_STATUS.read_text(encoding="utf-8")
        )
        current["provider_convergence"]["active_route_id"] = route_check.EXPECTED_V1_ROUTE_ID
        problems = route_check.validate_route_views(self.index, current, project)
        self.assertTrue(any("current_state.v1.toml" in item for item in problems))

    def test_definition_and_index_digests_are_deterministic(self) -> None:
        self.assertEqual(self.v2["definition_digest"], route_check.definition_digest(self.v2))
        self.assertEqual(self.index["index_digest"], route_check.index_digest(self.index))

    def test_v1_provider_pin_drift_is_rejected_without_rewriting_history(self) -> None:
        changed = copy.deepcopy(self.v1)
        changed["provider_pins"]["universal_launcher"] = "0" * 40
        problems = route_check.validate(changed)
        self.assertIn("successor route changed the stable universal_launcher pin", problems)

    def test_human_verdict_never_promotes_route_directly(self) -> None:
        changed = copy.deepcopy(self.v2)
        changed["verdict_law"]["Pass"]["authority_granted"] = True
        changed["definition_digest"] = route_check.definition_digest(changed)
        problems = route_check.validate_v2(changed)
        self.assertTrue(any("verdict_law drifted" in item for item in problems))


if __name__ == "__main__":
    unittest.main()
