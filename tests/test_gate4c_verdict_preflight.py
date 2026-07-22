# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "gate4c_verdict_preflight", ROOT / "tools/gate4c_verdict_preflight.py"
)
assert SPEC and SPEC.loader
PREFLIGHT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREFLIGHT)


class Gate4CVerdictPreflightTests(unittest.TestCase):
    def test_canonical_digest_is_order_independent(self) -> None:
        left = PREFLIGHT.digest_value({"b": 2, "a": [1, 3]})
        right = PREFLIGHT.digest_value({"a": [1, 3], "b": 2})
        self.assertEqual(left, right)

    def test_artifact_manifest_detects_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "facman.exe"
            artifact.write_bytes(b"reviewed")
            digest = hashlib.sha256(b"reviewed").hexdigest()
            manifest = root / "artifact-binding.v1.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema": "facman.gate4c_artifact_binding.v1",
                        "work_unit": PREFLIGHT.WORK_UNIT,
                        "source_candidate_revision": PREFLIGHT.CANDIDATE_REVISION,
                        "copy_verified": True,
                        "artifacts": [
                            {
                                "name": artifact.name,
                                "bytes": len(b"reviewed"),
                                "sha256": digest,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertTrue(PREFLIGHT.verify_artifact_manifest(manifest)["valid"])
            artifact.write_bytes(b"changed")
            self.assertFalse(PREFLIGHT.verify_artifact_manifest(manifest)["valid"])

    def test_source_is_never_inferred_when_artifact_is_absent(self) -> None:
        result = PREFLIGHT.source_evidence(None)
        self.assertEqual(result["status"], "missing")
        self.assertFalse(result["valid"])

    def test_quiet_host_attestation_is_exact_and_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            attestation = root / "attestation.json"
            value = {
                "schema": "factorio.gate4c_quiet_host_attestation.v1",
                "attested_at": "2026-07-22T13:00:00Z",
                "reviewer_id": "local-operator",
                "pending_restart_cleared": True,
                "steam_closed": True,
                "unrelated_factorio_facman_closed": True,
                "install_backup_sync_activity_paused": True,
                "sleep_and_restart_prevented_for_run": True,
            }
            attestation.write_text(json.dumps(value), encoding="utf-8")
            self.assertTrue(PREFLIGHT.operator_attestation(attestation)["valid"])
            value["unexpected"] = True
            attestation.write_text(json.dumps(value), encoding="utf-8")
            self.assertFalse(PREFLIGHT.operator_attestation(attestation)["valid"])

    def test_no_follow_audit_refuses_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target.txt"
            link = root / "link.txt"
            target.write_text("content", encoding="utf-8")
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest("symlink creation is unavailable")
            result = PREFLIGHT.audit_no_follow(link, require_file=True)
            self.assertFalse(result["safe"])
            self.assertIn("link_or_reparse", result["reason"])

    def test_record_writer_refuses_output_outside_task_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / PREFLIGHT.WORK_UNIT
            root.mkdir()
            with self.assertRaises(PREFLIGHT.PreflightError):
                PREFLIGHT.write_record(root.parent / "outside.json", {}, root)


if __name__ == "__main__":
    unittest.main()
