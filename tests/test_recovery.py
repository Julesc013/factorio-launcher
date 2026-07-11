# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from native_cli import invoke


def journal(workspace: Path, transaction_id: str, target: Path, staging: Path, state: str = "recovery_required") -> Path:
    root = workspace / "transactions"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{transaction_id}.transaction.v1.json"
    path.write_text(
        json.dumps(
            {
                "schema": "facman.transaction.v1",
                "transaction_id": transaction_id,
                "command_id": "instance.import",
                "workspace_id": "local",
                "target": str(target),
                "source_identities": ["portable.zip"],
                "created_utc": "2026-07-11T00:00:00Z",
                "updated_utc": "2026-07-11T00:00:00Z",
                "state": state,
                "completed_steps": ["staging_created"],
                "owned_staging_roots": [str(staging)],
                "expected_file_hashes": [],
                "commit_strategy": "destination_volume_stage_then_atomic_no_replace",
                "error": "injected termination",
                "recovery_actions": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


class RecoveryTests(unittest.TestCase):
    def test_inspect_plan_apply_and_repeated_apply_are_bounded_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            staging = workspace / "instances" / ".facman-instance-import-example"
            staging.mkdir(parents=True)
            (staging / ".facman-archive-staging.v1").write_text("schema=facman.archive_staging.v1\n")
            (staging / "partial.txt").write_text("partial")
            target = workspace / "instances" / "example"
            journal(workspace, "tx-example", target, staging)

            code, stdout, stderr = invoke(
                ["--workspace", tmp, "workspace", "recovery", "inspect", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)["transactions"][0]["transaction_id"], "tx-example")
            code, stdout, stderr = invoke(
                ["--workspace", tmp, "workspace", "recovery", "plan", "tx-example", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)["transactions"][0]["actions"], ["remove_owned_staging"])
            code, stdout, stderr = invoke(
                ["--workspace", tmp, "workspace", "recovery", "apply", "tx-example", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)["transactions"][0]["state"], "rolled_back")
            self.assertFalse(staging.exists())
            code, stdout, stderr = invoke(
                ["--workspace", tmp, "workspace", "recovery", "apply", "tx-example", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)["transactions"][0]["state"], "rolled_back")

    def test_committed_target_is_preserved_and_unknown_or_contended_state_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            target = workspace / "instances" / "committed"
            target.mkdir(parents=True)
            payload = target / "complete.txt"
            payload.write_text("complete")
            staging = workspace / "instances" / ".unused-stage"
            journal(workspace, "tx-committed", target, staging, "committing")
            code, stdout, stderr = invoke(
                ["--workspace", tmp, "workspace", "recovery", "apply", "tx-committed", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(payload.read_text(), "complete")
            recovered = json.loads(stdout)["transactions"][0]
            self.assertEqual(recovered["state"], "recovery_required")
            self.assertIn("manual_target_audit_required", recovered["actions"])

            bad = journal(workspace, "tx-bad", workspace / "none", staging)
            data = json.loads(bad.read_text())
            data["schema"] = "facman.transaction.v99"
            bad.write_text(json.dumps(data))
            code, stdout, _stderr = invoke(
                ["--workspace", tmp, "workspace", "recovery", "plan", "tx-bad", "--json"]
            )
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout)["refusal"]["code"], "recovery_journal_invalid")

            owned = workspace / "owned"
            owned.mkdir()
            (owned / ".facman-archive-staging.v1").write_text("owned")
            path = journal(workspace, "tx-locked", workspace / "missing", owned)
            lock = Path(str(path) + ".recovery.lock")
            lock.write_text("held")
            code, stdout, _stderr = invoke(
                ["--workspace", tmp, "workspace", "recovery", "apply", "tx-locked", "--json"]
            )
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout)["refusal"]["code"], "recovery_lock_contended")

            linked_path = journal(
                workspace,
                "tx-linked-lock",
                workspace / "linked-target",
                owned,
            )
            outside_lock = workspace / "outside-recovery-lock"
            outside_lock.write_text("foreign lock")
            linked_lock = Path(str(linked_path) + ".recovery.lock")
            os.link(outside_lock, linked_lock)
            code, stdout, _stderr = invoke(
                ["--workspace", tmp, "workspace", "recovery", "apply", "tx-linked-lock", "--json"]
            )
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout)["refusal"]["code"], "recovery_write_refused")
            self.assertEqual(outside_lock.read_text(), "foreign lock")

    def test_missing_and_substituted_staging_and_doctor_are_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            target = workspace / "instances" / "missing"
            missing = workspace / "instances" / ".missing-stage"
            journal(workspace, "tx-missing", target, missing)
            code, stdout, stderr = invoke(["--workspace", tmp, "doctor", "--json"])
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)["incomplete_transactions"], 1)
            self.assertFalse(missing.exists())
            code, stdout, stderr = invoke(
                ["--workspace", tmp, "workspace", "recovery", "apply", "tx-missing", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)["transactions"][0]["state"], "rolled_back")

            foreign = workspace / "foreign" / ".substituted"
            foreign.mkdir(parents=True)
            (foreign / ".facman-archive-staging.v1").write_text("forged")
            journal(workspace, "tx-substituted", workspace / "instances" / "target", foreign)
            code, stdout, _stderr = invoke(
                ["--workspace", tmp, "workspace", "recovery", "apply", "tx-substituted", "--json"]
            )
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout)["refusal"]["code"], "recovery_staging_unrecognized")
            self.assertTrue(foreign.is_dir())

    def test_read_only_recovery_state_refuses_without_touching_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            target = workspace / "target"
            staging = workspace / ".staging"
            staging.mkdir()
            (staging / ".facman-archive-staging.v1").write_text("owned")
            path = journal(workspace, "tx-read-only", target, staging)
            protected = path if os.name == "nt" else path.parent
            protected.chmod(0o444 if os.name == "nt" else 0o555)
            try:
                code, stdout, _stderr = invoke(
                    ["--workspace", tmp, "workspace", "recovery", "apply", "tx-read-only", "--json"]
                )
                self.assertEqual(code, 1)
                self.assertEqual(json.loads(stdout)["refusal"]["code"], "recovery_write_refused")
                self.assertTrue(staging.is_dir())
                self.assertFalse(target.exists())
            finally:
                protected.chmod(0o755 if protected.is_dir() else 0o644)


if __name__ == "__main__":
    unittest.main()
