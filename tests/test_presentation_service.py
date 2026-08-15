# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema

from native_cli import ROOT, facman_executable, invoke_machine


def tree(root: Path) -> list[str]:
    if not root.exists():
        return []
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))


def write_installation_fixture(root: Path) -> None:
    executable = (
        root / "bin" / "x64" / "factorio.exe"
        if sys.platform == "win32"
        else root / "Factorio.app" / "Contents" / "MacOS" / "factorio"
        if sys.platform == "darwin"
        else root / "bin" / "x64" / "factorio"
    )
    executable.parent.mkdir(parents=True)
    executable.write_text("synthetic fixture; never executed\n", encoding="utf-8")
    (root / "data" / "base").mkdir(parents=True)
    (root / "data" / "base" / "info.json").write_text(
        '{"name":"base","version":"2.0.77"}\n', encoding="utf-8"
    )


class PresentationServiceTests(unittest.TestCase):
    def test_ordinary_content_saves_and_settings_scopes_are_backend_snapshots(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-presentation-ordinary-") as temporary:
            workspace = Path(temporary) / "workspace"
            before = tree(workspace)
            schema = json.loads((
                ROOT / "contracts/schema/presentation/presentation_snapshot.v1.schema.json"
            ).read_text(encoding="utf-8"))

            snapshots: dict[str, dict[str, object]] = {}
            for scope in ("content", "saves", "settings_support"):
                code, stdout, stderr = invoke_machine([
                    "--workspace", str(workspace), "presentation", "query", scope, "--json",
                ])
                self.assertEqual((code, stderr), (0, ""), stdout)
                snapshot = json.loads(stdout)["payload"]
                jsonschema.Draft202012Validator(schema).validate(snapshot)
                self.assertEqual(snapshot["page"]["scope"], scope)
                self.assertEqual(snapshot["freshness"]["refresh_kind"], "repository_read_no_scan")
                self.assertFalse(snapshot["selected_context"]["workspace_mutated"])
                snapshots[scope] = snapshot

            self.assertIn(
                "profile:gui",
                {item["id"] for item in snapshots["content"]["page"]["items"]},
            )
            self.assertIn(
                "no_instance_selected",
                {item["code"] for item in snapshots["saves"]["specific_blockers"]},
            )
            self.assertIn(
                "preferred_transport",
                {item["id"] for item in snapshots["settings_support"]["page"]["items"]},
            )
            self.assertEqual(before, tree(workspace))

    def test_query_is_deterministic_read_only_schema_valid_and_transport_equivalent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-presentation-") as temporary:
            workspace = Path(temporary) / "workspace"
            before = tree(workspace)
            arguments = [
                "--workspace", str(workspace), "presentation", "query",
                "launch_deck", "--instance", "main", "--json",
            ]
            code, stdout, stderr = invoke_machine(arguments)
            self.assertEqual((code, stderr), (0, ""), stdout)
            envelope = json.loads(stdout)
            snapshot = envelope["payload"]
            schema = json.loads((
                ROOT / "contracts/schema/presentation/presentation_snapshot.v1.schema.json"
            ).read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator(schema).validate(snapshot)
            self.assertEqual(snapshot["freshness"]["refresh_kind"], "repository_read_no_scan")
            self.assertFalse(snapshot["selected_context"]["workspace_mutated"])
            self.assertEqual(snapshot["last_run"]["authority_state"], "no_record")
            self.assertEqual(
                snapshot["last_run"]["provider_id"],
                "ulk.session.journal.v1.authoritative",
            )

            code, repeated, stderr = invoke_machine(arguments)
            self.assertEqual((code, stderr), (0, ""), repeated)
            self.assertEqual(snapshot, json.loads(repeated)["payload"])
            self.assertEqual(before, tree(workspace))

            request = {
                "schema": "facman.transport_request.v2",
                "protocol_version": 2,
                "request_id": "presentation-parity",
                "operation_id": "presentation-parity-operation",
                "attempt_id": "presentation-parity-attempt",
                "workspace": str(workspace),
                "command": "presentation.query",
                "dry_run": True,
                "payload": {"scope": "launch_deck", "selected_instance_id": "main"},
            }
            transported = subprocess.run(
                [str(facman_executable()), "rpc", "--stdio"],
                cwd=ROOT,
                input=json.dumps(request),
                text=True,
                encoding="utf-8",
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
            )
            self.assertEqual((transported.returncode, transported.stderr), (0, ""), transported.stdout)
            self.assertEqual(json.loads(transported.stdout)["payload"], snapshot)

    def test_refresh_stale_revision_and_explicit_scan_action(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-presentation-action-") as temporary:
            workspace = Path(temporary) / "workspace"
            code, stdout, stderr = invoke_machine([
                "--workspace", str(workspace), "presentation", "query", "installations", "--json",
            ])
            self.assertEqual((code, stderr), (0, ""), stdout)
            revision = json.loads(stdout)["payload"]["revision"]

            common = [
                "--workspace", str(workspace), "presentation", "action",
                "presentation.refresh", "--scope", "installations",
                "--request-id", "request-1", "--json",
            ]
            code, stdout, stderr = invoke_machine([
                *common, "--expected-revision", "0" * 64,
            ])
            self.assertEqual((code, stderr), (1, ""), stdout)
            refusal = json.loads(stdout)
            self.assertEqual(refusal["outcome"], "conflict")
            self.assertEqual(refusal["error"]["code"], "stale_snapshot_revision")
            self.assertEqual(refusal["payload"]["outcome"], "refused_before_effects")

            launch_code, launch_stdout, launch_stderr = invoke_machine([
                "--workspace", str(workspace), "presentation", "query",
                "launch_deck", "--json",
            ])
            self.assertEqual((launch_code, launch_stderr), (0, ""), launch_stdout)
            launch_revision = json.loads(launch_stdout)["payload"]["revision"]
            code, stdout, stderr = invoke_machine([
                "--workspace", str(workspace), "presentation", "action",
                "installations.scan", "--scope", "launch_deck",
                "--expected-revision", launch_revision,
                "--request-id", "request-wrong-scope", "--json",
            ])
            self.assertEqual((code, stderr), (2, ""), stdout)
            self.assertEqual(
                json.loads(stdout)["error"]["code"],
                "semantic_action_unknown",
            )

            code, stdout, stderr = invoke_machine([
                "--workspace", str(workspace), "presentation", "action",
                "installations.scan", "--scope", "installations",
                "--expected-revision", revision, "--request-id", "request-2",
                "--idempotency-key", "scan-1", "--root", str(workspace), "--json",
            ])
            self.assertEqual((code, stderr), (0, ""), stdout)
            result = json.loads(stdout)["payload"]
            schema = json.loads((
                ROOT / "contracts/schema/presentation/semantic_action_result.v1.schema.json"
            ).read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator(schema).validate(result)
            self.assertEqual(result["outcome"], "completed")
            self.assertEqual(result["invalidation"]["reason"], "explicit_installation_scan_completed")
            self.assertIsNone(result["replacement_snapshot"])

    def test_effectful_actions_are_correlated_and_replay_across_cli_processes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-presentation-durable-") as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            installation = root / "factorio-fixture"
            write_installation_fixture(installation)

            code, stdout, stderr = invoke_machine([
                "--workspace", str(workspace), "presentation", "query",
                "installations", "--json",
            ])
            self.assertEqual((code, stderr), (0, ""), stdout)
            revision = json.loads(stdout)["payload"]["revision"]
            register = [
                "--workspace", str(workspace), "presentation", "action",
                "installation.register_read_only", "--scope", "installations",
                "--expected-revision", revision,
                "--request-id", "request-register-fixture",
                "--idempotency-key", "idempotency-register-fixture",
                "--operation-id", "operation-register-fixture",
                "--attempt-id", "attempt-register-fixture",
                "--confirmation", "explicit",
                "--installation", "fixture-read-only",
                "--installation-path", str(installation),
                "--json",
            ]
            code, first, stderr = invoke_machine(register)
            self.assertEqual((code, stderr), (0, ""), first)
            first_envelope = json.loads(first)
            self.assertEqual(first_envelope["request_id"], "request-register-fixture")
            self.assertEqual(
                first_envelope["operation"]["operation_id"],
                "operation-register-fixture",
            )
            self.assertEqual(
                first_envelope["operation"]["attempt_id"],
                "attempt-register-fixture",
            )
            self.assertEqual(first_envelope["payload"]["outcome"], "completed")

            code, replay, stderr = invoke_machine(register)
            self.assertEqual((code, stderr, replay), (0, "", first))
            self.assertTrue((workspace / ".facman" / "action-receipts-v1").is_dir())

            conflict = list(register)
            conflict[conflict.index("request-register-fixture")] = (
                "request-register-fixture-conflict"
            )
            code, conflict_stdout, stderr = invoke_machine(conflict)
            self.assertEqual((code, stderr), (1, ""), conflict_stdout)
            self.assertEqual(
                json.loads(conflict_stdout)["error"]["code"],
                "idempotency_key_conflict",
            )

            code, stdout, stderr = invoke_machine([
                "--workspace", str(workspace), "presentation", "query",
                "instances", "--json",
            ])
            self.assertEqual((code, stderr), (0, ""), stdout)
            revision = json.loads(stdout)["payload"]["revision"]
            create = [
                "--workspace", str(workspace), "presentation", "action",
                "instance.create_isolated", "--scope", "instances",
                "--expected-revision", revision,
                "--request-id", "request-create-fixture",
                "--idempotency-key", "idempotency-create-fixture",
                "--operation-id", "operation-create-fixture",
                "--attempt-id", "attempt-create-fixture",
                "--confirmation", "explicit",
                "--installation", "fixture-read-only",
                "--new-instance", "fixture-isolated",
                "--display-name", "Fixture Isolated",
                "--json",
            ]
            code, created, stderr = invoke_machine(create)
            self.assertEqual((code, stderr), (0, ""), created)
            self.assertEqual(json.loads(created)["payload"]["outcome"], "completed")
            code, replayed, stderr = invoke_machine(create)
            self.assertEqual((code, stderr, replayed), (0, "", created))

            code, stdout, stderr = invoke_machine([
                "--workspace", str(workspace), "presentation", "query",
                "launch_deck", "--instance", "fixture-isolated", "--json",
            ])
            self.assertEqual((code, stderr), (0, ""), stdout)
            selected = json.loads(stdout)["payload"]["selected_context"]
            self.assertEqual(selected["instance_id"], "fixture-isolated")
            self.assertEqual(selected["display_name"], "Fixture Isolated")
            self.assertEqual(selected["installation_id"], "fixture-read-only")


if __name__ == "__main__":
    unittest.main()
