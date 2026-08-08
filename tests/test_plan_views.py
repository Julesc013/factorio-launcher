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
        self.assertLessEqual(line_count, 170)

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
        self.assertEqual(gate["status"], "blocked")
        self.assertEqual(gate["stage"], "superseded_before_observer_self_test")
        self.assertIn(".aide/history/", gate["source"])
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
        self.assertIn("WIP: 0/3 including external gates", dashboard)
        self.assertIn("Ready: 1/10", dashboard)
        pending = [
            item
            for item in self.plan["workunit"]
            if item["status"] not in {"complete", "cancelled"}
        ]
        in_flight = [
            item
            for item in pending
            if item["status"] in generate_plan_views.ACTIVE_WORK_STATUSES
        ]
        self.assertIn(
            "Near-term queued work: "
            f"{len(pending) - len(in_flight)}/{self.plan['next_workunit_limit']}; "
            f"in-flight work: {len(in_flight)}",
            dashboard,
        )
        self.assertIn(
            "[x] `FACMAN-C1-BACKEND-IDENTITY-01`",
            dashboard,
        )
        self.assertIn(
            "Non-authorizing successor preparation may proceed",
            dashboard,
        )
        self.assertIn("scope: `authority_only`", dashboard)
        self.assertNotIn("external gate holds current WIP", dashboard)

    def test_truth_hierarchy_keeps_run_prompts_subordinate(self) -> None:
        self.assertEqual(
            self.plan["source_of_truth"],
            [
                "release/index/plan.v1.toml canonical execution graph",
                "release/index/component_ownership.v1.toml permanent authority",
                "release/index/workspace_lock.v1.toml exact consumed identities",
                "release/index/current_state.v1.toml reviewed checkpoint state",
                "durable architecture, contracts, safety invariants, journeys, and claim policy",
                "out-of-tree live checkout observation within its offline claim boundary",
                "run-specific generated prompt and run profile",
                "historical reports, archived plans, research notes, and prior prompts",
            ],
        )

    def test_pre_c1_hardening_precedes_packaged_live_acceptance(self) -> None:
        workunits = {item["id"]: item for item in self.plan["workunit"]}
        prerequisite_ids = (
            "FACMAN-WINFORMS-C1-TRANSPORT-HARDENING-01",
            "FACMAN-C1-BACKEND-IDENTITY-01",
            "FACMAN-WORKSPACE-ROOT-AUTHORITY-01",
        )
        transport = workunits["FACMAN-WINFORMS-C1-TRANSPORT-HARDENING-01"]
        self.assertEqual(transport["status"], "complete")
        self.assertEqual(
            transport["branch"], "task/winforms-c1-transport-hardening-01"
        )
        self.assertEqual(
            transport["base_revision"],
            "bfac7ce41f19856522b5f9603320f444b8f45094",
        )
        self.assertEqual(
            transport["depends_on"], ["FACMAN-C1-LIVE-SHELL-INTEGRATION-01"]
        )
        self.assertEqual(transport["repos"], ["factorio-launcher"])

        backend_identity = workunits["FACMAN-C1-BACKEND-IDENTITY-01"]
        self.assertEqual(backend_identity["status"], "complete")
        self.assertEqual(
            backend_identity["branch"], "task/c1-backend-identity-01"
        )
        self.assertEqual(
            backend_identity["base_revision"],
            "7ebbfa37b23ee173cbb15f399935d0e035e79375",
        )
        self.assertEqual(
            backend_identity["depends_on"],
            ["FACMAN-C1-LIVE-SHELL-INTEGRATION-01"],
        )
        self.assertNotIn("activation_after", backend_identity)
        self.assertEqual(backend_identity["repos"], ["factorio-launcher"])

        for workunit_id in prerequisite_ids[:2]:
            workunit = workunits[workunit_id]
            self.assertEqual(
                workunit["depends_on"], ["FACMAN-C1-LIVE-SHELL-INTEGRATION-01"]
            )
            self.assertEqual(workunit["repos"], ["factorio-launcher"])

        workspace = workunits["FACMAN-WORKSPACE-ROOT-AUTHORITY-01"]
        self.assertEqual(workspace["status"], "complete")
        self.assertEqual(workspace["depends_on"], list(prerequisite_ids[:2]))
        self.assertEqual(workspace["branch"], "task/workspace-root-authority-01")
        self.assertEqual(
            workspace["base_revision"],
            "9766c01afae3ef6b70a4e55b53ade1db479e254c",
        )
        self.assertEqual(
            workspace["evidence"],
            ["docs/release/checkpoints/facman-workspace-root-authority-01.md"],
        )

        synthetic_tck = workunits["SYNTHETIC-PRODUCT-TCK-01"]
        self.assertEqual(synthetic_tck["status"], "complete")
        self.assertEqual(synthetic_tck["branch"], "task/synthetic-product-tck-01")
        self.assertEqual(
            synthetic_tck["base_revision"],
            "5dfef289aa98a1a8df62b8e32b81e1743d2aeaad",
        )
        self.assertEqual(
            synthetic_tck["evidence"],
            ["docs/release/checkpoints/synthetic-product-tck-01.md"],
        )
        self.assertEqual(
            synthetic_tck["depends_on"],
            [
                "ULK-PRODUCT-COMPOSITION-CONTRACT-01",
                "USK-PRODUCT-PACKAGE-AND-RECIPE-CONTRACT-01",
            ],
        )

        candidate = workunits["C1-WINDOWS-RELEASE-CANDIDATE-01"]
        self.assertEqual(candidate["status"], "planned")
        self.assertEqual(candidate["branch"], "task/c1-windows-release-candidate-01")
        self.assertEqual(
            candidate["base_revision"],
            "3bf9998fd36b74b287ebf64b972dd26f7e47e1c8",
        )
        self.assertIn(
            "FACMAN-WORKSPACE-ROOT-AUTHORITY-01", candidate["depends_on"]
        )
        gate = self.plan["gate"][0]
        self.assertEqual(gate["status"], "blocked")
        self.assertEqual(
            gate["external_ref"],
            "FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-04",
        )
        self.assertEqual(gate["stage"], "superseded_before_observer_self_test")
        self.assertFalse(gate["operator_assignment_required"])
        self.assertEqual(
            gate["blocks"],
            [
                "FACMAN-EXACT-PLAY-ROUTE-CAPABILITY-01",
                "FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-ROUTE-PROMOTION-01",
                "C1-LIVE-PLAY-ACCEPTANCE-01",
            ],
        )
        for workunit_id in prerequisite_ids:
            self.assertIn(workunit_id, gate["non_blocking_work"])
        self.assertNotIn("C1-WINDOWS-PACKAGE-01", gate["non_blocking_work"])

        successor_ids = (
            "FACMAN-SUCCESSOR-PLAY-ROUTE-DEFINITION-01",
            "FACMAN-SUCCESSOR-PLAY-ROUTE-DEFINITION-02",
            "FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-01",
            "FACMAN-SUCCESSOR-PLAY-QUALIFICATION-01",
        )
        self.assertEqual(
            workunits[successor_ids[0]]["depends_on"],
            ["FACMAN-WORKSPACE-ROOT-AUTHORITY-01"],
        )
        self.assertEqual(
            workunits[successor_ids[1]]["depends_on"],
            [
                successor_ids[0],
                "FACMAN-PROVIDER-PIN-RECONCILIATION-01",
            ],
        )
        self.assertEqual(
            workunits[successor_ids[2]]["depends_on"], [successor_ids[1]]
        )
        self.assertEqual(
            workunits[successor_ids[3]]["depends_on"], [successor_ids[2]]
        )
        self.assertEqual(workunits[successor_ids[0]]["status"], "complete")
        self.assertEqual(
            workunits[successor_ids[0]]["branch"],
            "task/facman-successor-play-route-definition-01",
        )
        self.assertEqual(
            workunits[successor_ids[0]]["base_revision"],
            "b70be10696855628c6d2948eb016c8424912e14e",
        )
        self.assertEqual(
            workunits[successor_ids[0]]["definition_contract"],
            "release/index/successor_play_route.v1.toml",
        )
        self.assertIn(
            "docs/release/checkpoints/facman-successor-play-route-definition-01.md",
            workunits[successor_ids[0]]["evidence"],
        )
        self.assertEqual(workunits[successor_ids[1]]["status"], "ready")
        self.assertEqual(workunits[successor_ids[2]]["status"], "blocked")
        self.assertEqual(workunits[successor_ids[3]]["status"], "planned")
        self.assertEqual(
            workunits[successor_ids[1]]["immutable_predecessor_contract"],
            "release/index/successor_play_route.v1.toml",
        )
        self.assertEqual(
            workunits[successor_ids[1]]["pending_active_contract"],
            "release/index/successor_play_route.v2.toml",
        )
        self.assertEqual(
            workunits[successor_ids[2]]["pending_active_contract"],
            "release/index/successor_play_route.v2.toml",
        )
        for workunit_id in successor_ids:
            self.assertIn(workunit_id, gate["non_blocking_work"])

        self.assertEqual(
            self.plan["release"][0]["release_sequence"],
            [
                "FACMAN-WINFORMS-C1-TRANSPORT-HARDENING-01 and FACMAN-C1-BACKEND-IDENTITY-01",
                "FACMAN-WORKSPACE-ROOT-AUTHORITY-01",
                "FACMAN-SUCCESSOR-PLAY-ROUTE-DEFINITION-01",
                "THREE-REPO-SOURCE-VS-SDK-CONFORMANCE-01",
                "FACMAN-PROVIDER-SDK-CONSUMPTION-01",
                "FACMAN-PROVIDER-PIN-RECONCILIATION-01",
                "FACMAN-SUCCESSOR-PLAY-ROUTE-DEFINITION-02",
                "FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-01",
                "FACMAN-SUCCESSOR-PLAY-QUALIFICATION-01",
                "fresh stage, observer, prepare, permit, two launches, and human verdict",
                "FACMAN-EXACT-PLAY-ROUTE-CAPABILITY-01 then FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-ROUTE-PROMOTION-01 after Pass",
                "C1-WINDOWS-PACKAGE-01 then C1-LIVE-PLAY-ACCEPTANCE-01",
                "C1-WINDOWS-CLEAN-QUALIFICATION-01",
                "keyboard, DPI, high-contrast, and accessibility acceptance",
                "signing or explicit unsigned-preview classification, then C1 publication",
            ],
        )
        later = {item["id"]: item for item in self.plan["later"]}
        self.assertIn(
            "fresh successor Play qualification passes",
            later["C1-LIVE-PLAY-ACCEPTANCE-01"]["trigger"],
        )
        self.assertIn(
            "all three pre-C1",
            later["C1-WINDOWS-PACKAGE-01"]["trigger"],
        )
        self.assertEqual(
            later["C1-WINDOWS-CLEAN-QUALIFICATION-01"]["trigger"],
            "C1-LIVE-PLAY-ACCEPTANCE-01 is accepted for the exact packaged candidate.",
        )

    def test_gated_activation_cannot_be_marked_non_blocking(self) -> None:
        invalid = copy.deepcopy(self.plan)
        workunit_id = "FACMAN-WINFORMS-C1-TRANSPORT-HARDENING-01"
        invalid_workunit = next(
            item for item in invalid["workunit"] if item["id"] == workunit_id
        )
        invalid_workunit["activation_after"] = invalid["gate"][0]["blocks"][0]
        errors = generate_plan_views.validate_plan(invalid)
        self.assertTrue(
            any(
                f"{workunit_id} cannot be gate-non-blocking" in error
                for error in errors
            ),
            errors,
        )

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

    def test_fixture_vertical_slice_is_complete_and_exactly_based(self) -> None:
        workunit = next(
            item
            for item in self.plan["workunit"]
            if item["id"] == "C1-FIXTURE-VERTICAL-SLICE-01"
        )
        self.assertEqual(workunit["status"], "complete")
        self.assertEqual(
            workunit["branch"], "task/c1-fixture-vertical-slice-01"
        )
        self.assertEqual(
            workunit["base_revision"],
            "0cef638e407fd43b240d985ca9f3482238949c8c",
        )
        self.assertIn(
            "tests/fixtures/presentation/journeys/manifest.v0.json",
            workunit["evidence"],
        )
        contract = (
            generate_plan_views.ROOT
            / "docs/product/facman_c1_fixture_vertical_slice.md"
        ).read_text(encoding="utf-8")
        for marker in (
            "J01-FIXTURE-POSITIVE-01",
            "J01-FIXTURE-STALE-01",
            "J01-FIXTURE-INTERRUPTED-01",
            "`stale_readiness`",
            "`outcome_unknown`",
            "starts no Factorio process",
            "grants no live Play",
        ):
            self.assertIn(marker, contract)

    def test_winforms_c1_shell_is_complete_and_authority_bounded(self) -> None:
        workunit = next(
            item
            for item in self.plan["workunit"]
            if item["id"] == "FACMAN-WINFORMS-C1-SHELL-01"
        )
        self.assertEqual(workunit["status"], "complete")
        self.assertEqual(workunit["branch"], "task/facman-winforms-c1-shell-01")
        self.assertEqual(
            workunit["base_revision"],
            "94fd1b9565c300bbc0e274f8d40083d967c367db",
        )
        self.assertIn(
            "tools/facman_winforms_c1_check.py", workunit["evidence"]
        )
        contract = (
            generate_plan_views.ROOT / "docs/product/facman_winforms_c1_shell.md"
        ).read_text(encoding="utf-8")
        normalized = " ".join(contract.split())
        for marker in (
            "Windows 10 and Windows 11 x64",
            "Instances",
            "Installations",
            "Activity",
            "Settings / About",
            "Launch Deck",
            "`stale_readiness`",
            "Last Run",
            "Per-Monitor V2",
            "fixture_only",
            "starts no Factorio process",
            "Universal Launcher ABI",
        ):
            self.assertIn(marker, normalized)

    def test_dependency_cycle_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.plan)
        invalid["workunit"][0]["depends_on"] = [invalid["workunit"][1]["id"]]
        invalid["workunit"][1]["depends_on"] = [invalid["workunit"][0]["id"]]
        errors = generate_plan_views.validate_plan(invalid)
        self.assertTrue(any("dependency cycle" in error for error in errors), errors)

    def test_ready_work_requires_completed_dependencies(self) -> None:
        invalid = copy.deepcopy(self.plan)
        ready = invalid["workunit"][0]
        ready["status"] = "ready"
        incomplete = invalid["workunit"][1]
        incomplete["status"] = "planned"
        incomplete["depends_on"] = []
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
            + len(
                [
                    item
                    for item in pending
                    if item["status"] in generate_plan_views.ACTIVE_WORK_STATUSES
                ]
            ),
        )

    def test_verified_pending_closeout_requires_evidence(self) -> None:
        invalid = copy.deepcopy(self.plan)
        invalid["workunit"][0]["status"] = "verified_pending_closeout"
        invalid["workunit"][0]["evidence"] = []
        errors = generate_plan_views.validate_plan(invalid)
        self.assertIn(
            "PLAN-CANON-01 is verified_pending_closeout without evidence",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
