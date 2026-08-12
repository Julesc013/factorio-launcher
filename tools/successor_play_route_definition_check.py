# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import hashlib
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

V1_DEFINITION = ROOT / "release/index/successor_play_route.v1.toml"
V2_DEFINITION = ROOT / "release/index/successor_play_route.v2.toml"
ROUTE_INDEX = ROOT / "release/index/successor_play_route.index.v1.toml"
PLAN = ROOT / "release/index/plan.v1.toml"
WORKSPACE_LOCK = ROOT / "release/index/workspace_lock.v1.toml"
PROVIDER_LOCK = ROOT / "release/index/providers.lock.v2.toml"
CURRENT_STATE = ROOT / "release/index/current_state.v1.toml"
PROJECT_STATUS = ROOT / "release/index/project_status.v2.toml"
POLICY = ROOT / "contracts/policy/factorio/windows_instance_isolated_play_2_0_77_windows_x64.v1.toml"
PROVIDER_HEADER = ROOT / "runtime/factorio/launch/flb_factorio_hermetic_candidate.h"

EXPECTED_V1_ROUTE_ID = (
    "facman.play.windows-x64.factorio-2.0.77.standalone.menu."
    "instance-isolated.successor.v1"
)
EXPECTED_V2_ROUTE_ID = (
    "facman.play.windows-x64.factorio-2.0.77.standalone.menu."
    "instance-isolated.successor.v2"
)
EXPECTED_V1_SHA256 = "98561d1c956435d0d57fd7f184545c0fdfa3bf2586ec944c59b9ee75bdde8632"
EXPECTED_V1_DEFINITION_DIGEST = "2eb0921fc265e09055ac995fc7cfd8493098a4d1ed8a7c4716ef3ee04d6e597d"
EXPECTED_V2_BASE_REVISION = "72e4548f5072f01f8f59657ffa5d1b609fae5411"
EXPECTED_V2_BASE_TREE = "d7c416ec0cbe4d9976f6cfe5e0cfc1b5ff38f754"
EXPECTED_WORKSPACE_LOCK_SHA256 = "510511d597ef4ff1ce58f198b7d45796d7723411d09ca15f0e87d539445408e3"
EXPECTED_PROVIDER_LOCK_SHA256 = "59376482126a8226bb28c5b5d73e980d21d3081b76bdf10bd5c10297f2462249"
SOURCE_CLOSURE_ADMISSION_WORK_UNIT = (
    "FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-ADMISSION-01"
)
DEV_RECONCILIATION_WORK_UNIT = "FACMAN-DEV-RECONCILIATION-01"
SOURCE_CLOSURE_ADMISSION_BRANCH = (
    "task/facman-successor-play-source-closure-admission-01"
)
SOURCE_CLOSURE_ADMISSION_BASE_REVISION = (
    "4da0bf2c4c1df92d8e3a4d2d7eae39ebf65cba2f"
)
SOURCE_CLOSURE_ADMISSION_BASE_TREE = (
    "5e127a96825170c04b71736f6598aeb4a98ba0ef"
)
EXPECTED_POLICY = {
    "path": "contracts/policy/factorio/windows_instance_isolated_play_2_0_77_windows_x64.v1.toml",
    "schema": "factorio.windows_instance_isolated_play_policy.v1",
    "id": "facman.windows-instance-isolated-play.2.0.77.x64.v1",
    "revision": "1",
    "digest": "8d8189a9e8fc9ff7e479f7dda1adf0ea516bed2878046468022b2da8355e2432",
    "status": "frozen_criteria_no_result",
}
EXPECTED_SELECTOR = {
    "platform": "windows",
    "architecture": "x86_64",
    "factorio_version": "2.0.77",
    "distribution": "standalone_non_steam",
    "launch_operation": "instance.play",
    "launch_intent": "menu",
    "isolation_mode": "instance_isolated",
    "process_environment": "factorio.menu-minimal.v2",
    "source_authentication": "sha256_bound_to_authenticated_wube_source",
    "filesystem": "ntfs",
    "volume": "fixed_local",
    "instance_ownership": "facman_owned",
    "content_capability": "base_game",
    "mod_state": "explicit_empty_lock",
    "account_requirement": "none",
    "credential_requirement": "none",
    "network_requirement": "none",
}
EXPECTED_PROCESS_PROVIDER = {
    "id": "factorio.launch.local",
    "revision": "windows-instance-isolated-play-candidate.v1",
    "binding": "exact_candidate_evidence_required",
}
EXPECTED_OBSERVER_PROVIDER = {
    "id": "factorio.play.process-tree-observer",
    "revision": "gate4c-etw-file-registry-process.v6",
    "binding": "exact_observer_generation_and_packet_required",
    "independent_of_process_provider": True,
}
EXPECTED_V1_PROVIDER_PINS = {
    "universal_launcher": "7fc25340623131ba86c08dca4fb8a43b18a4520d",
    "universal_setup": "3048128963dc718a7c38c1cfcdda9e813a23b0db",
}
RECONCILED_PROVIDER_PINS = {
    "universal_launcher": "1cafe4054297cc11e02458b83d230db0cd064471",
    "universal_setup": "32488fc13bd2439f9f6e52e83a97f6da345a7650",
}
EXPECTED_PROVIDER_BINDINGS = [
    {
        "id": "universal_launcher",
        "source_revision": "1cafe4054297cc11e02458b83d230db0cd064471",
        "source_tree": "47018102de4b9fd20af9f77acd4e1e35e51590f3",
        "package_identity_kind": "canonical_sdk_package_set",
        "package_version": "1.8.0",
        "package_digest": "b75f2385af47a66a530b53314424bd87bd20600c1ac9e10817d4b2aa42d739ac",
        "abi_version": "1.8",
        "abi_manifest_digest": "0b8125b03aeb7bef30be23b9510a943b43c83d1f3247cbc911cb953ef0a61295",
        "contract_set_id": "ulk_contract_set_1_8",
        "contract_digest": "e925de410275faa151070ac8110d772e6dc815f75c850fe7c2b50e18d07dbf2f",
        "supported_consumption_modes": ["source", "installed_static", "installed_shared"],
        "authorizing": False,
    },
    {
        "id": "universal_setup",
        "source_revision": "32488fc13bd2439f9f6e52e83a97f6da345a7650",
        "source_tree": "12fe757b1fc2ae78768a8cf912d03835f46ca65b",
        "package_identity_kind": "canonical_sdk_package_set",
        "package_version": "1.0.0",
        "package_digest": "556bfec1362fb59d75056b98a5a50b329fbc402b183e4530fd36f072e8cee424",
        "abi_version": "1.0",
        "abi_manifest_digest": "07c2d023d4ecf6854301f10babb779a8ccd20eafb8f088a4cc29e361ca7beea0",
        "contract_set_id": "usk_product_package_contract_set_1",
        "contract_digest": "1e2f45c6292909abfee1119a09d464f573a84047f24c22ee57e9224f44464c71",
        "supported_consumption_modes": ["source", "installed_static", "installed_shared"],
        "authorizing": False,
    },
]
EXPECTED_ROLES = [
    "route_definition",
    "source_closure",
    "candidate_qualification",
    "stage",
    "observer_generation",
    "baseline",
    "prepare_lease",
    "launch_1_operation",
    "launch_1_attempt",
    "launch_1_permit",
    "launch_1_technical_packet",
    "launch_2_operation",
    "launch_2_attempt",
    "launch_2_permit",
    "launch_2_technical_packet",
    "human_verdict",
    "route_capability",
    "route_promotion",
]
EXPECTED_V2_IDENTITY_IDS = {
    "route_definition": "facman.successor-play.route-definition.02",
    "source_closure": "facman.successor-play.source-closure.02",
    "candidate_qualification": "facman.successor-play.candidate-qualification.02",
    "stage": "facman.successor-play.stage.02",
    "observer_generation": "facman.successor-play.observer-generation.02",
    "baseline": "facman.successor-play.baseline.02",
    "prepare_lease": "facman.successor-play.prepare-lease.02",
    "launch_1_operation": "facman.successor-play.launch-1.operation.02",
    "launch_1_attempt": "facman.successor-play.launch-1.attempt.02",
    "launch_1_permit": "facman.successor-play.launch-1.permit-slot.02",
    "launch_1_technical_packet": "facman.successor-play.launch-1.technical-packet.02",
    "launch_2_operation": "facman.successor-play.launch-2.operation.02",
    "launch_2_attempt": "facman.successor-play.launch-2.attempt.02",
    "launch_2_permit": "facman.successor-play.launch-2.permit-slot.02",
    "launch_2_technical_packet": "facman.successor-play.launch-2.technical-packet.02",
    "human_verdict": "facman.successor-play.human-verdict.02",
    "route_capability": "facman.successor-play.route-capability.02",
    "route_promotion": "facman.successor-play.route-promotion.02",
}
EXPECTED_VERDICTS = {
    "Pass": "eligible_for_separate_exact_route_capability_and_promotion_review",
    "Fail": "bounded_repair_and_fresh_qualification_required",
    "Inconclusive": "improve_evidence_and_repeat_with_fresh_runtime_identities",
}
FORBIDDEN_HISTORICAL_IDENTITIES = {
    "FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-04",
    "gate4c-instance-isolated-bae3edc4-8176-4677-b91d-32297a1aa5ab",
    "gate4c-instance-isolated-29723835-2fae-4e8a-8e53-75a12878f2ac",
    "gate4c-instance-isolated-8fd23c7e-e358-481c-9e29-1b3283c931f8",
    "gate4c-instance-isolated-cd2eb04e-43e5-4abe-83c6-c230f6cb95eb",
}
EXPECTED_V1_TOP_LEVEL = {
    "schema",
    "route_id",
    "definition_work_unit",
    "definition_status",
    "base_revision",
    "canonicalization_version",
    "definition_digest",
    "immutable_after_accepted_integration",
    "predecessor_history",
    "predecessor_authority_reused",
    "policy",
    "selector",
    "process_provider",
    "observer_provider",
    "permit_profile",
    "workspace_root_contract",
    "packaged_backend_contract",
    "transport_hardening_contract",
    "provider_pins",
    "future_bindings",
    "evidence_identity",
    "sequence",
    "verdict_law",
    "source_closure_workunit",
    "qualification_workunit",
    "non_goals",
    "authority",
}

