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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

POLICY = ROOT / "contracts/policy/factorio/hermetic_standalone_play_2_0_77_windows_x64.v1.toml"
SCHEMA_ROOT = ROOT / "contracts/schema/factorio"

SCHEMAS = {
    "policy": "factorio_hermetic_standalone_play_policy.v1.schema.json",
    "root": "factorio_play_protected_root.v1.schema.json",
    "evidence": "factorio_play_evidence_requirement.v1.schema.json",
    "observation": "factorio_play_observation_scope.v1.schema.json",
    "interruption": "factorio_play_interruption_case.v1.schema.json",
    "verdict": "factorio_play_verdict_criteria.v1.schema.json",
}

EXPECTED_CANDIDATE = {
    "platform": "windows",
    "architecture": "x86_64",
    "factorio_version": "2.0.77",
    "distribution": "standalone_non_steam",
    "source_authentication": "sha256_bound_to_authenticated_wube_source",
    "filesystem": "ntfs",
    "volume": "fixed_local",
    "reparse_policy": "no_links_or_reparse_points_in_bound_closure",
    "instance_ownership": "facman_owned",
    "content_capability_requirement": "base_game",
    "optional_content_treatment": "reported_capability_not_entitlement",
    "mod_state": "explicit_empty_lock",
    "account_requirement": "none",
    "credential_requirement": "none",
    "network_requirement": "none",
    "candidate_revision_binding": "exact_reviewed_candidate_revision_required",
}

EXPECTED_PROVIDER_BASELINE = {
    "universal_launcher_revision": "7bd4425f0c35414f738159b45d8bec42edf70235",
    "universal_setup_revision": "3f8489275077347c2918f3bb03614ec6431362ff",
    "facman_candidate_revision": "bound_by_candidate_evidence",
    "process_provider_revision": "bound_by_candidate_evidence",
    "observation_provider_revision": "bound_by_candidate_evidence",
}

EXPECTED_LAUNCH = {
    "operation_kind": "instance.play",
    "intent": "menu",
    "isolation_mode": "hermetic",
    "permitted_effects": ["workspace_read", "workspace_write", "process_execute"],
    "required_capabilities": ["launch.execute.hermetic", "process.execute"],
    "direct_save_allowed": False,
    "scenario_allowed": False,
    "server_allowed": False,
    "editor_allowed": False,
    "benchmark_allowed": False,
    "multiplayer_connect_allowed": False,
    "network_allowed": False,
    "credentials_allowed": False,
    "preparation_allowed": False,
    "setup_allowed": False,
    "factorio_update_checks": "disabled",
    "mod_updates": "disabled",
    "process_environment": "versioned_minimal",
    "temporary_directory_policy": "workspace_operation_temporary_only",
}

EXPECTED_WRITABLE_IDS = {
    "instance.config", "instance.mods", "instance.saves", "instance.scenarios",
    "instance.script_output", "instance.logs", "instance.crash", "instance.cache",
    "instance.state", "instance.locks", "operation.record", "workspace.audit",
    "operation.temporary",
}

EXPECTED_PROTECTED_IDS = {
    "installation.selected", "installation.siblings", "factorio.default_user_data",
    "factorio.appdata", "factorio.localappdata", "factorio.programdata",
    "steam.install_roots", "steam.userdata", "steam.cloud_cache", "facman.package",
    "instances.other", "factorio.source_material", "registry.factorio_uninstall",
    "registry.factorio", "registry.steam", "effects.external_filesystem",
    "effects.external_registry", "host.external_unobserved",
}

EXPECTED_EVIDENCE_IDS = {
    "facman.source_revision", "facman.build_identity", "universal_launcher.revision",
    "universal_setup.revision", "policy.revision", "policy.digest", "machine.binding",
    "principal.identity", "application.session", "instance.spec_digest",
    "instance.binding_digest", "instance.readiness_digest", "installation.evidence_digest",
    "installation.root_identity", "executable.identity", "executable.sha256",
    "executable.publisher_source", "factorio.version", "factorio.content_capabilities",
    "config.digest", "read_data.identity", "write_data.identity", "mod_root.identity",
    "modset.state", "launch.intent", "launch.plan_identity", "launch.plan_digest",
    "isolation.mode", "protected.baseline_digest", "writable.baseline_digest",
    "observation.provider_revision",
}

