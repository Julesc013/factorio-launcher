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

DEFINITION = ROOT / "release/index/successor_play_route.v1.toml"
PLAN = ROOT / "release/index/plan.v1.toml"
WORKSPACE_LOCK = ROOT / "release/index/workspace_lock.v1.toml"
POLICY = ROOT / "contracts/policy/factorio/windows_instance_isolated_play_2_0_77_windows_x64.v1.toml"
PROVIDER_HEADER = ROOT / "runtime/factorio/launch/flb_factorio_hermetic_candidate.h"

EXPECTED_ROUTE_ID = (
    "facman.play.windows-x64.factorio-2.0.77.standalone.menu."
    "instance-isolated.successor.v1"
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
EXPECTED_PROVIDER_PINS = {
    "universal_launcher": "7fc25340623131ba86c08dca4fb8a43b18a4520d",
    "universal_setup": "3048128963dc718a7c38c1cfcdda9e813a23b0db",
}
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
EXPECTED_TOP_LEVEL = {
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


def load_definition() -> dict[str, Any]:
    with DEFINITION.open("rb") as handle:
        return tomllib.load(handle)


def definition_digest(record: dict[str, Any]) -> str:
    canonical = copy.deepcopy(record)
    canonical.pop("definition_digest", None)
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
    problems: list[str] = []
    if record is None:
        try:
            record = load_definition()
        except (OSError, tomllib.TOMLDecodeError) as exc:
            return [f"successor route definition cannot be loaded: {exc}"]
    else:
        record = copy.deepcopy(record)

    if set(record) != EXPECTED_TOP_LEVEL:
        problems.append("successor route top-level contract is incomplete or open")
    if record.get("schema") != "facman.successor_play_route_definition.v1":
        problems.append("successor route schema identity drifted")
    if record.get("route_id") != EXPECTED_ROUTE_ID:
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
    for provider, revision in EXPECTED_PROVIDER_PINS.items():
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
            for provider, revision in EXPECTED_PROVIDER_PINS.items():
                if locked.get(provider) != revision:
                    problems.append(f"workspace lock drifted from route pin {provider}")
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
            if source_plan is None or source_plan.get("status") != "ready":
                problems.append("canonical plan does not leave source closure ready")
            if qualification_plan is None or qualification_plan.get("status") != "planned":
                problems.append("canonical plan activates qualification prematurely")
        except (OSError, tomllib.TOMLDecodeError) as exc:
            problems.append(f"canonical plan cannot be read: {exc}")

    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"successor-play-route-definition-check: {problem}", file=sys.stderr)
        return 1
    print("successor-play-route-definition-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