EXPECTED_V2_TOP_LEVEL = {
    "schema",
    "route_id",
    "definition_work_unit",
    "definition_status",
    "base_revision",
    "base_tree",
    "canonicalization_version",
    "definition_digest",
    "immutable_after_accepted_integration",
    "predecessor_route",
    "policy",
    "selector",
    "process_provider",
    "observer_provider",
    "permit_profile",
    "workspace_root_contract",
    "packaged_backend_contract",
    "transport_hardening_contract",
    "provider_pins",
    "provider_binding",
    "future_bindings",
    "evidence_identity",
    "sequence",
    "verdict_law",
    "source_closure_workunit",
    "qualification_workunit",
    "non_goals",
    "authority",
}

EXPECTED_INDEX_TOP_LEVEL = {
    "schema",
    "canonicalization_version",
    "index_digest",
    "selection_status",
    "current_route_id",
    "current_route_contract",
    "current_route_schema",
    "current_route_definition_digest",
    "current_route_sha256",
    "current_route_integration_revision",
    "current_route_integration_tree",
    "current_route_integration_pull_request",
    "new_evidence_target_route_id",
    "new_evidence_execution_authorized",
    "mixed_route_evidence_allowed",
    "source_closure_execution_authorized",
    "route_capability_authorized",
    "route_promotion_authorized",
    "route",
}

