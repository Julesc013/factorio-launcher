# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

import jsonschema

from tools import contract_compatibility
from tools.codegen import generate_contracts


ROOT = Path(__file__).resolve().parents[1]


class ContractCompilerTests(unittest.TestCase):
    def bundle(self) -> dict:
        return json.loads(generate_contracts.OUTPUTS["bundle"].read_text(encoding="utf-8"))

    def schema(self, suffix: str) -> dict:
        entry = next(
            item for item in self.bundle()["contracts"] if item["source_path"].endswith(suffix)
        )
        return entry["schema"]

    def test_generated_outputs_are_deterministic_and_current(self) -> None:
        first = generate_contracts.render()
        second = generate_contracts.render()
        self.assertEqual(first, second)
        self.assertEqual(generate_contracts.generate(write=False), [])

    def test_effect_input_is_closed_and_read_extension_is_namespaced(self) -> None:
        action = {
            "action_id": "presentation.refresh",
            "scope": "instances",
            "expected_snapshot_revision": "0" * 64,
            "request_id": "request-1",
        }
        jsonschema.validate(action, self.schema("presentation.action.request.v1.schema.json"))
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(
                {**action, "unknown_authority": True},
                self.schema("presentation.action.request.v1.schema.json"),
            )
        snapshot = json.loads(
            (ROOT / "tests/golden/commands/presentation.query.success.json").read_text(
                encoding="utf-8"
            )
        )
        schema = self.schema("presentation_snapshot.v1.schema.json")
        jsonschema.validate({**snapshot, "x-facman.test": {"value": 1}}, schema)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate({**snapshot, "ordinary_unknown": {}}, schema)

    def test_producer_and_consumer_fixtures_match_bundle(self) -> None:
        fixtures = {
            "presentation_snapshot.v1.schema.json": "presentation.query.success.json",
            "semantic_action_result.v1.schema.json": "presentation.action.success.json",
        }
        for schema_name, fixture_name in fixtures.items():
            with self.subTest(schema=schema_name):
                fixture = json.loads(
                    (ROOT / "tests/golden/commands" / fixture_name).read_text(encoding="utf-8")
                )
                jsonschema.validate(fixture, self.schema(schema_name))

    def test_generated_python_consumer_imports(self) -> None:
        path = generate_contracts.OUTPUTS["python"]
        spec = importlib.util.spec_from_file_location("generated_presentation_contracts", path)
        self.assertIsNotNone(spec)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        query = module.PresentationQuery(scope="instances")
        self.assertEqual(query.scope, "instances")
        self.assertRegex(module.SOURCE_DIGEST, r"^[0-9a-f]{64}$")

    def test_compatibility_report_classifies_required_optional_and_type_changes(self) -> None:
        previous = self.bundle()
        current = copy.deepcopy(previous)
        contract = current["contracts"][0]["schema"]
        contract["properties"]["optional_added"] = {"type": "string"}
        contract["properties"]["required_added"] = {"type": "string"}
        contract["required"].append("required_added")
        existing = next(iter(contract["properties"]))
        contract["properties"][existing]["type"] = "boolean"
        report = contract_compatibility.compare(previous, current)
        kinds = {item["kind"] for item in report["changes"]}
        self.assertIn("optional_field_added", kinds)
        self.assertIn("required_field_added", kinds)
        self.assertIn("type_changed", kinds)
        self.assertEqual(report["status"], "migration_required")
        self.assertFalse(report["semver_allocation_authorized"])


if __name__ == "__main__":
    unittest.main()
