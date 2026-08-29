# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the exact, non-authorizing Factorio 2.1.14 route-v5 D3/D4 request."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

try:
    import jsonschema
except ModuleNotFoundError:  # pragma: no cover - exercised by dependency-free CI lanes
    jsonschema = None

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import factorio_2_1_14_release_route_v5_check as route_v5_check
from tools import json_contract

REQUEST = ROOT / "release/index/factorio_2_1_14_route_d3_d4_request.v1.toml"
REQUEST_SCHEMA = (
    ROOT
    / "contracts/schema/release/factorio_2_1_14_route_d3_d4_request.v1.schema.json"
)
ROUTE = ROOT / "release/index/successor_play_route.v5.toml"
POLICY = (
    ROOT
    / "contracts/policy/factorio/windows_sandbox_play_2_1_14_base_windows_x64.v3.toml"
)
TAG_CLOSEOUT = ROOT / "release/index/alpha1_tag_truth_closeout.v1.toml"
AUTONOMY = ROOT / "release/index/autonomy_policy.v1.toml"
DELEGATION = ROOT / "release/index/alpha_delegation.v1.toml"
PROJECT = ROOT / "release/index/project_status.v2.toml"
PLAN = ROOT / "release/index/plan.v1.toml"
CHECKPOINT = ROOT / "docs/release/checkpoints/facman-2-1-14-route-d3-d4-request-01.md"

WORK_UNIT = "FACMAN-2.1.14-ROUTE-D3-D4-REQUEST-01"
PHASE = "facman_2_1_14_route_d3_d4_request"
SENTINEL_PREFIX = "UNASSIGNED_"

EXPECTED_CONTROL_PLANE = {
    "repository": "Julesc013/factorio-launcher",
    "request_base_revision": "3c8634fb84d4ab7a806d57d31b813faa9a7c499a",
    "request_base_tree": "865d05ac929a9661c113ea8cd8f78793e3d29dbe",
    "tag_truth_closeout_pull_request": 199,
    "tag_truth_closeout_task_revision": "d7d4b51c469d65a96d8075e977cbf538ef486af7",
    "tag_truth_closeout_dev_revision": "3c8634fb84d4ab7a806d57d31b813faa9a7c499a",
    "tag_truth_closeout_dev_tree": "865d05ac929a9661c113ea8cd8f78793e3d29dbe",
    "tag_truth_closeout_sha256": "2db1bfdb2ce27fd470a86c4c4e28e7bad204f13c0bd3c697c883dbe629184e40",
    "route_v5_pull_request": 198,
    "route_v5_task_revision": "89b9ec1d7a269aecc87a5b8f6910e2f898d99d21",
    "route_v5_dev_revision": "31548e443955179d1fdfff2fe79d0019907d0a31",
    "route_v5_dev_tree": "76c2075703c8ad83ddf415861b1a9294a5db2de5",
}

EXPECTED_WORKFLOWS = [
    {"name": "ci", "run_id": 33256117773, "conclusion": "success"},
    {"name": "code-security", "run_id": 33256117771, "conclusion": "success"},
    {"name": "schema-check", "run_id": 33256117819, "conclusion": "success"},
    {"name": "security-policy", "run_id": 33256117781, "conclusion": "success"},
    {"name": "synthetic-product-tck", "run_id": 33256117768, "conclusion": "success"},
]

EXPECTED_D3_SCOPE = [
    "fresh_windows_sandbox_observation",
    "task_owned_private_archive_materialization",
    "launch_one_permit_issuance_and_execution",
    "launch_one_terminal_receipt_export",
    "fresh_host_safety_revalidation",
    "launch_two_permit_issuance_and_execution",
    "sandbox_cleanup_and_reset_proof",
]