EXPECTED_INDEX_ROUTE_KEYS = {
    "route_id",
    "contract",
    "schema",
    "sha256",
    "definition_digest",
    "state",
    "new_evidence_target",
    "new_source_closure_evidence_allowed",
    "new_qualification_evidence_allowed",
    "route_capability_creation_allowed",
    "route_promotion_allowed",
}


def load_definition() -> dict[str, Any]:
    """Load immutable route v1 for backwards-compatible callers."""
    with V1_DEFINITION.open("rb") as handle:
        return tomllib.load(handle)


def load_v2_definition() -> dict[str, Any]:
    with V2_DEFINITION.open("rb") as handle:
        return tomllib.load(handle)


def load_route_index() -> dict[str, Any]:
    with ROUTE_INDEX.open("rb") as handle:
        return tomllib.load(handle)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def definition_digest(record: dict[str, Any]) -> str:
    canonical = copy.deepcopy(record)
    canonical.pop("definition_digest", None)
    encoded = json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def index_digest(record: dict[str, Any]) -> str:
    canonical = copy.deepcopy(record)
    canonical.pop("index_digest", None)
    encoded = json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _workunit(plan: dict[str, Any], workunit_id: str) -> dict[str, Any] | None:
    return next(
        (item for item in plan.get("workunit", []) if item.get("id") == workunit_id),
        None,
    )


