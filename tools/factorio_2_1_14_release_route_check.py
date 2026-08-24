# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the exact non-authorizing Factorio 2.1.14 base-game route."""

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


POLICY = (
    ROOT
    / "contracts/policy/factorio/"
    "windows_sandbox_play_2_1_14_base_windows_x64.v1.toml"
)
POLICY_SCHEMA = (
    ROOT
    / "contracts/schema/factorio/"
    "factorio_2_1_14_sandbox_play_policy.v1.schema.json"
)
ROUTE = ROOT / "release/index/successor_play_route.v3.toml"
ROUTE_SCHEMA = (
    ROOT
    / "contracts/schema/release/"
    "successor_play_route_definition.v3.schema.json"
)
RECORD = ROOT / "release/index/factorio_2_1_14_release_route.v1.toml"
RECORD_SCHEMA = (
    ROOT
    / "contracts/schema/release/"
    "factorio_2_1_14_release_route.v1.schema.json"
)
PREDECESSOR_PACKET = ROOT / "release/index/factorio_2_1_14_route_packet.v1.toml"
ROUTE_INDEX = ROOT / "release/index/successor_play_route.index.v1.toml"
PROVIDER_LOCK = ROOT / "release/index/providers.lock.v2.toml"
PREDECESSOR_ROUTE = ROOT / "release/index/successor_play_route.v2.toml"
OBSERVER_SOURCE = ROOT / "tests/native/facman_engineering_play_harness.cpp"
OBSERVER_BUILD_DEFINITION = ROOT / "tests/native/CMakeLists.txt"
OBSERVER_GUEST_RUNNER = ROOT / "tools/windows_private_route_guest.ps1"
OBSERVER_BUNDLE_BUILDER = ROOT / "tools/windows_private_route_bundle.py"

EXPECTED_BASE_REVISION = "41dce656d6e75d9991a101c71b3a7683db873bb3"
EXPECTED_BASE_TREE = "58e56a63f21af0747aa04e73e06b71333ec2a61e"
EXPECTED_ROUTE_ID = (
    "facman.play.windows-x64.factorio-2.1.14.base.menu."
    "sandbox-task-owned.successor.v3"
)
EXPECTED_POLICY_ID = "facman.windows-sandbox-play.2.1.14.base.x64.v1"
EXPECTED_PACKET_SHA256 = (
    "568c6d5ea7906cc38fc508680b2b9019d3bd6f1df9069c4662cd8d9e84da9151"
)
EXPECTED_V2_SHA256 = (
    "765545f0325b649a29c0dd175be52b879d7ada8db6b7ac2423da54c498d9bff8"
)
EXPECTED_HOST_SHA256 = (
    "8e7fb8ac781c7cad00a9504ae488069b08c39fbb48b06a88b04ba0110c17e08a"
)
EXPECTED_OBSERVER = (
    "55b4897cf5f5f20de64dac5d67f639073ebedf0ccaf339fca581b57cfcd9fcb8"
)
EXPECTED_OBSERVER_RECORD = {
    "id": "facman.release-route-harness.windows-sandbox.v1",
    "revision": EXPECTED_OBSERVER,
    "harness_source_sha256": EXPECTED_OBSERVER,
    "build_definition_sha256": "39d83fb6ec156386110d3e12d6ff3fb06e56569ddbd3d1847791922ecb8fd5fb",
    "guest_runner_sha256": "2d1e80a1f7c934b9dc9a545c3346972e1bd899b837dd8af6cae96a1a93beed5f",
    "bundle_builder_sha256": "916fd8ab69f6a44725f91610cc9e338fb18e4f9340be964169bed98a4f163f42",
    "binary_identity_assignment": "external_after_reviewed_integration_build",
    "human_observer": "Jules",
}
EXPECTED_PROVIDER_LOCK = (
    "d33943841431afdeffb7961c7453d8999619ef371793a6310ad2c2952b118f00"
)
EXPECTED_CANDIDATE = {
    "product_version": "0.1.0-alpha.1",
    "source_revision": "8362ddc55cbb98b538f4af410819c9503604ef99",
    "source_tree": "859695fdcaead2e5e11c5454976432df13cacc1a",
    "package_id": "facman-0.1.0-alpha.1-windows-winforms-x86_64-technical-preview",
    "package_size": 4273707,
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
    "executable_relative_path": "bin/x64/factorio.exe",
    "executable_size": 49045456,
    "executable_sha256": "0ee725652cfa340008d793bece687aea112475599da01521de05413bdf792695",
}
EXPECTED_NEGATIVE_CONTROLS = [
    "wrong_facman_source",
    "wrong_package_digest",
    "wrong_provider_identity",
    "wrong_factorio_archive_digest",
    "changed_route_definition",
    "non_disposable_or_stale_sandbox",
    "missing_observer",
    "writable_private_archive_mapping",
    "live_or_foreign_installation_target",
    "stale_permit",
    "replayed_permit",
]
AUTHORITY_KEYS = {
    "policy_accepted",
    "route_accepted",
    "factorio_execution_authorized",
    "product_route_capability",
    "d3_active",
    "d4_route_verdict_active",
    "setup_mutation_outside_sandbox",
    "tagging",
    "signing",
    "publication",
    "support_activation",
}


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


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(record: dict[str, Any], digest_field: str) -> str:
    canonical = copy.deepcopy(record)
    canonical.pop(digest_field, None)
    encoded = json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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


