# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import generate_plan_views


class PlanViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = generate_plan_views.load_plan()

    def test_canonical_plan_is_valid(self) -> None:
        self.assertEqual(generate_plan_views.validate_plan(self.plan), [])

    def test_generated_views_are_current(self) -> None:
        for path, expected in generate_plan_views.render_outputs(self.plan).items():
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.read_text(encoding="utf-8"), expected)

    def test_dashboard_remains_bounded(self) -> None:
        line_count = len(generate_plan_views.render_dashboard(self.plan).splitlines())
        self.assertGreaterEqual(line_count, 80)
        self.assertLessEqual(line_count, 150)

    def test_interface_design_system_is_a_validated_source(self) -> None:
        path = generate_plan_views.ROOT / self.plan["interface_design_system"]
        self.assertTrue(path.is_file(), path)
        content = path.read_text(encoding="utf-8")
        self.assertIn("Portable semantics, native presentation", content)
        self.assertIn("System Native", content)
        self.assertIn("OEM+", content)

    def test_c1_release_contract_is_a_validated_source(self) -> None:
        path = generate_plan_views.ROOT / self.plan["c1_release_contract"]
        self.assertTrue(path.is_file(), path)
        content = path.read_text(encoding="utf-8")
        self.assertIn("facman.presentation.v0", content)
        self.assertIn("Authority-only Play gate", content)
        self.assertIn("System Native", content)

    def test_play_gate_blocks_only_named_authorities(self) -> None:
        gate = self.plan["gate"][0]
        self.assertEqual(gate["gate_scope"], "authority_only")
        self.assertEqual(
            gate["blocks"],
            [
                "FACMAN-EXACT-PLAY-ROUTE-CAPABILITY-01",
                "FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-ROUTE-PROMOTION-01",
                "C1-LIVE-PLAY-ACCEPTANCE-01",
            ],
        )
        self.assertIn("FACMAN-WINFORMS-C1-SHELL-01", gate["non_blocking_work"])
        self.assertIn(
            "FACMAN-CLASSIC-PREVIEW-SHELLS-01", gate["non_blocking_work"]
        )
        dashboard = generate_plan_views.render_dashboard(self.plan)
        self.assertIn("scope: `authority_only`", dashboard)
        self.assertNotIn("external gate holds current WIP", dashboard)

    def test_gate_scope_and_overlap_are_rejected(self) -> None:
        invalid = copy.deepcopy(self.plan)
        invalid["gate"][0]["gate_scope"] = "global_mutex"
        invalid["gate"][0]["non_blocking_work"].append(
            invalid["gate"][0]["blocks"][0]
        )
        errors = generate_plan_views.validate_plan(invalid)
        self.assertTrue(any("invalid gate_scope" in error for error in errors), errors)
        self.assertTrue(any("both block and permit" in error for error in errors), errors)

    def test_task_branch_binding_is_mechanical(self) -> None:
        cutline = next(
            item
            for item in self.plan["workunit"]
            if item["id"] == "FACMAN-C1-CUTLINE-01"
        )
        self.assertEqual(cutline["branch"], "task/facman-c1-cutline-01")
        self.assertEqual(
            cutline["base_revision"],
            "239f9c04822f83bdab6b9c3dd191cfaa337f7b23",
        )

    def test_c1_journey_contract_is_complete_and_authority_bounded(self) -> None:
        journey = next(
            item
            for item in self.plan["workunit"]
            if item["id"] == "FACMAN-JOURNEYS-01"
        )
        self.assertEqual(journey["status"], "complete")
        self.assertEqual(journey["branch"], "task/facman-journeys-01")
        self.assertEqual(
            journey["base_revision"],
            "4620ebe8a382960d48e82a0a5ff90230a8f70588",
        )

        contract_path = generate_plan_views.ROOT / "docs/product/facman_c1_journeys.md"
        checkpoint_path = (
            generate_plan_views.ROOT
            / "docs/release/checkpoints/facman-journeys-01.md"
        )
        self.assertIn(
            "docs/product/facman_c1_journeys.md", journey["evidence"]
        )
        self.assertTrue(contract_path.is_file())
        self.assertTrue(checkpoint_path.is_file())

        contract = contract_path.read_text(encoding="utf-8")
        for marker in (
            "J01-P — positive existing-install-to-Play journey",
            "J01-F — stale-readiness refusal and rescan",
            "J01-I — interruption and recovery expectations",
            "at most four major player decisions",
            "structured code `stale_readiness`",
            "No Factorio process starts",
            "outcome_unknown",
            "cancellation_requested_but_completed",
            "Keyboard and accessibility contract",
            "Bounded claims and evidence mapping",
            "FACMAN-CLAIM-001",
            "J01-FIXTURE-STALE-01",
            "Explicit exclusions",
            "grants no live Play authority",
        ):
            self.assertIn(marker, contract)

    def test_journey_contract_keeps_fixture_and_live_evidence_distinct(self) -> None:
        contract = (
            generate_plan_views.ROOT / "docs/product/facman_c1_journeys.md"
        ).read_text(encoding="utf-8")
        normalized = " ".join(contract.split())
        self.assertIn("Deterministic fixture", contract)
        self.assertIn("Later live acceptance", contract)
        self.assertIn(
            "Current maturity from this specification is `declared`", normalized
        )
        self.assertIn("Fixture evidence never substitutes for live", normalized)
        self.assertIn("Windows evidence never promotes AppKit or GTK", normalized)

    def test_dependency_cycle_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.plan)
        invalid["workunit"][0]["depends_on"] = [invalid["workunit"][1]["id"]]
        invalid["workunit"][1]["depends_on"] = [invalid["workunit"][0]["id"]]
        errors = generate_plan_views.validate_plan(invalid)
        self.assertTrue(any("dependency cycle" in error for error in errors), errors)

    def test_ready_work_requires_completed_dependencies(self) -> None:
        invalid = copy.deepcopy(self.plan)
        ready = next(
            item
            for item in invalid["workunit"]
            if item["status"] not in {"complete", "cancelled"}
        )
        ready["status"] = "ready"
        incomplete = next(
            item
            for item in invalid["workunit"]
            if item["status"] not in {"complete", "cancelled"}
            and item["id"] != ready["id"]
        )
        ready["depends_on"] = [incomplete["id"]]
        errors = generate_plan_views.validate_plan(invalid)
        self.assertTrue(
            any("ready with incomplete dependencies" in error for error in errors),
            errors,
        )

    def test_completed_work_requires_evidence(self) -> None:
        invalid = copy.deepcopy(self.plan)
        invalid["workunit"][0]["status"] = "complete"
        invalid["workunit"][0]["evidence"] = []
        errors = generate_plan_views.validate_plan(invalid)
        self.assertIn("PLAN-CANON-01 is complete without evidence", errors)

    def test_near_term_plan_is_bounded(self) -> None:
        pending = [
            item
            for item in self.plan["workunit"]
            if item["status"] not in {"complete", "cancelled"}
        ]
        self.assertLessEqual(
            len(pending),
            self.plan["next_workunit_limit"]
            + len([item for item in pending if item["status"] == "active"]),
        )


if __name__ == "__main__":
    unittest.main()