def validate(record: dict[str, Any] | None = None) -> list[str]:
    """Validate immutable route v1 without interpreting it as current truth."""
    problems: list[str] = []
    if record is None:
        try:
            record = load_definition()
        except (OSError, tomllib.TOMLDecodeError) as exc:
            return [f"successor route definition cannot be loaded: {exc}"]
    else:
        record = copy.deepcopy(record)

    if set(record) != EXPECTED_V1_TOP_LEVEL:
        problems.append("successor route top-level contract is incomplete or open")
    if record.get("schema") != "facman.successor_play_route_definition.v1":
        problems.append("successor route schema identity drifted")
    if record.get("route_id") != EXPECTED_V1_ROUTE_ID:
        problems.append("successor route ID drifted")
    if record.get("base_revision") != "b70be10696855628c6d2948eb016c8424912e14e":
        problems.append("successor definition is not bound to the exact authorized base")
    if record.get("definition_digest") != definition_digest(record):
        problems.append("successor route definition digest does not match canonical content")
    if record.get("policy") != EXPECTED_POLICY:
        problems.append("successor route does not bind the exact frozen policy")
    if record.get("selector") != EXPECTED_SELECTOR:
        problems.append("successor route selector is not the exact supported route")
    if record.get("process_provider") != EXPECTED_PROCESS_PROVIDER:
        problems.append("successor route process provider drifted")
    if record.get("observer_provider") != EXPECTED_OBSERVER_PROVIDER:
        problems.append("successor route observer provider drifted")

    permit = record.get("permit_profile", {})
    expected_permit = {
        "id": "facman.successor-play.instance-isolated.permit.v1",
        "claims_schema": "common.operation_permit_claims.v1",
        "envelope_schema": "common.operation_permit_envelope.v1",
        "canonicalization_version": "facman.sorted-json.v1",
        "authenticator": "hmac-sha256.process.v1",
        "maximum_ttl_seconds": 120,
        "maximum_future_skew_seconds": 5,
        "one_time_consumption": True,
        "exact_plan_binding": True,
        "exact_resource_binding": True,
        "exact_provider_binding": True,
        "exact_principal_and_machine_binding": True,
        "exact_evidence_and_policy_binding": True,
        "issuance_authorized": False,
    }
    if permit != expected_permit:
        problems.append("successor route permit profile drifted or grants issuance")

    pins = record.get("provider_pins", {})
    for provider, revision in EXPECTED_V1_PROVIDER_PINS.items():
        if pins.get(provider) != revision:
            problems.append(f"successor route changed the stable {provider} pin")
    if pins.get("required_ref") != "refs/heads/main" or pins.get("provider_repin") is not False:
        problems.append("successor route provider-pin law is not stable-main/no-repin")

    future = record.get("future_bindings", {})
    unassigned = {
        "source_revision",
        "source_closure_digest",
        "candidate_package_identity",
        "candidate_package_sha256",
        "candidate_manifest_sha256",
        "factorio_archive_sha256",
        "factorio_executable_sha256",
        "instance_spec_digest",
        "instance_binding_digest",
        "instance_readiness_digest",
    }
    if any(future.get(field) != "unassigned" for field in unassigned):
        problems.append("definition-only route assigns source, package, or candidate evidence")
    if future.get("assignment_work_unit") != "FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-01":
        problems.append("future candidate bindings are not owned by source closure")
    if future.get("assignment_mutates_route_definition") is not False:
        problems.append("future evidence may not mutate the immutable route definition")

    identities = record.get("evidence_identity", [])
    roles = [item.get("role") for item in identities if isinstance(item, dict)]
    values = [item.get("id") for item in identities if isinstance(item, dict)]
    if roles != EXPECTED_ROLES:
        problems.append("successor evidence roles are missing, reordered, or duplicated")
    if len(values) != len(set(values)):
        problems.append("successor evidence identities must be unique")
    reused = sorted(FORBIDDEN_HISTORICAL_IDENTITIES.intersection(values))
    if reused:
        problems.append("successor evidence reuses revalidation-04 identity: " + ", ".join(reused))
    if any(
        item.get("state") not in {
            "defined",
            "reserved_uncreated",
            "reserved_unissued",
            "reserved_unrecorded",
        }
        for item in identities
        if isinstance(item, dict)
    ):
        problems.append("successor evidence contains an executed or unsupported state")
    sequence = record.get("sequence", {})
    if sequence.get("ordered_roles") != EXPECTED_ROLES:
        problems.append("successor evidence sequence is not closed over every identity")
    if sequence.get("historical_revalidation_04_identity_reuse_forbidden") is not True:
        problems.append("successor sequence does not forbid historical identity reuse")
    if sequence.get("later_steps_require_separate_authority") is not True:
        problems.append("successor sequence does not retain later authority gates")

    verdict = record.get("verdict_law", {})
    if verdict.get("allowed") != ["Pass", "Fail", "Inconclusive"]:
        problems.append("successor verdict law must contain exactly Pass, Fail, Inconclusive")
    for result, expected_next in EXPECTED_VERDICTS.items():
        branch = verdict.get(result, {})
        if branch.get("next") != expected_next or branch.get("authority_granted") is not False:
            problems.append(f"successor {result} branch drifted or grants authority")
    for key in (
        "requires_two_independently_permitted_launches",
        "requires_complete_hash_closed_technical_packets",
        "human_only",
        "automated_inference_forbidden",
    ):
        if verdict.get(key) is not True:
            problems.append(f"successor verdict law requires {key}")
    if verdict.get("verdict_grants_route_authority") is not False:
        problems.append("a successor verdict may not grant route authority")

    source = record.get("source_closure_workunit", {})
    if source.get("id") != "FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-01":
        problems.append("source-closure WorkUnit specification is missing")
    if source.get("status") != "ready_not_active":
        problems.append("source closure must be ready but not active")
    qualification = record.get("qualification_workunit", {})
    if qualification.get("id") != "FACMAN-SUCCESSOR-PLAY-QUALIFICATION-01":
        problems.append("qualification WorkUnit specification is missing")
    if qualification.get("status") != "planned_blocked_on_source_closure":
        problems.append("qualification must remain blocked on source closure")

    authority = record.get("authority", {})
    true_authority = sorted(key for key, value in authority.items() if value is not False)
    if true_authority:
        problems.append("definition-only route opens authority: " + ", ".join(true_authority))
    if record.get("predecessor_authority_reused") is not False:
        problems.append("revalidation-04 authority reuse must remain false")

    if record is not None:
        try:
            with POLICY.open("rb") as handle:
                policy = tomllib.load(handle)
            if policy.get("policy_id") != EXPECTED_POLICY["id"] or policy.get("policy_digest") != EXPECTED_POLICY["digest"]:
                problems.append("the referenced frozen policy no longer matches the route")
            with WORKSPACE_LOCK.open("rb") as handle:
                workspace_lock = tomllib.load(handle)
            locked = {item["id"]: item["pin"] for item in workspace_lock.get("component", [])}
            active_provider_set = {
                provider: locked.get(provider) for provider in EXPECTED_V1_PROVIDER_PINS
            }
            if active_provider_set not in (
                EXPECTED_V1_PROVIDER_PINS,
                RECONCILED_PROVIDER_PINS,
            ):
                problems.append(
                    "workspace lock is neither the immutable route-v1 provider set "
                    "nor the exact atomic reconciliation selected for route v2"
                )
            provider_header = PROVIDER_HEADER.read_text(encoding="utf-8")
            for anchor in (
                'kInstanceIsolatedCandidateProviderRevision =\n    "windows-instance-isolated-play-candidate.v1"',
                'kInstanceIsolatedObservationProviderRevision =\n    "gate4c-etw-file-registry-process.v6"',
            ):
                if anchor not in provider_header:
                    problems.append("runtime provider constant drifted from successor route")
        except (OSError, tomllib.TOMLDecodeError) as exc:
            problems.append(f"successor route dependency cannot be read: {exc}")

        try:
            with PLAN.open("rb") as handle:
                plan = tomllib.load(handle)
            definition = _workunit(plan, "FACMAN-SUCCESSOR-PLAY-ROUTE-DEFINITION-01")
            source_plan = _workunit(plan, "FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-01")
            qualification_plan = _workunit(plan, "FACMAN-SUCCESSOR-PLAY-QUALIFICATION-01")
            if definition is None or definition.get("status") != "complete":
                problems.append("canonical plan does not complete the route-definition WorkUnit")
            source_plan_is_ready = source_plan is not None and source_plan.get("status") == "ready"
            source_plan_is_explicitly_gated = (
                source_plan is not None
                and source_plan.get("status") == "blocked"
                and source_plan.get("depends_on")
                == ["FACMAN-SUCCESSOR-PLAY-ROUTE-DEFINITION-02"]
                and source_plan.get("immutable_predecessor_contract")
                == "release/index/successor_play_route.v1.toml"
                and source_plan.get("integrated_active_contract")
                == "release/index/successor_play_route.v2.toml"
                and bool(source_plan.get("blockers"))
            )
            if not source_plan_is_ready and not source_plan_is_explicitly_gated:
                problems.append(
                    "canonical plan neither leaves source closure ready nor records its exact integrated-v2 capable-host gate"
                )
            if qualification_plan is None or qualification_plan.get("status") != "planned":
                problems.append("canonical plan activates qualification prematurely")
        except (OSError, tomllib.TOMLDecodeError) as exc:
            problems.append(f"canonical plan cannot be read: {exc}")

    return problems


def validate_v1_file() -> list[str]:
    try:
        payload = V1_DEFINITION.read_bytes()
    except OSError as exc:
        return [f"immutable route v1 cannot be hashed: {exc}"]
    return validate_v1_bytes(payload)


def validate_v1_bytes(payload: bytes) -> list[str]:
    actual = hashlib.sha256(payload).hexdigest()
    if actual != EXPECTED_V1_SHA256:
        return [
            "immutable route v1 SHA-256 drifted: "
            f"expected {EXPECTED_V1_SHA256}, got {actual}"
        ]
    return []


