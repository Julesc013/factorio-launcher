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
from unittest import mock

from tools import alpha_tag_gate


class AlphaTagGateTests(unittest.TestCase):
    NOW = dt.datetime(2026, 8, 27, 0, 0, tzinfo=dt.timezone.utc)
    REVISION = "1" * 40
    TREE = "2" * 40

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.candidate_path = self.root / "candidate.v1.json"
        evidence = {
            "implementation": "3" * 64,
            "assurance": "4" * 64,
            "control": "5" * 64,
        }
        workspace_lock = alpha_tag_gate._toml(alpha_tag_gate.WORKSPACE_LOCK_PATH)
        workspace_components = {
            item["id"]: item for item in workspace_lock["component"]
        }
        provider_lock = alpha_tag_gate._toml(alpha_tag_gate.PROVIDER_LOCK_PATH)
        provider_records = {item["id"]: item for item in provider_lock["provider"]}
        workspace_lock_sha256 = alpha_tag_gate._sha256(
            alpha_tag_gate.WORKSPACE_LOCK_PATH
        )
        provider_lock_sha256 = alpha_tag_gate._sha256(
            alpha_tag_gate.PROVIDER_LOCK_PATH
        )
        self.candidate = {
            "schema": "facman.release_candidate.v1",
            "candidate_id": "facman-alpha-1-test",
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
                "workspace_lock_sha256": workspace_lock_sha256,
                "provider_lock_sha256": provider_lock_sha256,
                "identities": [
                    {
                        "id": provider,
                        "revision": workspace_components[provider]["pin"],
                        "tree": workspace_components[provider]["tree"],
                        "package_identity": provider_records[provider]["package_digest"],
                        "abi": provider_records[provider]["abi_version"],
                        "contract_digest": provider_records[provider]["contract_digest"],
                    }
                    for provider in ("universal_launcher", "universal_setup")
                ],
            },
            "resolution": {
                "schema": "facman.release_resolution.v1",
                "root_sha256": "a" * 64,
            },
            "artifacts": [
                {
                    "name": name,
                    "bytes": 100,
                    "sha256": str(index) * 64,
                    "media_type": "application/zip",
                    "signed": False,
                    "published": False,
                }
                for index, name in enumerate(
                    (
                        "facman-0.1.0-alpha.1-windows-cli-x64-portable.zip",
                        "facman-0.1.0-alpha.1-windows-tui-x64-portable.zip",
                        "FacMan-0.1.0-alpha.1-windows-x64-portable.zip",
                    ),
                    start=6,
                )
            ],
            "evidence": {
                "test_summary_sha256": "c" * 64,
                "sbom_sha256": "d" * 64,
                "provenance_sha256": "e" * 64,
                "known_limitations": ["test fixture"],
            },
            "three_key": {
                "implementation": {
                    "role": "implementation",
                    "result": "pass",
                    "evidence_sha256": evidence["implementation"],
                },
                "assurance": {
                    "role": "assurance",
                    "result": "pass",
                    "evidence_sha256": evidence["assurance"],
                },
                "policy": {
                    "role": "control",
                    "result": "pass",
                    "evidence_sha256": evidence["control"],
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
        self._write_candidate()
        policy = alpha_tag_gate._toml(alpha_tag_gate.POLICY_PATH)
        self.eligibility = {
            "schema": "facman.alpha_tag_eligibility.v1",
            "work_unit": "FACMAN-AUTONOMOUS-ALPHA-DELEGATION-01",
            "version": "0.1.0-alpha.1",
            "tag": "v0.1.0-alpha.1",
            "release_significance": "security_or_authority_boundary",
            "source": {
                "revision": self.REVISION,
                "tree": self.TREE,
                "ref": "dev",
                "protected": True,
                "clean": True,
            },
            "candidate": {
                "path": self.candidate_path.name,
                "sha256": self._candidate_sha256(),
                "status": "qualified",
                "three_root_reproducible": True,
            },
            "providers": {
                "workspace_lock_sha256": workspace_lock_sha256,
                "provider_lock_sha256": provider_lock_sha256,
                "canonical_main_reachable": True,
                "mixed_identity": False,
            },
            "contracts": {
                "contract_set_sha256": alpha_tag_gate.current_contract_set_sha256(),
                "state_identity": "facman.workspace.v1",
                "package_profiles": [
                    "windows_portable_cli_x64",
                    "windows_portable_tui_x64",
                    "windows_legacy_winforms_x64",
                ],
            },
            "checks": {
                "source_revision": self.REVISION,
                "observed_at": "2026-08-27T00:00:00Z",
                "required_unknown_skips": 0,
                "runs": [
                    {
                        "name": name,
                        "head_sha": self.REVISION,
                        "status": "completed",
                        "conclusion": "success",
                        "app_id": 15368,
                    }
                    for name in policy["required_checks"]
                ],
            },
            "attestations": [
                {
                    "role": role,
                    "issuer": issuer,
                    "source_revision": self.REVISION,
                    "source_tree": self.TREE,
                    "result": "pass",
                    "evidence_sha256": evidence[role],
                }
                for role, issuer in (
                    ("implementation", "implementation-agent"),
                    ("assurance", "assurance-agent"),
                    ("control", "control-agent"),
                )
            ],
            "allocation": {
                "next_number": 1,
                "existing_versions": [],
                "number_reused": False,
                "retroactive_bulk_allocation": False,
            },
            "authority": {
                "tag_creation": True,
                "publication": False,
                "signing": False,
                "beta_rc_stable_tags": False,
                "protected_dev_merge": False,
                "route_effects": False,
                "support_activation": False,
                "human_verdict": False,
            },
        }
        self.tag_ruleset_observation = alpha_tag_gate._json(
            alpha_tag_gate.TAG_RULESET_OBSERVATION_PATH
        )
        live_ruleset = copy.deepcopy(self.tag_ruleset_observation["ruleset"])
        live_ruleset.pop("bypass_actors")
        self.github_tag_rulesets = [live_ruleset]
        self.github_ref = {"object": {"sha": self.REVISION}}
        self.github_check_runs = {
            "check_runs": [
                {
                    "name": name,
                    "head_sha": self.REVISION,
                    "status": "completed",
                    "conclusion": "success",
                    "completed_at": "2026-08-27T00:00:00Z",
                    "app": {"id": 15368},
                }
                for name in policy["required_checks"]
            ]
        }
        self.github_branch_rules = [
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

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_candidate(self) -> None:
        self.candidate_path.write_text(
            json.dumps(self.candidate, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _candidate_sha256(self) -> str:
        return hashlib.sha256(self.candidate_path.read_bytes()).hexdigest()

    def validate(
        self,
        eligibility: dict | None = None,
        candidate: dict | None = None,
        **overrides: object,
    ) -> list[str]:
        selected_candidate = candidate if candidate is not None else copy.deepcopy(self.candidate)
        self.candidate = selected_candidate
        self._write_candidate()
        selected_eligibility = (
            eligibility if eligibility is not None else copy.deepcopy(self.eligibility)
        )
        selected_eligibility["candidate"]["sha256"] = self._candidate_sha256()
        arguments = {
            "candidate_path": self.candidate_path,
            "protected_dev_revision": self.REVISION,
            "head_revision": self.REVISION,
            "head_tree": self.TREE,
            "checkout_clean": True,
            "existing_tags": set(),
            "existing_ledger_versions": set(),
            "github_ref": copy.deepcopy(self.github_ref),
            "github_check_runs": copy.deepcopy(self.github_check_runs),
            "github_branch_rules": copy.deepcopy(self.github_branch_rules),
            "github_tag_rulesets": copy.deepcopy(self.github_tag_rulesets),
            "tag_ruleset_observation": copy.deepcopy(
                self.tag_ruleset_observation
            ),
            "now": self.NOW,
        }
        arguments.update(overrides)
        return alpha_tag_gate.validate(
            selected_eligibility,
            selected_candidate,
            **arguments,
        )

    def test_canonical_delegation_policy_is_bounded_and_active(self) -> None:
        self.assertEqual(alpha_tag_gate.validate_policy(), [])

    def test_exact_alpha_one_is_eligible_without_prior_tags(self) -> None:
        self.assertEqual(self.validate(), [])

    def test_prospective_ledger_reservation_is_not_prior_issuance(self) -> None:
        ledger_root = self.root / "ledger"
        version_root = ledger_root / "0.1.0-alpha.1"
        version_root.mkdir(parents=True)
        (version_root / "prospective-entry.v1.json").write_text(
            json.dumps(
                {
                    "schema": "facman.prospective_release_ledger_entry.v1",
                    "version": "0.1.0-alpha.1",
                    "tag": "v0.1.0-alpha.1",
                }
            ),
            encoding="utf-8",
        )
        with mock.patch.object(alpha_tag_gate, "LEDGER_ROOT", ledger_root):
            self.assertEqual(alpha_tag_gate.ledger_versions(), set())
            (version_root / "entry.v1.json").write_text(
                json.dumps(
                    {
                        "schema": "facman.release_ledger_entry.v1",
                        "version": "0.1.0-alpha.1",
                        "tag": "v0.1.0-alpha.1",
                        "immutable": True,
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                alpha_tag_gate.ledger_versions(), {"0.1.0-alpha.1"}
            )

    def test_protected_dev_movement_invalidates_eligibility(self) -> None:
        problems = self.validate(protected_dev_revision="0" * 40)
        self.assertTrue(any("protected dev moved" in item for item in problems), problems)

    def test_dirty_source_is_rejected(self) -> None:
        problems = self.validate(checkout_clean=False)
        self.assertTrue(any("checkout is dirty" in item for item in problems), problems)

    def test_mixed_provider_identity_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.eligibility)
        invalid["providers"]["mixed_identity"] = True
        problems = self.validate(invalid)
        self.assertTrue(
            any("schema rejection" in item or "mixed or non-canonical" in item for item in problems),
            problems,
        )

    def test_provider_locks_and_identities_are_not_self_asserted(self) -> None:
        invalid = copy.deepcopy(self.eligibility)
        invalid["providers"]["workspace_lock_sha256"] = "6" * 64
        candidate = copy.deepcopy(self.candidate)
        candidate["providers"]["workspace_lock_sha256"] = "6" * 64
        problems = self.validate(invalid, candidate)
        self.assertTrue(any("current source tree" in item for item in problems), problems)

        candidate = copy.deepcopy(self.candidate)
        candidate["providers"]["identities"][0]["revision"] = "8" * 40
        problems = self.validate(candidate=candidate)
        self.assertTrue(any("differs from canonical locks" in item for item in problems), problems)

    def test_non_release_significant_change_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.eligibility)
        invalid["release_significance"] = "prose_only_without_contract_or_package_effect"
        problems = self.validate(invalid)
        self.assertTrue(
            any("schema rejection" in item or "not release-significant" in item for item in problems),
            problems,
        )

    def test_stale_checks_are_rejected(self) -> None:
        problems = self.validate(now=self.NOW + dt.timedelta(hours=25))
        self.assertTrue(any("observation is stale" in item for item in problems), problems)

    def test_missing_required_check_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.eligibility)
        invalid["checks"]["runs"].pop()
        problems = self.validate(invalid)
        self.assertTrue(any("every required check" in item for item in problems), problems)

    def test_unknown_required_skip_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.eligibility)
        invalid["checks"]["required_unknown_skips"] = 1
        problems = self.validate(invalid)
        self.assertTrue(
            any("schema rejection" in item or "unknown skips" in item for item in problems),
            problems,
        )

    def test_non_successful_required_check_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.eligibility)
        invalid["checks"]["runs"][0]["conclusion"] = "failure"
        problems = self.validate(invalid)
        self.assertTrue(
            any("schema rejection" in item or "not successful" in item for item in problems),
            problems,
        )

    def test_same_issuer_cannot_fill_multiple_keys(self) -> None:
        invalid = copy.deepcopy(self.eligibility)
        invalid["attestations"][1]["issuer"] = invalid["attestations"][0]["issuer"]
        problems = self.validate(invalid)
        self.assertTrue(any("not logically independent" in item for item in problems), problems)

    def test_non_passing_attestation_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.eligibility)
        invalid["attestations"][0]["result"] = "fail"
        problems = self.validate(invalid)
        self.assertTrue(
            any("schema rejection" in item or "attestation is not passing" in item for item in problems),
            problems,
        )

    def test_existing_tag_forces_the_next_never_used_number(self) -> None:
        invalid = copy.deepcopy(self.eligibility)
        invalid["allocation"]["existing_versions"] = ["0.1.0-alpha.1"]
        invalid["allocation"]["next_number"] = 2
        problems = self.validate(invalid, existing_tags={"v0.1.0-alpha.1"})
        self.assertTrue(any("requested alpha version" in item for item in problems), problems)
        self.assertTrue(any("already exists" in item for item in problems), problems)

    def test_requested_tag_must_match_tracked_product_version(self) -> None:
        invalid = copy.deepcopy(self.eligibility)
        invalid["version"] = "0.1.0-alpha.2"
        invalid["tag"] = "v0.1.0-alpha.2"
        invalid["allocation"]["next_number"] = 2
        invalid["allocation"]["existing_versions"] = ["0.1.0-alpha.1"]
        candidate = copy.deepcopy(self.candidate)
        candidate["version"] = "0.1.0-alpha.2"
        problems = self.validate(
            invalid,
            candidate,
            existing_ledger_versions={"0.1.0-alpha.1"},
        )
        self.assertTrue(any("historical alpha release source" in item for item in problems), problems)

    def test_contract_state_and_package_identities_are_not_self_asserted(self) -> None:
        for field, value, message in (
            ("contract_set_sha256", "f" * 64, "contract-set digest"),
            ("state_identity", "invented.workspace.v9", "state identity"),
            ("package_profiles", ["invented_profile"], "package profiles"),
        ):
            with self.subTest(field=field):
                invalid = copy.deepcopy(self.eligibility)
                invalid["contracts"][field] = value
                problems = self.validate(invalid)
                self.assertTrue(
                    any(message in item or "schema rejection" in item for item in problems),
                    problems,
                )

    def test_authenticated_github_checks_cannot_be_self_asserted(self) -> None:
        github_checks = {
            "check_runs": [
                {
                    "name": run["name"],
                    "head_sha": self.REVISION,
                    "status": "completed",
                    "conclusion": "success",
                    "completed_at": "2026-08-27T00:00:00Z",
                    "app": {"id": 15368},
                }
                for run in self.eligibility["checks"]["runs"][:-1]
            ]
        }
        problems = self.validate(github_check_runs=github_checks)
        self.assertTrue(any("authenticated GitHub observation lacks" in item for item in problems), problems)

    def test_authenticated_observations_are_mandatory(self) -> None:
        for field, message in (
            ("github_ref", "dev observation was not supplied"),
            ("github_check_runs", "check-run observation was not supplied"),
            ("github_branch_rules", "dev-rule observation was not supplied"),
            ("github_tag_rulesets", "tag-protection rules were not supplied"),
            (
                "tag_ruleset_observation",
                "user-context tag-ruleset observation was not supplied",
            ),
        ):
            with self.subTest(field=field):
                problems = self.validate(**{field: None})
                self.assertTrue(any(message in item for item in problems), problems)

    def test_stale_authenticated_check_run_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.github_check_runs)
        invalid["check_runs"][0]["completed_at"] = "2026-08-25T00:00:00Z"
        problems = self.validate(github_check_runs=invalid)
        self.assertTrue(any("fresh successful required check" in item for item in problems), problems)

    def test_authenticated_dev_rules_must_match_the_approved_check_set(self) -> None:
        policy = alpha_tag_gate._toml(alpha_tag_gate.POLICY_PATH)
        github_rules = [
            {
                "type": "required_status_checks",
                "parameters": {
                    "strict_required_status_checks_policy": True,
                    "required_status_checks": [
                        {"context": name, "integration_id": 15368}
                        for name in policy["required_checks"][:-1]
                    ],
                },
            }
        ]
        problems = self.validate(github_branch_rules=github_rules)
        self.assertTrue(any("dev rules do not strictly require" in item for item in problems), problems)

    def test_authenticated_dev_rules_accept_the_exact_approved_check_set(self) -> None:
        policy = alpha_tag_gate._toml(alpha_tag_gate.POLICY_PATH)
        github_rules = [
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
        self.assertEqual(self.validate(github_branch_rules=github_rules), [])

    def test_tag_rules_must_prevent_updates_and_deletion_without_bypass(self) -> None:
        invalid = copy.deepcopy(self.github_tag_rulesets)
        invalid[0]["rules"] = [{"type": "deletion"}]
        problems = self.validate(github_tag_rulesets=invalid)
        self.assertTrue(any("prevent alpha tag updates and deletion" in item for item in problems))

        invalid = copy.deepcopy(self.github_tag_rulesets)
        invalid[0]["conditions"]["ref_name"]["exclude"] = [
            "refs/tags/v0.1.0-alpha.9"
        ]
        problems = self.validate(github_tag_rulesets=invalid)
        self.assertTrue(any("prevent alpha tag updates and deletion" in item for item in problems))

        invalid = copy.deepcopy(self.github_tag_rulesets)
        invalid[0]["bypass_actors"] = [{"actor_type": "RepositoryRole"}]
        problems = self.validate(github_tag_rulesets=invalid)
        self.assertTrue(any("prevent alpha tag updates and deletion" in item for item in problems))

    def test_hidden_bypass_field_requires_unchanged_user_context_observation(self) -> None:
        self.assertNotIn("bypass_actors", self.github_tag_rulesets[0])
        self.assertEqual(self.validate(), [])

        invalid = copy.deepcopy(self.github_tag_rulesets)
        invalid[0]["updated_at"] = "2026-08-29T07:47:37Z"
        problems = self.validate(github_tag_rulesets=invalid)
        self.assertTrue(any("prevent alpha tag updates and deletion" in item for item in problems))

        invalid_observation = copy.deepcopy(self.tag_ruleset_observation)
        invalid_observation["ruleset"]["bypass_actors"] = [
            {"actor_type": "RepositoryRole"}
        ]
        problems = self.validate(tag_ruleset_observation=invalid_observation)
        self.assertTrue(any("tag ruleset observation" in item for item in problems))

    def test_publication_and_signing_remain_closed(self) -> None:
        invalid = copy.deepcopy(self.eligibility)
        invalid["authority"]["publication"] = True
        invalid["authority"]["signing"] = True
        problems = self.validate(invalid)
        self.assertTrue(any("authority exceeds" in item for item in problems), problems)

    def test_next_number_never_fills_a_reused_gap(self) -> None:
        self.assertEqual(
            alpha_tag_gate.next_alpha_number(
                {"0.1.0-alpha.1", "0.1.0-alpha.3"}
            ),
            4,
        )

    def test_reuse_or_bulk_allocation_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.eligibility)
        invalid["allocation"]["number_reused"] = True
        invalid["allocation"]["retroactive_bulk_allocation"] = True
        problems = self.validate(invalid)
        self.assertTrue(
            any("schema rejection" in item or "reuse or retroactive" in item for item in problems),
            problems,
        )


if __name__ == "__main__":
    unittest.main()