EXPECTED_SEQUENCE = [
    "record_exact_request_bound_d3_authorization",
    "confirm_jules_d4_observer_availability",
    "collect_fresh_host_observation",
    "run_negative_controls",
    "build_and_bind_observer_binary",
    "issue_one_time_launch_one_permit",
    "launch_one_to_main_menu_and_clean_exit",
    "export_launch_one_terminal_ready_receipt",
    "fresh_host_safety_revalidation",
    "issue_distinct_one_time_launch_two_permit",
    "launch_two_to_main_menu_and_clean_exit",
    "compare_immutable_inputs",
    "destroy_sandbox_and_prove_reset",
    "jules_records_human_route_verdict",
]

EXPECTED_CONSTRAINTS = {
    "request_itself_grants_no_authority": True,
    "live_freshness_values_absent": True,
    "permit_material_absent": True,
    "hmac_key_absent": True,
    "factorio_process_started": False,
    "windows_sandbox_started": False,
    "private_archive_path_recorded": False,
    "user_workspace_visible_to_guest": False,
    "host_installations_visible_to_guest": False,
    "publication_effects_absent": True,
}

EXPECTED_REMAINING_GATES = {
    "human_alpha_result": "Inconclusive",
    "human_alpha_tester": "UNASSIGNED",
    "accepted_play_route": False,
    "public_alpha": False,
    "beta": False,
    "rc": False,
    "stable_0_1_0": False,
    "main_promotion": False,
    "signing": False,
    "publication": False,
    "support_activation": False,
}


def _toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        value = tomllib.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a TOML table")
    return value


def _json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def request_digest(record: dict[str, Any]) -> str:
    canonical = copy.deepcopy(record)
    canonical.pop("request_digest", None)
    encoded = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _bounded_schema(
    schema: dict[str, Any], root: dict[str, Any] | None = None
) -> dict[str, Any]:
    root = schema if root is None else root
    result: dict[str, Any] = {}
    reference = schema.get("$ref")
    if isinstance(reference, str):
        prefix = "#/$defs/"
        if not reference.startswith(prefix):
            raise ValueError(f"unsupported non-local schema reference: {reference}")
        target = root.get("$defs", {}).get(reference[len(prefix) :])
        if not isinstance(target, dict):
            raise ValueError(f"missing local schema reference: {reference}")
        result.update(_bounded_schema(target, root))
    for key, value in schema.items():
        if key in {"$ref", "$defs", "format", "uniqueItems"}:
            continue
        if isinstance(value, dict):
            result[key] = _bounded_schema(value, root)
        elif isinstance(value, list):
            result[key] = [
                _bounded_schema(item, root) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def _schema_problems(
    instance: dict[str, Any], schema: dict[str, Any]
) -> list[str]:
    if jsonschema is None:
        bounded = _bounded_schema(schema)
        unsupported = json_contract.supported_schema_problems(bounded)
        if unsupported:
            return [f"request bounded schema is unsupported: {item}" for item in unsupported]
        return [
            f"request schema rejection at {item}"
            for item in json_contract.validate(instance, bounded)
        ]
    validator_class = jsonschema.validators.validator_for(schema)
    try:
        validator_class.check_schema(schema)
    except jsonschema.exceptions.SchemaError as exc:
        return [f"request schema is invalid: {exc.message}"]
    validator = validator_class(schema)
    problems: list[str] = []
    for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.absolute_path) or "$"
        problems.append(f"request schema rejection at {location}: {error.message}")
    return problems


def load_request() -> dict[str, Any]:
    return _toml(REQUEST)


def _workunits(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("id")): item
        for item in plan.get("workunit", [])
        if isinstance(item, dict)
    }


