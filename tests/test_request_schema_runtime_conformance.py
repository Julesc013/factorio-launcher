# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tests.native_cli import facman_executable
from tools import json_contract

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "contracts" / "generated-index" / "command_catalog.v2.json"


def sample_value(rule: dict[str, Any]) -> Any:
    if rule.get("enum"):
        return rule["enum"][0]
    if rule.get("type") == "array":
        return []
    pattern = str(rule.get("pattern", ""))
    if "0-9a-f" in pattern and int(rule.get("minLength", 0)) == 64:
        return "a" * 64
    if "0-9" in pattern:
        return "1"
    return "sample"


def invalid_value(rule: dict[str, Any]) -> Any:
    if rule.get("type") == "array":
        return "not-an-array"
    if rule.get("enum"):
        return "__unsupported__"
    return 17


class RequestSchemaRuntimeConformanceTests(unittest.TestCase):
    maxDiff = None

    def invoke(self, workspace: Path, command: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        request = {
            "schema": "facman.transport_request.v1",
            "protocol_version": 1,
            "request_id": f"schema-{command['runtime_id']}",
            "workspace": str(workspace),
            "command": command["runtime_id"],
            "dry_run": not bool(command.get("writes_state")),
            "payload": payload,
        }
        completed = subprocess.run(
            [str(facman_executable()), "rpc", "--stdio"],
            cwd=ROOT,
            input=json.dumps(request),
            check=False,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(completed.stderr, "", (command["runtime_id"], completed.stderr))
        lines = completed.stdout.splitlines()
        self.assertEqual(len(lines), 1, (command["runtime_id"], completed.stdout))
        return json.loads(lines[0])

    def test_required_and_unknown_field_law_matches_live_runtime(self) -> None:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        commands = [command for command in catalog["commands"] if command["registered"]]
        with tempfile.TemporaryDirectory(prefix="facman schema runtime ") as temporary:
            workspace = Path(temporary) / "workspace"
            for command in commands:
                with self.subTest(command=command["runtime_id"]):
                    schema_path = ROOT / command["request_schema"]
                    schema = json_contract.load_schema(schema_path)
                    properties = schema.get("properties", {})
                    required = set(schema.get("required", []))
                    metadata = {field["name"]: field for field in command["request_fields"]}
                    self.assertEqual(set(properties), set(metadata))
                    self.assertEqual(required, {name for name, field in metadata.items() if field["required"]})

                    payload = {name: sample_value(properties[name]) for name in required}
                    self.assertEqual(json_contract.validate(payload, schema), [])
                    accepted = self.invoke(workspace, command, payload)
                    self.assertNotEqual(
                        accepted["outcome"],
                        "invalid_argument",
                        (command["runtime_id"], accepted),
                    )

                    unknown = dict(payload)
                    unknown["__schema_runtime_unknown"] = "rejected"
                    self.assertTrue(json_contract.validate(unknown, schema))
                    rejected = self.invoke(workspace, command, unknown)
                    self.assertEqual(
                        rejected["outcome"],
                        "invalid_argument",
                        (command["runtime_id"], rejected),
                    )

                    for missing in sorted(required):
                        incomplete = {name: value for name, value in payload.items() if name != missing}
                        self.assertTrue(json_contract.validate(incomplete, schema))
                        rejected = self.invoke(workspace, command, incomplete)
                        self.assertEqual(
                            rejected["outcome"],
                            "invalid_argument",
                            (command["runtime_id"], missing, rejected),
                        )

                    for name, rule in properties.items():
                        if name not in required:
                            extended = dict(payload)
                            extended[name] = sample_value(rule)
                            self.assertEqual(json_contract.validate(extended, schema), [])
                            accepted = self.invoke(workspace, command, extended)
                            self.assertNotEqual(
                                accepted["outcome"],
                                "invalid_argument",
                                (command["runtime_id"], name, accepted),
                            )

                        invalid = dict(payload)
                        invalid[name] = invalid_value(rule)
                        self.assertTrue(json_contract.validate(invalid, schema))
                        rejected = self.invoke(workspace, command, invalid)
                        self.assertEqual(
                            rejected["outcome"],
                            "invalid_argument",
                            (command["runtime_id"], name, rejected),
                        )


if __name__ == "__main__":
    unittest.main()