def _expected_permit_profile() -> dict[str, Any]:
    return {
        "id": "facman.successor-play.instance-isolated.permit.v1",
        "claims_schema": "common.operation_permit_claims.v1",
        "envelope_schema": "common.operation_permit_envelope.v1",
        "canonicalization_version": "facman.sorted-json.v1",
        "authenticator": "hmac-sha256.process.v1",
        "maximum_ttl_seconds": 120,
        "maximum_future_skew_seconds": 5,
        "one_time_consumption": True,
        "exact_plan_binding": True,
        "exact_resource_binding": True,
        "exact_provider_binding": True,
        "exact_principal_and_machine_binding": True,
        "exact_evidence_and_policy_binding": True,
        "issuance_authorized": False,
    }


def _expected_v2_identities() -> list[dict[str, Any]]:
    assignments = {
        "route_definition": ("defined", "FACMAN-SUCCESSOR-PLAY-ROUTE-DEFINITION-02"),
        "source_closure": ("reserved_uncreated", "FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-01"),
        "candidate_qualification": (
            "reserved_uncreated",
            "FACMAN-SUCCESSOR-PLAY-QUALIFICATION-01",
        ),
        "stage": ("reserved_uncreated", "separate_owner_authorized_stage_work_unit"),
        "observer_generation": (
            "reserved_uncreated",
            "separate_owner_authorized_observer_step",
        ),
        "baseline": ("reserved_uncreated", "separate_owner_authorized_prepare_sequence"),
        "prepare_lease": (
            "reserved_uncreated",
            "separate_owner_authorized_prepare_sequence",
        ),
        "launch_1_operation": (
            "reserved_uncreated",
            "separate_owner_authorized_launch_1_sequence",
        ),
        "launch_1_attempt": (
            "reserved_uncreated",
            "separate_owner_authorized_launch_1_sequence",
        ),
        "launch_1_permit": (
            "reserved_unissued",
            "separate_owner_authorized_launch_1_permit_issuance",
        ),
        "launch_1_technical_packet": (
            "reserved_uncreated",
            "separate_owner_authorized_launch_1_evidence_closeout",
        ),
        "launch_2_operation": (
            "reserved_uncreated",
            "separate_owner_authorized_launch_2_sequence",
        ),
        "launch_2_attempt": (
            "reserved_uncreated",
            "separate_owner_authorized_launch_2_sequence",
        ),
        "launch_2_permit": (
            "reserved_unissued",
            "separate_owner_authorized_launch_2_permit_issuance",
        ),
        "launch_2_technical_packet": (
            "reserved_uncreated",
            "separate_owner_authorized_launch_2_evidence_closeout",
        ),
        "human_verdict": ("reserved_unrecorded", "separate_human_verdict_work_unit"),
        "route_capability": (
            "reserved_uncreated",
            "FACMAN-EXACT-PLAY-ROUTE-CAPABILITY-01",
        ),
        "route_promotion": (
            "reserved_uncreated",
            "FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-ROUTE-PROMOTION-01",
        ),
    }
    return [
        {
            "role": role,
            "id": EXPECTED_V2_IDENTITY_IDS[role],
            "state": assignments[role][0],
            "assigned_by": assignments[role][1],
        }
        for role in EXPECTED_ROLES
    ]


