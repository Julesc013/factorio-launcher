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

    def test_phase0_governance_is_closed_with_alpha6_next(
        self,
    ) -> None:
        workunits = {item["id"]: item for item in self.plan["workunit"]}
        beta = workunits["FACMAN-0.1-BETA-READINESS-01"]
        closeout = workunits[
            "FACMAN-0.1-ALPHA5-PROMOTION-CANDIDATE-CLOSEOUT-01"
        ]
        remediation = workunits["FACMAN-0.1-ALPHA5-TRUTH-REMEDIATION-01"]
        final_closeout = workunits[
            "FACMAN-0.1-ALPHA5-FINAL-CANDIDATE-CLOSEOUT-01"
        ]
        active_release_view = workunits[
            "FACMAN-ACTIVE-RELEASE-VIEW-CONSOLIDATION-01"
        ]
        self.assertEqual(beta["status"], "complete")
        self.assertEqual(closeout["status"], "complete")
        self.assertEqual(
            closeout["base_revision"],
            "43af71f8231c5a1b843636df7fd0ab8a6040d25c",
        )
        self.assertEqual(
            closeout["depends_on"], ["FACMAN-0.1-BETA-READINESS-01"]
        )
        self.assertIn(
            "release/index/alpha5_promotion_candidate_closeout.v1.toml",
            closeout["evidence"],
        )
        self.assertEqual(remediation["status"], "complete")
        self.assertIn(
            "docs/release/checkpoints/facman-0-1-alpha5-truth-remediation-01.md",
            remediation["evidence"],
        )
        self.assertEqual(
            remediation["depends_on"],
            ["FACMAN-0.1-ALPHA5-PROMOTION-CANDIDATE-CLOSEOUT-01"],
        )
        self.assertEqual(final_closeout["status"], "complete")
        self.assertEqual(
            final_closeout["base_revision"],
            "488994a81ddb5eb54d541ef3a48b64ca83f67d4a",
        )
        self.assertEqual(
            final_closeout["depends_on"],
            ["FACMAN-0.1-ALPHA5-TRUTH-REMEDIATION-01"],
        )
        self.assertIn(
            "release/index/alpha5_final_candidate_closeout.v1.toml",
            final_closeout["evidence"],
        )
        self.assertEqual(active_release_view["status"], "complete")
        self.assertEqual(
            active_release_view["depends_on"],
            ["FACMAN-0.1-ALPHA5-FINAL-CANDIDATE-CLOSEOUT-01"],
        )
        self.assertEqual(
            active_release_view["base_revision"],
            "f99d96e002f5af519824942a1f8b74bcc26d96f8",
        )
        self.assertIn(
            "release/index/active_release_view.v1.toml",
            active_release_view["evidence"],
        )
        self.assertIn(
            "docs/release/checkpoints/facman-active-release-view-consolidation-01.md",
            active_release_view["evidence"],
        )
        identity = workunits["FACMAN-BETA-REPOSITORY-IDENTITY-DECISION-01"]
        self.assertEqual(identity["status"], "complete")
        self.assertEqual(
            identity["base_revision"],
            "0d61feede2acd49bf54a4a7a1cd00bba3c867fb2",
        )
        self.assertIn(
            "release/index/beta_repository_identity_decision.v1.toml",
            identity["evidence"],
        )
        in_flight = [
            item["id"]
            for item in self.plan["workunit"]
            if item["status"] in generate_plan_views.ACTIVE_WORK_STATUSES
        ]
        self.assertEqual(
            in_flight,
            ["FACMAN-0.1-ALPHA6-WORKSPACE-MIGRATION-RECOVERY-01"],
        )
        ruleset = workunits["FACMAN-BETA-RULESET-AND-TAG-PROTECTION-01"]
        self.assertEqual(ruleset["status"], "complete")
        self.assertEqual(
            ruleset["base_revision"],
            "b94365074835c092b3c9a60b71d4ec985d0849d0",
        )
        self.assertIn(
            "release/index/beta_ruleset_and_tag_protection.v1.toml",
            ruleset["evidence"],
        )

    def test_future_alpha_to_beta_workunits_are_linear_planned_and_unactivated(self) -> None:
        workunits = {item["id"]: item for item in self.plan["workunit"]}
        graph = [
            (
                "FACMAN-0.1-ALPHA6-WORKSPACE-MIGRATION-RECOVERY-01",
                "FACMAN-BETA-RULESET-AND-TAG-PROTECTION-01",
            ),
            (
                "FACMAN-0.1-ALPHA6-MANAGED-INSTALL-LIFECYCLE-01",
                "FACMAN-0.1-ALPHA6-WORKSPACE-MIGRATION-RECOVERY-01",
            ),
            (
                "FACMAN-0.1-ALPHA7-CONTENT-WORLD-ROUTES-01",
                "FACMAN-0.1-ALPHA6-MANAGED-INSTALL-LIFECYCLE-01",
            ),
            (
                "FACMAN-0.1-ALPHA7-PLAY-FRONTEND-CONVERGENCE-01",
                "FACMAN-0.1-ALPHA7-CONTENT-WORLD-ROUTES-01",
            ),
            (
                "FACMAN-0.1-FEATURE-FREEZE-01",
                "FACMAN-0.1-ALPHA7-PLAY-FRONTEND-CONVERGENCE-01",
            ),
            (
                "FACMAN-0.1-BETA1-EXACT-RELEASE-01",
                "FACMAN-0.1-FEATURE-FREEZE-01",
            ),
        ]
        for workunit_id, dependency_id in graph:
            workunit = workunits[workunit_id]
            alpha6_entry = (
                workunit_id
                == "FACMAN-0.1-ALPHA6-WORKSPACE-MIGRATION-RECOVERY-01"
            )
            expected_status = (
                "active"
                if alpha6_entry
                else "planned"
            )
            self.assertEqual(workunit["status"], expected_status)
            self.assertEqual(workunit["depends_on"], [dependency_id])
            if alpha6_entry:
                self.assertEqual(
                    workunit["branch"],
                    "task/facman-0-1-alpha6-workspace-migration-recovery-01",
                )
                self.assertEqual(
                    workunit["base_revision"],
                    "c5262596483a5a9767b4c66d4d5ef51b8086cfdc",
                )
                self.assertNotIn("evidence", workunit)
            else:
                for field in ("branch", "base_revision", "evidence"):
                    self.assertNotIn(field, workunit)

    def test_feature_freeze_is_qualification_not_a_catch_all_implementation_workunit(self) -> None:
        workunits = {item["id"]: item for item in self.plan["workunit"]}
        freeze = workunits["FACMAN-0.1-FEATURE-FREEZE-01"]
        self.assertIn("already machine-closed", freeze["outcome"])
        self.assertIn("Entry is refused unless", freeze["acceptance"][0])
        self.assertNotIn("Close J01-J12", freeze["outcome"])

    def test_generated_views_are_current(self) -> None:
        for path, expected in generate_plan_views.render_outputs(self.plan).items():
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.read_text(encoding="utf-8"), expected)

    def test_dashboard_remains_bounded(self) -> None:
        line_count = len(generate_plan_views.render_dashboard(self.plan).splitlines())
        self.assertGreaterEqual(line_count, 80)
        self.assertLessEqual(line_count, 200)

    def test_interface_design_system_is_a_validated_source(self) -> None:
        path = generate_plan_views.ROOT / self.plan["interface_design_system"]
        self.assertTrue(path.is_file(), path)
        content = path.read_text(encoding="utf-8")
        self.assertIn("Portable semantics, native presentation", content)
        self.assertIn("System Native", content)
        self.assertIn("OEM+", content)

    def test_unified_interaction_architecture_is_a_validated_source(self) -> None:
        path = generate_plan_views.ROOT / self.plan["interaction_architecture"]
        self.assertTrue(path.is_file(), path)
        content = path.read_text(encoding="utf-8")
        self.assertIn("facman tui", content)
        self.assertIn("FrontendSession", content)
        self.assertIn("Optional local service mode", content)
        self.assertIn("Machines and automation agents", content)
        self.assertIn("FACMAN-SAME-BINARY-TUI-PARITY-01", content)

    def test_c1_release_contract_is_a_validated_source(self) -> None:
        path = generate_plan_views.ROOT / self.plan["c1_release_contract"]
        self.assertTrue(path.is_file(), path)
        content = path.read_text(encoding="utf-8")
        self.assertIn("facman.presentation.v0", content)
        self.assertIn("Authority-only Play gate", content)
        self.assertIn("System Native", content)

    def test_technical_preview_contract_is_a_validated_source(self) -> None:
        path = generate_plan_views.ROOT / self.plan["technical_preview_contract"]
        self.assertTrue(path.is_file(), path)
        content = path.read_text(encoding="utf-8")
        self.assertIn("facman tui", content)
        self.assertIn("same-binary TUI", content)

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
        in_flight_count = sum(
            item["status"] in generate_plan_views.ACTIVE_WORK_STATUSES
            for item in self.plan["workunit"]
        )
        active_gate_count = sum(
            item["status"] == "active" for item in self.plan["gate"]
        )
        self.assertIn(
            f"WIP: {in_flight_count + active_gate_count}/"
            f"{self.plan['wip_limit']} including external gates",
            dashboard,
        )
        ready_count = sum(
            item["status"] == "ready" for item in self.plan["workunit"]
        )
        self.assertIn(
            f"Ready: {ready_count}/{self.plan['ready_limit']}", dashboard
        )
        pending = [
            item
            for item in self.plan["workunit"]
            if item["status"] not in generate_plan_views.TERMINAL_WORK_STATUSES
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
        self.assertNotIn("State: `superseded`", dashboard)

    def test_truth_hierarchy_keeps_run_prompts_subordinate(self) -> None:
        self.assertEqual(
            self.plan["source_of_truth"],
            [
                "release/index/plan.v1.toml canonical execution graph",
                "release/index/component_ownership.v1.toml permanent authority",
                "release/index/workspace_lock.v1.toml exact consumed identities",
                "release/index/current_state.v1.toml reviewed checkpoint state",
                "release/index/version_train.v1.toml product version and release-class law",
                "release/index/autonomy_policy.v1.toml delegated-operation authority law",
                "release/index/alpha_delegation.v1.toml bounded alpha allocation and tag authority law",
                "release/index/plan.v1.toml finite engineering and public release milestones",
                "release/index/capability_frontend_matrix.v1.toml semantic parity census",
                "contracts/schema/frontend typed frontend-session request and projection law",
                "release/ledger append-only release disposition and withdrawal records",
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
        self.assertEqual(candidate["status"], "cancelled")
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
            "FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-ADMISSION-01",
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
            workunits[successor_ids[3]]["depends_on"], [successor_ids[1]]
        )
        self.assertEqual(
            workunits[successor_ids[4]]["depends_on"], [successor_ids[3]]
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
        self.assertEqual(workunits[successor_ids[1]]["status"], "complete")
        self.assertEqual(
            workunits[successor_ids[1]]["base_revision"],
            "72e4548f5072f01f8f59657ffa5d1b609fae5411",
        )
        self.assertEqual(
            workunits[successor_ids[1]]["base_tree"],
            "d7c416ec0cbe4d9976f6cfe5e0cfc1b5ff38f754",
        )
        self.assertEqual(
            workunits[successor_ids[1]]["route_index_contract"],
            "release/index/successor_play_route.index.v1.toml",
        )
        self.assertEqual(workunits[successor_ids[2]]["status"], "superseded")
        self.assertEqual(workunits[successor_ids[3]]["status"], "superseded")
        self.assertEqual(workunits[successor_ids[4]]["status"], "cancelled")
        self.assertEqual(
            workunits["FACMAN-DEV-RECONCILIATION-01"]["status"],
            "complete",
        )
        self.assertEqual(
            workunits[successor_ids[1]]["immutable_predecessor_contract"],
            "release/index/successor_play_route.v1.toml",
        )
        self.assertEqual(
            workunits[successor_ids[1]]["integrated_active_contract"],
            "release/index/successor_play_route.v2.toml",
        )
        self.assertEqual(workunits[successor_ids[1]]["reviewed_pull_request"], 129)
        self.assertEqual(
            workunits[successor_ids[1]]["dev_integration_revision"],
            "c197b5c977bbc442adfba454f12103b8f93f5e39",
        )
        self.assertEqual(
            workunits[successor_ids[1]]["dev_integration_tree"],
            "312c4d2383b60f8780bc320b005fca997d615dd6",
        )
        self.assertEqual(
            workunits[successor_ids[3]]["integrated_active_contract"],
            "release/index/successor_play_route.v2.toml",
        )
        self.assertEqual(
            workunits[successor_ids[3]]["blockers"],
            [
                "Task-ref and canonical closure are deferred until a fresh qualified Windows host and the private read-only Factorio archive are separately available."
            ],
        )
        self.assertEqual(
            workunits[successor_ids[2]]["branch"],
            "task/facman-successor-play-source-closure-admission-01",
        )
        self.assertEqual(
            workunits[successor_ids[2]]["base_revision"],
            "4da0bf2c4c1df92d8e3a4d2d7eae39ebf65cba2f",
        )
        self.assertEqual(workunits[successor_ids[2]]["task_ref_run_limit"], 1)
        self.assertEqual(workunits[successor_ids[2]]["canonical_dev_run_limit"], 1)
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
                "FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-ADMISSION-01",
                "FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-01",
                "FACMAN-SUCCESSOR-PLAY-QUALIFICATION-01",
                "fresh stage, observer, prepare, permit, two launches, and human verdict",
                "FACMAN-EXACT-PLAY-ROUTE-CAPABILITY-01 then FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-ROUTE-PROMOTION-01 after Pass",
                "C1-WINDOWS-PACKAGE-01 then C1-LIVE-PLAY-ACCEPTANCE-01",
                "C1-WINDOWS-CLEAN-QUALIFICATION-01",
                "keyboard, DPI, high-contrast, and accessibility acceptance",
                "explicit unpublished/unsigned classification, then internal C1 evidence closeout",
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
        workunit = next(
            item for item in invalid["workunit"] if item["id"] == "PLAN-CANON-01"
        )
        workunit["status"] = "complete"
        workunit["evidence"] = []
        errors = generate_plan_views.validate_plan(invalid)
        self.assertIn("PLAN-CANON-01 is complete without evidence", errors)

    def test_near_term_plan_is_bounded(self) -> None:
        pending = [
            item
            for item in self.plan["workunit"]
            if item["status"] not in generate_plan_views.TERMINAL_WORK_STATUSES
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
        workunit = next(
            item for item in invalid["workunit"] if item["id"] == "PLAN-CANON-01"
        )
        workunit["status"] = "verified_pending_closeout"
        workunit["evidence"] = []
        errors = generate_plan_views.validate_plan(invalid)
        self.assertIn(
            "PLAN-CANON-01 is verified_pending_closeout without evidence",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
