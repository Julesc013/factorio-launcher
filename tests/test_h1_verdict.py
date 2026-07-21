# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import re
import tomllib
import unittest
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
VERDICT_PATH = (
    ROOT
    / "docs"
    / "quality"
    / "evidence"
    / "h1"
    / "eb629caa-steam-backed.h1-verdict.v1.json"
)
SCHEMA_PATH = (
    ROOT
    / "contracts"
    / "schema"
    / "factorio"
    / "factorio_h1_verdict.v1.schema.json"
)


class H1VerdictTests(unittest.TestCase):
    def test_sanitized_verdict_matches_its_schema(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        verdict = json.loads(VERDICT_PATH.read_text(encoding="utf-8"))

        jsonschema.Draft202012Validator(schema).validate(verdict)
        self.assertEqual("Fail", verdict["operator_verdict"])
        self.assertTrue(verdict["operator_reviewed"])
        self.assertEqual("protected_root_change_detected", verdict["result"])

    def test_record_contains_no_raw_machine_or_account_identity(self) -> None:
        text = VERDICT_PATH.read_text(encoding="utf-8")

        self.assertNotRegex(text, re.compile(r"[A-Z]:\\", re.IGNORECASE))
        self.assertNotIn("steam_user_id", text)
        self.assertNotIn("account_name", text)
        self.assertNotIn("raw_evidence_path", text)

    def test_fail_does_not_promote_execution_authority(self) -> None:
        with (ROOT / "release" / "index" / "project_status.v2.toml").open("rb") as handle:
            status = tomllib.load(handle)

        self.assertEqual("Fail", status["execution"]["operator_verdict"])
        self.assertEqual("unavailable", status["execution"]["status"])
        self.assertFalse(status["safe_beta"])
        self.assertIn("launch.execute.instance_isolated", status["quarantined_capabilities"])
        self.assertIn("launch.execute.hermetic", status["quarantined_capabilities"])
        self.assertEqual("historical_steam_backed_h1_only", status["execution"]["operator_verdict_scope"])


if __name__ == "__main__":
    unittest.main()