def validate_v2(record: dict[str, Any] | None = None) -> list[str]:
    problems: list[str] = []
    if record is None:
        try:
            record = load_v2_definition()
        except (OSError, tomllib.TOMLDecodeError) as exc:
            return [f"successor route v2 definition cannot be loaded: {exc}"]
    else:
        record = copy.deepcopy(record)

    try:
        v1 = load_definition()
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [f"immutable route v1 cannot be loaded for compatibility validation: {exc}"]

    if set(record) != EXPECTED_V2_TOP_LEVEL:
        problems.append("successor route v2 top-level contract is incomplete or open")
    if record.get("schema") != "facman.successor_play_route_definition.v2":
        problems.append("successor route v2 schema identity drifted")
    if record.get("route_id") != EXPECTED_V2_ROUTE_ID:
        problems.append("successor route v2 ID drifted or duplicates another route")
    if record.get("definition_work_unit") != "FACMAN-SUCCESSOR-PLAY-ROUTE-DEFINITION-02":
        problems.append("successor route v2 definition WorkUnit drifted")
    if record.get("definition_status") != "task_complete_no_authority":
        problems.append("successor route v2 definition status is unsupported")
    if record.get("base_revision") != EXPECTED_V2_BASE_REVISION:
        problems.append("successor route v2 is bound to a stale or unauthorized base revision")
    if record.get("base_tree") != EXPECTED_V2_BASE_TREE:
        problems.append("successor route v2 is bound to a stale or unauthorized base tree")
    if record.get("canonicalization_version") != "facman.sorted-json.v1":
        problems.append("successor route v2 canonicalization version drifted")
    if record.get("definition_digest") != definition_digest(record):
        problems.append("successor route v2 definition digest does not match canonical content")
    if record.get("immutable_after_accepted_integration") is not True:
        problems.append("successor route v2 is not immutable after accepted integration")

    expected_predecessor = {
        "route_id": EXPECTED_V1_ROUTE_ID,
        "schema": "facman.successor_play_route_definition.v1",
        "contract": "release/index/successor_play_route.v1.toml",
        "sha256": EXPECTED_V1_SHA256,
        "definition_digest": EXPECTED_V1_DEFINITION_DIGEST,
        "state": "historical_predecessor_superseded_for_new_evidence",
        "authority_reused": False,
    }
    if record.get("predecessor_route") != expected_predecessor:
        problems.append("successor route v2 predecessor lineage is incomplete or drifted")

    exact_unchanged_sections = {
        "policy": EXPECTED_POLICY,
        "selector": EXPECTED_SELECTOR,
        "process_provider": EXPECTED_PROCESS_PROVIDER,
        "observer_provider": EXPECTED_OBSERVER_PROVIDER,
        "permit_profile": _expected_permit_profile(),
        "workspace_root_contract": v1.get("workspace_root_contract"),
        "packaged_backend_contract": v1.get("packaged_backend_contract"),
        "transport_hardening_contract": v1.get("transport_hardening_contract"),
        "verdict_law": v1.get("verdict_law"),
        "qualification_workunit": v1.get("qualification_workunit"),
        "non_goals": v1.get("non_goals"),
        "authority": v1.get("authority"),
    }
    for section, expected in exact_unchanged_sections.items():
        if record.get(section) != expected:
            problems.append(f"successor route v2 {section} drifted from the closed route law")

    expected_pins = {
        "source": "release/index/workspace_lock.v1.toml",
        "workspace_lock_sha256": EXPECTED_WORKSPACE_LOCK_SHA256,
        "provider_lock": "release/index/providers.lock.v2.toml",
        "provider_lock_sha256": EXPECTED_PROVIDER_LOCK_SHA256,
        "required_ref": "refs/heads/main",
        **RECONCILED_PROVIDER_PINS,
        "provider_repin": False,
    }
    if record.get("provider_pins") != expected_pins:
        problems.append("successor route v2 does not bind the exact reconciled provider locks")
    if record.get("provider_binding") != EXPECTED_PROVIDER_BINDINGS:
        problems.append("successor route v2 provider package, ABI, or contract identity drifted")

    expected_future = {
        "assignment_work_unit": "FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-01",
        "source_revision": "unassigned",
        "source_closure_digest": "unassigned",
        "candidate_package_identity": "unassigned",
        "candidate_package_sha256": "unassigned",
        "candidate_manifest_sha256": "unassigned",
        "factorio_archive_sha256": "unassigned",
        "factorio_executable_sha256": "unassigned",
        "instance_spec_digest": "unassigned",
        "instance_binding_digest": "unassigned",
        "instance_readiness_digest": "unassigned",
        "assignment_mutates_route_definition": False,
    }
    if record.get("future_bindings") != expected_future:
        problems.append("successor route v2 assigns or opens future source/candidate bindings")

    expected_identities = _expected_v2_identities()
    if record.get("evidence_identity") != expected_identities:
        problems.append("successor route v2 evidence identities are not the exact fresh .02 family")
    identity_values = [item.get("id", "") for item in record.get("evidence_identity", [])]
    if any(value.endswith(".01") or value in FORBIDDEN_HISTORICAL_IDENTITIES for value in identity_values):
        problems.append("successor route v2 reuses a predecessor or .01 evidence identity")
    if len(identity_values) != len(set(identity_values)):
        problems.append("successor route v2 evidence identities must be unique")

    expected_sequence = copy.deepcopy(v1.get("sequence", {}))
    expected_sequence.pop("historical_revalidation_04_identity_reuse_forbidden", None)
    expected_sequence["predecessor_route_identity_reuse_forbidden"] = True
    if record.get("sequence") != expected_sequence:
        problems.append("successor route v2 evidence sequence or reuse law drifted")

    source = record.get("source_closure_workunit", {})
    expected_source_keys = {
        "id",
        "status",
        "depends_on",
        "required_ref",
        "remote_mode",
        "output_schema",
        "blockers",
        "required_outputs",
        "forbidden_actions",
    }
    if set(source) != expected_source_keys:
        problems.append("successor route v2 source-closure contract is incomplete or open")
    if source.get("id") != "FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-01":
        problems.append("successor route v2 source-closure WorkUnit drifted")
    if source.get("status") != "blocked_not_active":
        problems.append("successor route v2 must keep source closure blocked and inactive")
    if source.get("depends_on") != "FACMAN-SUCCESSOR-PLAY-ROUTE-DEFINITION-02":
        problems.append("successor route v2 source closure does not depend on route definition 02")
    if source.get("required_ref") != "accepted_route_v2_integration_head":
        problems.append("successor route v2 source closure does not require the accepted v2 integration head")
    if source.get("blockers") != [
        "route_v2_not_integrated",
        "capable_windows_native_closure_host_unavailable",
    ]:
        problems.append("successor route v2 source-closure blockers drifted")
    if source.get("required_outputs") != v1.get("source_closure_workunit", {}).get("required_outputs"):
        problems.append("successor route v2 source-closure outputs drifted")
    if source.get("forbidden_actions") != v1.get("source_closure_workunit", {}).get("forbidden_actions"):
        problems.append("successor route v2 source-closure authority ceiling drifted")
    if source.get("remote_mode") != "fresh_empty_clones_remote_only":
        problems.append("successor route v2 source closure is not remote-only from empty clones")
    if source.get("output_schema") != "facman.successor_play_source_closure.v1":
        problems.append("successor route v2 source-closure output schema drifted")

    true_authority = sorted(
        key for key, value in record.get("authority", {}).items() if value is not False
    )
    if true_authority:
        problems.append("successor route v2 opens authority: " + ", ".join(true_authority))
    if any(binding.get("authorizing") is not False for binding in record.get("provider_binding", [])):
        problems.append("successor route v2 provider binding is authorizing")

    try:
        if file_sha256(WORKSPACE_LOCK) != EXPECTED_WORKSPACE_LOCK_SHA256:
            problems.append("workspace lock bytes drifted from the route v2 binding")
        if file_sha256(PROVIDER_LOCK) != EXPECTED_PROVIDER_LOCK_SHA256:
            problems.append("provider lock bytes drifted from the route v2 binding")
        if file_sha256(V1_DEFINITION) != EXPECTED_V1_SHA256:
            problems.append("immutable route v1 bytes drifted while defining route v2")
        workspace = tomllib.loads(WORKSPACE_LOCK.read_text(encoding="utf-8"))
        pins = {item["id"]: item["pin"] for item in workspace.get("component", [])}
        if {key: pins.get(key) for key in RECONCILED_PROVIDER_PINS} != RECONCILED_PROVIDER_PINS:
            problems.append("workspace lock does not contain the reconciled route v2 provider set")
        provider_lock = tomllib.loads(PROVIDER_LOCK.read_text(encoding="utf-8"))
        providers = {item["id"]: item for item in provider_lock.get("provider", [])}
        for expected in EXPECTED_PROVIDER_BINDINGS:
            actual = providers.get(expected["id"], {})
            for field, value in expected.items():
                if field == "authorizing":
                    continue
                if actual.get(field) != value:
                    problems.append(
                        f"provider lock {expected['id']} {field} disagrees with route v2"
                    )
    except (OSError, tomllib.TOMLDecodeError, KeyError) as exc:
        problems.append(f"successor route v2 dependency cannot be read: {exc}")

    try:
        plan = tomllib.loads(PLAN.read_text(encoding="utf-8"))
        definition_plan = _workunit(plan, "FACMAN-SUCCESSOR-PLAY-ROUTE-DEFINITION-02")
        admission_plan = _workunit(plan, SOURCE_CLOSURE_ADMISSION_WORK_UNIT)
        reconciliation_plan = _workunit(plan, DEV_RECONCILIATION_WORK_UNIT)
        source_plan = _workunit(plan, "FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-01")
        qualification_plan = _workunit(plan, "FACMAN-SUCCESSOR-PLAY-QUALIFICATION-01")
        if definition_plan is None or definition_plan.get("status") not in {"active", "complete"}:
            problems.append("canonical plan does not track route definition v2 as active or complete")
        if definition_plan is not None:
            if definition_plan.get("branch") != "task/facman-successor-play-route-definition-02":
                problems.append("canonical plan route v2 branch drifted")
            if definition_plan.get("base_revision") != EXPECTED_V2_BASE_REVISION:
                problems.append("canonical plan route v2 base revision drifted")
            if definition_plan.get("base_tree") != EXPECTED_V2_BASE_TREE:
                problems.append("canonical plan route v2 base tree drifted")
            if definition_plan.get("definition_contract") != "release/index/successor_play_route.v2.toml":
                problems.append("canonical plan route v2 definition contract drifted")
            if definition_plan.get("route_index_contract") != "release/index/successor_play_route.index.v1.toml":
                problems.append("canonical plan route v2 index contract drifted")
        if source_plan is None or source_plan.get("status") != "blocked":
            problems.append("canonical plan must keep source closure blocked during admission")
        if source_plan is not None and source_plan.get("depends_on") != [
            "FACMAN-SUCCESSOR-PLAY-ROUTE-DEFINITION-02"
        ]:
            problems.append("canonical plan source closure does not depend on route definition v2")
        if reconciliation_plan is None or reconciliation_plan.get("status") != "active":
            problems.append("canonical plan does not activate dev reconciliation")
        if admission_plan is None or admission_plan.get("status") != "superseded":
            problems.append("canonical plan does not supersede the bounded source-closure admission")
        if admission_plan is not None:
            if admission_plan.get("branch") != SOURCE_CLOSURE_ADMISSION_BRANCH:
                problems.append("canonical plan source-closure admission branch drifted")
            if admission_plan.get("base_revision") != SOURCE_CLOSURE_ADMISSION_BASE_REVISION:
                problems.append("canonical plan source-closure admission base revision drifted")
            if admission_plan.get("base_tree") != SOURCE_CLOSURE_ADMISSION_BASE_TREE:
                problems.append("canonical plan source-closure admission base tree drifted")
            if admission_plan.get("depends_on") != [
                "FACMAN-SUCCESSOR-PLAY-ROUTE-DEFINITION-02"
            ]:
                problems.append("canonical plan source-closure admission dependency drifted")
            if admission_plan.get("route_index_contract") != (
                "release/index/successor_play_route.index.v1.toml"
            ):
                problems.append("canonical plan source-closure admission index contract drifted")
        if qualification_plan is None or qualification_plan.get("status") != "planned":
            problems.append("canonical plan activates qualification prematurely")
    except (OSError, tomllib.TOMLDecodeError) as exc:
        problems.append(f"canonical plan cannot be read for route v2: {exc}")

    return problems