def load_policy() -> dict[str, Any]:
    return _toml(POLICY)


def load_route() -> dict[str, Any]:
    return _toml(ROUTE)


def load_record() -> dict[str, Any]:
    return _toml(RECORD)


def computed_digests() -> dict[str, str]:
    policy = load_policy()
    policy_digest = canonical_digest(policy, "policy_digest")
    route = load_route()
    route["policy"]["digest"] = policy_digest
    route["source_closure_digest"] = source_closure_digest()
    route_digest = canonical_digest(route, "definition_digest")
    record = load_record()
    record["policy_digest"] = policy_digest
    record["route_definition_digest"] = route_digest
    record["source_closure_digest"] = source_closure_digest()
    return {
        "policy_digest": policy_digest,
        "source_closure_digest": source_closure_digest(),
        "route_definition_digest": route_digest,
        "record_digest": canonical_digest(record, "record_digest"),
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


def _route_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return {key: candidate.get(key) for key in EXPECTED_CANDIDATE if key != "package_size"}


def _factorio_identity(record: dict[str, Any]) -> dict[str, Any]:
    return {key: record.get(key) for key in EXPECTED_FACTORIO}


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

    problems.extend(_schema_problems(policy, POLICY_SCHEMA, "sandbox policy"))
    problems.extend(_schema_problems(route, ROUTE_SCHEMA, "route v3"))
    problems.extend(_schema_problems(record, RECORD_SCHEMA, "release route record"))

    digests = computed_digests()
    if policy.get("policy_digest") != digests["policy_digest"]:
        problems.append("sandbox policy digest does not match canonical content")
    if route.get("source_closure_digest") != digests["source_closure_digest"]:
        problems.append("route v3 source closure digest drifted")
    if route.get("definition_digest") != digests["route_definition_digest"]:
        problems.append("route v3 definition digest does not match canonical content")
    if record.get("record_digest") != digests["record_digest"]:
        problems.append("release route record digest does not match canonical content")

    if policy.get("negative_controls") != EXPECTED_NEGATIVE_CONTROLS:
        problems.append("sandbox policy negative controls are incomplete or reordered")
    if policy.get("candidate") != EXPECTED_CANDIDATE:
        problems.append("sandbox policy candidate identity drifted")
    if policy.get("provider") != EXPECTED_PROVIDERS:
        problems.append("sandbox policy provider identities drifted")
    if policy.get("provider_lock") != {
        "path": "release/index/providers.lock.v2.toml",
        "sha256": EXPECTED_PROVIDER_LOCK,
    }:
        problems.append("sandbox policy provider lock drifted")
    policy_factorio = policy.get("factorio", {})
    if _factorio_identity(policy_factorio) != EXPECTED_FACTORIO:
        problems.append("sandbox policy Factorio identity drifted")
    if policy_factorio.get("content_capability") != "base_game":
        problems.append("sandbox policy is not bound to the base game")
    sandbox = policy.get("sandbox", {})
    if sandbox.get("qualification_receipt_sha256") != EXPECTED_HOST_SHA256:
        problems.append("sandbox policy clean-host receipt drifted")
    if sandbox.get("networking") != "disabled" or sandbox.get("reset_probes_passed") != 2:
        problems.append("sandbox policy does not bind the qualified reset/network state")
    observer = policy.get("observer", {})
    if {key: observer.get(key) for key in EXPECTED_OBSERVER_RECORD} != EXPECTED_OBSERVER_RECORD:
        problems.append("sandbox policy observer source identity drifted or is unnamed")
    if policy.get("launch", {}).get("host_materialization_allowed") is not False:
        problems.append("sandbox policy permits a host Factorio materialization")
    problems.extend(_closed_authority(policy, "sandbox policy"))

    if route.get("route_id") != EXPECTED_ROUTE_ID:
        problems.append("route v3 identity drifted")
    if route.get("base_revision") != EXPECTED_BASE_REVISION or route.get("base_tree") != EXPECTED_BASE_TREE:
        problems.append("route v3 is not based on the authorized protected dev identity")
    if route.get("predecessor", {}).get("sha256") != EXPECTED_V2_SHA256:
        problems.append("route v3 does not preserve immutable route v2")
    if route.get("policy", {}).get("digest") != policy.get("policy_digest"):
        problems.append("route v3 does not bind the exact policy digest")
    if _route_candidate(route.get("candidate", {})) != _route_candidate(EXPECTED_CANDIDATE):
        problems.append("route v3 candidate identity drifted")
    if route.get("provider") != EXPECTED_PROVIDERS:
        problems.append("route v3 provider identities drifted")
    if _factorio_identity(route.get("factorio", {})) != EXPECTED_FACTORIO:
        problems.append("route v3 Factorio identity drifted")
    if route.get("host", {}).get("qualification_receipt_sha256") != EXPECTED_HOST_SHA256:
        problems.append("route v3 host identity drifted")
    route_observer = route.get("observer", {})
    if {key: route_observer.get(key) for key in EXPECTED_OBSERVER_RECORD} != EXPECTED_OBSERVER_RECORD:
        problems.append("route v3 observer source identity drifted")
    if route.get("permit", {}).get("one_time_consumption") is not True:
        problems.append("route v3 does not require one-time permits")
    if route.get("sequence", {}).get("launches") != 2:
        problems.append("route v3 does not require exactly two launches")
    problems.extend(_closed_authority(route, "route v3"))

    if record.get("predecessor_packet_sha256") != EXPECTED_PACKET_SHA256:
        problems.append("release route record does not preserve the preparation packet")
    if record.get("policy_digest") != policy.get("policy_digest"):
        problems.append("release route record policy digest drifted")
    if record.get("route_definition_digest") != route.get("definition_digest"):
        problems.append("release route record definition digest drifted")
    if record.get("source_closure_digest") != route.get("source_closure_digest"):
        problems.append("release route record source closure digest drifted")
    if record.get("clean_host_receipt_sha256") != EXPECTED_HOST_SHA256:
        problems.append("release route record clean-host digest drifted")
    if record.get("observer_revision") != EXPECTED_OBSERVER:
        problems.append("release route record observer drifted")
    problems.extend(_closed_authority(record, "release route record"))

    for path, expected, label in (
        (PREDECESSOR_PACKET, EXPECTED_PACKET_SHA256, "predecessor packet"),
        (PREDECESSOR_ROUTE, EXPECTED_V2_SHA256, "predecessor route"),
        (PROVIDER_LOCK, EXPECTED_PROVIDER_LOCK, "provider lock"),
        (OBSERVER_SOURCE, EXPECTED_OBSERVER_RECORD["harness_source_sha256"], "observer source"),
        (OBSERVER_BUILD_DEFINITION, EXPECTED_OBSERVER_RECORD["build_definition_sha256"], "observer build definition"),
        (OBSERVER_GUEST_RUNNER, EXPECTED_OBSERVER_RECORD["guest_runner_sha256"], "observer guest runner"),
        (OBSERVER_BUNDLE_BUILDER, EXPECTED_OBSERVER_RECORD["bundle_builder_sha256"], "observer bundle builder"),
    ):
        try:
            actual = file_sha256(path)
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
            problems.append("unaccepted route v3 was selected in the active route index")
        if record.get("active_route_index_unchanged") is not True:
            problems.append("release route record claims the route index changed")

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
        "source_closure_digest": digests["source_closure_digest"],
        "clean_host_receipt_sha256": EXPECTED_HOST_SHA256,
        "observer_revision": EXPECTED_OBSERVER,
        "sandbox_fresh": True,
        "observer_present": True,
        "archive_mapping_read_only": True,
        "target_kind": "sandbox_task_owned_instance",
        "operation_id": f"facman-alpha1-base-route-launch-{launch}-operation",
        "attempt_id": f"facman-alpha1-base-route-launch-{launch}-attempt",
        "permit_id": f"facman-alpha1-base-route-launch-{launch}-permit",
        "permit_fresh": True,
        "permit_replayed": False,
        "permit_consumed": False,
        "factorio_dispatched": False,
    }


def validate_execution_request(request: dict[str, Any]) -> list[str]:
    expected = valid_execution_request()
    problems: list[str] = []
    for field in (
        "source_revision", "source_tree", "package_sha256", "provider_lock_sha256",
        "archive_sha256", "executable_sha256", "policy_digest",
        "route_definition_digest", "source_closure_digest",
        "clean_host_receipt_sha256", "observer_revision",
    ):
        if request.get(field) != expected[field]:
            problems.append(f"execution request {field} mismatch; refuse before dispatch")
    if request.get("sandbox_fresh") is not True:
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
            print(f"factorio-2-1-14-release-route-check: {problem}", file=sys.stderr)
        return 1
    print("factorio-2-1-14-release-route-check: ok (review ready; all authority false)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
