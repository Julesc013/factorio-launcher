# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools import alpha_tag_gate, alpha_tag_eligibility_producer as producer


class AlphaTagEligibilityProducerTests(unittest.TestCase):
    REVISION = "a" * 40
    TREE = "b" * 40
    CONTROL_REVISION = "c" * 40
    CONTROL_TREE = "d" * 40
    OBSERVED = dt.datetime(2026, 8, 29, 6, 0, tzinfo=dt.timezone.utc)

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        workspace = alpha_tag_gate._toml(alpha_tag_gate.WORKSPACE_LOCK_PATH)
        provider_lock = alpha_tag_gate._toml(alpha_tag_gate.PROVIDER_LOCK_PATH)
        workspace_by_id = {
            item["id"]: item for item in workspace["component"]
        }
        provider_by_id = {
            item["id"]: item for item in provider_lock["provider"]
        }
        self.provider_main = {
            provider_id: str(workspace_by_id[provider_id]["pin"])
            for provider_id in ("universal_launcher", "universal_setup")
        }
        qualification_providers = []
        candidate_providers = []
        for provider_id in ("universal_launcher", "universal_setup"):
            workspace_item = workspace_by_id[provider_id]
            provider_item = provider_by_id[provider_id]
            qualification_providers.append(
                {
                    "id": provider_id,
                    "source_revision": provider_item["source_revision"],
                    "source_tree": provider_item["source_tree"],
                    "package_version": provider_item["package_version"],
                    "package_identity": (
                        f"{provider_item['package_identity_kind']}:"
                        f"{provider_item['package_digest']}"
                    ),
                    "abi_version": provider_item["abi_version"],
                    "abi_manifest_sha256": provider_item["abi_manifest_digest"],
                    "contract_set_id": provider_item["contract_set_id"],
                    "contract_digest": provider_item["contract_digest"],
                }
            )
            candidate_providers.append(
                {
                    "id": provider_id,
                    "revision": workspace_item["pin"],
                    "tree": workspace_item["tree"],
                    "package_identity": (
                        f"{provider_item['package_identity_kind']}:"
                        f"{provider_item['package_digest']}"
                    ),
                    "abi": provider_item["abi_version"],
                    "contract_digest": provider_item["contract_digest"],
                }
            )
        specs = (
            (
                "windows_cli_x64_portable",
                "windows_portable_cli_x64",
                "facman-0.1.0-alpha.1-windows-cli-x64-portable.zip",
            ),
            (
                "windows_tui_x64_portable",
                "windows_portable_tui_x64",
                "facman-0.1.0-alpha.1-windows-tui-x64-portable.zip",
            ),
            (
                "windows_winforms_x64_portable",
                "windows_legacy_winforms_x64",
                "FacMan-0.1.0-alpha.1-windows-x64-portable.zip",
            ),
        )
        contract_set = alpha_tag_gate.current_contract_set_sha256()
        packages = []
        for index, (package_id, profile, filename) in enumerate(specs, start=1):
            packages.append(
                {
                    "id": package_id,
                    "profile": profile,
                    "filename": filename,
                    "source_revision": self.REVISION,
                    "source_tree": self.TREE,
                    "providers": copy.deepcopy(qualification_providers),
                    "contract_set_sha256": contract_set,
                    "state_identity": "facman.workspace.v1",
                    "package_tree_sha256": f"{index}" * 64,
                    "archive_sha256": f"{index + 3}" * 64,
                    "embedded_manifest_sha256": f"{index + 6}" * 64,
                    "sbom_sha256": "a" * 64,
                    "provenance_sha256": "b" * 64,
                    "licence_inventory_sha256": "c" * 64,
                    "file_count": 10 + index,
                    "uncompressed_bytes": 1000 + index,
                    "archive_bytes": 500 + index,
                }
            )
        self.qualification = {
            "schema": "facman.alpha1_final_dev_three_root_qualification.v1",
            "status": "pass",
            "source_revision": self.REVISION,
            "source_tree": self.TREE,
            "root_count": 3,
            "roots": ["root1", "root2", "root3"],
            "packages": packages,
            "comparison_table_sha256": "e" * 64,
            "mismatch_count": 0,
            "mismatches": [],
            "classification": {
                "platform": "Windows 10/11 x64",
                "support": "unsupported alpha",
                "signed": False,
                "published": False,
                "distribution": "portable",
                "accepted_real_play_routes": 0,
            },
            "qualification": {
                "fresh_roots": "pass_in_every_root",
                "native_static_debug_release": "pass_in_every_root",
                "native_shared_debug_release": "pass_in_every_root",
                "package_runtime": "pass_in_every_root",
                "hash_manifest": "pass_in_every_root",
                "drift_refusal": "pass_in_every_root",
                "byte_identical_archives": "pass_in_every_root",
            },
            "authority": {
                "tagging": False,
                "signing": False,
                "publication": False,
                "support": False,
                "setup_mutation": False,
                "factorio_execution": False,
                "human_verdict": False,
            },
        }
        self.qualification_path = self.root / "three-root-qualification.v1.json"
        self._write(self.qualification_path, self.qualification)
        qualification_sha = hashlib.sha256(
            self.qualification_path.read_bytes()
        ).hexdigest()
        self.candidate = {
            "schema": "facman.release_candidate.v1",
            "candidate_id": "facman-0.1.0-alpha.1-windows-x64-package-set",
            "version": "0.1.0-alpha.1",
            "release_class": "alpha",
            "status": "qualified",
            "source": {
                "revision": self.REVISION,
                "tree": self.TREE,
                "ref": "dev",
                "ref_kind": "dev",
                "clean": True,
            },
            "providers": {
                "workspace_lock_sha256": producer.sha256(
                    alpha_tag_gate.WORKSPACE_LOCK_PATH
                ),
                "provider_lock_sha256": producer.sha256(
                    alpha_tag_gate.PROVIDER_LOCK_PATH
                ),
                "identities": candidate_providers,
            },
            "resolution": {
                "schema": "facman.alpha1_final_dev_three_root_qualification.v1",
                "root_sha256": self.qualification["comparison_table_sha256"],
            },
            "artifacts": [
                {
                    "name": item["filename"],
                    "bytes": item["archive_bytes"],
                    "sha256": item["archive_sha256"],
                    "media_type": "application/zip",
                    "signed": False,
                    "published": False,
                }
                for item in packages
            ],
            "evidence": {
                "test_summary_sha256": qualification_sha,
                "sbom_sha256": "d" * 64,
                "provenance_sha256": "f" * 64,
                "known_limitations": ["test fixture"],
            },
            "three_key": {
                "implementation": {
                    "role": "implementation",
                    "result": "pass",
                    "evidence_sha256": self.qualification[
                        "comparison_table_sha256"
                    ],
                },
                "assurance": {
                    "role": "assurance",
                    "result": "pass",
                    "evidence_sha256": qualification_sha,
                },
                "policy": {
                    "role": "control",
                    "result": "pass",
                    "evidence_sha256": producer.sha256(
                        producer.ALPHA_RELEASE_SOURCE
                    ),
                },
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
        self.candidate_path = self.root / "candidate.v1.json"
        self._write(self.candidate_path, self.candidate)
        policy = alpha_tag_gate._toml(alpha_tag_gate.POLICY_PATH)
        self.check_runs = {
            "check_runs": [
                {
                    "name": name,
                    "head_sha": self.REVISION,
                    "status": "completed",
                    "conclusion": "success",
                    "completed_at": "2026-08-29T05:59:00Z",
                    "app": {"id": 15368},
                }
                for name in policy["required_checks"]
            ]
        }
        self.branch_rules = [
            {
                "type": "required_status_checks",
                "parameters": {
                    "strict_required_status_checks_policy": True,
                    "required_status_checks": [
                        {"context": name, "integration_id": 15368}
                        for name in policy["required_checks"]
                    ],
                },
            }
        ]
        self.tag_ruleset_observation_path = (
            alpha_tag_gate.TAG_RULESET_OBSERVATION_PATH
        )
        self.tag_ruleset_observation = alpha_tag_gate._json(
            self.tag_ruleset_observation_path
        )
        live_ruleset = copy.deepcopy(self.tag_ruleset_observation["ruleset"])
        live_ruleset.pop("bypass_actors")
        self.tag_rulesets = [live_ruleset]

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def _write(path: Path, value: dict[str, object]) -> None:
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def produce(self, **overrides: object) -> tuple[dict, dict]:
        arguments = {
            "candidate_path": self.candidate_path,
            "qualification_path": self.qualification_path,
            "product_revision": self.REVISION,
            "product_tree": self.TREE,
            "checkout_clean": True,
            "protected_dev_revision": self.REVISION,
            "github_ref": {"object": {"sha": self.REVISION}},
            "github_check_runs": self.check_runs,
            "github_branch_rules": self.branch_rules,
            "github_tag_rulesets": self.tag_rulesets,
            "tag_ruleset_observation": self.tag_ruleset_observation,
            "tag_ruleset_observation_path": self.tag_ruleset_observation_path,
            "provider_main_revisions": self.provider_main,
            "existing_tags": [],
            "existing_ledger_versions": [],
            "qualification_run_id": 33200886091,
            "control_source_revision": self.CONTROL_REVISION,
            "control_source_tree": self.CONTROL_TREE,
            "control_source_ref": "task/facman-alpha-tag-eligibility-producer-01",
            "github_run_id": 12345,
            "observed_at": self.OBSERVED,
        }
        arguments.update(overrides)
        return producer.produce_records(**arguments)

    def test_produces_gate_valid_exact_records(self) -> None:
        eligibility, receipt = self.produce()
        self.assertEqual(eligibility["tag"], "v0.1.0-alpha.1")
        self.assertEqual(eligibility["candidate"]["sha256"], producer.sha256(self.candidate_path))
        self.assertEqual(len(eligibility["checks"]["runs"]), 11)
        self.assertEqual(receipt["qualification"]["run_id"], 33200886091)
        self.assertEqual(receipt["tag_ruleset_ids"], [21787868])
        self.assertEqual(
            receipt["tag_ruleset_observation"]["sha256"],
            producer.sha256(self.tag_ruleset_observation_path),
        )
        self.assertEqual(receipt["product_source"]["revision"], self.REVISION)
        self.assertEqual(
            receipt["control_plane_source"]["revision"], self.CONTROL_REVISION
        )
        self.assertTrue(all(value is False for value in receipt["authority"].values()))
        eligibility_path = self.root / "eligibility.v1.json"
        eligibility_path.write_bytes(producer.json_bytes(eligibility))
        self.assertEqual(
            alpha_tag_gate.validate_producer_receipt(
                receipt,
                eligibility,
                eligibility_path=eligibility_path,
                candidate_path=self.candidate_path,
                eligibility_run_id=12345,
                control_revision=self.CONTROL_REVISION,
                control_tree=self.CONTROL_TREE,
                control_clean=True,
                github_tag_rulesets=self.tag_rulesets,
                tag_ruleset_observation=self.tag_ruleset_observation,
                tag_ruleset_observation_path=self.tag_ruleset_observation_path,
            ),
            [],
        )

    def test_consumer_refuses_a_different_control_plane_commit(self) -> None:
        eligibility, receipt = self.produce()
        eligibility_path = self.root / "eligibility.v1.json"
        eligibility_path.write_bytes(producer.json_bytes(eligibility))
        problems = alpha_tag_gate.validate_producer_receipt(
            receipt,
            eligibility,
            eligibility_path=eligibility_path,
            candidate_path=self.candidate_path,
            eligibility_run_id=12345,
            control_revision="0" * 40,
            control_tree=self.CONTROL_TREE,
            control_clean=True,
            github_tag_rulesets=self.tag_rulesets,
            tag_ruleset_observation=self.tag_ruleset_observation,
            tag_ruleset_observation_path=self.tag_ruleset_observation_path,
        )
        self.assertTrue(any("reviewed producer source" in item for item in problems))

    def test_consumer_refuses_different_ruleset_observation_bytes(self) -> None:
        eligibility, receipt = self.produce()
        eligibility_path = self.root / "eligibility.v1.json"
        eligibility_path.write_bytes(producer.json_bytes(eligibility))
        changed_observation = copy.deepcopy(self.tag_ruleset_observation)
        changed_observation["observed_at"] = "2026-08-29T07:48:00Z"
        changed_path = self.root / "changed-ruleset-observation.json"
        self._write(changed_path, changed_observation)
        problems = alpha_tag_gate.validate_producer_receipt(
            receipt,
            eligibility,
            eligibility_path=eligibility_path,
            candidate_path=self.candidate_path,
            eligibility_run_id=12345,
            control_revision=self.CONTROL_REVISION,
            control_tree=self.CONTROL_TREE,
            control_clean=True,
            github_tag_rulesets=self.tag_rulesets,
            tag_ruleset_observation=changed_observation,
            tag_ruleset_observation_path=changed_path,
        )
        self.assertTrue(any("reviewed bytes" in item for item in problems))

    def test_refuses_provider_main_drift(self) -> None:
        invalid = dict(self.provider_main)
        invalid["universal_launcher"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "provider pins"):
            self.produce(provider_main_revisions=invalid)

    def test_refuses_candidate_package_substitution(self) -> None:
        self.candidate["artifacts"][0]["sha256"] = "0" * 64
        self._write(self.candidate_path, self.candidate)
        with self.assertRaisesRegex(ValueError, "candidate package bytes"):
            self.produce()

    def test_refuses_stale_required_checks(self) -> None:
        stale = copy.deepcopy(self.check_runs)
        for run in stale["check_runs"]:
            run["completed_at"] = "2026-08-27T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "fresh required check"):
            self.produce(github_check_runs=stale)


if __name__ == "__main__":
    unittest.main()
