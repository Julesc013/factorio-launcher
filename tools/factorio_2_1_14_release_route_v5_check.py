# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the closed exact-alpha v5 two-phase Factorio release route."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.factorio_2_1_14_release_route_v4_check import (  # noqa: E402
    _schema_problems,
    _toml,
    canonical_digest,
    source_file_sha256,
)

POLICY = ROOT / "contracts/policy/factorio/windows_sandbox_play_2_1_14_base_windows_x64.v3.toml"
POLICY_SCHEMA = ROOT / "contracts/schema/factorio/factorio_2_1_14_sandbox_play_policy.v3.schema.json"
ROUTE = ROOT / "release/index/successor_play_route.v5.toml"
ROUTE_SCHEMA = ROOT / "contracts/schema/release/successor_play_route_definition.v5.schema.json"
HISTORICAL_POLICY = ROOT / "contracts/policy/factorio/windows_sandbox_play_2_1_14_base_windows_x64.v2.toml"
HISTORICAL_ROUTE = ROOT / "release/index/successor_play_route.v4.toml"
ROUTE_INDEX = ROOT / "release/index/successor_play_route.index.v1.toml"
PROVIDER_LOCK = ROOT / "release/index/providers.lock.v2.toml"
OBSERVER_SOURCE = ROOT / "tests/native/facman_engineering_play_harness.cpp"
PERMIT_GATE_SOURCE = ROOT / "tests/native/facman_release_route_permit_gate.cpp"
PERMIT_GATE_HEADER = ROOT / "tests/native/facman_release_route_permit_gate.h"
OBSERVER_BUILD_DEFINITION = ROOT / "tests/native/CMakeLists.txt"
OBSERVER_GUEST_RUNNER = ROOT / "tools/windows_private_route_guest.ps1"
OBSERVER_BUNDLE_BUILDER = ROOT / "tools/windows_private_route_bundle.py"

EXPECTED_BASE_REVISION = "428ff530e09d0a63ed4ecebe11f17cac29f51451"
EXPECTED_BASE_TREE = "5cd260c461c75b93b60b0eaf3d9cf0d76f22cc4d"
EXPECTED_ROUTE_ID = (
    "facman.play.windows-x64.factorio-2.1.14.base.menu."
    "sandbox-task-owned.successor.v5"
)
EXPECTED_POLICY_ID = "facman.windows-sandbox-play.2.1.14.base.x64.v3"
EXPECTED_V4_SHA256 = "32c5df2d755965aaf07f4193c6754c3a9a1d49526bf6573e6546b03417cb9541"
EXPECTED_V2_POLICY_SHA256 = "0fa86b6abf0f7fb5feb9c387d6b9b6d1618e25210ee6d7740fd77f33bf9e9825"
EXPECTED_PROVIDER_LOCK = "d33943841431afdeffb7961c7453d8999619ef371793a6310ad2c2952b118f00"
EXPECTED_HOST_SHA256 = "8e7fb8ac781c7cad00a9504ae488069b08c39fbb48b06a88b04ba0110c17e08a"

