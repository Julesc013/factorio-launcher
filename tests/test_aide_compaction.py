# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest
import json
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
            "current_revisions", "current_phase", "active_workunit",
            "quarantined_capabilities", "claim_levels", "provider_pins",
            "target_proof_platforms", "current_artifacts", "known_blockers",
            "current_checkpoint", "completed_wave", "command_law", "machine_protocol",
            "implementation_revision", "integration_revision", "evidence_revision",
            "provider_revisions", "active_wave", "baseline_evidence",
        ):
            self.assertIn(key, data)
        self.assertFalse(data["truth_boundaries"][2].startswith("Automated checks pass"))

    def test_r37_baseline_preserves_r36_provider_and_catalog_truth(self) -> None:
        data = project_state.collect()
        self.assertEqual("r3.7-instance-content-lifecycle-active", data["current_phase"])
        self.assertEqual("r3.7-baseline", data["current_checkpoint"])
        self.assertEqual("29cf22fa15250698b7587a9868737c10f3bcc749", data["evidence_revision"])
        self.assertEqual(data["evidence_revision"], data["integration_revision"])
        self.assertEqual(
            "fc8423572e9c055991558f8a4e7cbbc95e0c4a24",
            data["completed_wave"]["revision"],
        )
        self.assertEqual(
            "de6c7c6cfa80c524296066bd6bb90a70ba02b760",
            data["provider_pins"]["universal_launcher"]["revision"],
        )
        catalog = json.loads(
            (project_state.ROOT / "contracts/generated-index/command_catalog.v2.json").read_text(encoding="utf-8")
        )
        self.assertEqual(catalog["source_digest"], data["command_law"]["catalog_digest"])

    def test_artifact_evidence_is_structured_and_revision_specific(self) -> None:
        records = project_state.collect()["current_artifacts"]
        self.assertTrue(records)
        for record in records:
            self.assertEqual(
                {"artifact", "revision", "checkpoint", "target", "sha256", "authenticity"},
                set(record),
            )
            self.assertEqual("not_proven_unsigned", record["authenticity"])
        windows_cli = [
            record for record in records
            if record["artifact"] == "facman-0.1.0-dev.contract-windows-cli-x64-portable.zip"
        ]
        self.assertEqual(2, len(windows_cli))
        self.assertEqual(2, len({record["revision"] for record in windows_cli}))

    def test_lifecycle_transitions_and_hashes_archived_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            policy = root / "contracts" / "policy"
            policy.mkdir(parents=True)
            source = project_state.ROOT / "contracts" / "policy" / "test_impact.v1.json"
            policy.joinpath("test_impact.v1.json").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
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
            self.assertIn("task.yaml", index["tasks"][0]["files"])


if __name__ == "__main__":
    unittest.main()
