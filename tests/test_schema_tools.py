# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path

from tools import package_check, schema_validate, security_policy_check, strict_check, structure_policy_check


class ToolTests(unittest.TestCase):
    def test_schema_validate(self) -> None:
        self.assertEqual(schema_validate.main(), 0)

    def test_standards_metaschema_rejects_invalid_keyword_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "invalid.schema.json"
            path.write_text(json.dumps({
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": "https://example.invalid/test",
                "title": "Invalid",
                "type": "object",
                "required": "not-an-array",
            }), encoding="utf-8")
            problems = schema_validate.validate_schema_file(path)
        self.assertTrue(any("standards metaschema rejection" in problem for problem in problems), problems)

    def test_structure_policy_check(self) -> None:
        self.assertEqual(structure_policy_check.main(), 0)

    def test_security_policy_check(self) -> None:
        self.assertEqual(security_policy_check.main(), 0)

    def test_package_check(self) -> None:
        self.assertEqual(package_check.main(), 0)

    def test_strict_check(self) -> None:
        self.assertEqual(strict_check.main(), 0)


if __name__ == "__main__":
    unittest.main()
