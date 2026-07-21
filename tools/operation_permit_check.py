# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCHEMAS = {
    "operation_permit_claims.v1.schema.json": "common.operation_permit_claims.v1",
    "operation_permit_envelope.v1.schema.json": "common.operation_permit_envelope.v1",
    "permit_resource_binding.v1.schema.json": None,
    "permit_provider_identity.v1.schema.json": None,
    "permit_policy_binding.v1.schema.json": None,
    "permit_validation_result.v1.schema.json": "common.permit_validation_result.v1",
    "permit_consumption_result.v1.schema.json": "common.permit_consumption_result.v1",
}

REFUSALS = {
    "permit_missing", "permit_malformed", "permit_schema_unsupported",
    "permit_authentication_failed", "permit_not_yet_valid", "permit_expired",
    "permit_lifetime_exceeded", "permit_revoked", "permit_replayed",
    "permit_wrong_issuer_session", "permit_wrong_operation", "permit_wrong_audience",
    "permit_wrong_machine", "permit_wrong_principal", "permit_wrong_provider",
    "permit_wrong_plan", "permit_wrong_policy", "permit_wrong_evidence",
    "permit_wrong_resource", "permit_resource_stale", "permit_effect_scope_mismatch",
    "permit_capability_scope_mismatch", "permit_intent_mismatch",
    "permit_isolation_mismatch", "permit_resource_set_not_closed",
}


def check() -> list[str]:
    problems: list[str] = []
    schema_root = ROOT / "contracts/schema/common"
    loaded: dict[str, dict[str, object]] = {}
    for name, schema_id in SCHEMAS.items():
        path = schema_root / name
        if not path.is_file():
            problems.append(f"missing permit schema: {path.relative_to(ROOT)}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        loaded[name] = data
        if data.get("additionalProperties") is not False:
            problems.append(f"{name}: root must reject additional properties")
        if schema_id is not None and data.get("properties", {}).get("schema", {}).get("const") != schema_id:
            problems.append(f"{name}: schema identity mismatch")

    claims = loaded.get("operation_permit_claims.v1.schema.json", {})
    required = set(claims.get("required", []))
    expected_claims = {
        "schema", "canonicalization_version", "permit_id", "issuer_session_id",
        "operation", "plan", "audience", "resources", "effects",
        "required_capabilities", "machine_binding_id", "principal",
        "evidence_digest", "policy", "provider_revisions",
        "issued_at_unix_seconds", "not_before_unix_seconds",
        "expires_at_unix_seconds", "nonce",
    }
    if required != expected_claims:
        problems.append("permit claims required fields do not match the frozen exact set")
    envelope = loaded.get("operation_permit_envelope.v1.schema.json", {})
    algorithm = (
        envelope.get("properties", {}).get("authenticator", {})
        .get("properties", {}).get("algorithm", {}).get("const")
    )
    if algorithm != "hmac-sha256.process.v1":
        problems.append("permit envelope does not require the process HMAC algorithm")

    with (ROOT / "contracts/refusal/refusal_codes.v1.toml").open("rb") as handle:
        refusal_registry = tomllib.load(handle)
    registered = {str(item.get("id", "")) for item in refusal_registry.get("code", [])}
    missing_refusals = sorted(REFUSALS - registered)
    if missing_refusals:
        problems.append(f"permit refusals are missing: {missing_refusals}")

    core_header = (ROOT / "runtime/core/permit/fl_operation_permit.h").read_text(encoding="utf-8")
    core_source = (ROOT / "runtime/core/permit/fl_operation_permit.cpp").read_text(encoding="utf-8")
    for anchor in (
        "class PermitAuthenticator", "class ProcessSessionAuthenticator",
        "class PermitLedger", "class PermitValidator", "register_issued",
        "maximum_ttl_seconds", "monotonic_milliseconds", "constant_time_equal",
        "hmac_sha256_hex", "permit_replayed", "permit_resource_set_not_closed",
    ):
        if anchor not in core_header + core_source:
            problems.append(f"permit core is missing anchor: {anchor}")

    launch_header = (ROOT / "runtime/factorio/launch/flb_factorio_launch_permit.h").read_text(encoding="utf-8")
    launch_source = (ROOT / "runtime/factorio/launch/flb_factorio_launch_permit.cpp").read_text(encoding="utf-8")
    if "foundation.factorio-permit-proof" not in launch_header:
        problems.append("dormant launch verifier is not foundation-operation-bound")
    if "execution_available() noexcept { return false; }" not in launch_header:
        problems.append("dormant launch verifier execution boundary is not closed")
    for forbidden in ("flb_factorio_execution.h", "fl_process_supervisor.h", "LaunchExecutionService", "supervise_process"):
        if forbidden in launch_header + launch_source:
            problems.append(f"dormant launch verifier reaches execution primitive: {forbidden}")

    projection = (ROOT / "runtime/factorio/instance/flb_factorio_permit_projection.cpp").read_text(encoding="utf-8")
    for missing in (
        "exact_executable_identity", "exact_launch_plan_digest", "frozen_play_policy",
        "operation_permit_issuance", "real_process_provider_authority",
    ):
        if missing not in projection:
            problems.append(f"permit resource projection does not disclose missing Play resource: {missing}")
    if "launch_authority_complete = false" not in (
        ROOT / "runtime/factorio/instance/flb_factorio_permit_projection.h"
    ).read_text(encoding="utf-8"):
        problems.append("permit resource projection does not fail closed on Play authority")

    application_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted((ROOT / "runtime/factorio/application").glob("**/*"))
        if path.is_file()
    )
    for forbidden in ("seal_claims", "ProcessSessionAuthenticator", "OperationPermitEnvelope"):
        if forbidden in application_text:
            problems.append(f"product application unexpectedly gained permit issuance plumbing: {forbidden}")

    catalog = json.loads((ROOT / "contracts/generated-index/command_catalog.v2.json").read_text(encoding="utf-8"))
    serialized_catalog = json.dumps(catalog, sort_keys=True)
    for forbidden in ("permit.issue", "permits.issue", "operation_permit.issue"):
        if forbidden in serialized_catalog:
            problems.append(f"public command catalog exposes permit issuance: {forbidden}")

    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    for anchor in (
        "facman_operation_permit_fuzz",
        "facman_operation_permit_libfuzzer",
        "tests/fixtures/operation_permits",
    ):
        if anchor not in workflow:
            problems.append(f"hosted permit fuzz proof is missing: {anchor}")

    with (ROOT / "release/index/project_status.v2.toml").open("rb") as handle:
        status = tomllib.load(handle)
    permit_program = status.get("operation_permit_program", {})
    if permit_program.get("permit_issuance_authority") is not False:
        problems.append("project truth promoted permit issuance authority")
    if status.get("execution", {}).get("status") != "unavailable":
        problems.append("project truth promoted real execution")
    return problems


def main() -> int:
    problems = check()
    if problems:
        for problem in problems:
            print(f"operation-permit-check: {problem}", file=sys.stderr)
        return 1
    print("operation-permit-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
