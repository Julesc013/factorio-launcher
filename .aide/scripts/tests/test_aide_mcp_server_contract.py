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

from core.interop import mcp_server_contract

MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_mcp_server_contract", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_mcp_server_contract"] = aide_lite
SPEC.loader.exec_module(aide_lite)


def copy_mcp_source_files(root: Path) -> None:
    for rel in mcp_server_contract.source_artifact_paths(REPO_ROOT):
        src = REPO_ROOT / rel
        if src.exists():
            dst = root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def validate_record(record: dict) -> list[str]:
    errors, _warnings = mcp_server_contract.validate_mcp_server_contract_with_schema(
        record,
        mcp_server_contract.load_mcp_server_contract_schema(REPO_ROOT),
    )
    return errors


def validate_fixtures(fixtures: dict) -> list[str]:
    return mcp_server_contract.validate_fixtures(
        fixtures,
        mcp_server_contract.build_mcp_server_contract(REPO_ROOT),
    )


class AIDEMcpServerContractTests(unittest.TestCase):
    def test_01_valid_minimal_contract_passes_with_warnings(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        errors, warnings = mcp_server_contract.validate_mcp_server_contract_with_schema(record, {})
        self.assertEqual(errors, [])
        self.assertTrue(warnings)
        self.assertEqual(record["kind"], "McpServerContract")

    def test_02_stable_contract_identity(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        self.assertEqual(record["spec"]["contract_id"], "mcp-server-contract-v0")
        self.assertEqual(record["spec"]["advisory_contract_ref"], "aide://interop/mcp-server-contract-v0")
        self.assertFalse(record["spec"]["reference_id_kind_supported"])

    def test_03_exact_target_protocol_version(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        self.assertEqual(record["spec"]["target_protocol_version"], "2025-11-25")
        self.assertEqual(record["spec"]["supported_protocol_versions"], ["2025-11-25"])
        self.assertFalse(record["spec"]["backward_compatibility_claimed"])
        self.assertFalse(record["spec"]["forward_compatibility_claimed"])

    def test_04_exact_jsonrpc_version(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        self.assertEqual(record["spec"]["jsonrpc_version"], "2.0")

    def test_05_unsupported_protocol_fixture_refuses(self) -> None:
        fixture = mcp_server_contract.build_fixtures()["protocol-version-refusal.json"]
        self.assertEqual(fixture["jsonrpc"], "2.0")
        self.assertEqual(fixture["error"]["data"]["reason_code"], "MCP_UNSUPPORTED_PROTOCOL_VERSION")
        self.assertIn("2025-11-25", fixture["error"]["data"]["supported_protocol_versions"])

    def test_06_initialize_request_present(self) -> None:
        fixture = mcp_server_contract.build_fixtures()["initialize-request.json"]
        self.assertEqual(fixture["method"], "initialize")
        self.assertEqual(fixture["params"]["protocolVersion"], "2025-11-25")

    def test_07_initialize_result_present(self) -> None:
        fixture = mcp_server_contract.build_fixtures()["initialize-result.json"]
        self.assertEqual(fixture["result"]["protocolVersion"], "2025-11-25")
        self.assertIn("serverInfo", fixture["result"])

    def test_08_initialized_notification_present(self) -> None:
        fixture = mcp_server_contract.build_fixtures()["initialized-notification.json"]
        self.assertEqual(fixture["method"], "notifications/initialized")

    def test_09_operation_cannot_precede_initialization_in_lifecycle_model(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        states = [item["state"] for item in record["spec"]["lifecycle_expectations"]]
        self.assertLess(states.index("initialization"), states.index("operation"))
        bad = copy.deepcopy(record)
        bad["spec"]["lifecycle_expectations"] = list(reversed(bad["spec"]["lifecycle_expectations"]))
        self.assertTrue(any("initialization before operation" in item for item in validate_record(bad)))

    def test_10_declared_capabilities_match_catalogues(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        declared = record["spec"]["declared_contract_capabilities"]
        self.assertEqual(declared["resources"]["catalog_defined"], bool(record["spec"]["resources"]))
        self.assertEqual(declared["tools"]["catalog_defined"], bool(record["spec"]["tools"]))
        self.assertTrue(declared["prompts"]["catalog_defined"])

    def test_11_unknown_required_capability_fails_closed(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        record["spec"]["required_mcp_capabilities"].append("sampling")
        self.assertTrue(any("unknown required MCP capability" in item for item in validate_record(record)))

    def test_12_resource_uris_validate(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        for resource in record["spec"]["resources"]:
            valid, reason = mcp_server_contract.validate_resource_uri(resource["uri"])
            self.assertTrue(valid, reason)

    def test_13_invalid_resource_uri_fails(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        record["spec"]["resources"][0]["uri"] = "file:///etc/passwd"
        self.assertTrue(any("invalid resource URI" in item for item in validate_record(record)))

    def test_14_duplicate_resource_uri_fails(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        record["spec"]["resources"][1]["uri"] = record["spec"]["resources"][0]["uri"]
        self.assertTrue(any("duplicate resource URI" in item for item in validate_record(record)))

    def test_15_resource_template_is_bounded(self) -> None:
        self.assertTrue(mcp_server_contract.validate_resource_uri("aide://workunit/{id}")[0])
        self.assertFalse(mcp_server_contract.validate_resource_uri("aide://workunit/{id")[0])

    def test_16_no_arbitrary_filesystem_resource_template_exists(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        for resource in record["spec"]["resources"]:
            self.assertFalse(resource["uri"].startswith("file://"))
            self.assertNotIn(".aide.local", resource["uri"])

    def test_17_tools_have_unique_valid_names(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        names = [item["name"] for item in record["spec"]["tools"]]
        self.assertEqual(len(names), len(set(names)))
        for name in names:
            self.assertTrue(mcp_server_contract.validate_tool_name(name)[0])

    def test_18_tool_input_schemas_are_objects(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        for tool in record["spec"]["tools"]:
            self.assertEqual(tool["inputSchema"]["type"], "object")

    def test_19_duplicate_tool_name_fails(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        record["spec"]["tools"][1]["name"] = record["spec"]["tools"][0]["name"]
        self.assertTrue(any("duplicate tool name" in item for item in validate_record(record)))

    def test_20_mutation_capable_tool_fails_v0_validation(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        record["spec"]["tools"][0]["name"] = "aide.patch.apply"
        record["spec"]["tools"][0]["side_effect_class"] = "mutation"
        errors = validate_record(record)
        self.assertTrue(any("mutation-capable tool" in item or "read-only/report-only" in item for item in errors))

    def test_21_tools_call_fixture_refuses_not_executes(self) -> None:
        fixture = mcp_server_contract.build_fixtures()["tools-call-refusal.json"]
        self.assertIn("error", fixture)
        self.assertNotIn("result", fixture)
        self.assertEqual(fixture["error"]["data"]["reason_code"], "MCP_RUNTIME_NOT_IMPLEMENTED")

    def test_22_prompt_catalogue_is_empty_and_structural(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        self.assertEqual(record["spec"]["prompts"], [])
        fixture = mcp_server_contract.build_fixtures(record)["prompts-list-result.json"]
        self.assertEqual(fixture["result"]["prompts"], [])

    def test_23_invalid_prompt_argument_definition_fails(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        record["spec"]["prompts"] = [{"name": "aide.invalid", "arguments": [{"description": "missing name"}]}]
        self.assertTrue(any("argument definitions" in item for item in validate_record(record)))

    def test_24_resource_not_found_fixture_uses_bounded_error_mapping(self) -> None:
        fixture = mcp_server_contract.build_fixtures()["resource-not-found-refusal.json"]
        self.assertEqual(fixture["error"]["code"], -32002)
        self.assertEqual(fixture["error"]["message"], "Resource not found")
        self.assertEqual(fixture["error"]["data"]["reason_code"], "MCP_RESOURCE_NOT_FOUND")

    def test_25_typed_aide_refusal_data_is_preserved(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        reason_codes = {item["reason_code"] for item in record["spec"]["refusal_mappings"]}
        self.assertIn("AIDE_POLICY_OR_GRANT_UNAVAILABLE", reason_codes)

    def test_26_stdio_profile_records_not_implemented(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        stdio = next(item for item in record["spec"]["transport_profiles"] if item["name"] == "stdio")
        self.assertEqual(stdio["implementation_status"], "not_implemented")

    def test_27_streamable_http_profile_records_not_implemented(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        http = next(item for item in record["spec"]["transport_profiles"] if item["name"] == "streamable_http")
        self.assertEqual(http["implementation_status"], "not_implemented")

    def test_28_http_profile_records_origin_validation_requirement(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        http = next(item for item in record["spec"]["transport_profiles"] if item["name"] == "streamable_http")
        self.assertIn("Origin validation", http["security_requirements"])

    def test_29_http_profile_records_localhost_default_expectation(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        http = next(item for item in record["spec"]["transport_profiles"] if item["name"] == "streamable_http")
        self.assertIn("localhost-only default for local service", http["security_requirements"])

    def test_30_authorization_declared_but_unimplemented(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        auth = record["spec"]["authorization"]
        self.assertTrue(auth["authorization_supported_by_contract"])
        self.assertFalse(auth["authorization_implemented"])

    def test_31_no_concrete_credentials_or_secret_values_appear(self) -> None:
        text = mcp_server_contract.stable_json(mcp_server_contract.build_mcp_server_contract(REPO_ROOT))
        forbidden_fragments = ["sk-", "xoxb-", "-----BEGIN PRIVATE KEY-----", "password=", "api_key="]
        for fragment in forbidden_fragments:
            self.assertNotIn(fragment, text)

    def test_32_no_live_endpoint_appears(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        self.assertFalse(record["status"]["http_endpoint_bound"])
        self.assertNotIn("http://", mcp_server_contract.stable_json(record))
        self.assertNotIn("https://", mcp_server_contract.stable_json(record))

    def test_33_runtime_facts_all_remain_false(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        for field in mcp_server_contract.FALSE_RUNTIME_FIELDS:
            self.assertFalse(record["status"][field], field)

    def test_34_no_worker_model_or_network_activity_occurs(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        self.assertFalse(record["status"]["worker_dispatched"])
        self.assertFalse(record["status"]["model_or_provider_called"])
        self.assertFalse(record["status"]["network_call_performed"])

    def test_35_repeated_projection_is_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_mcp_source_files(root)
            mcp_server_contract.write_mcp_server_contract_reports(root)
            first = (root / mcp_server_contract.SERVER_CONTRACT_JSON).read_bytes()
            mcp_server_contract.write_mcp_server_contract_reports(root)
            second = (root / mcp_server_contract.SERVER_CONTRACT_JSON).read_bytes()
        self.assertEqual(first, second)

    def test_36_source_interop_export_artifacts_remain_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_mcp_source_files(root)
            source_paths = [
                root / ".aide/interop/exports/manifest.json",
                root / ".aide/interop/exports/mcp-manifest.preview.json",
            ]
            before = {path.as_posix(): path.read_bytes() for path in source_paths if path.exists()}
            report = mcp_server_contract.write_mcp_server_contract_reports(root)
            after = {path.as_posix(): path.read_bytes() for path in source_paths if path.exists()}
        self.assertEqual(before, after)
        self.assertFalse(report["source_artifacts_mutated"])

    def test_37_accepted_predecessor_records_remain_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_mcp_source_files(root)
            predecessors = [
                root / ".aide/reports/interop-exports-accept/acceptance-report.json",
                root / ".aide/reports/context-pack-v2-resume-accept/acceptance-report.json",
            ]
            before = {path.as_posix(): path.read_bytes() for path in predecessors if path.exists()}
            mcp_server_contract.write_mcp_server_contract_reports(root)
            after = {path.as_posix(): path.read_bytes() for path in predecessors if path.exists()}
        self.assertEqual(before, after)

    def test_38_unsupported_execution_commands_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_mcp_source_files(root)
            for command in ["start", "serve", "connect", "call", "listen", "install", "authorize"]:
                with self.subTest(command=command):
                    with self.assertRaises(SystemExit):
                        aide_lite.main(["--repo-root", str(root), "mcp-server-contract", command])

    def test_39_static_mcp_preview_and_contract_projection_are_consistent(self) -> None:
        preview = json.loads((REPO_ROOT / ".aide/interop/exports/mcp-manifest.preview.json").read_text(encoding="utf-8"))
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        self.assertFalse(preview["server_implemented"])
        self.assertEqual(preview["transport"], "none")
        self.assertEqual(record["spec"]["server_info"]["implementation_status"], "contract_only")

    def test_40_explicit_non_capabilities_remain_present(self) -> None:
        record = mcp_server_contract.build_mcp_server_contract(REPO_ROOT)
        self.assertEqual(record["spec"]["explicit_non_capabilities"], mcp_server_contract.EXPLICIT_NON_CAPABILITIES)
        self.assertIn("live_mcp_server", record["spec"]["explicit_non_capabilities"])
        self.assertIn("network_calls", record["spec"]["explicit_non_capabilities"])

    def test_41_resources_list_request_omits_absent_cursor(self) -> None:
        fixture = mcp_server_contract.build_fixtures()["resources-list-request.json"]
        self.assertNotIn("params", fixture)

    def test_42_resources_list_result_omits_absent_next_cursor(self) -> None:
        fixture = mcp_server_contract.build_fixtures()["resources-list-result.json"]
        self.assertNotIn("nextCursor", fixture["result"])

    def test_43_tools_list_request_omits_absent_cursor(self) -> None:
        fixture = mcp_server_contract.build_fixtures()["tools-list-request.json"]
        self.assertNotIn("params", fixture)

    def test_44_tools_list_result_omits_absent_next_cursor(self) -> None:
        fixture = mcp_server_contract.build_fixtures()["tools-list-result.json"]
        self.assertNotIn("nextCursor", fixture["result"])

    def test_45_prompts_list_request_omits_absent_cursor(self) -> None:
        fixture = mcp_server_contract.build_fixtures()["prompts-list-request.json"]
        self.assertNotIn("params", fixture)

    def test_46_prompts_list_result_omits_absent_next_cursor(self) -> None:
        fixture = mcp_server_contract.build_fixtures()["prompts-list-result.json"]
        self.assertNotIn("nextCursor", fixture["result"])

    def test_47_any_supported_request_with_null_cursor_fails(self) -> None:
        fixtures = mcp_server_contract.build_fixtures()
        fixtures["resources-list-request.json"]["params"] = {"cursor": None}
        self.assertTrue(any("resources-list-request.json params.cursor" in item for item in validate_fixtures(fixtures)))

    def test_48_any_supported_result_with_null_next_cursor_fails(self) -> None:
        fixtures = mcp_server_contract.build_fixtures()
        fixtures["resources-list-result.json"]["result"]["nextCursor"] = None
        self.assertTrue(any("resources-list-result.json result.nextCursor" in item for item in validate_fixtures(fixtures)))

    def test_49_numeric_cursor_fails(self) -> None:
        fixtures = mcp_server_contract.build_fixtures()
        fixtures["tools-list-request.json"]["params"] = {"cursor": 12}
        self.assertTrue(any("tools-list-request.json params.cursor" in item for item in validate_fixtures(fixtures)))

    def test_50_object_cursor_fails(self) -> None:
        fixtures = mcp_server_contract.build_fixtures()
        fixtures["tools-list-request.json"]["params"] = {"cursor": {"opaque": "cursor"}}
        self.assertTrue(any("tools-list-request.json params.cursor" in item for item in validate_fixtures(fixtures)))

    def test_51_array_cursor_fails(self) -> None:
        fixtures = mcp_server_contract.build_fixtures()
        fixtures["tools-list-request.json"]["params"] = {"cursor": ["opaque-cursor"]}
        self.assertTrue(any("tools-list-request.json params.cursor" in item for item in validate_fixtures(fixtures)))

    def test_52_numeric_next_cursor_fails(self) -> None:
        fixtures = mcp_server_contract.build_fixtures()
        fixtures["tools-list-result.json"]["result"]["nextCursor"] = 12
        self.assertTrue(any("tools-list-result.json result.nextCursor" in item for item in validate_fixtures(fixtures)))

    def test_53_valid_string_cursor_passes(self) -> None:
        fixtures = mcp_server_contract.build_fixtures()
        fixtures["resources-list-request.json"]["params"] = {"cursor": "opaque-cursor-value"}
        self.assertEqual(validate_fixtures(fixtures), [])

    def test_54_valid_string_next_cursor_passes(self) -> None:
        fixtures = mcp_server_contract.build_fixtures()
        fixtures["resources-list-result.json"]["result"]["nextCursor"] = "opaque-next-cursor"
        self.assertEqual(validate_fixtures(fixtures), [])

    def test_55_omitted_params_passes_when_no_request_parameters_are_needed(self) -> None:
        fixtures = mcp_server_contract.build_fixtures()
        self.assertNotIn("params", fixtures["resources-list-request.json"])
        self.assertEqual(validate_fixtures(fixtures), [])

    def test_56_empty_params_object_passes_for_current_subset(self) -> None:
        fixtures = mcp_server_contract.build_fixtures()
        fixtures["resources-list-request.json"]["params"] = {}
        self.assertEqual(validate_fixtures(fixtures), [])

    def test_57_resource_not_found_using_old_custom_code_fails(self) -> None:
        fixtures = mcp_server_contract.build_fixtures()
        fixtures["resource-not-found-refusal.json"]["error"]["code"] = -32043
        self.assertTrue(any("resource-not-found-refusal.json error.code" in item for item in validate_fixtures(fixtures)))

    def test_58_resource_not_found_using_other_custom_code_fails(self) -> None:
        fixtures = mcp_server_contract.build_fixtures()
        fixtures["resource-not-found-refusal.json"]["error"]["code"] = -32040
        self.assertTrue(any("resource-not-found-refusal.json error.code" in item for item in validate_fixtures(fixtures)))

    def test_59_runtime_not_implemented_custom_refusal_remains_valid(self) -> None:
        fixtures = mcp_server_contract.build_fixtures()
        fixture = fixtures["tools-call-refusal.json"]
        self.assertEqual(fixture["error"]["code"], -32040)
        self.assertEqual(fixture["error"]["data"]["reason_code"], "MCP_RUNTIME_NOT_IMPLEMENTED")
        self.assertEqual(validate_fixtures(fixtures), [])

    def test_60_required_capability_custom_refusal_remains_valid(self) -> None:
        fixtures = mcp_server_contract.build_fixtures()
        fixture = fixtures["capability-refusal.json"]
        self.assertEqual(fixture["error"]["code"], -32042)
        self.assertEqual(fixture["error"]["data"]["reason_code"], "MCP_REQUIRED_CAPABILITY_UNAVAILABLE")
        self.assertEqual(validate_fixtures(fixtures), [])

    def test_61_unsupported_protocol_custom_refusal_remains_valid(self) -> None:
        fixtures = mcp_server_contract.build_fixtures()
        fixture = fixtures["protocol-version-refusal.json"]
        self.assertEqual(fixture["error"]["code"], -32041)
        self.assertEqual(fixture["error"]["data"]["reason_code"], "MCP_UNSUPPORTED_PROTOCOL_VERSION")
        self.assertEqual(validate_fixtures(fixtures), [])

    def test_62_all_fixtures_retain_jsonrpc_2_0(self) -> None:
        fixtures = mcp_server_contract.build_fixtures()
        for name, fixture in fixtures.items():
            with self.subTest(name=name):
                self.assertEqual(fixture["jsonrpc"], "2.0")

    def test_63_request_and_response_ids_remain_aligned(self) -> None:
        fixtures = mcp_server_contract.build_fixtures()
        pairs = [
            ("resources-list-request.json", "resources-list-result.json"),
            ("resources-read-request.json", "resources-read-result.json"),
            ("tools-list-request.json", "tools-list-result.json"),
            ("prompts-list-request.json", "prompts-list-result.json"),
        ]
        for request_name, response_name in pairs:
            with self.subTest(request_name=request_name):
                self.assertEqual(fixtures[request_name]["id"], fixtures[response_name]["id"])

    def test_64_notifications_remain_id_free(self) -> None:
        fixture = mcp_server_contract.build_fixtures()["initialized-notification.json"]
        self.assertNotIn("id", fixture)

    def test_cli_status_project_validate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_mcp_source_files(root)
            for command in ["status", "project", "validate"]:
                with self.subTest(command=command):
                    exit_code = aide_lite.main(["--repo-root", str(root), "mcp-server-contract", command])
                    self.assertEqual(exit_code, 0)
            report = json.loads((root / mcp_server_contract.VALIDATION_JSON).read_text(encoding="utf-8"))
            self.assertEqual(report["validation_status"], "PASS_WITH_WARNINGS")


if __name__ == "__main__":
    unittest.main()
