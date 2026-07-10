from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.native_cli import invoke
from tools import json_contract

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"
SCHEMAS = ROOT / "contracts" / "schema"


def run_json(args: list[str]) -> tuple[int, dict, str]:
    code, stdout, stderr = invoke(args)
    return code, json.loads(stdout), stderr


class RuntimeContractTruthTests(unittest.TestCase):
    def test_instance_output_matches_persisted_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _install, stderr = run_json(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            code, instance, stderr = run_json(
                [
                    "--workspace",
                    tmp,
                    "instances",
                    "create",
                    "Contract Truth",
                    "--install",
                    "fixture",
                    "--json",
                ]
            )
            self.assertEqual(code, 0, stderr)
            schema = json_contract.load_schema(SCHEMAS / "factorio" / "factorio_instance.v1.schema.json")
            self.assertEqual(json_contract.validate(instance, schema), [])
            persisted = json.loads(
                (Path(tmp) / "instances" / "contract-truth" / "instance.v1.json").read_text(encoding="utf-8")
            )
            self.assertEqual(json_contract.validate(persisted, schema), [])

    def test_discovery_and_doctor_live_outputs_match_schemas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            code, discovery, stderr = run_json(
                [
                    "--workspace",
                    str(workspace),
                    "installs",
                    "scan",
                    "--path",
                    str(FIXTURE_INSTALL),
                    "--json",
                ]
            )
            self.assertEqual(code, 0, stderr)
            discovery_schema = json_contract.load_schema(
                SCHEMAS / "factorio" / "factorio_discovery_report.v1.schema.json"
            )
            self.assertEqual(json_contract.validate(discovery, discovery_schema), [])

            code, doctor, stderr = run_json(["--workspace", str(workspace), "doctor", "--json"])
            self.assertEqual(code, 0, stderr)
            doctor_schema = json_contract.load_schema(
                SCHEMAS / "factorio" / "factorio_diagnostic_report.v1.schema.json"
            )
            self.assertEqual(json_contract.validate(doctor, doctor_schema), [])

    def test_declared_read_only_commands_create_no_workspace_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            code, _doctor, stderr = run_json(["--workspace", str(workspace), "doctor", "--json"])
            self.assertEqual(code, 0, stderr)
            self.assertFalse(workspace.exists())

            code, _scan, stderr = run_json(
                [
                    "--workspace",
                    str(workspace),
                    "installs",
                    "scan",
                    "--path",
                    str(FIXTURE_INSTALL),
                    "--json",
                ]
            )
            self.assertEqual(code, 0, stderr)
            self.assertFalse(workspace.exists())

    def test_quarantined_refusals_match_common_refusal_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _install, stderr = run_json(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            code, _instance, stderr = run_json(
                ["--workspace", tmp, "instances", "create", "Blocked Run", "--install", "fixture", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            code, response, _stderr = run_json(
                ["--workspace", tmp, "run", "blocked-run", "--execute", "--json"]
            )
            self.assertEqual(code, 1)
            refusal_schema = json_contract.load_schema(SCHEMAS / "common" / "refusal.v1.schema.json")
            self.assertEqual(json_contract.validate(response["refusal"], refusal_schema), [])


if __name__ == "__main__":
    unittest.main()