def validate(
    request: dict[str, Any] | None = None,
    project: dict[str, Any] | None = None,
    plan: dict[str, Any] | None = None,
) -> list[str]:
    problems: list[str] = []
    try:
        request = copy.deepcopy(request) if request is not None else load_request()
        project = copy.deepcopy(project) if project is not None else _toml(PROJECT)
        plan = copy.deepcopy(plan) if plan is not None else _toml(PLAN)
        schema = _json(REQUEST_SCHEMA)
        route = _toml(ROUTE)
        autonomy = _toml(AUTONOMY)
        delegation = _toml(DELEGATION)
    except (OSError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        return [f"route D3/D4 request input cannot be read: {exc}"]

    problems.extend(_schema_problems(request, schema))
    if request.get("request_digest") != request_digest(request):
        problems.append("request digest does not match canonical content")

    control_plane = request.get("control_plane", {})
    if not isinstance(control_plane, dict):
        control_plane = {}
    for key, expected in EXPECTED_CONTROL_PLANE.items():
        if control_plane.get(key) != expected:
            problems.append(f"control-plane {key} differs from the exact reviewed base")
    if control_plane.get("workflow") != EXPECTED_WORKFLOWS:
        problems.append("control-plane post-merge workflow set is not the exact five-success receipt")
    try:
        if file_sha256(TAG_CLOSEOUT) != EXPECTED_CONTROL_PLANE["tag_truth_closeout_sha256"]:
            problems.append("tag-truth closeout source hash drifted after reviewed integration")
    except OSError as exc:
        problems.append(f"tag-truth closeout source cannot be hashed: {exc}")

    route_problems = route_v5_check.validate()
    problems.extend(f"route v5: {item}" for item in route_problems)
    digests = route_v5_check.computed_digests()
    expected_route = {
        "path": "release/index/successor_play_route.v5.toml",
        "route_id": route.get("route_id"),
        "definition_digest": digests["route_definition_digest"],
        "record_sha256": digests["route_record_sha256"],
        "source_closure_digest": digests["source_closure_digest"],
        "policy_path": route.get("policy", {}).get("path"),
        "policy_digest": digests["policy_digest"],
        "definition_status": "review_ready_non_authorizing",
        "route_accepted": False,
        "product_route_capability": False,
    }
    if request.get("route") != expected_route:
        problems.append("request route binding differs from immutable route v5")

    candidate = route.get("candidate", {})
    expected_candidate = {
        key: candidate.get(key)
        for key in (
            "product_version",
            "source_revision",
            "source_tree",
            "tag_object",
            "candidate_record_sha256",
            "contract_set_sha256",
            "package_id",
            "package_filename",
            "package_size",
            "package_sha256",
        )
    }
    expected_candidate["tag"] = "v0.1.0-alpha.1"
    expected_candidate["provider_lock_sha256"] = route.get("provider_lock", {}).get("sha256")
    if request.get("candidate") != expected_candidate:
        problems.append("request candidate binding differs from immutable route v5")

    factorio = route.get("factorio", {})
    expected_factorio = {
        key: factorio.get(key)
        for key in (
            "version",
            "build",
            "distribution",
            "archive_size",
            "archive_sha256",
            "executable_relative_path",
            "executable_size",
            "executable_sha256",
        )
    }
    if request.get("factorio") != expected_factorio:
        problems.append("request Factorio binding differs from immutable route v5")

    host = route.get("host", {})
    expected_host = {
        key: host.get(key)
        for key in (
            "kind",
            "qualification_receipt_id",
            "qualification_receipt_sha256",
            "host_os_build",
            "guest_os_build",
            "freshness_schema",
            "networking",
            "clipboard_redirection",
            "printer_redirection",
            "audio_input",
            "video_input",
            "vgpu",
        )
    }
    expected_host["freshness_schema_sha256"] = route.get("contracts", {}).get(
        "host_freshness_sha256"
    )
    if request.get("host") != expected_host:
        problems.append("request host binding differs from immutable route v5")

    observer = route.get("observer", {})
    expected_observer = {
        "id": observer.get("id"),
        "source_revision": observer.get("revision"),
        "guest_runner_sha256": observer.get("guest_runner_sha256"),
        "bundle_builder_sha256": observer.get("bundle_builder_sha256"),
        "binary_identity": "UNASSIGNED_UNTIL_D3_AUTHORIZED_AND_REVIEWED_HOST_BUILD",
        "human_observer": "Jules",
    }
    if request.get("observer") != expected_observer:
        problems.append("request observer binding or unassigned binary sentinel drifted")

    d3 = request.get("requested_d3", {})
    if d3.get("scope") != EXPECTED_D3_SCOPE:
        problems.append("D3 request scope differs from the exact bounded effect set")
    for key, expected in {
        "authority_class": "D3",
        "requested": True,
        "currently_authorized": False,
        "authorizer": "Jules",
        "authorization_response": "UNRECORDED",
        "authorization_must_bind_request_digest": True,
        "setup_mutation_outside_sandbox": False,
        "production_credentials": False,
        "production_signing_keys": False,
        "public_route_authority": False,
    }.items():
        if d3.get(key) != expected:
            problems.append(f"D3 request field {key} opens or changes authority")

    d4 = request.get("requested_d4", {})
    for key, expected in {
        "authority_class": "D4",
        "requested": True,
        "currently_authorized": False,
        "actor": "Jules",
        "delegable": False,
        "authorization_response": "UNRECORDED",
        "scope": "observe_factorio_main_menu_in_both_launches_and_record_exact_route_verdict",
        "machine_inference_allowed": False,
        "verdict": "UNRECORDED",
        "verdict_grants_route_capability": False,
        "verdict_grants_publication": False,
    }.items():
        if d4.get(key) != expected:
            problems.append(f"D4 request field {key} opens or changes human authority")

    launches = request.get("launch", [])
    expected_ids = route.get("evidence", {})
    if [item.get("ordinal") for item in launches if isinstance(item, dict)] != [1, 2]:
        problems.append("request launch ordinals must be exactly one then two")
    for index, launch in enumerate(launches, start=1):
        if not isinstance(launch, dict):
            problems.append(f"launch {index} is not a table")
            continue
        for key, expected in {
            "status": "unstarted",
            "operation_id": expected_ids.get(f"launch_{index}_operation_id"),
            "attempt_id": expected_ids.get(f"launch_{index}_attempt_id"),
            "permit_slot_id": expected_ids.get(f"launch_{index}_permit_id"),
            "permit_issued": False,
            "permit_consumed": False,
            "factorio_dispatched": False,
            "human_menu_observed": False,
            "second_permit_preissued": False,
        }.items():
            if launch.get(key) != expected:
                problems.append(f"launch {index} field {key} is not safely unstarted")
        for key in (
            "permit_id",
            "host_freshness_sha256",
            "sandbox_configuration_sha256",
            "permit_issue_receipt_sha256",
        ):
            if not str(launch.get(key, "")).startswith(SENTINEL_PREFIX):
                problems.append(f"launch {index} field {key} contains premature live material")
    if len(launches) == 2:
        first, second = launches
        if first.get("terminal_receipt_id") != expected_ids.get("launch_1_terminal_id"):
            problems.append("launch one terminal receipt identity drifted")
        if second.get("terminal_receipt_id") != "UNASSIGNED_UNTIL_LAUNCH_TWO_TERMINAL":
            problems.append("launch two terminal receipt identity was assigned prematurely")
        if second.get("launch_1_terminal_receipt_sha256") != "UNASSIGNED_UNTIL_LAUNCH_ONE_TERMINAL":
            problems.append("launch two claims a launch-one terminal receipt prematurely")
        for key in ("operation_id", "attempt_id", "permit_slot_id"):
            if first.get(key) == second.get(key):
                problems.append(f"launch pair reuses {key}")

    sequence = request.get("sequence", {})
    expected_sequence_flags = {
        "launches": 2,
        "permit_maximum_ttl_seconds": 120,
        "preissue_both_permits": False,
        "second_issue_requires_first_terminal_receipt": True,
        "second_issue_requires_fresh_safety_revalidation": True,
        "automatic_second_permit_issuance": False,
    }
    for key, expected in expected_sequence_flags.items():
        if sequence.get(key) != expected:
            problems.append(f"request sequence field {key} weakens two-phase authority")
    if sequence.get("ordered_steps") != EXPECTED_SEQUENCE:
        problems.append("request sequence differs from the exact two-phase order")

    if request.get("constraints") != EXPECTED_CONSTRAINTS:
        problems.append("request constraints no longer prove zero effects")
    if request.get("remaining_gates") != EXPECTED_REMAINING_GATES:
        problems.append("request overstates a later release gate")
    authority = request.get("authority", {})
    if not authority or any(value is not False for value in authority.values()):
        problems.append("request itself opens authority")
    if request.get("authorization_response_recorded") is not False:
        problems.append("request claims an authorization response")
    if request.get("route_execution_allowed") is not False:
        problems.append("request allows route execution before explicit authorization")

    route_authority = route.get("authority", {})
    if not route_authority or any(value is not False for value in route_authority.values()):
        problems.append("immutable route v5 unexpectedly opens authority")
    if autonomy.get("authority", {}).get("isolated_lab_effects") is not False:
        problems.append("autonomy policy unexpectedly activates isolated-lab effects")
    if autonomy.get("authority", {}).get("human_verdict") is not False:
        problems.append("autonomy policy unexpectedly activates a human verdict")
    if delegation.get("authority", {}).get("route_effects") is not False:
        problems.append("alpha delegation unexpectedly activates route effects")
    if delegation.get("authority", {}).get("human_verdict") is not False:
        problems.append("alpha delegation unexpectedly activates a human verdict")

    workunits = _workunits(plan)
    for work_unit, expected in {
        "FACMAN-0.1.0-ALPHA.1-TAG-TRUTH-CLOSEOUT-01": "complete",
        WORK_UNIT: "complete",
        "FACMAN-0.1.0-ALPHA.1-PUBLICATION-PREPARATION-01": "complete",
        "FACMAN-0.1.0-ALPHA.1-HUMAN-ACCEPTANCE-01": "blocked",
    }.items():
        if workunits.get(work_unit, {}).get("status") != expected:
            problems.append(f"canonical plan does not record {work_unit} as {expected}")
    if project.get("accepted_integration_revision") != "edf61bdf0fe00692a73a58c3586ac4f7c0dbfec4":
        problems.append("project truth does not bind the publication-preparation merge")
    if project.get("reviewed_dev_checkpoint_tree") != "7dc49419a7127a70b6085952d03d1acd179985e4":
        problems.append("project truth does not bind the publication-preparation tree")
    if project.get("active_work_unit") != "":
        problems.append("project truth must keep automated work inactive at the human gate")
    if project.get("last_closed_work_unit") != "FACMAN-0.1.0-ALPHA.1-PUBLICATION-PREPARATION-01":
        problems.append("project truth does not close publication preparation")
    product = project.get("product", {})
    if product.get("phase") != "facman_0_1_0_alpha_1_human_acceptance_pending":
        problems.append("project phase does not preserve the completed request at the human gate")
    if product.get("current_work_unit") != "":
        problems.append("product truth must not select automated human execution")

    try:
        checkpoint = CHECKPOINT.read_text(encoding="utf-8")
    except OSError as exc:
        problems.append(f"request checkpoint cannot be read: {exc}")
    else:
        for anchor in (
            WORK_UNIT,
            "prepared_pending_explicit_operator_authorization",
            "33256117773",
            "No permit, HMAC key, freshness record, Sandbox, or Factorio process was created",
            "only Jules may record the D4 verdict",
        ):
            if anchor not in checkpoint:
                problems.append(f"request checkpoint is missing {anchor!r}")

    return problems


def main() -> int:
    request = load_request()
    if "--print-digest" in sys.argv:
        print(request_digest(request))
        return 0
    problems = validate(request)
    if problems:
        for problem in problems:
            print(f"factorio-2-1-14-route-d3-d4-request-check: {problem}", file=sys.stderr)
        return 1
    print(
        "factorio-2-1-14-route-d3-d4-request-check: ok "
        "(exact request prepared; D3/D4 and all effects remain unauthorized)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
