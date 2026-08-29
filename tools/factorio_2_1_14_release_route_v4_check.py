# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the closed, non-authorizing v4 two-phase release route."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import jsonschema
except ModuleNotFoundError:  # pragma: no cover - strict CI installs the lock
    jsonschema = None

from tools import json_contract

POLICY = ROOT / "contracts/policy/factorio/windows_sandbox_play_2_1_14_base_windows_x64.v2.toml"
POLICY_SCHEMA = ROOT / "contracts/schema/factorio/factorio_2_1_14_sandbox_play_policy.v2.schema.json"
ROUTE = ROOT / "release/index/successor_play_route.v4.toml"
ROUTE_SCHEMA = ROOT / "contracts/schema/release/successor_play_route_definition.v4.schema.json"
HISTORICAL_POLICY = ROOT / "contracts/policy/factorio/windows_sandbox_play_2_1_14_base_windows_x64.v1.toml"
HISTORICAL_ROUTE = ROOT / "release/index/successor_play_route.v3.toml"
HISTORICAL_RECORD = ROOT / "release/index/factorio_2_1_14_release_route.v1.toml"
HISTORICAL_RECORD_SCHEMA = ROOT / "contracts/schema/release/factorio_2_1_14_release_route.v1.schema.json"
ROUTE_INDEX = ROOT / "release/index/successor_play_route.index.v1.toml"
PROVIDER_LOCK = ROOT / "release/index/providers.lock.v2.toml"
OBSERVER_SOURCE = ROOT / "tests/native/facman_engineering_play_harness.cpp"
PERMIT_GATE_SOURCE = ROOT / "tests/native/facman_release_route_permit_gate.cpp"
PERMIT_GATE_HEADER = ROOT / "tests/native/facman_release_route_permit_gate.h"
OBSERVER_BUILD_DEFINITION = ROOT / "tests/native/CMakeLists.txt"
OBSERVER_GUEST_RUNNER = ROOT / "tools/windows_private_route_guest.ps1"
OBSERVER_BUNDLE_BUILDER = ROOT / "tools/windows_private_route_bundle.py"

EXPECTED_BASE_REVISION = "e73d778173be283d47925fa055ba1aae7b82fb28"
EXPECTED_BASE_TREE = "a1f96dd4fe2cf5d3eb69e428e2721d9356e8fe24"
EXPECTED_ROUTE_ID = (
    "facman.play.windows-x64.factorio-2.1.14.base.menu."
    "sandbox-task-owned.successor.v4"
)
EXPECTED_POLICY_ID = "facman.windows-sandbox-play.2.1.14.base.x64.v2"
EXPECTED_V3_SHA256 = "242b1ce14ab6c8ae36706d97d5f4f19a05921524ca5aed2dca836499c8c55fd9"
EXPECTED_V1_POLICY_SHA256 = "3522068f75842a871f87096863b52e86b610730cdfc3e4fdd23b81bd8005ec73"
EXPECTED_V1_RECORD_SHA256 = "661d280272fbe5587fbfb54affe170c98da67adbacc33a9fa60575fbdcc23863"
EXPECTED_PROVIDER_LOCK = "d33943841431afdeffb7961c7453d8999619ef371793a6310ad2c2952b118f00"
EXPECTED_HOST_SHA256 = "8e7fb8ac781c7cad00a9504ae488069b08c39fbb48b06a88b04ba0110c17e08a"
EXPECTED_SOURCE_CLOSURE = "4badcfcf3d9e57d09e4bb08fe186164b2095c4eafe7aab99ca9adb7536589013"
EXPECTED_OBSERVER_REVISION = "dc1bcb3d7e56db07ad83fe653fffdc3cef28fd40c94636b8ca2f658d24fc487a"
EXPECTED_OBSERVER_HASHES = {
    "harness_source_sha256": "8d9ca65dc68dcfba573be4e7f1dbf2273c7b96d057a5110524c5bb45755760ac",
    "permit_gate_source_sha256": "a23279ad56bad7ffe51fe6a00af012ff777e59ffb928db3aa8b1b4018efa3275",
    "permit_gate_header_sha256": "b5f7b4c04b758d9452e76863208357854c37c12eeedeee6b3f2fdf0b1981f7df",
    "build_definition_sha256": "3494443c338d4643e285169adcd06d98d63b3373eb0f295dbd94061f2c0278e7",
    "guest_runner_sha256": "25b93252925547c38f7cf35f3ff3f367b8aafa6bc1c8c2117098463118e88da3",
    "bundle_builder_sha256": "c12cd88b571d8be0777de629a13a67d8f29fa6a6e223fc4d8ef452a6061fadff",
}