EXPECTED_OBSERVER_IDS = {
    "factorio.play.process_tree_effects.v1",
    "factorio.play.protected_comparison.v1",
}

EXPECTED_AUTOMATED_CASES = {
    "permit.mutation", "permit.replay", "permit.expiry", "launch.wrong_intent",
    "launch.wrong_isolation", "readiness.stale", "executable.changed", "config.changed",
    "modset.changed", "installation.changed", "instance.wrong", "launch.concurrent",
    "cancel.before_process", "cancel.during_execution", "execution.timeout", "process.crash",
    "journal.write_failure", "run_lock.stale", "provider.restart", "issuer.restart",
    "observer.event_loss",
}

EXPECTED_HUMAN_CASES = {
    "human.menu_reached", "human.no_save_inferred", "human.create_or_load",
    "human.save_works", "human.clean_exit", "human.last_run_accurate",
    "human.relaunch_persists",
}

EXPECTED_DEFERRED_CASES = {"power_loss.synthetic"}

EXPECTED_NEGATIVE_CONTROLS = {
    "mutate_authenticated_permit_claim", "replay_permit_sequentially",
    "replay_permit_concurrently", "expire_permit", "change_launch_intent",
    "change_isolation_mode", "stale_readiness", "replace_executable_same_path",
    "replace_effective_config", "change_modset_state", "change_installation_evidence",
    "select_sibling_instance", "attempt_concurrent_launch", "cancel_before_process_creation",
    "cancel_during_execution", "force_timeout", "force_process_crash", "fail_journal_write",
    "present_stale_run_lock", "restart_provider_session", "restart_issuer_session",
    "lose_observer_events", "add_wildcard_or_prefix_resource",
    "change_protected_root_identity", "write_os_global_temporary_directory",
}

EXPECTED_EXCLUSIONS = {
    "whole_host_immutability", "steam_aware_play", "other_factorio_versions",
    "other_operating_systems", "third_party_modpacks", "account_or_credential_bindings",
    "networked_mod_acquisition", "load_save_intent", "new_game_intent",
    "map_editor_intent", "connect_server_intent", "start_server_intent",
    "benchmark_intent", "instrumented_dev_intent",
    "installation_or_instance_preparation", "universal_setup_mutation",
    "signing_and_publication",
}

EXPECTED_LOCAL_VALIDATION = [
    "policy_validator", "schema_metaschema", "negative_controls", "strict",
    "native_ctest", "python_unittest", "clean_reproduction",
]

EXPECTED_HOSTED_VALIDATION = [
    "windows_native_package", "linux", "macos", "sanitizers", "bounded_fuzzers",
    "coverage", "codeql", "schema", "security_policy", "package_proof",
]


def load_policy(path: Path = POLICY) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def canonical_policy_bytes(policy: dict[str, Any]) -> bytes:
    payload = copy.deepcopy(policy)
    payload.pop("policy_digest", None)
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_policy_digest(policy: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_policy_bytes(policy)).hexdigest()


def _load_schemas() -> tuple[dict[str, dict[str, Any]], list[str]]:
    problems: list[str] = []
    schemas: dict[str, dict[str, Any]] = {}
    for role, name in SCHEMAS.items():
        path = SCHEMA_ROOT / name
        if not path.is_file():
            problems.append(f"missing policy schema: {path.relative_to(ROOT)}")
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"{path.relative_to(ROOT)}: {exc}")
            continue
        if data.get("additionalProperties") is not False:
            problems.append(f"{name}: root must reject additional properties")
        schemas[role] = data
    return schemas, problems


def _ids(records: list[dict[str, Any]], key: str, label: str, problems: list[str]) -> set[str]:
    values = [str(record.get(key, "")) for record in records]
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        problems.append(f"duplicate {label}: {duplicates}")
    return set(values)


def _expect_exact(actual: set[str], expected: set[str], label: str, problems: list[str]) -> None:
    if actual != expected:
        problems.append(
            f"{label} mismatch; missing={sorted(expected - actual)} extra={sorted(actual - expected)}"
        )


