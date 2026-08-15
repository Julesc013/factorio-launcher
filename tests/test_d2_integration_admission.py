# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools import d2_integration_admission as admission


class D2IntegrationAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name)
        self.git("init", "-b", "dev")
        self.git("config", "user.name", "FacMan Test")
        self.git("config", "user.email", "facman-test@example.invalid")
        (self.repo / "base.txt").write_text("base\n", encoding="utf-8")
        self.git("add", "base.txt")
        self.git("commit", "-m", "test: base")
        self.base = self.git("rev-parse", "HEAD")
        self.base_tree = self.git("rev-parse", "HEAD^{tree}")
        self.git("switch", "-c", "task/d2-test")
        (self.repo / "head.txt").write_text("head\n", encoding="utf-8")
        self.git("add", "head.txt")
        self.git("commit", "-m", "test: head")
        self.head = self.git("rev-parse", "HEAD")
        self.head_tree = self.git("rev-parse", "HEAD^{tree}")
        self.changed_digest = admission.changed_paths_sha256(["head.txt"])
        self.implementation_digest = "a" * 64
        self.assurance_digest = "b" * 64
        self.implementation = self.implementation_record()
        self.assurance = self.assurance_record()
        self.policy = self.policy_record()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.strip()

    def authority(self) -> dict[str, bool]:
        return {
            "production_credentials": False,
            "production_signing": False,
            "publication": False,
            "route_promotion": False,
            "human_verdict": False,
            "stable_promotion": False,
            "protected_branch_write": False,
            "self_merge": False,
        }

    def subject(self) -> dict[str, str]:
        return {
            "base_revision": self.base,
            "base_tree": self.base_tree,
            "head_revision": self.head,
            "head_tree": self.head_tree,
            "changed_paths_sha256": self.changed_digest,
        }

    def checks(self) -> list[dict[str, str]]:
        return [{"name": "required-ci", "state": "success", "head_revision": self.head}]

    def implementation_record(self) -> dict:
        return {
            "schema": "facman.d2_implementation_attestation.v1",
            "attestation_id": "facman.d2.implementation.test",
            "repository": "Julesc013/factorio-launcher",
            "workunit": "FACMAN-D2-TEST-01",
            "base": {"ref": "refs/heads/dev", "revision": self.base, "tree": self.base_tree},
            "head": {"ref": "refs/heads/task/d2-test", "revision": self.head, "tree": self.head_tree},
            "changed_paths_sha256": self.changed_digest,
            "author_identity": "implementation@example.invalid",
            "test_evidence": [{"id": "focused-tests", "status": "pass", "sha256": "c" * 64}],
            "high_risk_surfaces": ["branch-policy"],
            "created_at": "2026-08-16T00:00:00Z",
            "authority": self.authority(),
        }

    def assurance_record(self) -> dict:
        return {
            "schema": "facman.d2_independent_assurance.v1",
            "attestation_id": "facman.d2.assurance.test",
            "repository": "Julesc013/factorio-launcher",
            "workunit": "FACMAN-D2-TEST-01",
            "subject": self.subject(),
            "implementation_attestation_sha256": self.implementation_digest,
            "assurance_identity": "assurance@example.invalid",
            "logically_independent": True,
            "checks": self.checks(),
            "findings": [],
            "unresolved_findings": 0,
            "high_risk_review_complete": True,
            "conclusion": "pass",
            "created_at": "2026-08-16T00:01:00Z",
            "authority": self.authority(),
        }

    def policy_record(self) -> dict:
        return {
            "schema": "facman.d2_policy_admission.v1",
            "admission_id": "facman.d2.policy.test",
            "repository": "Julesc013/factorio-launcher",
            "workunit": "FACMAN-D2-TEST-01",
            "subject": self.subject(),
            "implementation_attestation_sha256": self.implementation_digest,
            "assurance_attestation_sha256": self.assurance_digest,
            "policy_identity": "policy@example.invalid",
            "exact_head_immutable": True,
            "history_preserving_merge": True,
            "merge_method": "merge",
            "checks": self.checks(),
            "unresolved_review_threads": 0,
            "post_merge_verification_required": True,
            "d4_excluded": True,
            "owner_ratification": {"required": True, "status": "pending", "record_sha256": None},
            "decision": "ready_for_owner_ratification",
            "created_at": "2026-08-16T00:02:00Z",
            "authority": self.authority(),
        }

    def premerge(self, implementation: dict | None = None, assurance: dict | None = None, policy: dict | None = None) -> list[str]:
        return admission.validate_premerge(
            implementation or copy.deepcopy(self.implementation),
            assurance or copy.deepcopy(self.assurance),
            policy or copy.deepcopy(self.policy),
            implementation_sha256=self.implementation_digest,
            assurance_sha256=self.assurance_digest,
            repo_root=self.repo,
        )

    def test_exact_three_key_candidate_passes(self) -> None:
        self.assertEqual([], self.premerge())

    def test_same_identity_is_refused(self) -> None:
        assurance = copy.deepcopy(self.assurance)
        assurance["assurance_identity"] = self.implementation["author_identity"]
        self.assertTrue(any("distinct" in problem for problem in self.premerge(assurance=assurance)))

    def test_changed_path_drift_is_refused(self) -> None:
        implementation = copy.deepcopy(self.implementation)
        implementation["changed_paths_sha256"] = "d" * 64
        assurance = copy.deepcopy(self.assurance)
        policy = copy.deepcopy(self.policy)
        assurance["subject"]["changed_paths_sha256"] = "d" * 64
        policy["subject"]["changed_paths_sha256"] = "d" * 64
        self.assertTrue(any("changed-path" in problem for problem in self.premerge(implementation, assurance, policy)))

    def test_red_check_and_authority_grant_are_refused(self) -> None:
        assurance = copy.deepcopy(self.assurance)
        assurance["checks"][0]["state"] = "failure"
        implementation = copy.deepcopy(self.implementation)
        implementation["authority"]["publication"] = True
        problems = self.premerge(implementation=implementation, assurance=assurance)
        self.assertTrue(any("success" in problem for problem in problems))
        self.assertTrue(any("False" in problem for problem in problems))

    def test_normal_merge_and_exact_post_merge_checks_pass(self) -> None:
        self.git("switch", "dev")
        self.git("merge", "--no-ff", "--no-edit", self.head)
        merge_revision = self.git("rev-parse", "HEAD")
        checks = {
            "revision": merge_revision,
            "checks": [{"name": "post-merge-ci", "state": "success", "revision": merge_revision}],
        }
        self.assertEqual(
            [],
            admission.validate_postmerge(
                self.policy,
                merge_revision=merge_revision,
                integration_ref="refs/heads/dev",
                post_merge_checks=checks,
                repo_root=self.repo,
            ),
        )

    def test_non_merge_history_is_refused(self) -> None:
        checks = {
            "revision": self.head,
            "checks": [{"name": "post-merge-ci", "state": "success", "revision": self.head}],
        }
        problems = admission.validate_postmerge(
            self.policy,
            merge_revision=self.head,
            integration_ref="refs/heads/task/d2-test",
            post_merge_checks=checks,
            repo_root=self.repo,
        )
        self.assertTrue(any("two ordered parents" in problem for problem in problems))


if __name__ == "__main__":
    unittest.main()