def validate_route_index(
    record: dict[str, Any] | None = None,
    *,
    check_views: bool = True,
    admission_open: bool = False,
) -> list[str]:
    problems: list[str] = []
    if record is None:
        try:
            record = load_route_index()
        except (OSError, tomllib.TOMLDecodeError) as exc:
            return [f"successor route index cannot be loaded: {exc}"]
    else:
        record = copy.deepcopy(record)

    try:
        v2 = load_v2_definition()
        v2_sha256 = file_sha256(V2_DEFINITION)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [f"successor route v2 cannot be loaded for index validation: {exc}"]

    if set(record) != EXPECTED_INDEX_TOP_LEVEL:
        problems.append("successor route index top-level contract is incomplete or open")
    if record.get("schema") != "facman.successor_play_route_index.v1":
        problems.append("successor route index schema identity drifted")
    if record.get("canonicalization_version") != "facman.sorted-json.v1":
        problems.append("successor route index canonicalization version drifted")
    if record.get("index_digest") != index_digest(record):
        problems.append("successor route index digest does not match canonical content")
    expected_current = {
        "selection_status": "one_integrated_current_definition_no_product_authority",
        "current_route_id": EXPECTED_V2_ROUTE_ID,
        "current_route_contract": "release/index/successor_play_route.v2.toml",
        "current_route_schema": "facman.successor_play_route_definition.v2",
        "current_route_definition_digest": v2.get("definition_digest"),
        "current_route_sha256": v2_sha256,
        "current_route_integration_revision": "c197b5c977bbc442adfba454f12103b8f93f5e39",
        "current_route_integration_tree": "312c4d2383b60f8780bc320b005fca997d615dd6",
        "current_route_integration_pull_request": 129,
        "new_evidence_target_route_id": EXPECTED_V2_ROUTE_ID,
        "new_evidence_execution_authorized": admission_open,
        "mixed_route_evidence_allowed": False,
        "source_closure_execution_authorized": admission_open,
        "route_capability_authorized": False,
        "route_promotion_authorized": False,
    }
    for field, expected in expected_current.items():
        if record.get(field) != expected:
            problems.append(f"successor route index {field} must be {expected!r}")

    routes = record.get("route", [])
    if len(routes) != 2 or any(set(item) != EXPECTED_INDEX_ROUTE_KEYS for item in routes if isinstance(item, dict)):
        problems.append("successor route index route entries are incomplete or open")
    route_ids = [item.get("route_id") for item in routes if isinstance(item, dict)]
    if route_ids != [EXPECTED_V1_ROUTE_ID, EXPECTED_V2_ROUTE_ID]:
        problems.append("successor route index IDs are duplicated, reordered, or incomplete")
    indexed = {item.get("route_id"): item for item in routes if isinstance(item, dict)}
    expected_v1 = {
        "route_id": EXPECTED_V1_ROUTE_ID,
        "contract": "release/index/successor_play_route.v1.toml",
        "schema": "facman.successor_play_route_definition.v1",
        "sha256": EXPECTED_V1_SHA256,
        "definition_digest": EXPECTED_V1_DEFINITION_DIGEST,
        "state": "historical_predecessor_superseded_for_new_evidence",
        "new_evidence_target": False,
        "new_source_closure_evidence_allowed": False,
        "new_qualification_evidence_allowed": False,
        "route_capability_creation_allowed": False,
        "route_promotion_allowed": False,
    }
    expected_v2 = {
        "route_id": EXPECTED_V2_ROUTE_ID,
        "contract": "release/index/successor_play_route.v2.toml",
        "schema": "facman.successor_play_route_definition.v2",
        "sha256": v2_sha256,
        "definition_digest": v2.get("definition_digest"),
        "state": "current_integrated_non_authorizing_definition",
        "new_evidence_target": True,
        "new_source_closure_evidence_allowed": admission_open,
        "new_qualification_evidence_allowed": False,
        "route_capability_creation_allowed": False,
        "route_promotion_allowed": False,
    }
    if indexed.get(EXPECTED_V1_ROUTE_ID) != expected_v1:
        problems.append("successor route index does not preserve and supersede v1 exactly")
    if indexed.get(EXPECTED_V2_ROUTE_ID) != expected_v2:
        problems.append("successor route index does not select exact authority state for v2")

    if check_views:
        problems.extend(validate_route_views(record))

    return problems


