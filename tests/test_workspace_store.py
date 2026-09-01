# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

from native_cli import invoke, invoke_machine

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"


def snapshot(root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))


class WorkspaceStoreTests(unittest.TestCase):
    def test_unsupported_identity_migration_is_read_only_and_apply_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            before = snapshot(workspace)
            for operation in ("inspect", "plan"):
                code, stdout, stderr = invoke(
                    ["--workspace", tmp, "workspace", "migration", operation, "--json"]
                )
                self.assertEqual(code, 0, stderr)
                data = json.loads(stdout)
                self.assertEqual(data["command"], f"workspace.migration.{operation}")
                self.assertEqual(data["status"], "changes_detected")
                self.assertFalse(data["apply_enabled"])
                self.assertEqual(data["actions"][0]["kind"], "create_workspace_identity")
                self.assertEqual(snapshot(workspace), before)

            code, stdout, _stderr = invoke(
                ["--workspace", tmp, "workspace", "migration", "apply", "--json"]
            )
            self.assertEqual(code, 1)
            self.assertEqual(
                json.loads(stdout)["refusal"]["code"],
                "workspace_migration_action_unsupported",
            )
            self.assertEqual(snapshot(workspace), before)

    def test_legacy_record_canonicalization_is_journaled_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            canonical_install = workspace / "installs" / "refs" / "fixture.json"
            legacy_install = workspace / "installs" / "installed_state" / "fixture.json"
            legacy_install.parent.mkdir(parents=True, exist_ok=True)
            canonical_install.replace(legacy_install)
            legacy_instance = workspace / "instances" / "legacy" / "instance.manifest.json"
            legacy_instance.parent.mkdir(parents=True, exist_ok=True)
            legacy_instance.write_text(
                json.dumps(
                    {
                        "instance_id": "legacy",
                        "install_ref": "fixture",
                        "factorio_version": "2.0",
                        "extension": {"preserved": True},
                    }
                ),
                encoding="utf-8",
            )
            install_before = legacy_install.read_bytes()
            instance_before = legacy_instance.read_bytes()

            code, stdout, stderr = invoke(
                ["--workspace", tmp, "workspace", "migration", "plan", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            plan = json.loads(stdout)
            self.assertTrue(plan["apply_enabled"])
            self.assertEqual(len(plan["actions"]), 2)

            code, stdout, stderr = invoke(
                ["--workspace", tmp, "workspace", "migration", "apply", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            applied = json.loads(stdout)
            self.assertTrue(applied["apply_enabled"])
            self.assertEqual(len(applied["actions"]), 2)
            self.assertEqual(legacy_install.read_bytes(), install_before)
            self.assertEqual(legacy_instance.read_bytes(), instance_before)
            self.assertTrue(canonical_install.is_file())
            canonical_instance = json.loads(
                (workspace / "instances" / "legacy" / "instance.v1.json").read_text(encoding="utf-8")
            )
            self.assertEqual(canonical_instance["schema"], "factorio.instance.v1")
            self.assertEqual(canonical_instance["extension"], {"preserved": True})
            journals = list(
                (workspace / "transactions" / "workspace-migrations").glob(
                    "*.workspace-migration.v1.json"
                )
            )
            self.assertEqual(len(journals), 1)
            self.assertEqual(json.loads(journals[0].read_text(encoding="utf-8"))["state"], "complete")

            code, stdout, stderr = invoke(
                ["--workspace", tmp, "workspace", "migration", "apply", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            repeated = json.loads(stdout)
            self.assertEqual(repeated["status"], "no_changes")
            self.assertEqual(repeated["actions"], [])

    def test_recovery_required_is_recoverable_but_not_directly_retryable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            migration_root = Path(tmp) / "transactions" / "workspace-migrations"
            migration_root.mkdir(parents=True, exist_ok=True)
            journal = migration_root / "manual.workspace-migration.v1.json"
            journal.write_text(
                json.dumps(
                    {
                        "schema": "facman.workspace_migration_journal.v1",
                        "migration_id": "manual",
                        "state": "recovery_required",
                        "completed_actions": 0,
                        "actions": [],
                    }
                ),
                encoding="utf-8",
            )
            code, stdout, stderr = invoke_machine(
                ["--workspace", tmp, "workspace", "migration", "apply", "--json"]
            )
            self.assertEqual((code, stderr), (1, ""), stdout)
            envelope = json.loads(stdout)
            self.assertEqual(envelope["outcome"], "refused")
            self.assertEqual(envelope["error"]["code"], "workspace_migration_recovery_required")
            refusal = envelope["payload"]["refusal"]
            self.assertTrue(refusal["recoverable"])
            self.assertFalse(refusal["retryable"])
            self.assertNotIn("suggested_next_command", refusal)
            self.assertFalse(envelope["operation"]["recovery"]["required"])
            self.assertEqual(envelope["operation"]["recovery"]["inspect_command"], "")

    def test_divergent_recovery_target_is_retryable_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            target = workspace / "installs" / "refs" / "fixture.json"
            source = workspace / "installs" / "installed_state" / "fixture.json"
            source.parent.mkdir(parents=True, exist_ok=True)
            target.replace(source)
            payload = source.read_bytes()
            target.write_text("{}\n", encoding="utf-8")
            digest = hashlib.sha256(payload).hexdigest()
            migration_root = workspace / "transactions" / "workspace-migrations"
            data_root = migration_root / "conflict.data"
            data_root.mkdir(parents=True, exist_ok=True)
            (data_root / "0.source.json").write_bytes(payload)
            (data_root / "0.target.json").write_bytes(payload)
            (migration_root / "conflict.workspace-migration.v1.json").write_text(
                json.dumps(
                    {
                        "schema": "facman.workspace_migration_journal.v1",
                        "migration_id": "conflict",
                        "state": "applying",
                        "completed_actions": 0,
                        "actions": [
                            {
                                "kind": "canonicalize_legacy_install_ref",
                                "source": "installs/installed_state/fixture.json",
                                "target": "installs/refs/fixture.json",
                                "source_sha256": digest,
                                "target_sha256": digest,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            code, stdout, stderr = invoke_machine(
                ["--workspace", tmp, "workspace", "migration", "apply", "--json"]
            )
            self.assertEqual((code, stderr), (1, ""), stdout)
            envelope = json.loads(stdout)
            self.assertEqual(envelope["outcome"], "conflict")
            self.assertEqual(envelope["error"]["code"], "workspace_migration_conflict")
            refusal = envelope["payload"]["refusal"]
            self.assertTrue(refusal["recoverable"])
            self.assertTrue(refusal["retryable"])
            self.assertEqual(target.read_text(encoding="utf-8"), "{}\n")

    def test_new_workspace_gets_stable_random_uuid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            manifest = json.loads((Path(tmp) / "workspace.v1.json").read_text(encoding="utf-8"))
            self.assertNotEqual(manifest["workspace_id"], "local")
            self.assertRegex(
                manifest["workspace_id"],
                re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"),
            )
            code, stdout, stderr = invoke(
                ["--workspace", tmp, "workspace", "migration", "inspect", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)["status"], "no_changes")

    def test_future_workspace_refuses_before_creating_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "workspace.v1.json").write_text(
                json.dumps(
                    {
                        "schema": "facman.factorio.workspace.v2",
                        "workspace_id": "future",
                        "layout_version": 2,
                    }
                ),
                encoding="utf-8",
            )
            before = snapshot(workspace)
            code, stdout, _stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture", "--json"]
            )
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout)["refusal"]["code"], "workspace_layout_future_or_unknown")
            self.assertEqual(snapshot(workspace), before)


if __name__ == "__main__":
    unittest.main()
