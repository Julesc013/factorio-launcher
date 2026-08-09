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
        cls.readme = release_programme_check.LEDGER_README.read_text(encoding="utf-8")

    def validate(self, records: dict | None = None, schemas: dict | None = None) -> list[str]:
        return release_programme_check.validate(
            records if records is not None else copy.deepcopy(self.records),
            schemas if schemas is not None else copy.deepcopy(self.schemas),
            self.readme,
        )

    def test_canonical_release_programme_is_valid(self) -> None:
        self.assertEqual(release_programme_check.check(), [])

    def test_release_index_binds_every_canonical_programme_record(self) -> None:
        invalid = copy.deepcopy(self.release_index)
        invalid["milestones"] = "release/index/not-the-milestones.toml"
        errors = release_programme_check.validate(
            copy.deepcopy(self.records),
            copy.deepcopy(self.schemas),
            self.readme,
            invalid,
        )
        self.assertIn(
            "release index does not bind milestones to "
            "release/index/milestones.v1.toml",
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

    def test_every_policy_is_ratified_design_pending_activation(self) -> None:
        for name, record in self.records.items():
            with self.subTest(record=name):
                self.assertEqual(record["design_status"], "ratified")
                self.assertEqual(record["activation_status"], "pending_workunits")
                self.assertTrue(record["activation_workunits"])
                self.assertTrue(all(value is False for value in record["authority"].values()))

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
        self.assertEqual(classes["beta"]["source_ref"], "release/<minor>")
        self.assertTrue(classes["beta"]["human_receipt_required"])
        self.assertEqual(classes["stable_0x"]["source_ref"], "main")
        self.assertTrue(classes["stable_0x"]["human_receipt_required"])
        self.assertTrue(self.records["version_train"]["published_tags_are_immutable"])
        self.assertFalse(self.records["version_train"]["tag_every_commit"])
        self.assertFalse(
            self.records["version_train"]["tracked_contract_identity_is_publishable"]
        )
        self.assertTrue(
            self.records["version_train"][
                "dynamic_snapshot_identity_projected_at_build_time"
            ]
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

    def test_c1_is_internal_and_public_beta_is_bounded(self) -> None:
        milestones = {
            item["id"]: item for item in self.records["milestones"]["milestone"]
        }
        self.assertFalse(milestones["FACMAN-C1"]["public_release"])
        self.assertEqual(
            milestones["0.1.0"]["required_frontends"],
            release_programme_check.PROJECTIONS_0_1,
        )
        self.assertEqual(
            milestones["1.0.0"]["required_frontends"],
            release_programme_check.PROJECTIONS_1_0,
        )

    def test_capability_matrix_is_seeded_and_command_census_not_started(self) -> None:
        capabilities = self.records["capability_matrix"]["capability"]
        self.assertEqual(
            {item["id"] for item in capabilities},
            release_programme_check.SEED_CAPABILITY_IDS,
        )
        self.assertEqual(
            self.records["capability_matrix"]["matrix_scope"],
            "seed_release_slices",
        )
        self.assertEqual(self.records["capability_matrix"]["census_state"], "not_started")
        self.assertFalse(
            self.records["capability_matrix"]["command_level_census_complete"]
        )
        self.assertTrue(
            self.records["capability_matrix"]["one_row_per_command_census_required"]
        )
        self.assertTrue(
            all(item["implementation_state"] == "census_pending" for item in capabilities)
        )
        self.assertFalse(self.records["capability_matrix"]["completion_claim_authorized"])

    def test_capability_completion_requires_evidence_and_projection_parity(self) -> None:
        invalid = copy.deepcopy(self.records)
        capability = invalid["capability_matrix"]["capability"][0]
        capability["implementation_state"] = "complete"
        capability["backend_status"] = "complete"
        errors = self.validate(invalid)
        self.assertIn(
            "workspace.onboarding completion requires complete evidence",
            errors,
        )
        self.assertTrue(
            any(
                "workspace.onboarding completion has incomplete projections" in error
                for error in errors
            ),
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
        invalid["withdrawal_policy"]["tag_move_allowed"] = True
        invalid["withdrawal_policy"]["release_class_authority"][-1][
            "automated_after_activation"
        ] = True
        errors = self.validate(invalid)
        self.assertIn("withdrawal policy tag_move_allowed must be False", errors)
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
