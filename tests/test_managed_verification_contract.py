# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Strict owned-observation shape at the public verification response boundary."""
import copy
import json
from pathlib import Path
import unittest

import jsonschema

ROOT = Path(__file__).resolve().parents[1]


class ManagedVerificationContract(unittest.TestCase):
    def test_owned_observation_shapes(self):
        schema = json.loads((ROOT / "contracts/schema/factorio/usk_verification_report.v1.schema.json").read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        validator = jsonschema.Draft202012Validator(schema)
        report = json.loads((ROOT / "tests/golden/commands/installs.verify.success.json").read_text())
        validator.validate(report)
        for path in ["../foreign", "/foreign", "bin\\foreign", "foreign\0file", "bin/", "file.", "file ", "bin/../file"]:
            with self.subTest(path=path):
                changed = copy.deepcopy(report)
                changed["files"][0]["relative_path"] = path
                self.assertTrue(list(validator.iter_errors(changed)))
        for status in ["missing", "wrong_type", "unreadable"]:
            changed = copy.deepcopy(report)
            changed["files"][0]["status"] = status
            self.assertTrue(list(validator.iter_errors(changed)))
            del changed["files"][0]["actual_sha256"]
            validator.validate(changed)
        for status in ["present", "modified"]:
            changed = copy.deepcopy(report)
            changed["files"][0]["status"] = status
            del changed["files"][0]["actual_sha256"]
            self.assertTrue(list(validator.iter_errors(changed)))
        changed = copy.deepcopy(report)
        changed["directories"][0]["status"] = "unreadable"
        self.assertTrue(list(validator.iter_errors(changed)))


if __name__ == "__main__":
    unittest.main()
