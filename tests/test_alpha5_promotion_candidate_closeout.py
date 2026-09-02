# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from tools import alpha5_promotion_candidate_closeout_check as closeout


class Alpha5PromotionCandidateCloseoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.receipt = closeout.load_toml(closeout.RECEIPT)

    def repository_values(self) -> list[dict]:
        return [
            closeout.load_toml(path)
            for path in (
                closeout.RELEASE_INDEX,
                closeout.READINESS,
                closeout.PACKAGE_PRODUCERS,
                closeout.PROJECT,
                closeout.PLAN,
                closeout.VERSION_TRAIN,
                closeout.PROVIDER_LOCK,
                closeout.WORKSPACE_LOCK,
            )
        ]

    def manifest(self) -> dict:
        bundle = self.receipt["bundle"]
        rows = self.receipt["bundle_file"]
        return {
            "assets": [
                {key: row[key] for key in ("filename", "bytes", "sha256")}
                for row in rows
                if row["role"] == "product"
            ],
            "authority": copy.deepcopy(bundle["manifest_authority"]),
            "candidate_class": bundle["candidate_class"],
            "checksum": {
                key: next(row for row in rows if row["role"] == "checksum")[key]
                for key in ("filename", "bytes", "sha256")
            },
            "evidence": [
                {key: row[key] for key in ("filename", "bytes", "sha256")}
                for row in rows
                if row["role"] == "evidence"
            ],
            "github": {
                "job": bundle["github_job"],
                "repository": bundle["github_repository"],
                "run_attempt": str(bundle["github_run_attempt"]),
                "run_id": str(bundle["github_run_id"]),
                "workflow_ref": bundle["github_workflow_ref"],
            },
            "payload_equivalence_adapters": copy.deepcopy(
                bundle["payload_equivalence_adapters"]
            ),
            "platform_job": bundle["platform_job"],
            "schema": bundle["manifest_schema"],
            "source_revision": bundle["source_revision"],
            "source_tree": bundle["source_tree"],
            "status": bundle["manifest_status"],
            "version": bundle["version"],
        }

    def test_exact_receipt_and_repository_bindings_pass(self) -> None:
        self.assertEqual(closeout.validate_receipt(copy.deepcopy(self.receipt)), [])
        self.assertEqual(closeout.repository_problems(self.receipt), [])
        self.assertEqual(closeout.check(), [])

    def test_schema_is_closed_and_candidate_producer_alias_is_exact(self) -> None:
        changed = copy.deepcopy(self.receipt)
        changed["unexpected"] = True
        changed["candidate_producer_work_unit"] = "FACMAN-WRONG-01"
        problems = closeout.validate_receipt(changed)
        self.assertTrue(any("Additional properties" in item for item in problems), problems)
        self.assertTrue(
            any("candidate_producer_work_unit" in item for item in problems), problems
        )

    def test_revision_topology_and_non_circular_boundary_cannot_drift(self) -> None:
        changed = copy.deepcopy(self.receipt)
        changed["revision_topology"]["main_candidate_revision"] = "0" * 40
        changed["revision_topology"]["dev_sync_revision"] = "0" * 40
        changed["non_circular"]["closeout_revision_candidate_qualified"] = True
        changed["non_circular"]["future_revision_requires_new_candidate_run"] = False
        problems = closeout.validate_receipt(changed)
        self.assertTrue(any("revision_topology" in item for item in problems), problems)
        self.assertTrue(any("non_circular" in item for item in problems), problems)
        self.assertTrue(any("distinct" in item for item in problems), problems)

    def test_failure_chronology_jobs_and_artifacts_are_exact(self) -> None:
        changed = copy.deepcopy(self.receipt)
        changed["failure_chain"][0]["request_timestamp"] = "2026-09-01T00:00:00Z"
        changed["failure_chain"][2]["linux_artifact_digest"] = "sha256:" + "0" * 64
        changed["job"][4]["id"] = 1
        changed["artifact"][0]["digest"] = "sha256:" + "1" * 64
        problems = closeout.validate_receipt(changed)
        self.assertTrue(any("failure_chain" in item for item in problems), problems)
        self.assertTrue(any("job" in item for item in problems), problems)
        self.assertTrue(any("artifact" in item for item in problems), problems)

    def test_exact_fourteen_file_manifest_cross_binding(self) -> None:
        manifest = self.manifest()
        self.assertEqual(
            closeout.validate_downloaded_manifest(self.receipt, manifest), []
        )
        changed = copy.deepcopy(manifest)
        changed["source_revision"] = "0" * 40
        changed["assets"][0]["sha256"] = "0" * 64
        changed["evidence"].pop()
        changed["authority"]["publication"] = True
        problems = closeout.validate_downloaded_manifest(self.receipt, changed)
        self.assertTrue(any("source_revision" in item for item in problems), problems)
        self.assertTrue(any("assets" in item for item in problems), problems)
        self.assertTrue(any("evidence" in item for item in problems), problems)
        self.assertTrue(any("authority" in item for item in problems), problems)

    def test_provider_pins_and_all_authority_remain_closed(self) -> None:
        changed = copy.deepcopy(self.receipt)
        changed["provider"][0]["workspace_pin"] = "0" * 40
        changed["authority"]["publication"] = True
        changed["bundle"]["manifest_authority"]["signing"] = True
        problems = closeout.validate_receipt(changed)
        self.assertTrue(any("provider" in item for item in problems), problems)
        self.assertTrue(any("authority" in item for item in problems), problems)
        self.assertTrue(any("bundle" in item for item in problems), problems)

    def test_bundle_custody_locators_are_machine_independent(self) -> None:
        bundle = self.receipt["bundle"]
        for key in ("marker_root_locator", "download_root_locator"):
            locator = bundle[key]
            self.assertTrue(locator.startswith("facman-development://tasks/"))
            self.assertNotIn("\\", locator)
            self.assertNotIn("C:", locator)
            self.assertNotIn("/Users/", locator)
            self.assertNotIn("/home/", locator)

    def test_archive_index_digest_is_lf_canonical_across_checkouts(self) -> None:
        canonical = b'{\n  "schema": "aide.history_index.v1"\n}\n'
        windows = canonical.replace(b"\n", b"\r\n")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lf_path = root / "lf.json"
            crlf_path = root / "crlf.json"
            lf_path.write_bytes(canonical)
            crlf_path.write_bytes(windows)
            self.assertEqual(
                closeout.sha256_text_lf(lf_path),
                closeout.sha256_text_lf(crlf_path),
            )
        self.assertEqual(
            closeout.sha256_text_lf(closeout.ARCHIVE_INDEX),
            closeout.ARCHIVE_SHA256,
        )

    def test_release_index_and_truth_drift_are_rejected(self) -> None:
        values = self.repository_values()
        values[0]["alpha5_promotion_candidate_closeout"] = "release/index/wrong.toml"
        values[1]["exact_candidate"]["workflow_run"] = 1
        next(
            row for row in values[2]["producer"] if row["id"] == "platform_self_setup"
        )["payload_equivalence_candidate_run"] = 1
        values[3]["alpha5_beta_readiness"]["candidate_run"] = 1
        next(
            row for row in values[4]["workunit"] if row["id"] == closeout.WORK_UNIT
        )["base_revision"] = "0" * 40
        problems = closeout.validate_repository_bindings(self.receipt, *values)
        self.assertTrue(any("release index" in item for item in problems), problems)
        self.assertTrue(any("foundation readiness" in item for item in problems), problems)
        self.assertTrue(any("package producer" in item for item in problems), problems)
        self.assertTrue(any("project" in item for item in problems), problems)
        self.assertTrue(any("canonical plan" in item for item in problems), problems)

    def test_plan_lifecycle_accepts_only_the_pending_closeout_transition(self) -> None:
        values = self.repository_values()
        planned = next(
            row
            for row in values[4]["workunit"]
            if row["id"] == closeout.WORK_UNIT
        )
        planned["status"] = "verified_pending_closeout"
        self.assertEqual(
            closeout.validate_repository_bindings(self.receipt, *values), []
        )
        planned["status"] = "complete"
        problems = closeout.validate_repository_bindings(self.receipt, *values)
        self.assertTrue(any("canonical plan" in item for item in problems), problems)


if __name__ == "__main__":
    unittest.main()
