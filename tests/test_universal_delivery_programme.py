# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import universal_delivery_programme_check


class UniversalDeliveryProgrammeTests(unittest.TestCase):
    def setUp(self) -> None:
        (
            self.plan,
            self.trust,
            self.support,
            self.providers,
            self.doctrine,
        ) = universal_delivery_programme_check.load_inputs()

    def _validate(self) -> list[str]:
        return universal_delivery_programme_check.validate(
            self.plan,
            self.trust,
            self.support,
            self.providers,
            self.doctrine,
        )

    def test_preparation_is_complete_and_non_authorizing(self) -> None:
        self.assertEqual(self._validate(), [])

    def test_source_sdk_conformance_cannot_return_to_active(self) -> None:
        changed = copy.deepcopy(self.plan)
        workunit = next(
            item
            for item in changed["workunit"]
            if item["id"] == "THREE-REPO-SOURCE-VS-SDK-CONFORMANCE-01"
        )
        workunit["status"] = "active"
        problems = universal_delivery_programme_check.validate(
            changed,
            self.trust,
            self.support,
            self.providers,
            self.doctrine,
        )
        self.assertTrue(any("status must remain 'complete'" in item for item in problems))

    def test_semantic_closeout_cannot_regress_to_partial(self) -> None:
        changed = copy.deepcopy(self.plan)
        workunit = next(
            item
            for item in changed["workunit"]
            if item["id"] == "THREE-REPO-SOURCE-VS-SDK-CONFORMANCE-01"
        )
        workunit["parent_result"] = "partial"
        workunit["next_required_phase"] = "semantic_equivalence"
        problems = universal_delivery_programme_check.validate(
            changed,
            self.trust,
            self.support,
            self.providers,
            self.doctrine,
        )
        self.assertTrue(any("parent_result must remain 'complete'" in item for item in problems))
        self.assertTrue(
            any("next_required_phase must remain 'provider_sdk_consumption'" in item for item in problems)
        )

    def test_sdk_consumption_cannot_return_to_ready(self) -> None:
        changed = copy.deepcopy(self.plan)
        workunit = next(
            item
            for item in changed["workunit"]
            if item["id"] == "FACMAN-PROVIDER-SDK-CONSUMPTION-01"
        )
        workunit["status"] = "ready"
        problems = universal_delivery_programme_check.validate(
            changed,
            self.trust,
            self.support,
            self.providers,
            self.doctrine,
        )
        self.assertTrue(any("status must remain 'complete'" in item for item in problems))

    def test_provider_reconciliation_cannot_return_to_active(self) -> None:
        changed = copy.deepcopy(self.plan)
        workunit = next(
            item
            for item in changed["workunit"]
            if item["id"] == "FACMAN-PROVIDER-PIN-RECONCILIATION-01"
        )
        workunit["status"] = "active"
        problems = universal_delivery_programme_check.validate(
            changed,
            self.trust,
            self.support,
            self.providers,
            self.doctrine,
        )
        self.assertTrue(any("status must remain 'complete'" in item for item in problems))

    def test_route_v2_cannot_return_to_planned(self) -> None:
        changed = copy.deepcopy(self.plan)
        workunit = next(
            item
            for item in changed["workunit"]
            if item["id"] == "FACMAN-SUCCESSOR-PLAY-ROUTE-DEFINITION-02"
        )
        workunit["status"] = "planned"
        problems = universal_delivery_programme_check.validate(
            changed,
            self.trust,
            self.support,
            self.providers,
            self.doctrine,
        )
        self.assertTrue(any("status must remain 'ready'" in item for item in problems))

    def test_provider_adoption_preserves_route_definition_immutability(self) -> None:
        changed = copy.deepcopy(self.plan)
        workunits = {item["id"]: item for item in changed["workunit"]}
        route = workunits["FACMAN-SUCCESSOR-PLAY-ROUTE-DEFINITION-02"]
        closure = workunits["FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-01"]
        route["pending_active_contract"] = "release/index/successor_play_route.v1.toml"
        closure["depends_on"] = ["FACMAN-SUCCESSOR-PLAY-ROUTE-DEFINITION-01"]
        problems = universal_delivery_programme_check.validate(
            changed,
            self.trust,
            self.support,
            self.providers,
            self.doctrine,
        )
        self.assertTrue(any("pending_active_contract" in item for item in problems))
        self.assertTrue(any("depends_on" in item for item in problems))

    def test_provider_sdk_consumption_cannot_be_inferred_from_planning(self) -> None:
        changed = copy.deepcopy(self.providers)
        changed["provider"][0]["consumption_mode"] = "installed_sdk"
        problems = universal_delivery_programme_check.validate(
            self.plan,
            self.trust,
            self.support,
            changed,
            self.doctrine,
        )
        self.assertTrue(any("source-closure default changed" in item for item in problems))

    def test_planning_cannot_grant_release_authority(self) -> None:
        changed_trust = copy.deepcopy(self.trust)
        changed_support = copy.deepcopy(self.support)
        changed_trust["role"][1]["authorized"] = True
        changed_support["support"][0]["release_authorized"] = True
        problems = universal_delivery_programme_check.validate(
            self.plan,
            changed_trust,
            changed_support,
            self.providers,
            self.doctrine,
        )
        self.assertTrue(any("cannot authorize build_operator" in item for item in problems))
        self.assertTrue(any("cannot authorize support" in item for item in problems))

    def test_constitutional_anchor_removal_is_detected(self) -> None:
        changed = self.doctrine.replace("not a fourth repository", "another repository")
        problems = universal_delivery_programme_check.validate(
            self.plan,
            self.trust,
            self.support,
            self.providers,
            changed,
        )
        self.assertIn(
            "programme doctrine is missing anchor: not a fourth repository",
            problems,
        )

    def test_evolution_gates_remain_post_c1_only(self) -> None:
        workunits = {item["id"] for item in self.plan["workunit"]}
        later = {item["id"]: item for item in self.plan["later"]}
        for workunit_id in universal_delivery_programme_check.EVOLUTION_GATES:
            self.assertNotIn(workunit_id, workunits)
            self.assertIn(workunit_id, later)
            self.assertIn("C1 is release-proven", later[workunit_id]["trigger"])

    def test_missing_evolution_gate_is_detected(self) -> None:
        changed = copy.deepcopy(self.plan)
        missing = "FACMAN-DOCTOR-AND-SAFE-MODE-01"
        changed["later"] = [
            item for item in changed["later"] if item["id"] != missing
        ]
        problems = universal_delivery_programme_check.validate(
            changed,
            self.trust,
            self.support,
            self.providers,
            self.doctrine,
        )
        self.assertTrue(any(missing in item for item in problems))

    def test_evolution_gate_cannot_enter_near_term_graph(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["workunit"].append(
            {
                "id": "FACMAN-DOCTOR-AND-SAFE-MODE-01",
                "status": "planned",
            }
        )
        problems = universal_delivery_programme_check.validate(
            changed,
            self.trust,
            self.support,
            self.providers,
            self.doctrine,
        )
        self.assertTrue(any("cannot enter the active WorkUnit graph" in item for item in problems))

    def test_evolution_gate_requires_release_proven_c1(self) -> None:
        changed = copy.deepcopy(self.plan)
        workunit = next(
            item
            for item in changed["later"]
            if item["id"] == "UNIVERSAL-CAPABILITY-GUARANTEE-MODEL-01"
        )
        workunit["trigger"] = "C1 implementation begins."
        problems = universal_delivery_programme_check.validate(
            changed,
            self.trust,
            self.support,
            self.providers,
            self.doctrine,
        )
        self.assertTrue(any("trigger must require C1" in item for item in problems))

    def test_windows_classic_gates_remain_post_c1_only(self) -> None:
        workunits = {item["id"] for item in self.plan["workunit"]}
        later = {item["id"]: item for item in self.plan["later"]}
        for workunit_id in universal_delivery_programme_check.WINDOWS_CLASSIC_GATES:
            self.assertNotIn(workunit_id, workunits)
            self.assertIn(workunit_id, later)
            self.assertIn("C1 is release-proven", later[workunit_id]["trigger"])

    def test_missing_windows_classic_gate_is_detected(self) -> None:
        changed = copy.deepcopy(self.plan)
        missing = "FACMAN-WINFORMS-NET48-QUALIFICATION-01"
        changed["later"] = [item for item in changed["later"] if item["id"] != missing]
        problems = universal_delivery_programme_check.validate(
            changed,
            self.trust,
            self.support,
            self.providers,
            self.doctrine,
        )
        self.assertTrue(any(missing in item for item in problems))


if __name__ == "__main__":
    unittest.main()
