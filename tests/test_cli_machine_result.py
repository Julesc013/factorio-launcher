# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from native_cli import invoke_machine
from tools import json_contract

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts" / "schema" / "transport" / "transport_response.v2.schema.json"
GOLDENS = ROOT / "tests" / "golden" / "cli_machine"


class CliMachineResultTests(unittest.TestCase):
    def assert_golden(self, name: str, document: dict[str, object]) -> None:
        summary = {
            "schema": document["schema"],
            "protocol_version": document["protocol_version"],
            "command": document["command"],
            "outcome": document["outcome"],
            "has_payload": document["payload"] is not None,
            "error_code": None if document["error"] is None else document["error"]["code"],
            "operation_outcome": document["operation"]["outcome"],
        }
        expected = json.loads((GOLDENS / name).read_text(encoding="utf-8"))
        self.assertEqual(expected, summary)

    def assert_machine_result(
        self,
        args: list[str],
        expected_code: int,
        expected_outcome: str,
    ) -> dict[str, object]:
        code, stdout, stderr = invoke_machine(args)
        self.assertEqual(expected_code, code, stderr or stdout)
        self.assertEqual("", stderr)
        self.assertEqual(1, len(stdout.strip().splitlines()))
        document = json.loads(stdout)
        schema = json_contract.load_schema(SCHEMA)
        self.assertEqual([], json_contract.validate(document, schema))
        self.assertEqual("facman.transport_response.v2", document["schema"])
        self.assertEqual(2, document["protocol_version"])
        self.assertEqual(expected_outcome, document["outcome"])
        self.assertTrue(document["request_id"])
        self.assertTrue(document["operation"]["operation_id"])
        self.assertTrue(document["operation"]["attempt_id"])
        return document

    def test_success_has_one_envelope_and_payload(self) -> None:
        result = self.assert_machine_result(
            ["product", "inspect", "--json"], 0, "ok"
        )
        self.assertEqual("product.inspect", result["command"])
        self.assertEqual("factorio", result["payload"]["product_id"])
        self.assertIsNone(result["error"])
        self.assert_golden("success.summary.json", result)

    def test_invalid_invocation_is_machine_readable(self) -> None:
        result = self.assert_machine_result(
            ["not-a-command", "--json"], 2, "invalid_argument"
        )
        self.assertEqual("cli_invalid_invocation", result["error"]["code"])
        self.assertIsNone(result["payload"])
        self.assertEqual(
            "refused_before_effects", result["operation"]["outcome"]
        )
        self.assert_golden("invalid-invocation.summary.json", result)

    def test_backend_refusal_keeps_envelope_and_compatible_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = self.assert_machine_result(
                [
                    "--workspace",
                    temporary,
                    "installs",
                    "describe",
                    "missing",
                    "--json",
                ],
                1,
                "refused",
            )
        self.assertEqual("installs.describe", result["command"])
        self.assertIsNotNone(result["error"])
        self.assert_golden("backend-refusal.summary.json", result)

    def test_local_workflow_no_longer_bypasses_envelope(self) -> None:
        result = self.assert_machine_result(
            ["installs", "workflow", "--json"], 0, "ok"
        )
        self.assertEqual("installs.workflow", result["command"])
        self.assertEqual("facman.setup_workflow.v1", result["payload"]["schema"])
        self.assert_golden("local-workflow.summary.json", result)


if __name__ == "__main__":
    unittest.main()
