# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest
import json
import hashlib
import sys
import tempfile
from pathlib import Path

from tools import aide_compaction_check, project_state

sys.path.insert(0, str(project_state.ROOT / ".aide" / "scripts"))
import aide_lifecycle


class AideCompactionTests(unittest.TestCase):
    def test_queue_history_and_docs_are_compact_and_consistent(self) -> None:
        self.assertEqual([], aide_compaction_check.validate())

    def test_machine_state_has_every_required_truth_family(self) -> None:
        data = project_state.collect()
        for key in (
            "current_revisions", "active_work_unit", "last_closed_work_unit",
            "r3_8_repair", "r3_8_public_integration", "m1_managed_portable_install",
            "m1_public_integration",
            "m2_live_portable_setup",
            "universal_repository_licenses",
            "next_authority_gate",
            "quarantined_capabilities", "claim_levels", "provider_pins", "platforms",
            "known_blockers", "current_checkpoint", "completed_wave", "command_law",
            "machine_protocol", "execution", "release", "validation", "safe_beta",
        ):
            self.assertIn(key, data)
        self.assertFalse(data["truth_boundaries"][2].startswith("Automated checks pass"))

    def test_m2_wu1_closeout_preserves_provider_gate_and_catalog_truth(self) -> None:
        data = project_state.collect()
        self.assertEqual("m2-wu1-live-target-policy", data["current_checkpoint"])
        self.assertEqual("H1", data["next_authority_gate"])
        self.assertEqual("unavailable", data["execution"]["status"])
        self.assertEqual("Fail", data["execution"]["operator_verdict"])
        self.assertEqual("M2-WU2-PUBLIC-SETUP-LIFECYCLE-01", data["active_work_unit"])
        self.assertEqual(
            "active_public_lifecycle_activation",
            data["m2_live_portable_setup"]["status"],
        )
        self.assertEqual("pending", data["m2_live_portable_setup"]["operator_verdict"])
        self.assertEqual(
            "M2-WU1-LIVE-TARGET-POLICY-01",
            data["last_closed_work_unit"],
        )
        self.assertEqual("accepted_dev_integration_proof", data["m2_wu1_target_policy"]["status"])
        self.assertFalse(data["m2_wu1_target_policy"]["mutation_authority"])
        self.assertEqual("d96384bf8f48230256d35fa7015cbc7374e83319", data["m2_wu1_target_policy"]["facman_dev_integration_revision"])
        self.assertEqual("29318247825", data["m2_wu1_target_policy"]["facman_dev_ci_run"])
        self.assertEqual("active", data["m2_wu2_public_lifecycle"]["status"])
        self.assertTrue(data["m2_wu2_public_lifecycle"]["plan_commands_read_only"])
        self.assertFalse(data["m2_wu2_public_lifecycle"]["execution_authority"])
        self.assertEqual("closed", data["r3_8_repair"]["status"])
        self.assertEqual(
            "f10aef03517a86a7c9d6afaf8b75c19549b6fa51",
            data["r3_8_repair"]["dev_integration_revision"],
        )
        self.assertEqual("unproven", data["r3_8_repair"]["standalone_manual_isolation"])
        self.assertFalse(data["r3_8_repair"]["authority_promotion"])
        integration = data["r3_8_public_integration"]
        self.assertEqual("accepted", integration["status"])
        self.assertEqual(
            "70d04edb77525ae43945a2199acda87eaf48a469",
            integration["shared_tree_identity"],
        )
        self.assertTrue(integration["main_dev_synchronized_at_proof"])
        self.assertFalse(integration["authority_promotion"])
        self.assertEqual(
            "2f13923a9cbdd60d47cab114ba1e280282259bb5",
            data["validation"]["accepted_revision"],
        )
        self.assertEqual(35, data["validation"]["native_test_count"])
        self.assertEqual(337, data["validation"]["python_test_count"])
        self.assertFalse(data["safe_beta"])
        self.assertEqual(
            "774628f442b0cd92ba7de14553f9bcd423aa3d9a",
            data["completed_wave"]["implementation_proof_revision"],
        )
        self.assertEqual(
            "6d41e07b76cd19b2a7630835e05ac3aa125d57b8",
            data["provider_pins"]["universal_launcher"]["revision"],
        )
        m1 = data["m1_managed_portable_install"]
        self.assertEqual("fixture_proven", m1["status"])
        self.assertEqual(
            "2f13923a9cbdd60d47cab114ba1e280282259bb5",
            m1["implementation_head_revision"],
        )
        self.assertEqual(
            "10b1caa915ed4ad5e934f625f3e1384ecc700eaa",
            m1["dev_integration_revision"],
        )
        self.assertEqual(
            "2bc4bf93b1a77c5c906fdc6d3f12b286dadc8ca7",
            m1["universal_setup_revision"],
        )
        self.assertEqual(
            "unavailable_pending_live_target_acceptance",
            m1["ordinary_setup_apply"],
        )
        self.assertFalse(m1["authority_promotion"])
        public_integration = data["m1_public_integration"]
        self.assertEqual("accepted", public_integration["status"])
        self.assertEqual(
            "73bec99916d509b0ab055a43562e93ef20a6b4b7",
            public_integration["canonical_main_revision"],
        )
        self.assertEqual(
            public_integration["dev_tree_identity"],
            public_integration["main_tree_identity"],
        )
        self.assertEqual("29310497458", public_integration["final_main_ci_run"])
        self.assertTrue(public_integration["main_dev_synchronized_at_proof"])
        self.assertFalse(public_integration["authority_promotion"])
        licenses = data["universal_repository_licenses"]
        self.assertEqual("accepted_mit", licenses["status"])
        self.assertEqual(
            "17db1bd9a680d97611fa73f7639c38e1c9472680",
            data["provider_pins"]["universal_setup"]["revision"],
        )
        self.assertEqual("MIT", licenses["spdx_license_expression"])
        self.assertFalse(licenses["publication_authority"])
        catalog = json.loads(
            (project_state.ROOT / "contracts/generated-index/command_catalog.v2.json").read_text(encoding="utf-8")
        )
        self.assertEqual(catalog["source_digest"], data["command_law"]["catalog_digest"])

    def test_platform_evidence_separates_proof_and_publication_status(self) -> None:
        data = project_state.collect()
        records = data["platforms"]
        self.assertTrue(records)
        for record in records:
            self.assertEqual("unpublished", record["publication_status"])
            self.assertIn(record["support_status"], {"candidate", "experimental", "unavailable"})
        appkit = next(record for record in records if record["id"] == "macos_legacy_appkit_x64")
        self.assertEqual("passed", appkit["compile_status"])
        self.assertEqual("not_proven", appkit["runtime_status"])

    def test_lifecycle_transitions_and_hashes_archived_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            policy = root / "contracts" / "policy"
            policy.mkdir(parents=True)
            source = project_state.ROOT / "contracts" / "policy" / "test_impact.v1.json"
            policy.joinpath("test_impact.v1.json").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            compacted = root / ".aide" / "queue" / "next" / "COMPACTED-EVIDENCE-ONLY"
            compacted.joinpath("evidence").mkdir(parents=True)
            path = aide_lifecycle.create(root, "TEST-LIFECYCLE-01", "Lifecycle proof", "Prove state transitions.", ["docs/"])
            self.assertEqual("planned", aide_lifecycle.state_for(path))
            self.assertEqual("active", aide_lifecycle.transition(root, "TEST-LIFECYCLE-01", "start"))
            active = root / ".aide" / "queue" / "active" / "TEST-LIFECYCLE-01"
            self.assertIn(
                ".aide/queue/active/TEST-LIFECYCLE-01/evidence/",
                active.joinpath("status.yaml").read_text(encoding="utf-8"),
            )
            for action, expected in (("verify", "verified"), ("review", "reviewed"), ("close", "closed")):
                self.assertEqual(expected, aide_lifecycle.transition(root, "TEST-LIFECYCLE-01", action))
            archived = aide_lifecycle.archive(root, "TEST-LIFECYCLE-01", "test-checkpoint")
            self.assertTrue(archived.is_dir())
            self.assertIn(
                ".aide/history/test-checkpoint/TEST-LIFECYCLE-01/evidence/",
                archived.joinpath("status.yaml").read_text(encoding="utf-8"),
            )
            index = json.loads((archived.parent / "index.json").read_text(encoding="utf-8"))
            self.assertTrue(index["immutable_task_records"])
            self.assertEqual("text_lf_v1", index["hash_canonicalization"])
            self.assertIn("task.yaml", index["tasks"][0]["files"])
            task_bytes = archived.joinpath("task.yaml").read_bytes()
            normalized = task_bytes.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            self.assertEqual(
                hashlib.sha256(normalized).hexdigest(),
                index["tasks"][0]["files"]["task.yaml"],
            )

    def test_queue_index_rejects_partially_materialized_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            partial = root / ".aide" / "queue" / "active" / "PARTIAL-RECORD"
            partial.mkdir(parents=True)
            partial.joinpath("task.yaml").write_text("id: PARTIAL-RECORD\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "incomplete mutable queue record"):
                aide_lifecycle.rebuild_queue_index(root)


if __name__ == "__main__":
    unittest.main()