def validate_route_views(
    index_record: dict[str, Any] | None = None,
    current_state_record: dict[str, Any] | None = None,
    project_status_record: dict[str, Any] | None = None,
) -> list[str]:
    problems: list[str] = []
    try:
        index_record = (
            copy.deepcopy(index_record)
            if index_record is not None
            else load_route_index()
        )
        current_state_record = (
            copy.deepcopy(current_state_record)
            if current_state_record is not None
            else tomllib.loads(CURRENT_STATE.read_text(encoding="utf-8"))
        )
        project_status_record = (
            copy.deepcopy(project_status_record)
            if project_status_record is not None
            else tomllib.loads(PROJECT_STATUS.read_text(encoding="utf-8"))
        )
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [f"generated current route view cannot be read: {exc}"]

    expected_view = {
        "route_index_contract": "release/index/successor_play_route.index.v1.toml",
        "historical_route_contract": "release/index/successor_play_route.v1.toml",
        "active_route_contract": index_record.get("current_route_contract"),
        "active_route_id": index_record.get("current_route_id"),
        "active_route_schema": index_record.get("current_route_schema"),
        "active_route_definition_digest": index_record.get(
            "current_route_definition_digest"
        ),
    }
    for label, view in (
        ("release/index/current_state.v1.toml", current_state_record),
        ("release/index/project_status.v2.toml", project_status_record),
    ):
        convergence = view.get("provider_convergence", {})
        for field, expected in expected_view.items():
            if convergence.get(field) != expected:
                problems.append(
                    f"{label} provider_convergence {field} does not match the route index"
                )
    return problems


def validate_evidence_target(
    route_id: str,
    evidence_ids: list[str],
    index_record: dict[str, Any] | None = None,
) -> list[str]:
    problems: list[str] = []
    index_record = copy.deepcopy(index_record) if index_record is not None else load_route_index()
    if route_id == EXPECTED_V1_ROUTE_ID:
        problems.append("new evidence may not target superseded successor route v1")
    elif route_id != index_record.get("new_evidence_target_route_id"):
        problems.append("new evidence does not target the current successor route")
    v1_ids = {
        item.get("id", "") for item in load_definition().get("evidence_identity", [])
    }
    v2_ids = set(EXPECTED_V2_IDENTITY_IDS.values())
    if any(identity in v1_ids or identity.endswith(".01") for identity in evidence_ids):
        problems.append("new evidence reuses a superseded .01 identity")
    if evidence_ids and any(identity not in v2_ids for identity in evidence_ids):
        problems.append("new evidence contains an unknown or wrong-route identity")
    has_v1 = any(identity in v1_ids or identity.endswith(".01") for identity in evidence_ids)
    has_v2 = any(identity in v2_ids for identity in evidence_ids)
    if has_v1 and has_v2:
        problems.append("mixed v1/v2 evidence chains are forbidden")
    return problems


def validate_all() -> list[str]:
    return [
        *validate_v1_file(),
        *validate(),
        *validate_v2(),
        *validate_route_index(),
    ]


def main() -> int:
    problems = validate_all()
    if problems:
        for problem in problems:
            print(f"successor-play-route-definition-check: {problem}", file=sys.stderr)
        return 1
    print("successor-play-route-definition-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
