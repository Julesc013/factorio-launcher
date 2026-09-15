# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import json
import unittest

import jsonschema

from tools import command_contract_check


class CommandContractTests(unittest.TestCase):
    def test_command_contract_check(self) -> None:
        self.assertEqual(command_contract_check.main(), 0)

    def test_uninstall_plan_schema_rejects_runtime_invalid_shapes(self) -> None:
        schema = json.loads(
            (
                command_contract_check.ROOT
                / "contracts/schema/factorio/usk_operation_plan.v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        golden = json.loads(
            (
                command_contract_check.ROOT
                / "tests/golden/commands/installs.uninstall.plan.success.json"
            ).read_text(encoding="utf-8")
        )
        validator = jsonschema.Draft202012Validator(schema)
        validator.validate(golden)

        state_effect = next(
            effect for effect in golden["effects"] if effect["kind"] == "write_state"
        )
        missing_state = copy.deepcopy(golden)
        missing_state["effects"] = [
            effect for effect in missing_state["effects"] if effect["kind"] != "write_state"
        ]
        duplicate_state = copy.deepcopy(golden)
        duplicate = copy.deepcopy(state_effect)
        duplicate["effect_id"] = "effect.duplicate-state"
        duplicate_state["effects"].append(duplicate)
        malformed_paths = ("..", "/absolute", "C:\\Windows", "bin/./x", "bin//x", "bin/x/")
        invalid_documents = [missing_state, duplicate_state]
        for malformed_path in malformed_paths:
            document = copy.deepcopy(golden)
            document["effects"][0]["relative_path"] = malformed_path
            invalid_documents.append(document)
        relative_root = copy.deepcopy(golden)
        relative_root["roots"][0]["root"] = "relative/install"
        invalid_documents.append(relative_root)

        for document in invalid_documents:
            with self.subTest(document=document):
                self.assertTrue(list(validator.iter_errors(document)))


if __name__ == "__main__":
    unittest.main()