EXPECTED_CANDIDATE = {
    "product_version": "0.1.0-alpha.1",
    "source_revision": "fa60aaa17e9044bef7bb7347261056959690f1cd",
    "source_tree": "5536891662461d3617ee40e93654cb2f0659905c",
    "source_ref": "refs/tags/v0.1.0-alpha.1",
    "tag_object": "52a7a66092ff2b3b3c1059e9c29260f95b1cb287",
    "candidate_id": "facman-0.1.0-alpha.1-windows-x64-package-set",
    "candidate_record_sha256": "8e18cf7b35d34aee2e39bc6bae0710db48dceef4196d5ff0373b880bfc866573",
    "tag_receipt_sha256": "b89822ae041e6b8c910f2aaec8c0105bd507998120fe5c4b5d05750d1e62f2c6",
    "qualification_run_id": 33200886091,
    "qualification_root_sha256": "d73f310a45fcb9d5ae08b434b5d0323da212c201055b438ad4a056f05b381446",
    "contract_set_sha256": "7d59831268babc1be96192f8ed74f5aa5f5c85d9d1fdf9e392cc943f99eae264",
    "package_id": "windows_winforms_x64_portable",
    "package_filename": "FacMan-0.1.0-alpha.1-windows-x64-portable.zip",
    "package_size": 6127233,
    "package_sha256": "00fcf5dfc9597a7118ad8d81ff4489d5ace6019c272e79bcc12e966547149c86",
    "signed": False,
    "published": False,
}
EXPECTED_PROVIDERS = [
    {
        "id": "universal_launcher",
        "version": "1.9.1",
        "source_revision": "5479939ca5cbc9ee0f901608a92012778b4752ae",
        "source_tree": "7728e4d415539a0f24e6f17aa7d22be00cc99d80",
        "package_identity": "canonical_sdk_package_set:012fd91d49a235493223a32793b536aa73437d759ad627ce1180db3b570f4a57",
        "abi": "1.9",
        "contract_digest": "edb62fda28fac02bf7e07a6295c867b3813f4881886c6783f379b52b5c8761f9",
    },
    {
        "id": "universal_setup",
        "version": "1.0.0",
        "source_revision": "d2a2aae7e61c47035c92334b0522143b4fea3880",
        "source_tree": "291d63214cdd0cd3d15c809de5744ee3514fb2b2",
        "package_identity": "canonical_sdk_package_set:04c61554ad37ef7fb3def46485e3558bb37edfc06347c7fc9ef0618e56294e1e",
        "abi": "1.0",
        "contract_digest": "045a570f305a9e578dccbe22ec1d3c1945d6743a5e8d55d3c754dc3c2efd6f56",
    },
]
EXPECTED_FACTORIO = {
    "version": "2.1.14",
    "build": 87180,
    "distribution": "standalone_non_steam_base_game_portable_windows",
    "archive_size": 1649579438,
    "archive_sha256": "4f2875cb5c1325a1fcd21b2d37248d508dc36f51ddeef7406ca96788773b872f",
    "archive_access": "read_only",
    "executable_relative_path": "bin/x64/factorio.exe",
    "executable_size": 49045456,
    "executable_sha256": "0ee725652cfa340008d793bece687aea112475599da01521de05413bdf792695",
    "content_capability": "base_game",
}
CONTRACT_PATHS = {
    "host_freshness_sha256": ROOT / "contracts/schema/release/route_host_freshness.v2.schema.json",
    "permit_ready_sha256": ROOT / "contracts/schema/release/route_permit_ready.v2.schema.json",
    "permit_issue_receipt_sha256": ROOT / "contracts/schema/release/route_permit_issue_receipt.v2.schema.json",
    "first_terminal_ready_sha256": ROOT / "contracts/schema/release/route_first_terminal_ready.v2.schema.json",
}
AUTHORITY_KEYS = {
    "policy_accepted", "route_accepted", "factorio_execution_authorized",
    "product_route_capability", "d3_active", "d4_route_verdict_active",
    "setup_mutation_outside_sandbox", "tagging", "signing", "publication",
    "support_activation",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def load_policy() -> dict[str, Any]:
    return _toml(POLICY)


def load_route() -> dict[str, Any]:
    return _toml(ROUTE)


def observer_source_digest() -> str:
    identities = ":".join(
        source_file_sha256(path)
        for path in (OBSERVER_SOURCE, PERMIT_GATE_SOURCE, PERMIT_GATE_HEADER)
    )
    return hashlib.sha256(identities.encode("ascii")).hexdigest()


def source_closure_digest() -> str:
    payload = {
        "candidate": EXPECTED_CANDIDATE,
        "provider_lock_sha256": EXPECTED_PROVIDER_LOCK,
        "providers": EXPECTED_PROVIDERS,
        "factorio": EXPECTED_FACTORIO,
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def computed_digests() -> dict[str, str]:
    policy_digest = canonical_digest(load_policy(), "policy_digest")
    route = load_route()
    route["policy"]["digest"] = policy_digest
    route["source_closure_digest"] = source_closure_digest()
    return {
        "policy_digest": policy_digest,
        "source_closure_digest": source_closure_digest(),
        "route_definition_digest": canonical_digest(route, "definition_digest"),
        "route_record_sha256": source_file_sha256(ROUTE),
    }


def _closed_authority(record: dict[str, Any], label: str) -> list[str]:
    authority = record.get("authority", {})
    problems: list[str] = []
    if set(authority) != AUTHORITY_KEYS:
        problems.append(f"{label} authority surface is incomplete or open")
    if any(value is not False for value in authority.values()):
        problems.append(f"{label} opens authority before reviewed integration and permits")
    return problems


def _exact(actual: object, expected: object, label: str) -> list[str]:
    return [] if actual == expected else [f"{label} drifted"]


def validate(
    policy: dict[str, Any] | None = None,
    route: dict[str, Any] | None = None,
) -> list[str]:
    problems: list[str] = []
    try:
        policy = copy.deepcopy(policy) if policy is not None else load_policy()
        route = copy.deepcopy(route) if route is not None else load_route()
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        return [f"release route inputs cannot be read: {exc}"]

    problems.extend(_schema_problems(policy, POLICY_SCHEMA, "sandbox policy v3"))
    problems.extend(_schema_problems(route, ROUTE_SCHEMA, "route v5"))
    digests = computed_digests()
    if policy.get("policy_digest") != digests["policy_digest"]:
        problems.append("sandbox policy v3 digest does not match canonical content")
    if route.get("policy", {}).get("digest") != digests["policy_digest"]:
        problems.append("route v5 does not bind the exact policy v3 digest")
    if route.get("definition_digest") != digests["route_definition_digest"]:
        problems.append("route v5 definition digest does not match canonical content")
    if route.get("source_closure_digest") != digests["source_closure_digest"]:
        problems.append("route v5 source closure digest drifted")

    if policy.get("policy_id") != EXPECTED_POLICY_ID:
        problems.append("sandbox policy v3 identity drifted")
    if policy.get("base_revision") != EXPECTED_BASE_REVISION or policy.get("base_tree") != EXPECTED_BASE_TREE:
        problems.append("sandbox policy v3 is not based on protected dev 428ff530")
    problems.extend(_exact(policy.get("predecessor", {}), {
        "path": "contracts/policy/factorio/windows_sandbox_play_2_1_14_base_windows_x64.v2.toml",
        "sha256": EXPECTED_V2_POLICY_SHA256,
        "state": "frozen_unchanged_superseded_for_exact_alpha1_candidate_binding",
    }, "policy v3 predecessor"))
    sandbox = policy.get("sandbox", {})
    for field in (
        "networking", "clipboard_redirection", "printer_redirection",
        "audio_input", "video_input", "vgpu",
    ):
        if sandbox.get(field) != "disabled":
            problems.append(f"sandbox policy v3 does not disable {field}")
    if sandbox.get("mapped_folder_count") != 5 or sandbox.get("read_only_mapping_count") != 4:
        problems.append("sandbox policy v3 mapped-folder isolation drifted")
    topology = policy.get("permit_topology", {})
    for field, expected in {
        "schema": "facman.route_permit_two_phase.v2",
        "topology": "host_guest_evidence_handshake",
        "preissue_both_permits": False,
        "launch_2_requires_launch_1_terminal_receipt": True,
        "launch_2_requires_fresh_host_revalidation": True,
        "atomic_claim_before_dispatch": True,
        "missing_or_invalid_permit_dispatch_count": 0,
    }.items():
        if topology.get(field) != expected:
            problems.append(f"sandbox policy v3 permit topology {field} drifted")
    if policy.get("launch", {}).get("second_issue_automatic") is not False:
        problems.append("sandbox policy v3 permits automatic second-permit issuance")
    problems.extend(_closed_authority(policy, "sandbox policy v3"))

    if route.get("route_id") != EXPECTED_ROUTE_ID:
        problems.append("route v5 identity drifted")
    if route.get("base_revision") != EXPECTED_BASE_REVISION or route.get("base_tree") != EXPECTED_BASE_TREE:
        problems.append("route v5 is not based on protected dev 428ff530")
    problems.extend(_exact(route.get("predecessor", {}), {
        "route_id": "facman.play.windows-x64.factorio-2.1.14.base.menu.sandbox-task-owned.successor.v4",
        "contract": "release/index/successor_play_route.v4.toml",
        "sha256": EXPECTED_V4_SHA256,
        "state": "frozen_unchanged_non_authorizing_superseded_for_exact_alpha1_candidate_binding",
    }, "route v5 predecessor"))
    problems.extend(_exact(route.get("candidate", {}), EXPECTED_CANDIDATE, "route v5 candidate"))
    if route.get("provider") != EXPECTED_PROVIDERS:
        problems.append("route v5 provider identities drifted")
    problems.extend(_exact(route.get("factorio", {}), EXPECTED_FACTORIO, "route v5 Factorio identity"))
    if route.get("provider_lock", {}).get("sha256") != EXPECTED_PROVIDER_LOCK:
        problems.append("route v5 provider lock drifted")
    host = route.get("host", {})
    if host.get("qualification_receipt_sha256") != EXPECTED_HOST_SHA256:
        problems.append("route v5 host qualification drifted")
    if host.get("freshness_schema") != "facman.route_host_freshness.v2":
        problems.append("route v5 host freshness schema drifted")
    for field in (
        "networking", "clipboard_redirection", "printer_redirection",
        "audio_input", "video_input", "vgpu",
    ):
        if host.get(field) != "disabled":
            problems.append(f"route v5 host does not disable {field}")

    observer_hashes = {
        "harness_source_sha256": source_file_sha256(OBSERVER_SOURCE),
        "permit_gate_source_sha256": source_file_sha256(PERMIT_GATE_SOURCE),
        "permit_gate_header_sha256": source_file_sha256(PERMIT_GATE_HEADER),
        "build_definition_sha256": source_file_sha256(OBSERVER_BUILD_DEFINITION),
        "guest_runner_sha256": source_file_sha256(OBSERVER_GUEST_RUNNER),
        "bundle_builder_sha256": source_file_sha256(OBSERVER_BUNDLE_BUILDER),
    }
    observer_revision = observer_source_digest()
    for label, observer in (
        ("policy v3", policy.get("observer", {})),
        ("route v5", route.get("observer", {})),
    ):
        for field, expected in observer_hashes.items():
            if observer.get(field) != expected:
                problems.append(f"{label} observer {field} drifted")
        revision_field = "observer_source_sha256" if label == "policy v3" else "revision"
        if observer.get(revision_field) != observer_revision:
            problems.append(f"{label} observer composite source identity drifted")

    route_contracts = route.get("contracts", {})
    for field, path in CONTRACT_PATHS.items():
        try:
            expected = source_file_sha256(path)
        except OSError as exc:
            problems.append(f"route v5 contract {path.name} cannot be hashed: {exc}")
        else:
            if route_contracts.get(field) != expected:
                problems.append(f"route v5 contract {field} drifted")
    route_permit = route.get("permit", {})
    for field, expected in {
        "protocol_schema": "facman.route_permit_two_phase.v2",
        "topology": "host_guest_evidence_handshake",
        "one_time_consumption": True,
        "atomic_claim_before_dispatch": True,
        "preissue_both_permits": False,
        "second_issue_requires_first_terminal_receipt": True,
        "second_issue_requires_safety_revalidation": True,
        "bind_source_package_candidate_contracts_providers_archive_host_policy_route_observer": True,
    }.items():
        if route_permit.get(field) != expected:
            problems.append(f"route v5 permit {field} drifted")
    evidence = route.get("evidence", {})
    for launch in (1, 2):
        if evidence.get(f"launch_{launch}_operation_id") != f"facman.successor-play.launch-{launch}.operation.05":
            problems.append(f"route v5 launch {launch} operation identity drifted")
        if evidence.get(f"launch_{launch}_attempt_id") != f"facman.successor-play.launch-{launch}.attempt.05":
            problems.append(f"route v5 launch {launch} attempt identity drifted")
    if route.get("sequence", {}).get("host_issuer_may_automatically_issue_second_permit") is not False:
        problems.append("route v5 silently authorizes second-permit issuance")
    problems.extend(_closed_authority(route, "route v5"))

    for path, expected, label in (
        (HISTORICAL_POLICY, EXPECTED_V2_POLICY_SHA256, "frozen policy v2"),
        (HISTORICAL_ROUTE, EXPECTED_V4_SHA256, "frozen route v4"),
        (PROVIDER_LOCK, EXPECTED_PROVIDER_LOCK, "provider lock"),
    ):
        try:
            actual = source_file_sha256(path)
        except OSError as exc:
            problems.append(f"{label} cannot be hashed: {exc}")
        else:
            if actual != expected:
                problems.append(f"{label} SHA-256 drifted")
    try:
        route_index = _toml(ROUTE_INDEX)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        problems.append(f"active route index cannot be read: {exc}")
    else:
        if route_index.get("current_route_id") == EXPECTED_ROUTE_ID:
            problems.append("unaccepted route v5 was selected in the active route index")
    return problems


def valid_execution_request(*, launch: int = 1) -> dict[str, Any]:
    digests = computed_digests()
    return {
        "source_revision": EXPECTED_CANDIDATE["source_revision"],
        "source_tree": EXPECTED_CANDIDATE["source_tree"],
        "candidate_record_sha256": EXPECTED_CANDIDATE["candidate_record_sha256"],
        "package_sha256": EXPECTED_CANDIDATE["package_sha256"],
        "contract_set_sha256": EXPECTED_CANDIDATE["contract_set_sha256"],
        "provider_lock_sha256": EXPECTED_PROVIDER_LOCK,
        "archive_sha256": EXPECTED_FACTORIO["archive_sha256"],
        "executable_sha256": EXPECTED_FACTORIO["executable_sha256"],
        "policy_digest": digests["policy_digest"],
        "route_definition_digest": digests["route_definition_digest"],
        "route_record_sha256": digests["route_record_sha256"],
        "source_closure_digest": digests["source_closure_digest"],
        "clean_host_receipt_sha256": EXPECTED_HOST_SHA256,
        "host_freshness_schema_sha256": source_file_sha256(CONTRACT_PATHS["host_freshness_sha256"]),
        "observer_revision": observer_source_digest(),
        "guest_runner_sha256": source_file_sha256(OBSERVER_GUEST_RUNNER),
        "bundle_builder_sha256": source_file_sha256(OBSERVER_BUNDLE_BUILDER),
        "sandbox_configuration_sha256": "a" * 64,
        "host_freshness_sha256": str(launch) * 64,
        "sandbox_fresh": True,
        "safety_revalidated": True,
        "observer_present": True,
        "archive_mapping_read_only": True,
        "target_kind": "sandbox_task_owned_instance",
        "launch_ordinal": launch,
        "operation_id": f"facman.successor-play.launch-{launch}.operation.05",
        "attempt_id": f"facman.successor-play.launch-{launch}.attempt.05",
        "permit_id": "permit-" + str(launch) * 32,
        "permit_fresh": True,
        "permit_replayed": False,
        "permit_consumed": False,
        "second_permit_preissued": False,
        "launch_1_terminal_receipt_present": launch == 2,
        "factorio_dispatched": False,
    }


def validate_execution_request(request: dict[str, Any]) -> list[str]:
    launch = request.get("launch_ordinal")
    expected = valid_execution_request(launch=launch if launch in {1, 2} else 1)
    problems: list[str] = []
    for field in (
        "source_revision", "source_tree", "candidate_record_sha256", "package_sha256",
        "contract_set_sha256", "provider_lock_sha256", "archive_sha256",
        "executable_sha256", "policy_digest", "route_definition_digest",
        "route_record_sha256", "source_closure_digest", "clean_host_receipt_sha256",
        "host_freshness_schema_sha256", "observer_revision", "guest_runner_sha256",
        "bundle_builder_sha256",
    ):
        if request.get(field) != expected[field]:
            problems.append(f"execution request {field} mismatch; refuse before dispatch")
    for field in ("sandbox_configuration_sha256", "host_freshness_sha256"):
        if not isinstance(request.get(field), str) or not SHA256_RE.fullmatch(request[field]):
            problems.append(f"execution request {field} is invalid; refuse before dispatch")
    if request.get("sandbox_fresh") is not True or request.get("safety_revalidated") is not True:
        problems.append("execution request sandbox is stale; refuse before dispatch")
    if request.get("observer_present") is not True:
        problems.append("execution request observer is missing; refuse before dispatch")
    if request.get("archive_mapping_read_only") is not True:
        problems.append("execution request private archive is writable; refuse before dispatch")
    if request.get("target_kind") != "sandbox_task_owned_instance":
        problems.append("execution request targets live or foreign state; refuse before dispatch")
    if request.get("permit_fresh") is not True:
        problems.append("execution request permit is stale; refuse before dispatch")
    if request.get("permit_replayed") is not False or request.get("permit_consumed") is not False:
        problems.append("execution request permit is replayed or consumed; refuse before dispatch")
    if request.get("second_permit_preissued") is not False:
        problems.append("execution request preissued the second permit; refuse before dispatch")
    if launch == 2 and request.get("launch_1_terminal_receipt_present") is not True:
        problems.append("second permit lacks first terminal receipt; refuse before dispatch")
    if request.get("factorio_dispatched") is not False:
        problems.append("negative controls were evaluated after dispatch")
    for field in ("operation_id", "attempt_id"):
        if request.get(field) != expected[field]:
            problems.append(f"execution request {field} mismatch; refuse before dispatch")
    permit_id = request.get("permit_id")
    if not isinstance(permit_id, str) or not re.fullmatch(r"permit-[0-9a-f]{32}", permit_id):
        problems.append("execution request permit_id is invalid")
    return problems


def validate_execution_pair(first: dict[str, Any], second: dict[str, Any]) -> list[str]:
    problems = [*validate_execution_request(first), *validate_execution_request(second)]
    for field in ("operation_id", "attempt_id", "permit_id", "host_freshness_sha256"):
        if first.get(field) == second.get(field):
            problems.append(f"launch pair reuses {field}")
    return problems


def main() -> int:
    if "--print-digests" in sys.argv:
        print(json.dumps(computed_digests(), sort_keys=True, indent=2))
        return 0
    problems = validate()
    if problems:
        for problem in problems:
            print(f"factorio-2-1-14-release-route-v5-check: {problem}", file=sys.stderr)
        return 1
    print("factorio-2-1-14-release-route-v5-check: ok (exact alpha; all authority false)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
