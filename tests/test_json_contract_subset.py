from __future__ import annotations

import unittest

from tools import json_contract, schema_validate


class JsonContractSubsetTests(unittest.TestCase):
    def test_live_schema_policy_uses_only_enforced_keywords(self) -> None:
        self.assertEqual(schema_validate.validate_live_schema_subset(schema_validate.LIVE_SCHEMA_POLICY), [])

    def test_unsupported_keyword_is_not_silently_accepted(self) -> None:
        problems = json_contract.supported_schema_problems({"type": "string", "anyOf": []})
        self.assertTrue(any("unsupported schema keyword 'anyOf'" in problem for problem in problems), problems)

    def test_unknown_type_is_not_silently_accepted(self) -> None:
        problems = json_contract.validate("anything", {"type": "mystery"})
        self.assertTrue(any("unsupported type 'mystery'" in problem for problem in problems), problems)

    def test_dynamic_properties_are_validated(self) -> None:
        schema = {"type": "object", "additionalProperties": {"type": "integer", "minimum": 1}}
        self.assertEqual(json_contract.validate({"one": 1}, schema), [])
        self.assertTrue(json_contract.validate({"zero": 0}, schema))
        self.assertTrue(json_contract.validate({"text": "1"}, schema))

    def test_pattern_and_array_bounds_are_enforced(self) -> None:
        schema = {
            "type": "object",
            "required": ["command", "items"],
            "properties": {
                "command": {"type": "string", "pattern": r"^[a-z]+\.[a-z-]+$"},
                "items": {"type": "array", "minItems": 1, "maxItems": 2, "items": {"type": "string"}},
            },
            "additionalProperties": False,
        }
        self.assertEqual(json_contract.validate({"command": "instance.create", "items": ["one"]}, schema), [])
        self.assertTrue(json_contract.validate({"command": "INVALID", "items": []}, schema))
        self.assertTrue(json_contract.validate({"command": "instance.create", "items": ["1", "2", "3"]}, schema))


if __name__ == "__main__":
    unittest.main()
