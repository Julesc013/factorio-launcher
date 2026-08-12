# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import jsonschema

from native_cli import ROOT, facman_executable, invoke_machine


def tree(root: Path) -> list[str]:
    if not root.exists():
        return []
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))


class PresentationServiceTests(unittest.TestCase):
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
            self.assertEqual(snapshot["last_run"]["authority_state"], "provider_unavailable")

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


if __name__ == "__main__":
    unittest.main()