EXPECTED_CANDIDATE = {
    "product_version": "0.1.0-alpha.1",
    "source_revision": "8362ddc55cbb98b538f4af410819c9503604ef99",
    "source_tree": "859695fdcaead2e5e11c5454976432df13cacc1a",
    "package_id": "facman-0.1.0-alpha.1-windows-winforms-x86_64-technical-preview",
    "package_sha256": "95d5836effa1494d0e976dc4937c198085a61fa30350e7e9f66667c8ffb0a70f",
    "resolution_sha256": "d86b7a30e9ff2cd610512ff4d88179754bfad8fe5ca12699f898b10266ada56f",
    "candidate_manifest_sha256": "2c2b2f132e316b8bfc645eb4dd75c7597f70ef90b8fb5d088565f94944af67f0",
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
AUTHORITY_KEYS = {
    "policy_accepted", "route_accepted", "factorio_execution_authorized",
    "product_route_capability", "d3_active", "d4_route_verdict_active",
    "setup_mutation_outside_sandbox", "tagging", "signing", "publication",
    "support_activation",
}

FACTORIO_INITIALISED_MARKER = "Factorio initialised"
CLOSED_DURING_LOADING_MARKER = "Closed during loading."


def factorio_menu_observed(standard_output: str) -> bool:
    return (
        FACTORIO_INITIALISED_MARKER in standard_output
        and CLOSED_DURING_LOADING_MARKER not in standard_output
    )


def _toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        value = tomllib.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a TOML table")
    return value


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def source_file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def canonical_digest(record: dict[str, Any], digest_field: str) -> str:
    canonical = copy.deepcopy(record)
    canonical.pop(digest_field, None)
    encoded = json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def observer_source_digest() -> str:
    """Return the frozen v4 observer identity, not the mutable successor sources."""

    return EXPECTED_OBSERVER_REVISION


def load_policy() -> dict[str, Any]:
    return _toml(POLICY)


def load_route() -> dict[str, Any]:
    return _toml(ROUTE)


def load_record() -> dict[str, Any]:
    return _toml(HISTORICAL_RECORD)


def computed_digests() -> dict[str, str]:
    policy = load_policy()
    policy_digest = canonical_digest(policy, "policy_digest")
    route = load_route()
    route["policy"]["digest"] = policy_digest
    return {
        "policy_digest": policy_digest,
        "source_closure_digest": EXPECTED_SOURCE_CLOSURE,
        "route_definition_digest": canonical_digest(route, "definition_digest"),
        "record_digest": load_record()["record_digest"],
    }


def _bounded_schema(schema: dict[str, Any], root: dict[str, Any] | None = None) -> dict[str, Any]:
    root = schema if root is None else root
    result: dict[str, Any] = {}
    reference = schema.get("$ref")
    if isinstance(reference, str):
        prefix = "#/$defs/"
        if not reference.startswith(prefix):
            raise ValueError(f"unsupported schema reference: {reference}")
        target = root.get("$defs", {}).get(reference[len(prefix) :])
        if not isinstance(target, dict):
            raise ValueError(f"missing schema reference: {reference}")
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


def _schema_problems(instance: dict[str, Any], schema_path: Path, label: str) -> list[str]:
    schema = _json(schema_path)
    if jsonschema is None:
        bounded = _bounded_schema(schema)
        unsupported = json_contract.supported_schema_problems(bounded)
        if unsupported:
            return [f"{label} schema unsupported: {item}" for item in unsupported]
        return [
            f"{label} schema rejection at {item}"
            for item in json_contract.validate(instance, bounded)
        ]
    validator_class = jsonschema.validators.validator_for(schema)
    validator_class.check_schema(schema)
    validator = validator_class(schema)
    return [
        f"{label} schema rejection at "
        f"{'.'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
        for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.path))
    ]


def _closed_authority(record: dict[str, Any], label: str) -> list[str]:
    authority = record.get("authority", {})
    problems: list[str] = []
    if set(authority) != AUTHORITY_KEYS:
        problems.append(f"{label} authority surface is incomplete or open")
    if any(value is not False for value in authority.values()):
        problems.append(f"{label} opens authority before protected integration and permits")
    return problems


