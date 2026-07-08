import copy
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.interop import a2a_agent_card_contract

MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_a2a_agent_card_contract", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_a2a_agent_card_contract"] = aide_lite
SPEC.loader.exec_module(aide_lite)


def copy_a2a_source_files(root: Path) -> None:
    for rel in a2a_agent_card_contract.source_artifact_paths(REPO_ROOT):
        src = REPO_ROOT / rel
        if src.exists():
            dst = root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def validate_record(record: dict) -> list[str]:
    errors, _warnings = a2a_agent_card_contract.validate_a2a_agent_card_contract_with_schema(
        record,
        a2a_agent_card_contract.load_a2a_agent_card_contract_schema(REPO_ROOT),
    )
    return errors


def valid_record() -> dict:
    return a2a_agent_card_contract.build_a2a_agent_card_contract(REPO_ROOT)


class AIDEA2AAgentCardContractTests(unittest.TestCase):
    def assertInvalid(self, record: dict, needle: str) -> None:
        self.assertTrue(any(needle in item for item in validate_record(record)), validate_record(record))

    def test_01_valid_contract_passes_with_warnings(self) -> None:
        record = valid_record()
        errors, warnings = a2a_agent_card_contract.validate_a2a_agent_card_contract_with_schema(record, {})
        self.assertEqual(errors, [])
        self.assertTrue(warnings)
        self.assertEqual(record["kind"], "A2AAgentCardContract")

    def test_02_explicit_specification_release_passes(self) -> None:
        self.assertEqual(valid_record()["spec"]["target_a2a_specification_release"], "1.0.0")

    def test_03_explicit_protocol_version_passes(self) -> None:
        self.assertEqual(valid_record()["spec"]["target_a2a_protocol_version"], "1.0")

    def test_04_missing_protocol_pin_fails(self) -> None:
        record = valid_record()
        del record["spec"]["target_a2a_protocol_version"]
        self.assertInvalid(record, "target_a2a_protocol_version")

    def test_05_missing_specification_pin_fails(self) -> None:
        record = valid_record()
        del record["spec"]["target_a2a_specification_release"]
        self.assertInvalid(record, "target_a2a_specification_release")

    def test_06_protocol_0_1_0_fails(self) -> None:
        record = valid_record()
        record["spec"]["target_a2a_protocol_version"] = "0.1.0"
        self.assertInvalid(record, "target_a2a_protocol_version")

    def test_07_protocol_latest_fails(self) -> None:
        record = valid_record()
        record["spec"]["target_a2a_protocol_version"] = "latest"
        self.assertInvalid(record, "target_a2a_protocol_version")

    def test_08_interface_protocol_mismatch_fails(self) -> None:
        record = valid_record()
        record["spec"]["agent_card"]["supportedInterfaces"][0]["protocolVersion"] = "0.3"
        self.assertInvalid(record, "supportedInterfaces[0].protocolVersion")

    def test_09_agent_version_distinct_from_protocol_version(self) -> None:
        record = valid_record()
        self.assertNotEqual(record["spec"]["agent_implementation_version"], record["spec"]["target_a2a_protocol_version"])

    def test_10_standards_clean_fixture_passes(self) -> None:
        card = a2a_agent_card_contract.build_agent_card()
        self.assertEqual(set(card) - a2a_agent_card_contract.OFFICIAL_AGENT_CARD_FIELDS, set())
        self.assertEqual(validate_record(valid_record()), [])

    def test_11_missing_supported_interfaces_fails(self) -> None:
        record = valid_record()
        del record["spec"]["agent_card"]["supportedInterfaces"]
        self.assertInvalid(record, "supportedInterfaces")

    def test_12_empty_supported_interfaces_fails(self) -> None:
        record = valid_record()
        record["spec"]["agent_card"]["supportedInterfaces"] = []
        self.assertInvalid(record, "supportedInterfaces")

    def test_13_missing_name_fails(self) -> None:
        record = valid_record()
        del record["spec"]["agent_card"]["name"]
        self.assertInvalid(record, "agent_card.name")

    def test_14_missing_description_fails(self) -> None:
        record = valid_record()
        del record["spec"]["agent_card"]["description"]
        self.assertInvalid(record, "agent_card.description")

    def test_15_missing_capabilities_fails(self) -> None:
        record = valid_record()
        del record["spec"]["agent_card"]["capabilities"]
        self.assertInvalid(record, "agent_card.capabilities")

    def test_16_missing_default_input_modes_fails(self) -> None:
        record = valid_record()
        del record["spec"]["agent_card"]["defaultInputModes"]
        self.assertInvalid(record, "defaultInputModes")

    def test_17_missing_default_output_modes_fails(self) -> None:
        record = valid_record()
        del record["spec"]["agent_card"]["defaultOutputModes"]
        self.assertInvalid(record, "defaultOutputModes")

    def test_18_missing_skills_fails(self) -> None:
        record = valid_record()
        del record["spec"]["agent_card"]["skills"]
        self.assertInvalid(record, "agent_card.skills")

    def test_19_valid_https_fixture_interface_passes(self) -> None:
        interface = valid_record()["spec"]["agent_card"]["supportedInterfaces"][0]
        self.assertEqual(interface["url"], "https://aide.invalid/a2a/v1")
        self.assertEqual(interface["protocolBinding"], "JSONRPC")
        self.assertEqual(interface["protocolVersion"], "1.0")

    def test_20_null_interface_url_fails(self) -> None:
        record = valid_record()
        record["spec"]["agent_card"]["supportedInterfaces"][0]["url"] = None
        self.assertInvalid(record, "supportedInterfaces[0].url")

    def test_21_relative_interface_url_fails(self) -> None:
        record = valid_record()
        record["spec"]["agent_card"]["supportedInterfaces"][0]["url"] = "/a2a"
        self.assertInvalid(record, "supportedInterfaces[0].url")

    def test_22_missing_protocol_binding_fails(self) -> None:
        record = valid_record()
        del record["spec"]["agent_card"]["supportedInterfaces"][0]["protocolBinding"]
        self.assertInvalid(record, "protocolBinding")

    def test_23_missing_protocol_version_fails(self) -> None:
        record = valid_record()
        del record["spec"]["agent_card"]["supportedInterfaces"][0]["protocolVersion"]
        self.assertInvalid(record, "protocolVersion")

    def test_24_non_1_0_protocol_version_fails(self) -> None:
        record = valid_record()
        record["spec"]["agent_card"]["supportedInterfaces"][0]["protocolVersion"] = "2.0"
        self.assertInvalid(record, "protocolVersion")

    def test_25_duplicate_interface_fails(self) -> None:
        record = valid_record()
        record["spec"]["agent_card"]["supportedInterfaces"].append(copy.deepcopy(record["spec"]["agent_card"]["supportedInterfaces"][0]))
        self.assertInvalid(record, "duplicate supported interface")

    def test_26_live_looking_fixture_url_fails(self) -> None:
        record = valid_record()
        record["spec"]["agent_card"]["supportedInterfaces"][0]["url"] = "https://example.com/a2a"
        self.assertInvalid(record, "approved non-live .invalid fixture host")

    def test_27_fixture_url_causes_no_network_activity(self) -> None:
        record = valid_record()
        self.assertTrue(record["spec"]["agent_card_fixture"]["network_target_intentionally_non_live"])
        self.assertFalse(record["status"]["network_call_performed"])

    def test_28_top_level_url_fails(self) -> None:
        record = valid_record()
        record["spec"]["agent_card"]["url"] = None
        self.assertInvalid(record, "agent_card.url")

    def test_29_top_level_supports_authenticated_extended_card_fails(self) -> None:
        record = valid_record()
        record["spec"]["agent_card"]["supportsAuthenticatedExtendedCard"] = False
        self.assertInvalid(record, "supportsAuthenticatedExtendedCard")

    def test_30_top_level_supports_extended_agent_card_fails(self) -> None:
        record = valid_record()
        record["spec"]["agent_card"]["supportsExtendedAgentCard"] = False
        self.assertInvalid(record, "supportsExtendedAgentCard")

    def test_31_state_transition_history_capability_fails(self) -> None:
        record = valid_record()
        record["spec"]["agent_card"]["capabilities"]["stateTransitionHistory"] = False
        self.assertInvalid(record, "stateTransitionHistory")

    def test_32_extended_agent_card_false_passes(self) -> None:
        self.assertFalse(valid_record()["spec"]["agent_card"]["capabilities"]["extendedAgentCard"])

    def test_33_capability_true_with_runtime_false_fails(self) -> None:
        for field in ["streaming", "pushNotifications", "extendedAgentCard"]:
            record = valid_record()
            record["spec"]["agent_card"]["capabilities"][field] = True
            self.assertInvalid(record, field)

    def test_34_omitted_provider_passes(self) -> None:
        self.assertNotIn("provider", valid_record()["spec"]["agent_card"])

    def test_35_valid_provider_passes_when_present(self) -> None:
        record = valid_record()
        record["spec"]["agent_card"]["provider"] = {
            "organization": "AIDE",
            "url": "https://aide.invalid/provider",
        }
        self.assertEqual(validate_record(record), [])

    def test_36_provider_null_url_fails(self) -> None:
        record = valid_record()
        record["spec"]["agent_card"]["provider"] = {"organization": "AIDE", "url": None}
        self.assertInvalid(record, "provider.url")

    def test_37_provider_missing_url_fails(self) -> None:
        record = valid_record()
        record["spec"]["agent_card"]["provider"] = {"organization": "AIDE"}
        self.assertInvalid(record, "provider.url")

    def test_38_provider_empty_organization_fails(self) -> None:
        record = valid_record()
        record["spec"]["agent_card"]["provider"] = {"organization": "", "url": "https://aide.invalid/provider"}
        self.assertInvalid(record, "provider.organization")

    def test_39_empty_official_skills_array_passes(self) -> None:
        self.assertEqual(valid_record()["spec"]["agent_card"]["skills"], [])

    def test_40_aide_governance_field_inside_agent_skill_fails(self) -> None:
        record = valid_record()
        skill = {
            "id": "aide.queue.inspect",
            "name": "Inspect",
            "description": "Bad official skill",
            "tags": ["queue"],
            "examples": [],
            "inputModes": ["application/json"],
            "outputModes": ["application/json"],
            "implemented": False,
        }
        record["spec"]["agent_card"]["skills"] = [skill]
        self.assertInvalid(record, "implemented")

    def test_41_unknown_agent_skill_field_fails(self) -> None:
        record = valid_record()
        record["spec"]["agent_card"]["skills"] = [
            {
                "id": "aide.queue.inspect",
                "name": "Inspect",
                "description": "Bad official skill",
                "tags": ["queue"],
                "examples": [],
                "inputModes": ["application/json"],
                "outputModes": ["application/json"],
                "unknown": True,
            }
        ]
        self.assertInvalid(record, "unknown")

    def test_42_candidate_skills_outside_card_pass(self) -> None:
        record = valid_record()
        self.assertEqual(len(record["spec"]["candidate_skill_governance"]), 4)
        self.assertEqual(record["spec"]["agent_card"]["skills"], [])

    def test_43_candidate_skill_retains_operation_mapping(self) -> None:
        for skill in valid_record()["spec"]["candidate_skill_governance"]:
            self.assertEqual(skill["aide_operation_mapping"], skill["skill_id"])

    def test_44_candidate_skill_remains_not_callable(self) -> None:
        for skill in valid_record()["spec"]["candidate_skill_governance"]:
            self.assertFalse(skill["implemented"])
            self.assertFalse(skill["callable"])

    def test_45_official_skill_count_zero_candidate_count_four(self) -> None:
        record = valid_record()
        self.assertEqual(record["spec"]["official_advertised_skill_count"], 0)
        self.assertEqual(record["spec"]["candidate_skill_count"], 4)

    def test_46_no_security_fields_passes(self) -> None:
        self.assertNotIn("securitySchemes", valid_record()["spec"]["agent_card"])
        self.assertNotIn("securityRequirements", valid_record()["spec"]["agent_card"])

    def test_47_security_requirement_without_scheme_fails(self) -> None:
        record = valid_record()
        record["spec"]["agent_card"]["securityRequirements"] = [{"apiKey": []}]
        self.assertInvalid(record, "securityRequirements")

    def test_48_legacy_top_level_security_field_fails(self) -> None:
        record = valid_record()
        record["spec"]["agent_card"]["security"] = []
        self.assertInvalid(record, "agent_card.security")

    def test_49_no_signatures_passes(self) -> None:
        self.assertNotIn("signatures", valid_record()["spec"]["agent_card"])

    def test_50_hash_is_not_agent_card_signature(self) -> None:
        record = valid_record()
        record["spec"]["agent_card"]["signatures"] = [{"signature": "sha256:abc"}]
        self.assertInvalid(record, "signatures")

    def test_51_no_endpoint_starts(self) -> None:
        self.assertFalse(valid_record()["status"]["live_a2a_endpoint_started"])

    def test_52_no_registration_occurs(self) -> None:
        self.assertFalse(valid_record()["status"]["agent_registered"])

    def test_53_no_network_call_occurs(self) -> None:
        self.assertFalse(valid_record()["status"]["network_call_performed"])

    def test_54_no_task_delegation_occurs(self) -> None:
        self.assertFalse(valid_record()["status"]["task_delegation_performed"])

    def test_55_no_worker_starts(self) -> None:
        self.assertFalse(valid_record()["status"]["worker_dispatched"])

    def test_56_no_provider_model_call_occurs(self) -> None:
        self.assertFalse(valid_record()["status"]["model_or_provider_called"])

    def test_57_no_target_mutation_occurs(self) -> None:
        self.assertFalse(valid_record()["status"]["repository_target_mutated"])

    def test_58_unsupported_execution_commands_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_a2a_source_files(root)
            for command in ["start", "serve", "register", "publish", "discover", "send", "delegate", "submit", "stream", "subscribe", "cancel", "authenticate", "connect"]:
                with self.subTest(command=command):
                    with self.assertRaises(SystemExit):
                        aide_lite.main(["--repo-root", str(root), "a2a-agent-card-contract", command])

    def test_59_projection_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_a2a_source_files(root)
            a2a_agent_card_contract.write_a2a_agent_card_contract_reports(root)
            first = (root / a2a_agent_card_contract.AGENT_CARD_CONTRACT_JSON).read_bytes()
            a2a_agent_card_contract.write_a2a_agent_card_contract_reports(root)
            second = (root / a2a_agent_card_contract.AGENT_CARD_CONTRACT_JSON).read_bytes()
        self.assertEqual(first, second)

    def test_60_predecessor_artifacts_remain_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_a2a_source_files(root)
            watched = [
                root / ".aide/interop/exports/manifest.json",
                root / ".aide/interop/exports/a2a-agent-card.preview.json",
                root / ".aide/reports/interop-exports-accept/acceptance-report.json",
                root / ".aide/reports/mcp-server-contract-accept/acceptance-report.json",
            ]
            before = {path.as_posix(): path.read_bytes() for path in watched if path.exists()}
            report = a2a_agent_card_contract.write_a2a_agent_card_contract_reports(root)
            after = {path.as_posix(): path.read_bytes() for path in watched if path.exists()}
        self.assertEqual(before, after)
        self.assertFalse(report["source_artifacts_mutated"])

    def test_61_explicit_non_capabilities_present(self) -> None:
        record = valid_record()
        self.assertEqual(record["spec"]["explicit_non_capabilities"], a2a_agent_card_contract.EXPLICIT_NON_CAPABILITIES)
        self.assertIn("live_a2a_endpoint", record["spec"]["explicit_non_capabilities"])
        self.assertIn("task_delegation", record["spec"]["explicit_non_capabilities"])

    def test_62_cli_status_project_validate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_a2a_source_files(root)
            for command in ["status", "project", "validate"]:
                with self.subTest(command=command):
                    exit_code = aide_lite.main(["--repo-root", str(root), "a2a-agent-card-contract", command])
                    self.assertEqual(exit_code, 0)
            report = json.loads((root / a2a_agent_card_contract.VALIDATION_JSON).read_text(encoding="utf-8"))
            self.assertEqual(report["validation_status"], "PASS_WITH_WARNINGS")

    def test_63_validation_writes_json_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_a2a_source_files(root)
            report = a2a_agent_card_contract.validate_a2a_agent_card_contract(root)
            self.assertEqual(report["validation_status"], "PASS_WITH_WARNINGS")
            self.assertTrue((root / a2a_agent_card_contract.ARTIFACT_INDEX_JSON).exists())
            self.assertTrue((root / a2a_agent_card_contract.AGENT_CARD_REPORT_JSON).exists())

    def test_64_mutating_status_combination_fails(self) -> None:
        for field in ["patch_applied", "repository_target_mutated", "github_mutation_performed", "trusted"]:
            record = valid_record()
            record["status"][field] = True
            self.assertInvalid(record, field)

    def test_65_candidate_skill_bad_flags_fail(self) -> None:
        record = valid_record()
        record["spec"]["candidate_skill_governance"][0]["callable"] = True
        self.assertInvalid(record, "callable")

    def test_66_unknown_required_capability_fails_closed(self) -> None:
        record = valid_record()
        record["spec"]["required_aide_capabilities"].append("aide.runtime.execute")
        self.assertInvalid(record, "required_aide_capabilities")


if __name__ == "__main__":
    unittest.main()