def validate_policy(policy: dict[str, Any]) -> list[str]:
    from tools import json_contract

    schemas, problems = _load_schemas()
    if "policy" in schemas:
        problems.extend(f"policy {item}" for item in json_contract.validate(policy, schemas["policy"]))

    recorded_digest = str(policy.get("policy_digest", ""))
    computed_digest = canonical_policy_digest(policy)
    if recorded_digest != computed_digest:
        problems.append(f"policy digest mismatch: recorded={recorded_digest} computed={computed_digest}")

    claim = policy.get("claim", {})
    if claim.get("claim_id") != "factorio.hermetic_process_tree.v1":
        problems.append("claim must be factorio.hermetic_process_tree.v1")
    if claim.get("whole_host_immutability_claimed") is not False:
        problems.append("policy must not claim whole-host immutability")
    if claim.get("external_unobserved_disclosed") is not True:
        problems.append("policy must disclose external unobserved host state")

    if policy.get("candidate") != EXPECTED_CANDIDATE:
        problems.append("candidate selector does not match the frozen Windows x64 standalone 2.0.77 class")
    if policy.get("provider_baseline") != EXPECTED_PROVIDER_BASELINE:
        problems.append("provider baseline does not match the frozen dependency binding")
    if policy.get("launch") != EXPECTED_LAUNCH:
        problems.append("launch law must remain exact menu/hermetic with no alternate intent or extra authority")

    writable = policy.get("writable_roots", [])
    protected = policy.get("protected_roots", [])
    evidence = policy.get("evidence_requirements", [])
    observations = policy.get("observation_scopes", [])
    interruptions = policy.get("interruption_cases", [])
    verdicts = policy.get("verdict_criteria", [])
    for records, role in (
        (writable, "root"), (protected, "root"), (evidence, "evidence"),
        (observations, "observation"), (interruptions, "interruption"),
        (verdicts, "verdict"),
    ):
        if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
            problems.append(f"{role} records must be an array of objects")
            continue
        schema = schemas.get(role)
        if schema:
            for index, record in enumerate(records):
                problems.extend(
                    f"{role}[{index}] {item}"
                    for item in json_contract.validate(record, schema)
                )

    writable_ids = _ids(writable, "resource_id", "writable resource ids", problems)
    protected_ids = _ids(protected, "resource_id", "protected resource ids", problems)
    _expect_exact(writable_ids, EXPECTED_WRITABLE_IDS, "writable resource set", problems)
    _expect_exact(protected_ids, EXPECTED_PROTECTED_IDS, "protected resource set", problems)
    if writable_ids & protected_ids:
        problems.append(f"resource ids cannot be both writable and protected: {sorted(writable_ids & protected_ids)}")

    required_writable_identity = {
        "stable_object_identity", "volume_identity", "filesystem_identity", "no_follow_reparse_status"
    }
    for record in writable:
        resource_id = str(record.get("resource_id", ""))
        selector = str(record.get("selector", ""))
        if record.get("classification") != "writable" or record.get("domain") != "filesystem":
            problems.append(f"{resource_id}: writable resources must be filesystem/writable")
        if set(record.get("identity_requirements", [])) != required_writable_identity:
            problems.append(f"{resource_id}: writable identity requirements are not exact")
        if set(record.get("permitted_effects", [])) != {"workspace_read", "workspace_write"}:
            problems.append(f"{resource_id}: writable effects are not exact")
        if record.get("attributed_write_disposition") != "permitted":
            problems.append(f"{resource_id}: writable resource must permit attributed writes")
        if "*" in selector or ".." in selector or selector in {"{workspace_root}", "{instance_root}"}:
            problems.append(f"{resource_id}: broad, wildcard, or parent resource selector is forbidden")

    external_unobserved = []
    for record in protected:
        resource_id = str(record.get("resource_id", ""))
        classification = str(record.get("classification", ""))
        if record.get("permitted_effects") != []:
            problems.append(f"{resource_id}: protected/disclosed resources cannot permit effects")
        if classification == "protected_snapshot":
            if record.get("attributed_write_disposition") != "fail" or record.get("comparison") != "stable_manifest":
                problems.append(f"{resource_id}: protected snapshot must fail writes and use stable comparison")
            identities = set(record.get("identity_requirements", []))
            if not ({"content_manifest", "registry_value_set"} & identities):
                problems.append(f"{resource_id}: protected snapshot lacks content or registry evidence")
        elif classification == "forbidden_observed":
            if record.get("attributed_write_disposition") != "fail" or record.get("comparison") != "event_only":
                problems.append(f"{resource_id}: forbidden observed scope must fail attributed writes")
        elif classification == "external_unobserved":
            external_unobserved.append(resource_id)
            if record.get("attributed_write_disposition") != "outside_claim" or record.get("comparison") != "no_comparison":
                problems.append(f"{resource_id}: disclosed external state must remain outside the claim")
        else:
            problems.append(f"{resource_id}: unsupported protected-root classification {classification}")
    if external_unobserved != ["host.external_unobserved"]:
        problems.append("exactly one explicit whole-host external-unobserved disclosure is required")

    evidence_ids = _ids(evidence, "requirement_id", "evidence requirement ids", problems)
    _expect_exact(evidence_ids, EXPECTED_EVIDENCE_IDS, "evidence requirement set", problems)
    for record in evidence:
        requirement_id = str(record.get("requirement_id", ""))
        if record.get("required") is not True or record.get("recorded_in_packet") is not True:
            problems.append(f"{requirement_id}: evidence must be required and packet-bound")
        if record.get("secret_value") is not False:
            problems.append(f"{requirement_id}: secret values are forbidden in Play evidence")

    observer_ids = _ids(observations, "observer_id", "observer ids", problems)
    _expect_exact(observer_ids, EXPECTED_OBSERVER_IDS, "observation scope", problems)
    for record in observations:
        observer_id = str(record.get("observer_id", ""))
        if record.get("gap_disposition") != "Inconclusive":
            problems.append(f"{observer_id}: every observation gap must be Inconclusive")
        if record.get("hash_closes_output") is not True or record.get("independent_of_process_provider") is not True:
            problems.append(f"{observer_id}: observation must be independent and hash-closed")
    event_loss = next((item for item in interruptions if item.get("case_id") == "observer.event_loss"), {})
    if event_loss.get("expected_outcome") != "inconclusive" or event_loss.get("verdict_impact") != "inconclusive":
        problems.append("observer event loss must force an Inconclusive result")

    interruption_ids = _ids(interruptions, "case_id", "interruption case ids", problems)
    _expect_exact(
        interruption_ids,
        EXPECTED_AUTOMATED_CASES | EXPECTED_HUMAN_CASES | EXPECTED_DEFERRED_CASES,
        "interruption matrix",
        problems,
    )
    lanes = {
        "automated": {str(item.get("case_id", "")) for item in interruptions if item.get("lane") == "automated"},
        "human": {str(item.get("case_id", "")) for item in interruptions if item.get("lane") == "human"},
        "synthetic_deferred": {
            str(item.get("case_id", "")) for item in interruptions if item.get("lane") == "synthetic_deferred"
        },
    }
    _expect_exact(lanes["automated"], EXPECTED_AUTOMATED_CASES, "automated interruption lane", problems)
    _expect_exact(lanes["human"], EXPECTED_HUMAN_CASES, "human journey lane", problems)
    _expect_exact(lanes["synthetic_deferred"], EXPECTED_DEFERRED_CASES, "deferred interruption lane", problems)

    verdict_by_result = {str(item.get("result", "")): item for item in verdicts}
    if set(verdict_by_result) != {"Pass", "Fail", "Inconclusive"} or len(verdicts) != 3:
        problems.append("verdict law must contain exactly Pass, Fail, and Inconclusive")
    expected_dispositions = {
        "Pass": "eligible_for_separate_exact_route_promotion",
        "Fail": "bounded_repair_required",
        "Inconclusive": "improve_observation_and_repeat",
    }
    for result, disposition in expected_dispositions.items():
        record = verdict_by_result.get(result, {})
        if record.get("requires_human_review") is not True:
            problems.append(f"{result}: human review is required")
        if record.get("grants_authority") is not False:
            problems.append(f"{result}: verdict record cannot grant authority")
        if record.get("hash_closed_packet_required") is not True or record.get("observation_gaps_allowed") is not False:
            problems.append(f"{result}: exact hash-closed evidence without observation gaps is required")
        if record.get("disposition") != disposition:
            problems.append(f"{result}: incorrect governance disposition")

    _expect_exact(set(policy.get("automated_negative_controls", [])), EXPECTED_NEGATIVE_CONTROLS, "negative controls", problems)
    _expect_exact(set(policy.get("explicit_exclusions", [])), EXPECTED_EXCLUSIONS, "explicit exclusions", problems)
    if len(policy.get("human_journey", [])) != len(set(policy.get("human_journey", []))):
        problems.append("human journey steps must be unique")

    validation = policy.get("required_validation", {})
    if validation.get("exact_head_required") is not True:
        problems.append("exact-head validation is required")
    if validation.get("local") != EXPECTED_LOCAL_VALIDATION:
        problems.append("local validation matrix does not match the frozen policy")
    if validation.get("hosted") != EXPECTED_HOSTED_VALIDATION:
        problems.append("hosted validation matrix does not match the frozen policy")

    governance = policy.get("governance", {})
    for key in (
        "policy_implementation_review_required", "policy_closeout_review_required",
        "canonical_policy_promotion_before_candidate", "main_to_dev_ancestry_sync_before_candidate",
        "candidate_implementation_separate", "human_verdict_separate",
        "criteria_change_after_candidate_observation_forbidden",
    ):
        if governance.get(key) is not True:
            problems.append(f"governance must require {key}")
    if governance.get("candidate_work_unit") != "FACMAN-HERMETIC-STANDALONE-PLAY-CANDIDATE-01":
        problems.append("candidate WorkUnit identity is not frozen")
    if governance.get("verdict_work_unit") != "FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-01":
        problems.append("verdict WorkUnit identity is not frozen")

    authority = policy.get("authority_boundary", {})
    promoted = sorted(key for key, value in authority.items() if value is not False)
    if promoted:
        problems.append(f"policy-only artifact promotes forbidden authority: {promoted}")

    catalog = json.loads((ROOT / "contracts/generated-index/command_catalog.v2.json").read_text(encoding="utf-8"))
    serialized_catalog = json.dumps(catalog, sort_keys=True)
    for forbidden in ("permit.issue", "permits.issue", "operation_permit.issue"):
        if forbidden in serialized_catalog:
            problems.append(f"public command catalog exposes permit issuance: {forbidden}")

    with (ROOT / "release/index/project_status.v2.toml").open("rb") as handle:
        status = tomllib.load(handle)
    if status.get("operation_permit_program", {}).get("permit_issuance_authority") is not False:
        problems.append("project truth promoted permit issuance authority")
    if status.get("execution", {}).get("status") != "unavailable":
        problems.append("project truth promoted real execution")
    policy_truth = status.get("hermetic_standalone_play_policy", {})
    if policy_truth.get("policy_digest") != policy.get("policy_digest"):
        problems.append("project truth does not bind the frozen hermetic Play policy digest")
    for key in (
        "public_command", "permit_issuance_authority", "real_factorio_execution",
        "product_apply_route", "setup_authority", "credential_authority",
        "network_authority", "host_mutation_authority", "authority_promotion",
        "playability_promotion", "signing", "publication",
    ):
        if policy_truth.get(key) is not False:
            problems.append(f"project policy truth promotes forbidden authority: {key}")
    if policy_truth.get("canonical_main_promotion") is not True:
        problems.append("project policy truth does not record the policy-only canonical promotion")
    return problems


def check() -> list[str]:
    try:
        policy = load_policy()
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [f"{POLICY.relative_to(ROOT)}: {exc}"]
    return validate_policy(policy)


def main() -> int:
    problems = check()
    if problems:
        for problem in problems:
            print(f"hermetic-play-policy-check: {problem}", file=sys.stderr)
        return 1
    policy = load_policy()
    print(
        "hermetic-play-policy-check: ok "
        f"({len(policy['writable_roots'])} writable, {len(policy['protected_roots'])} protected/disclosed, "
        f"{len(policy['evidence_requirements'])} evidence, {len(policy['interruption_cases'])} cases; "
        f"digest {policy['policy_digest']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
