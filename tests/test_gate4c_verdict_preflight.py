# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "gate4c_verdict_preflight", ROOT / "tools/gate4c_verdict_preflight.py"
)
assert SPEC and SPEC.loader
PREFLIGHT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREFLIGHT)


class Gate4CVerdictPreflightTests(unittest.TestCase):
    @staticmethod
    def source_signature(
        *,
        valid: bool = True,
        product_version: str = "2.0.77",
        original_filename: str = "Setup_Factorio_2.0.77.exe",
        description: str = "Factorio installer",
    ) -> dict[str, object]:
        return {
            "valid": valid,
            "status": "Valid" if valid else "NotSigned",
            "signer_subject": "CN=Wube Software Ltd",
            "signer_thumbprint": "wube-thumbprint",
            "timestamp_subject": "CN=Timestamp Provider",
            "timestamp_thumbprint": "timestamp-thumbprint",
            "product_version": product_version,
            "file_version": f"{product_version}.84539",
            "product_name": "Factorio",
            "file_description": description,
            "original_filename": original_filename,
            "internal_name": "Factorio Setup",
        }

    def test_canonical_digest_is_order_independent(self) -> None:
        left = PREFLIGHT.digest_value({"b": 2, "a": [1, 3]})
        right = PREFLIGHT.digest_value({"a": [1, 3], "b": 2})
        self.assertEqual(left, right)

    def test_host_state_changes_across_wake_or_observer_change(self) -> None:
        session = {
            "machine_binding_id": "machine",
            "boot_identity": "boot",
            "wake_identity": "wake-a",
        }
        processes = {"available": True, "processes": [], "quiet": True}
        baseline = PREFLIGHT.host_state_digest(session, processes, "observer-a")
        self.assertNotEqual(
            baseline,
            PREFLIGHT.host_state_digest(
                {**session, "wake_identity": "wake-b"}, processes, "observer-a"
            ),
        )
        self.assertNotEqual(
            baseline, PREFLIGHT.host_state_digest(session, processes, "observer-b")
        )

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

    def test_source_requires_recognized_distinct_installer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            installed = root / "factorio.exe"
            source = root / "Setup_Factorio_2.0.77.exe"
            installed.write_bytes(b"installed executable")
            source.write_bytes(b"owned installer")
            with mock.patch.object(
                PREFLIGHT, "authenticode", return_value=self.source_signature()
            ):
                result = PREFLIGHT.source_evidence(source, installed)
            self.assertTrue(result["valid"])
            self.assertEqual("operator_supplied", result["evidence_origin"])
            self.assertEqual("wube_windows_installer", result["source_artifact_kind"])
            self.assertTrue(
                result["installed_executable_comparison"][
                    "distinct_stable_identity_and_content"
                ]
            )

    def test_installed_executable_cannot_be_its_own_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            installed = Path(temporary) / "factorio.exe"
            installed.write_bytes(b"installed executable")
            signature = self.source_signature(
                original_filename="factorio.exe", description="Factorio"
            )
            with mock.patch.object(PREFLIGHT, "authenticode", return_value=signature):
                result = PREFLIGHT.source_evidence(installed, installed)
            self.assertFalse(result["valid"])
            self.assertFalse(result["artifact_class_valid"])
            self.assertFalse(
                result["installed_executable_comparison"][
                    "distinct_stable_identity_and_content"
                ]
            )

    def test_other_signed_executable_is_not_a_source_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            installed = root / "factorio.exe"
            other = root / "Setup_Factorio_2.0.77.exe"
            installed.write_bytes(b"installed")
            other.write_bytes(b"helper")
            signature = self.source_signature(
                original_filename="wube-helper.exe", description="Factorio helper"
            )
            with mock.patch.object(PREFLIGHT, "authenticode", return_value=signature):
                result = PREFLIGHT.source_evidence(other, installed)
            self.assertFalse(result["valid"])
            self.assertEqual("unrecognized", result["source_artifact_kind"])

    def test_wrong_version_and_unsigned_renamed_installers_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            installed = root / "factorio.exe"
            source = root / "Setup_Factorio_2.0.77.exe"
            installed.write_bytes(b"installed")
            source.write_bytes(b"installer")
            with mock.patch.object(
                PREFLIGHT,
                "authenticode",
                return_value=self.source_signature(product_version="2.0.76"),
            ):
                self.assertFalse(PREFLIGHT.source_evidence(source, installed)["valid"])
            with mock.patch.object(
                PREFLIGHT,
                "authenticode",
                return_value=self.source_signature(valid=False),
            ):
                self.assertFalse(PREFLIGHT.source_evidence(source, installed)["valid"])

    def test_source_reparse_path_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            installed = root / "factorio.exe"
            source = root / "Setup_Factorio_2.0.77.exe"
            link = root / "Setup_Factorio_2.0.77-link.exe"
            installed.write_bytes(b"installed")
            source.write_bytes(b"installer")
            try:
                link.symlink_to(source)
            except OSError:
                self.skipTest("symlink creation is unavailable")
            result = PREFLIGHT.source_evidence(link, installed)
            self.assertFalse(result["valid"])
            self.assertIn("link_or_reparse", result["path_audit"]["reason"])

    def test_source_reparse_refusal_does_not_depend_on_symlink_privilege(self) -> None:
        source = Path("Setup_Factorio_2.0.77-link.exe")
        installed = Path("factorio.exe")
        reparse_audit = {
            "path": str(source),
            "present": True,
            "safe": False,
            "reason": "link_or_reparse:source",
        }
        with mock.patch.object(PREFLIGHT, "audit_no_follow", return_value=reparse_audit):
            result = PREFLIGHT.source_evidence(source, installed)
        self.assertFalse(result["valid"])
        self.assertEqual("link_or_reparse:source", result["path_audit"]["reason"])

    def test_quiet_host_attestation_is_exact_and_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            attestation = root / "attestation.json"
            now = datetime(2026, 7, 22, 13, 5, tzinfo=timezone.utc)
            value = {
                "schema": PREFLIGHT.ATTESTATION_SCHEMA,
                "attested_at": "2026-07-22T13:00:00Z",
                "reviewer_id": "windows.local:jules",
                "machine_binding_id": "machine",
                "boot_identity": "boot",
                "observer_self_test_digest": "observer",
                "host_state_digest": "host",
                "pending_restart_cleared": True,
                "steam_closed": True,
                "unrelated_factorio_facman_closed": True,
                "install_backup_sync_activity_paused": True,
                "sleep_and_restart_prevented_for_run": True,
            }
            attestation.write_text(json.dumps(value), encoding="utf-8")
            arguments = {
                "machine_binding_id": "machine",
                "boot_identity": "boot",
                "observer_self_test_digest": "observer",
                "observer_generated_at": "2026-07-22T12:59:00Z",
                "current_host_state_digest": "host",
                "now": now,
            }
            result = PREFLIGHT.operator_attestation(attestation, **arguments)
            self.assertTrue(result["valid"])
            self.assertEqual("2026-07-22T13:10:00Z", result["baseline_must_begin_before"])
            value["unexpected"] = True
            attestation.write_text(json.dumps(value), encoding="utf-8")
            self.assertFalse(PREFLIGHT.operator_attestation(attestation, **arguments)["valid"])

    def test_attestation_rejects_stale_future_unscoped_and_changed_host(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "attestation.json"
            now = datetime(2026, 7, 22, 13, 30, tzinfo=timezone.utc)
            value = {
                "schema": PREFLIGHT.ATTESTATION_SCHEMA,
                "attested_at": "2026-07-22T13:00:00Z",
                "reviewer_id": "windows.local:jules",
                "machine_binding_id": "machine",
                "boot_identity": "boot",
                "observer_self_test_digest": "observer",
                "host_state_digest": "host",
                "pending_restart_cleared": True,
                "steam_closed": True,
                "unrelated_factorio_facman_closed": True,
                "install_backup_sync_activity_paused": True,
                "sleep_and_restart_prevented_for_run": True,
            }
            arguments = {
                "machine_binding_id": "machine",
                "boot_identity": "boot",
                "observer_self_test_digest": "observer",
                "observer_generated_at": "2026-07-22T12:59:00Z",
                "current_host_state_digest": "host",
                "now": now,
            }
            path.write_text(json.dumps(value), encoding="utf-8")
            self.assertFalse(PREFLIGHT.operator_attestation(path, **arguments)["valid"])

            value["attested_at"] = (now + timedelta(seconds=31)).isoformat().replace("+00:00", "Z")
            path.write_text(json.dumps(value), encoding="utf-8")
            self.assertFalse(PREFLIGHT.operator_attestation(path, **arguments)["valid"])

            value["attested_at"] = now.isoformat().replace("+00:00", "Z")
            value["reviewer_id"] = "unscoped"
            path.write_text(json.dumps(value), encoding="utf-8")
            self.assertFalse(PREFLIGHT.operator_attestation(path, **arguments)["valid"])

            value["reviewer_id"] = "windows.local:jules"
            path.write_text(json.dumps(value), encoding="utf-8")
            changed = {**arguments, "current_host_state_digest": "changed"}
            self.assertFalse(PREFLIGHT.operator_attestation(path, **changed)["valid"])

            before_observer = {
                **arguments,
                "observer_generated_at": "2026-07-22T13:30:01Z",
            }
            self.assertFalse(
                PREFLIGHT.operator_attestation(path, **before_observer)["valid"]
            )

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