def _exact_table(
    actual: dict[str, Any], expected: dict[str, Any], label: str
) -> list[str]:
    return [] if actual == expected else [f"{label} drifted"]


def validate(
    policy: dict[str, Any] | None = None,
    route: dict[str, Any] | None = None,
    record: dict[str, Any] | None = None,
) -> list[str]:
    problems: list[str] = []
    try:
        policy = copy.deepcopy(policy) if policy is not None else load_policy()
        route = copy.deepcopy(route) if route is not None else load_route()
        record = copy.deepcopy(record) if record is not None else load_record()
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        return [f"release route inputs cannot be read: {exc}"]

    problems.extend(_schema_problems(policy, POLICY_SCHEMA, "sandbox policy v2"))
    problems.extend(_schema_problems(route, ROUTE_SCHEMA, "route v4"))
    problems.extend(_schema_problems(record, HISTORICAL_RECORD_SCHEMA, "historical route record"))
    digests = computed_digests()
    if policy.get("policy_digest") != digests["policy_digest"]:
        problems.append("sandbox policy v2 digest does not match canonical content")
    if route.get("policy", {}).get("digest") != digests["policy_digest"]:
        problems.append("route v4 does not bind the exact policy v2 digest")
    if route.get("definition_digest") != digests["route_definition_digest"]:
        problems.append("route v4 definition digest does not match canonical content")
    if route.get("source_closure_digest") != EXPECTED_SOURCE_CLOSURE:
        problems.append("route v4 source closure digest drifted")

    if policy.get("base_revision") != EXPECTED_BASE_REVISION or policy.get("base_tree") != EXPECTED_BASE_TREE:
        problems.append("policy v2 is not based on the protected PR #187 merge")
    problems.extend(_exact_table(policy.get("predecessor", {}), {
        "path": "contracts/policy/factorio/windows_sandbox_play_2_1_14_base_windows_x64.v1.toml",
        "sha256": EXPECTED_V1_POLICY_SHA256,
        "state": "frozen_unchanged_superseded_for_observer_and_permit_topology",
    }, "policy v2 predecessor"))
    sandbox = policy.get("sandbox", {})
    for field in (
        "networking", "clipboard_redirection", "printer_redirection",
        "audio_input", "video_input", "vgpu",
    ):
        if sandbox.get(field) != "disabled":
            problems.append(f"sandbox policy does not disable {field}")
    if sandbox.get("mapped_folder_count") != 5 or sandbox.get("read_only_mapping_count") != 4:
        problems.append("sandbox policy mapped-folder isolation drifted")
    topology = policy.get("permit_topology", {})
    required_topology = {
        "topology": "host_guest_evidence_handshake",
        "preissue_both_permits": False,
        "launch_2_requires_launch_1_terminal_receipt": True,
        "launch_2_requires_fresh_host_revalidation": True,
        "atomic_claim_before_dispatch": True,
        "missing_or_invalid_permit_dispatch_count": 0,
    }
    for field, expected in required_topology.items():
        if topology.get(field) != expected:
            problems.append(f"permit topology {field} drifted")
    if policy.get("launch", {}).get("second_issue_automatic") is not False:
        problems.append("policy permits automatic second-permit issuance")
    problems.extend(_closed_authority(policy, "sandbox policy v2"))

    if route.get("route_id") != EXPECTED_ROUTE_ID:
        problems.append("route v4 identity drifted")
    if route.get("base_revision") != EXPECTED_BASE_REVISION or route.get("base_tree") != EXPECTED_BASE_TREE:
        problems.append("route v4 is not based on the protected PR #187 merge")
    if route.get("predecessor", {}).get("sha256") != EXPECTED_V3_SHA256:
        problems.append("route v4 does not preserve immutable route v3")
    problems.extend(_exact_table(route.get("candidate", {}), EXPECTED_CANDIDATE, "route v4 candidate"))
    if route.get("provider") != EXPECTED_PROVIDERS:
        problems.append("route v4 provider identities drifted")
    problems.extend(_exact_table(route.get("factorio", {}), EXPECTED_FACTORIO, "route v4 Factorio identity"))
    if route.get("provider_lock", {}).get("sha256") != EXPECTED_PROVIDER_LOCK:
        problems.append("route v4 provider lock drifted")
    host = route.get("host", {})
    if host.get("qualification_receipt_sha256") != EXPECTED_HOST_SHA256:
        problems.append("route v4 host qualification drifted")
    for field in (
        "networking", "clipboard_redirection", "printer_redirection",
        "audio_input", "video_input", "vgpu",
    ):
        if host.get(field) != "disabled":
            problems.append(f"route v4 host does not disable {field}")
    route_permit = route.get("permit", {})
    for field, expected in {
        "topology": "host_guest_evidence_handshake",
        "one_time_consumption": True,
        "atomic_claim_before_dispatch": True,
        "preissue_both_permits": False,
        "second_issue_requires_first_terminal_receipt": True,
        "second_issue_requires_safety_revalidation": True,
    }.items():
        if route_permit.get(field) != expected:
            problems.append(f"route v4 permit {field} drifted")
    if route.get("sequence", {}).get("host_issuer_may_automatically_issue_second_permit") is not False:
        problems.append("route v4 silently authorizes second-permit issuance")
    problems.extend(_closed_authority(route, "route v4"))
    problems.extend(_closed_authority(record, "historical release route record"))

    observer_revision = EXPECTED_OBSERVER_REVISION
    for label, observer in (
        ("policy v2", policy.get("observer", {})),
        ("route v4", route.get("observer", {})),
    ):
        for field, expected in EXPECTED_OBSERVER_HASHES.items():
            if observer.get(field) != expected:
                problems.append(f"{label} observer {field} drifted")
        recorded_revision = observer.get("observer_source_sha256", observer.get("revision"))
        if recorded_revision != observer_revision:
            problems.append(f"{label} observer composite source identity drifted")

    for path, expected, label in (
        (HISTORICAL_POLICY, EXPECTED_V1_POLICY_SHA256, "frozen policy v1"),
        (HISTORICAL_ROUTE, EXPECTED_V3_SHA256, "frozen route v3"),
        (HISTORICAL_RECORD, EXPECTED_V1_RECORD_SHA256, "historical route record v1"),
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
            problems.append("unaccepted route v4 was selected in the active route index")
    return problems


def valid_execution_request(*, launch: int = 1) -> dict[str, Any]:
    digests = computed_digests()
    return {
        "source_revision": EXPECTED_CANDIDATE["source_revision"],
        "source_tree": EXPECTED_CANDIDATE["source_tree"],
        "package_sha256": EXPECTED_CANDIDATE["package_sha256"],
        "provider_lock_sha256": EXPECTED_PROVIDER_LOCK,
        "archive_sha256": EXPECTED_FACTORIO["archive_sha256"],
        "executable_sha256": EXPECTED_FACTORIO["executable_sha256"],
        "policy_digest": digests["policy_digest"],
        "route_definition_digest": digests["route_definition_digest"],
        "source_closure_digest": EXPECTED_SOURCE_CLOSURE,
        "clean_host_receipt_sha256": EXPECTED_HOST_SHA256,
        "observer_revision": observer_source_digest(),
        "sandbox_fresh": True,
        "safety_revalidated": True,
        "observer_present": True,
        "archive_mapping_read_only": True,
        "target_kind": "sandbox_task_owned_instance",
        "launch_ordinal": launch,
        "operation_id": f"facman.successor-play.launch-{launch}.operation.04",
        "attempt_id": f"facman.successor-play.launch-{launch}.attempt.04",
        "permit_id": f"facman-successor-play-launch-{launch}-permit-04",
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
        "source_revision", "source_tree", "package_sha256", "provider_lock_sha256",
        "archive_sha256", "executable_sha256", "policy_digest",
        "route_definition_digest", "source_closure_digest",
        "clean_host_receipt_sha256", "observer_revision",
    ):
        if request.get(field) != expected[field]:
            problems.append(f"execution request {field} mismatch; refuse before dispatch")
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
    for field in ("operation_id", "attempt_id", "permit_id"):
        if not isinstance(request.get(field), str) or not request[field]:
            problems.append(f"execution request {field} is missing")
    return problems


def validate_execution_pair(first: dict[str, Any], second: dict[str, Any]) -> list[str]:
    problems = [*validate_execution_request(first), *validate_execution_request(second)]
    for field in ("operation_id", "attempt_id", "permit_id"):
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
            print(f"factorio-2-1-14-release-route-v4-check: {problem}", file=sys.stderr)
        return 1
    print("factorio-2-1-14-release-route-v4-check: ok (two-phase; all authority false)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
