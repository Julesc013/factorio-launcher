# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import json
import re
import unittest

import jsonschema

from tools import release_programme_check


class ReleaseProgrammeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.records = release_programme_check.load_records()
        cls.schemas = release_programme_check.load_schemas()
        cls.release_index = release_programme_check.load_release_index()
        cls.index_schemas = release_programme_check.load_index_schemas()
        cls.plan = release_programme_check.load_plan()
        cls.readme = release_programme_check.LEDGER_README.read_text(encoding="utf-8")

    def validate(
        self,
        records: dict | None = None,
        schemas: dict | None = None,
        plan: dict | None = None,
    ) -> list[str]:
        return release_programme_check.validate(
            records if records is not None else copy.deepcopy(self.records),
            schemas if schemas is not None else copy.deepcopy(self.schemas),
            self.readme,
            plan=plan if plan is not None else copy.deepcopy(self.plan),
        )

    def test_canonical_release_programme_is_valid(self) -> None:
        self.assertEqual(release_programme_check.check(), [])

    def test_release_index_binds_every_canonical_programme_record(self) -> None:
        invalid = copy.deepcopy(self.release_index)
        invalid["version_train"] = "release/index/not-the-version-train.toml"
        errors = release_programme_check.validate(
            copy.deepcopy(self.records),
            copy.deepcopy(self.schemas),
            self.readme,
            invalid,
            index_schemas=copy.deepcopy(self.index_schemas),
        )
        self.assertIn(
            "release index does not bind version_train to "
            "release/index/version_train.v1.toml",
            errors,
        )
        self.assertNotIn("milestones", self.release_index)
        self.assertNotIn("withdrawal_policy", self.release_index)
        self.assertEqual(
            self.release_index["alpha5_promotion_candidate_closeout"],
            "release/index/alpha5_promotion_candidate_closeout.v1.toml",
        )
        self.assertEqual(
            self.release_index["alpha5_final_candidate_closeout"],
            "release/index/alpha5_final_candidate_closeout.v1.toml",
        )
        index_schema = json.loads(
            (
                release_programme_check.SCHEMA_ROOT
                / "release_index.v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        self.assertIs(index_schema["properties"]["milestones"], False)
        self.assertIs(index_schema["properties"]["withdrawal_policy"], False)
        self.assertEqual(index_schema["$id"], "facman.release_index.v1")
        self.assertIn("alpha5_promotion_candidate_closeout", index_schema["required"])
        self.assertIn("alpha5_final_candidate_closeout", index_schema["required"])
        self.assertEqual(
            index_schema["properties"]["alpha5_promotion_candidate_closeout"][
                "const"
            ],
            "release/index/alpha5_promotion_candidate_closeout.v1.toml",
        )
        self.assertEqual(
            self.index_schemas["alpha5_promotion_candidate_closeout"]["$id"],
            "facman.alpha5_promotion_candidate_closeout.v1",
        )
        self.assertEqual(
            self.index_schemas["alpha5_final_candidate_closeout"]["$id"],
            "facman.alpha5_final_candidate_closeout.v1",
        )

        duplicate = copy.deepcopy(self.release_index)
        duplicate["milestones"] = "release/index/milestones.v1.toml"
        errors = release_programme_check.validate(
            copy.deepcopy(self.records),
            copy.deepcopy(self.schemas),
            self.readme,
            duplicate,
            copy.deepcopy(self.plan),
            copy.deepcopy(self.index_schemas),
        )
        self.assertIn(
            "release index retains duplicate programme truth: milestones",
            errors,
        )

    def test_release_model_semver_accepts_prerelease_and_rejects_bad_identity(self) -> None:
        schema_path = (
            release_programme_check.SCHEMA_ROOT / "release_model.v2.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        pattern = schema["$defs"]["version"]["properties"]["semver"]["pattern"]
        self.assertEqual(pattern, release_programme_check.SEMVER_PATTERN)
        self.assertIsNotNone(re.fullmatch(pattern, "0.1.0-alpha.0"))
        self.assertIsNotNone(re.fullmatch(pattern, "1.0.0"))
        self.assertIsNone(re.fullmatch(pattern, "0.1-alpha"))
        self.assertIsNone(re.fullmatch(pattern, "01.0.0"))
        self.assertIsNone(re.fullmatch(pattern, "0.1.0-alpha.01"))

    def test_snapshot_candidate_accepts_exact_task_branch_source(self) -> None:
        schema = self.schemas["release_candidate"]
        revision = "0" * 40
        digest = "a" * 64
        candidate = {
            "schema": "facman.release_candidate.v1",
            "candidate_id": "facman.snapshot.test",
            "version": "0.1.0-alpha.0+dev.test.g0000000",
            "release_class": "snapshot",
            "status": "constructed",
            "source": {
                "revision": revision,
                "tree": revision,
                "ref": "task/example",
                "ref_kind": "task_branch",
                "clean": True,
            },
            "providers": {
                "workspace_lock_sha256": digest,
                "provider_lock_sha256": digest,
                "identities": [
                    {
                        "id": provider_id,
                        "revision": revision,
                        "tree": revision,
                        "package_identity": f"{provider_id}.test",
                        "abi": "test",
                        "contract_digest": digest,
                    }
                    for provider_id in ("universal_launcher", "universal_setup")
                ],
            },
            "resolution": {
                "schema": "facman.release_resolution.v1",
                "root_sha256": digest,
            },
            "artifacts": [
                {
                    "name": "facman-test.zip",
                    "bytes": 1,
                    "sha256": digest,
                    "media_type": "application/zip",
                    "signed": False,
                    "published": False,
                }
            ],
            "evidence": {
                "test_summary_sha256": digest,
                "sbom_sha256": digest,
                "provenance_sha256": digest,
                "known_limitations": ["fixture"],
            },
            "three_key": {
                role: {
                    "role": decision_role,
                    "result": "pending",
                    "evidence_sha256": digest,
                }
                for role, decision_role in (
                    ("implementation", "implementation"),
                    ("assurance", "assurance"),
                    ("policy", "control"),
                )
            },
            "authority": {
                "factorio_execution": False,
                "setup_mutation": False,
                "route_promotion": False,
                "signing": False,
                "publication": False,
                "support_promotion": False,
            },
        }
        validator = jsonschema.Draft202012Validator(schema)
        validator.validate(candidate)
        candidate["version"] = "0.1.0-alpha.01"
        self.assertTrue(list(validator.iter_errors(candidate)))
        candidate["version"] = "0.1.0-alpha.0+dev.test.g0000000"
        candidate["source"]["ref_kind"] = "arbitrary"
        self.assertTrue(list(validator.iter_errors(candidate)))

    def test_only_bounded_alpha_tag_authority_is_active(self) -> None:
        for name in ("version_train", "autonomy_policy", "capability_matrix"):
            self.assertEqual(self.records[name]["design_status"], "ratified")
        self.assertEqual(
            self.records["version_train"]["activation_status"],
            "partial_alpha_tagging_active",
        )
        self.assertEqual(
            self.records["autonomy_policy"]["activation_status"],
            "partial_alpha_tagging_active",
        )
        self.assertEqual(
            self.records["capability_matrix"]["activation_status"],
            "implemented_census_activation_graph_terminal",
        )
        self.assertEqual(
            self.records["alpha_delegation"]["status"],
            "active_when_reachable_from_protected_dev_and_tag_ruleset_enforced",
        )
        self.assertTrue(
            self.records["alpha_delegation"]["authority"]["tag_creation"]
        )
        for field in (
            "protected_dev_merge",
            "publication",
            "signing",
            "beta_rc_stable_tags",
            "route_effects",
            "support_activation",
            "human_verdict",
        ):
            self.assertFalse(self.records["alpha_delegation"]["authority"][field])

    def test_programme_authority_ceilings_are_closed(self) -> None:
        removed = copy.deepcopy(self.records)
        removed["version_train"]["authority"].pop("publication")
        self.assertIn(
            "version_train authority ceiling has the wrong closed fields",
            self.validate(removed),
        )

        added = copy.deepcopy(self.records)
        added["autonomy_policy"]["authority"]["invented_grant"] = False
        self.assertIn(
            "autonomy_policy authority ceiling has the wrong closed fields",
            self.validate(added),
        )

        promoted = copy.deepcopy(self.records)
        promoted["alpha_delegation"]["authority"]["publication"] = True
        self.assertIn(
            "alpha_delegation authority ceiling has drifted",
            self.validate(promoted),
        )

    def test_release_classes_bind_exact_sources_and_human_gates(self) -> None:
        classes = {
            item["id"]: item for item in self.records["version_train"]["release_class"]
        }
        self.assertEqual(classes["snapshot"]["source_ref"], "task_or_dev")
        self.assertEqual(
            classes["snapshot"]["source_requirement"],
            "exact_task_or_accepted_dev_commit",
        )
        self.assertEqual(classes["alpha"]["source_ref"], "dev")
        self.assertFalse(classes["alpha"]["human_receipt_required"])
        self.assertTrue(classes["alpha"]["currently_authorized"])
        self.assertEqual(
            classes["alpha"]["publication_kind"],
            "unpublished_annotated_tag",
        )
        self.assertEqual(classes["beta"]["source_ref"], "release/<minor>")
        self.assertTrue(classes["beta"]["human_receipt_required"])
        self.assertEqual(classes["stable_0x"]["source_ref"], "main")
        self.assertTrue(classes["stable_0x"]["human_receipt_required"])
        self.assertTrue(self.records["version_train"]["published_tags_are_immutable"])
        self.assertFalse(self.records["version_train"]["tag_every_commit"])
        self.assertTrue(
            self.records["version_train"]["tracked_contract_identity_is_publishable"]
        )
        self.assertFalse(
            self.records["version_train"][
                "dynamic_snapshot_identity_projected_at_build_time"
            ]
        )
        self.assertEqual(
            self.records["version_train"]["allocated_version"],
            "0.1.0-alpha.5",
        )
        self.assertEqual(
            self.records["version_train"]["release_source_workunit"],
            "FACMAN-0.1-ALPHA5-FINAL-CANDIDATE-CLOSEOUT-01",
        )
        train = self.records["version_train"]
        self.assertEqual(
            train["release_source_status"],
            "final_candidate_machine_qualified_unpublished",
        )
        self.assertEqual(
            train["release_source_revision"],
            release_programme_check.ALPHA5_CANDIDATE_SOURCE_REVISION,
        )
        self.assertEqual(
            train["release_source_tree"],
            release_programme_check.ALPHA5_CANDIDATE_SOURCE_TREE,
        )
        self.assertEqual(
            train["release_source_candidate_run"],
            release_programme_check.ALPHA5_CANDIDATE_RUN,
        )
        self.assertEqual(train["release_source_candidate_attempt"], 1)
        self.assertEqual(
            train["release_source_receipt"],
            release_programme_check.ALPHA5_CANDIDATE_RECEIPT,
        )
        self.assertFalse(train["release_source_is_closeout_revision"])
        self.assertFalse(train["release_source_is_dev_sync_revision"])

    def test_version_train_rejects_candidate_source_or_non_circular_drift(self) -> None:
        invalid = copy.deepcopy(self.records)
        train = invalid["version_train"]
        train["release_source_revision"] = "43af71f8231c5a1b843636df7fd0ab8a6040d25c"
        train["release_source_is_dev_sync_revision"] = True
        errors = self.validate(invalid)
        self.assertIn(
            "version train release_source_revision must be "
            f"{release_programme_check.ALPHA5_CANDIDATE_SOURCE_REVISION!r}",
            errors,
        )
        self.assertIn(
            "version train release_source_is_dev_sync_revision must be False",
            errors,
        )

    def test_release_index_schema_rejects_unbound_closeout_receipt(self) -> None:
        invalid_schemas = copy.deepcopy(self.index_schemas)
        invalid_schemas["release_index"]["properties"][
            "alpha5_promotion_candidate_closeout"
        ]["const"] = "release/index/not-the-alpha5-closeout.toml"
        errors = release_programme_check.validate(
            copy.deepcopy(self.records),
            copy.deepcopy(self.schemas),
            self.readme,
            copy.deepcopy(self.release_index),
            copy.deepcopy(self.plan),
            invalid_schemas,
        )
        self.assertIn(
            "release index schema does not bind alpha5_promotion_candidate_closeout "
            "to release/index/alpha5_promotion_candidate_closeout.v1.toml",
            errors,
        )

    def test_autonomy_cannot_delegate_d4(self) -> None:
        invalid = copy.deepcopy(self.records)
        invalid["autonomy_policy"]["authority_class"][-1]["delegable_after_activation"] = True
        self.assertIn("D4 has the wrong delegation rule", self.validate(invalid))

    def test_autonomy_requires_three_independent_keys(self) -> None:
        invalid = copy.deepcopy(self.records)
        invalid["autonomy_policy"]["three_key"]["assurance_role"] = "implementation"
        self.assertIn(
            "three-key roles must be distinct implementation, assurance, and control",
            self.validate(invalid),
        )

    def test_model_routing_is_dynamic_not_quota_based(self) -> None:
        routing = self.records["autonomy_policy"]["model_routing"]
        self.assertEqual(
            routing["routing_basis"],
            "task_semantics_risk_and_escalation",
        )
        self.assertTrue(routing["fixed_quota_forbidden"])

        invalid = copy.deepcopy(self.records)
        invalid["autonomy_policy"]["model_routing"]["fixed_quota_forbidden"] = False
        self.assertIn("model routing cannot become a fixed quota", self.validate(invalid))

    def test_historical_preview_is_bounded_and_alpha_5_is_active(self) -> None:
        milestones = {item["id"]: item for item in self.plan["release"]}
        self.assertEqual(
            self.plan["active_release"],
            "FACMAN-0.1.0-ALPHA.5",
        )
        self.assertEqual(milestones["FACMAN-C1"]["status"], "cancelled")
        self.assertEqual(
            milestones["FACMAN-0.1-WINDOWS-TECHNICAL-PREVIEW"]["status"],
            "complete",
        )
        self.assertEqual(
            milestones["FACMAN-0.1-WINDOWS-TECHNICAL-PREVIEW"]["required_frontends"],
            release_programme_check.PROJECTIONS_WINDOWS_REFERENCE_0_1,
        )
        self.assertTrue(
            milestones["FACMAN-0.1-WINDOWS-TECHNICAL-PREVIEW"]["tui_parity_blocking"]
        )
        self.assertEqual(
            milestones["FACMAN-1.0-SUPPORTED-RELEASE"]["required_frontends"],
            release_programme_check.PROJECTIONS_1_0,
        )
        self.assertEqual(
            milestones["FACMAN-1.0-SUPPORTED-RELEASE"]["separate_admission_frontends"],
            ["qt"],
        )
        self.assertEqual(milestones["FACMAN-0.1.0-ALPHA.1"]["status"], "complete")
        self.assertEqual(
            milestones["FACMAN-0.1.0-ALPHA.1"]["required_frontends"],
            release_programme_check.PROJECTIONS_ALPHA_1,
        )
        self.assertEqual(
            milestones["FACMAN-0.1.0-ALPHA.1"]["required_factorio_families"],
            release_programme_check.FACTORIO_FAMILIES_ALPHA_1,
        )
        self.assertEqual(milestones["FACMAN-0.1.0-ALPHA.2"]["status"], "complete")
        self.assertEqual(
            milestones["FACMAN-0.1.0-ALPHA.2"]["required_frontends"],
            release_programme_check.PROJECTIONS_ALPHA_2,
        )
        self.assertEqual(milestones["FACMAN-0.1.0-ALPHA.3"]["status"], "complete")
        self.assertEqual(
            milestones["FACMAN-0.1.0-ALPHA.3"]["required_frontends"],
            release_programme_check.PROJECTIONS_ALPHA_3,
        )
        self.assertEqual(milestones["FACMAN-0.1.0-ALPHA.4"]["status"], "complete")
        self.assertEqual(
            milestones["FACMAN-0.1.0-ALPHA.4"]["required_frontends"],
            release_programme_check.PROJECTIONS_ALPHA_4,
        )
        self.assertEqual(milestones["FACMAN-0.1.0-ALPHA.5"]["status"], "active")
        self.assertEqual(
            milestones["FACMAN-0.1.0-ALPHA.5"]["required_frontends"],
            release_programme_check.PROJECTIONS_ALPHA_5,
        )

        invalid = copy.deepcopy(self.plan)
        invalid["release"] = invalid["release"][:-1]
        self.assertTrue(
            any(
                "canonical plan release order" in error
                for error in self.validate(plan=invalid)
            )
        )

    def test_future_alpha_to_beta_graph_is_linear_planned_and_non_allocating(self) -> None:
        releases = {item["id"]: item for item in self.plan["release"]}
        epics = {item["id"]: item for item in self.plan["epic"]}
        workunits = {item["id"]: item for item in self.plan["workunit"]}
        for release_id, epic_id, workunit_id, dependency_id in (
            release_programme_check.FUTURE_PLAN_GRAPH
        ):
            self.assertEqual(releases[release_id]["status"], "planned")
            self.assertTrue(releases[release_id]["planning_label"])
            self.assertFalse(releases[release_id]["version_allocated"])
            self.assertEqual(epics[epic_id]["release"], release_id)
            self.assertEqual(epics[epic_id]["status"], "planned")
            self.assertEqual(workunits[workunit_id]["epic"], epic_id)
            self.assertEqual(workunits[workunit_id]["status"], "planned")
            self.assertEqual(workunits[workunit_id]["depends_on"], [dependency_id])
            for field in ("branch", "base_revision", "evidence"):
                self.assertNotIn(field, workunits[workunit_id])

        invalid = copy.deepcopy(self.plan)
        future = next(
            item
            for item in invalid["workunit"]
            if item["id"] == "FACMAN-0.1-ALPHA7-PLAY-FRONTEND-CONVERGENCE-01"
        )
        future["depends_on"] = ["FACMAN-0.1-FEATURE-FREEZE-01"]
        self.assertTrue(
            any("future dependency" in error for error in self.validate(plan=invalid))
        )

        invalid = copy.deepcopy(self.plan)
        next(
            item
            for item in invalid["workunit"]
            if item["id"] == "FACMAN-0.1-FEATURE-FREEZE-01"
        )["status"] = "ready"
        self.assertTrue(
            any("future WorkUnit binding or status" in error for error in self.validate(plan=invalid))
        )

        invalid = copy.deepcopy(self.plan)
        next(
            item
            for item in invalid["release"]
            if item["id"] == "FACMAN-0.1-FEATURE-FREEZE"
        )["version"] = "0.1.0-alpha.8"
        self.assertTrue(
            any("must not pre-allocate" in error for error in self.validate(plan=invalid))
        )

    def test_beta_candidate_authority_flags_remain_closed(self) -> None:
        invalid = copy.deepcopy(self.records)
        invalid["version_train"]["candidate_beta_allocation_authorized"] = True
        self.assertIn(
            "version train candidate_beta_allocation_authorized must remain false",
            self.validate(invalid),
        )

    def test_capability_matrix_is_user_outcome_census(self) -> None:
        capabilities = self.records["capability_matrix"]["capability"]
        self.assertGreaterEqual(len(capabilities), 20)
        self.assertLessEqual(len(capabilities), 40)
        self.assertEqual(
            self.records["capability_matrix"]["matrix_scope"],
            "user_outcomes",
        )
        self.assertTrue(
            self.records["capability_matrix"]["command_api_ledger_complete"]
        )
        self.assertFalse(
            self.records["capability_matrix"]["one_row_per_command_census_required"]
        )
        self.assertEqual(
            set(self.records["capability_matrix"]["maturity_states"]),
            release_programme_check.MATURITY_VALUES,
        )
        self.assertEqual(
            self.records["capability_matrix"]["tui_1_0_status"],
            "required_same_facman_binary",
        )
        self.assertEqual(
            self.records["capability_matrix"]["qt_1_0_status"],
            "separate_admission_required",
        )
        self.assertTrue(
            self.records["capability_matrix"]["tui_ordinary_workflow_parity_blocking"]
        )
        by_id = {item["id"]: item for item in capabilities}
        self.assertEqual(by_id["accessibility.tui"]["required_interfaces"], ["tui"])
        self.assertTrue(
            all(
                item["id"] == "accessibility.winforms"
                or "tui" in item["required_interfaces"]
                for item in capabilities
                if item["scope"] == "technical_preview_required"
            )
        )
        self.assertTrue(
            all(item["invalidation_triggers"] for item in capabilities)
        )
        self.assertFalse(self.records["capability_matrix"]["completion_claim_authorized"])

        invalid = copy.deepcopy(self.records)
        invalid["capability_matrix"]["capability"][0]["status"] = (
            "census_pending"
        )
        self.assertIn(
            "workspace.open_create_inspect has an invalid census status",
            self.validate(invalid),
        )

    def test_capability_completion_requires_outcome_evidence_and_scope(self) -> None:
        invalid = copy.deepcopy(self.records)
        capability = invalid["capability_matrix"]["capability"][0]
        capability["scope"] = "unknown"
        capability["invalidation_triggers"] = []
        errors = self.validate(invalid)
        self.assertIn(
            "workspace.open_create_inspect has an invalid milestone scope",
            errors,
        )
        self.assertIn(
            "workspace.open_create_inspect must bind invalidation triggers",
            errors,
        )

    def test_duplicate_capability_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.records)
        invalid["capability_matrix"]["capability"].append(
            copy.deepcopy(invalid["capability_matrix"]["capability"][0])
        )
        errors = self.validate(invalid)
        self.assertIn("capability matrix repeats a capability id", errors)

    def test_withdrawal_never_moves_a_tag_or_automates_stable_action(self) -> None:
        invalid = copy.deepcopy(self.records)
        invalid["version_train"]["withdrawal"]["tag_move_allowed"] = True
        invalid["version_train"]["withdrawal"]["release_class"][-1][
            "automated_supersession_after_activation"
        ] = True
        errors = self.validate(invalid)
        self.assertIn(
            "version train withdrawal.tag_move_allowed must be False",
            errors,
        )
        self.assertIn("stable_1x withdrawal must remain human-controlled", errors)

    def test_general_schemas_are_closed_and_non_authorizing(self) -> None:
        for name, schema in self.schemas.items():
            with self.subTest(schema=name):
                self.assertFalse(schema["additionalProperties"])
                self.assertIn("authority", schema["required"])
                authority = schema["$defs"]["authority"]["properties"]
                self.assertTrue(authority)
                self.assertTrue(all(value["const"] is False for value in authority.values()))

    def test_schema_authority_promotion_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.schemas)
        invalid["release_candidate"]["$defs"]["authority"]["properties"][
            "publication"
        ]["const"] = True
        self.assertIn(
            "release_candidate authority schema must keep every grant false",
            self.validate(schemas=invalid),
        )

    def test_boolean_schema_cannot_bypass_false_authority(self) -> None:
        invalid = copy.deepcopy(self.schemas)
        invalid["release_candidate"]["$defs"]["authority"]["properties"][
            "publication"
        ] = True
        self.assertIn(
            "release_candidate authority schema must keep every grant false",
            self.validate(schemas=invalid),
        )


if __name__ == "__main__":
    unittest.main()
