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

POLICY = (
    ROOT
    / "contracts/policy/factorio/"
    "windows_instance_isolated_play_2_0_77_windows_x64.v1.toml"
)
CANONICAL_POLICY = (
    ROOT
    / "contracts/generated-index/"
    "windows_instance_isolated_play_policy.v1.canonical.json"
)
HERMETIC_POLICY = (
    ROOT
    / "contracts/policy/factorio/"
    "hermetic_standalone_play_2_0_77_windows_x64.v1.toml"
)
HERMETIC_POLICY_FILE_SHA256 = (
    "5840b701801454cdc75f99203d1230bf52e07c4f9c45f02be2f5f35b01157215"
)
HERMETIC_POLICY_DIGEST = (
    "6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2"
)
SCHEMA_ROOT = ROOT / "contracts/schema/factorio"
SCHEMAS = {
    "policy": "factorio_windows_instance_isolated_play_policy.v1.schema.json",
    "resource": "factorio_instance_closure_resource.v1.schema.json",
    "disclosure": "factorio_external_effect_disclosure.v1.schema.json",
    "disposition": "factorio_external_effect_disposition.v1.schema.json",
    "observation": "factorio_instance_isolated_observation_scope.v1.schema.json",
    "verdict": "factorio_instance_isolated_verdict_criteria.v1.schema.json",
}

EXPECTED_SOURCE_EVIDENCE = {
    "source_work_unit": "FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-03",
    "source_verdict": "Inconclusive",
    "source_operation_id": "gate4c-verdict03-launch1-20260725a",
    "source_revision": "885b9822809c4b3e91e784bdd7e3b8b261533901",
    "repair_work_unit": "FACMAN-GATE4C-VERDICT03-POSTRUN-REPAIR-01",
    "repair_implementation_revision": "8382cb5768bd5d2690a6b34a2b6aa2e646b3d8b0",
    "repair_dev_integration_revision": "ab24b9c417726c9be2daa23684756d24ac0977ae",
    "frozen_hermetic_policy_digest": HERMETIC_POLICY_DIGEST,
    "etl_sha256": "ffd0e7648bc43e08d95c87abc5f1ff016ac55c1168fc07047162aae8e16f56e6",
    "events_csv_sha256": "37e0684e1aef8a39aece855d90cefa09344a08e55a09f662216e27ec16f64085",
    "retained_trace_effect_count": 611,
    "retained_trace_reused_for_authority": False,
    "retained_evidence_root_must_remain_unchanged": True,
}

EXPECTED_CLAIM = {
    "claim_id": "factorio.windows_instance_isolated_process_tree.v1",
    "user_label": "Instance-isolated — Windows",
    "guarantee": (
        "FacMan confines Factorio mutable product state to the exact bound Instance "
        "closure. Protected software remains immutable. Every external OS or driver "
        "effect must be resolved, classified, and exactly disclosed or rejected."
    ),
    "whole_host_immutability_claimed": False,
    "enforced_sandbox_claimed": False,
    "external_effects_are_facman_owned": False,
    "external_effects_are_permit_resources": False,
    "unknown_effects_can_pass": False,
    "unresolved_effects_can_pass": False,
}

EXPECTED_CANDIDATE = {
    "platform": "windows",
    "architecture": "x86_64",
    "factorio_version": "2.0.77",
    "distribution": "standalone_non_steam",
    "source_authentication": "sha256_bound_to_authenticated_wube_source",
    "filesystem": "ntfs",
    "volume": "fixed_local",
    "instance_ownership": "facman_owned",
    "content_capability_requirement": "base_game",
    "optional_content_treatment": "reported_capability_not_entitlement",
    "mod_state": "explicit_empty_lock",
    "account_requirement": "none",
    "credential_requirement": "none",
    "network_requirement": "none",
    "process_environment": "factorio.menu-minimal.v2",
    "observer_provider": "gate4c-etw-file-registry-process.v6",
    "candidate_revision_binding": "exact_reviewed_candidate_revision_required",
}

EXPECTED_PROVIDER_BASELINE = {
    "universal_launcher_revision": "7bd4425f0c35414f738159b45d8bec42edf70235",
    "universal_setup_revision": "3f8489275077347c2918f3bb03614ec6431362ff",
    "facman_candidate_revision": "bound_by_future_candidate_evidence",
    "process_provider_revision": "bound_by_future_candidate_evidence",
    "observation_provider_revision": "gate4c-etw-file-registry-process.v6",
}

EXPECTED_LAUNCH = {
    "operation_kind": "instance.play",
    "intent": "menu",
    "isolation_mode": "instance_isolated",
    "permitted_effects": ["workspace_read", "workspace_write", "process_execute"],
    "required_capabilities": ["launch.execute.instance_isolated", "process.execute"],
    "external_effects_authorized": False,
    "registry_write_authority": False,
    "driver_cache_write_authority": False,
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
    "working_directory": "exact_operation_temporary_process_root",
    "temporary_directory_policy": "exact_operation_temporary_process_root",
}

EXPECTED_INVENTORY = {
    "verdict03.instance_closure_writes": (195, "instance_owned"),
    "verdict03.installation_umdlogs": (2, "protected_software"),
    "verdict03.drive_root_umdlogs": (2, "unexpected_external"),
    "verdict03.factorio_external_registry": (327, "unexpected_external"),
    "verdict03.windows_bam": (1, "expected_external_disclosed"),
    "verdict03.unresolved_file_targets": (6, "unresolved"),
    "verdict03.remaining_resolved_effects": (78, "not_a_frozen_external_allowlist"),
    "verdict03.packet_collision": (1, "observation_gap"),
}

EXPECTED_WRITABLE_IDS = {
    "instance.closure",
    "operation.record",
    "operation.temporary",
    "operation.observer_artifacts",
    "operation.candidate_artifacts",
    "operation.audit_record",
    "operation.process_logs",
}

EXPECTED_PROTECTED_IDS = {
    "installation.selected",
    "installation.siblings",
    "instances.other",
    "factorio.default_user_data",
    "factorio.appdata",
    "factorio.localappdata",
    "factorio.programdata",
    "steam.installation",
    "steam.userdata",
    "facman.package",
    "factorio.source_artifacts",
    "registry.factorio_uninstall",
}

EXPECTED_DISPOSITIONS = {
    "instance_owned": ("facman", True, True, "allowed"),
    "operation_owned": ("facman", True, True, "allowed"),
    "protected_software": ("facman", False, False, "Fail"),
    "expected_external_disclosed": ("machine_external", False, True, "allowed"),
    "unexpected_external": ("machine_external", False, False, "Fail"),
    "unresolved": ("unknown", False, False, "Inconclusive"),
    "observation_gap": ("unknown", False, False, "Inconclusive"),
}

EXPECTED_DISCLOSURE_IDS = {"windows.bam.factorio_process_execution.v1"}
EXPECTED_OBSERVER_IDS = {
    "factorio.instance_isolated.process_tree_effects.v1",
    "factorio.instance_isolated.protected_comparison.v1",
}

EXPECTED_NEGATIVE_CONTROLS = {
    "instance_sibling_escape",
    "instance_reparse_escape",
    "instance_ancestor_replacement",
    "installation_umdlogs_creation",
    "drive_root_driver_directory_creation",
    "unexpected_hkcu_registry_write",
    "unexpected_hklm_registry_write",
    "bam_effect_with_wrong_executable_identity",
    "directinput_effect_after_environment_v2_suppression",
    "unresolved_fileio_target",
    "missing_fileio_op_end",
    "file_object_reuse",
    "kcb_reuse",
    "lost_events",
    "wrong_launch_intent",
    "wrong_isolation_mode",
    "elevated_factorio",
    "stale_permit",
    "replayed_permit",
    "observer_runtime_packet_collision",
    "incomplete_packet",
}

EXPECTED_EXCLUSIONS = {
    "hermetic_or_sandbox_claim",
    "whole_host_immutability",
    "steam_aware_play",
    "other_factorio_versions",
    "other_operating_systems",
    "third_party_modpacks",
    "account_or_credential_bindings",
    "networked_mod_acquisition",
    "alternate_launch_intents",
    "installation_or_instance_preparation",
    "universal_setup_mutation",
    "external_effect_authority",
    "arbitrary_registry_or_filesystem_write",
    "signing_and_publication",
}


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


def _ids(
    records: list[dict[str, Any]], key: str, label: str, problems: list[str]
) -> set[str]:
    values = [str(record.get(key, "")) for record in records]
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        problems.append(f"duplicate {label}: {duplicates}")
    return set(values)


def _expect_exact(
    actual: set[str], expected: set[str], label: str, problems: list[str]
) -> None:
    if actual != expected:
        problems.append(
            f"{label} mismatch; missing={sorted(expected - actual)} "
            f"extra={sorted(actual - expected)}"
        )


def _validate_records(
    records: Any,
    schema: dict[str, Any] | None,
    role: str,
    problems: list[str],
) -> list[dict[str, Any]]:
    from tools import json_contract

    if not isinstance(records, list) or not all(
        isinstance(item, dict) for item in records
    ):
        problems.append(f"{role} records must be an array of objects")
        return []
    if schema:
        for index, record in enumerate(records):
            problems.extend(
                f"{role}[{index}] {item}"
                for item in json_contract.validate(record, schema)
            )
    return records


def validate_policy(policy: dict[str, Any]) -> list[str]:
    from tools import json_contract

    schemas, problems = _load_schemas()
    if "policy" in schemas:
        problems.extend(
            f"policy {item}"
            for item in json_contract.validate(policy, schemas["policy"])
        )

    recorded_digest = str(policy.get("policy_digest", ""))
    computed_digest = canonical_policy_digest(policy)
    if recorded_digest != computed_digest:
        problems.append(
            f"policy digest mismatch: recorded={recorded_digest} computed={computed_digest}"
        )

    if policy.get("source_evidence") != EXPECTED_SOURCE_EVIDENCE:
        problems.append("retained Verdict 03 source evidence identity is not exact")
    if policy.get("claim") != EXPECTED_CLAIM:
        problems.append(
            "claim must remain the exact normal-host instance-isolated claim "
            "without a hermetic, sandbox, whole-host, ownership, or permit overclaim"
        )
    if policy.get("candidate") != EXPECTED_CANDIDATE:
        problems.append(
            "candidate selector does not match Windows x64 standalone Factorio "
            "2.0.77 with environment v2 and observer v6"
        )
    if policy.get("provider_baseline") != EXPECTED_PROVIDER_BASELINE:
        problems.append("provider baseline is not exact")
    if policy.get("launch") != EXPECTED_LAUNCH:
        problems.append(
            "launch law must remain one menu/instance_isolated operation with "
            "no external-effect authority"
        )

    inventory = _validate_records(
        policy.get("evidence_inventory"), None, "inventory", problems
    )
    inventory_ids = _ids(inventory, "inventory_id", "inventory ids", problems)
    _expect_exact(
        inventory_ids, set(EXPECTED_INVENTORY), "retained evidence inventory", problems
    )
    for record in inventory:
        inventory_id = str(record.get("inventory_id", ""))
        expected = EXPECTED_INVENTORY.get(inventory_id)
        if expected and (
            record.get("effect_count") != expected[0]
            or record.get("policy_disposition") != expected[1]
        ):
            problems.append(
                f"{inventory_id}: effect count or policy disposition is not exact"
            )
    trace_inventory_count = sum(
        int(record.get("effect_count", 0))
        for record in inventory
        if record.get("domain") != "operation_evidence"
    )
    if trace_inventory_count != 611:
        problems.append(
            f"retained ETW inventory must reconcile to 611 effects, got {trace_inventory_count}"
        )

    writable = _validate_records(
        policy.get("writable_resources"),
        schemas.get("resource"),
        "writable resource",
        problems,
    )
    writable_ids = _ids(writable, "resource_id", "writable resource ids", problems)
    _expect_exact(writable_ids, EXPECTED_WRITABLE_IDS, "writable resources", problems)
    for record in writable:
        resource_id = str(record.get("resource_id", ""))
        selector = str(record.get("logical_selector", ""))
        if record.get("string_prefix_authority") is not False:
            problems.append(f"{resource_id}: string-prefix authority is forbidden")
        if any(marker in selector for marker in ("\\", "/", "*", "..")):
            problems.append(
                f"{resource_id}: logical selector cannot be a path, wildcard, or parent prefix"
            )
        if record.get("reparse_policy") != (
            "refuse_reparse_mount_ancestor_replacement_or_escape"
        ):
            problems.append(f"{resource_id}: reparse and ancestor escape refusal is required")
        if set(record.get("permitted_effects", [])) != {
            "workspace_read",
            "workspace_write",
        }:
            problems.append(f"{resource_id}: writable effects are not exact")

    instance = next(
        (item for item in writable if item.get("resource_id") == "instance.closure"),
        {},
    )
    required_instance_identity = {
        "logical_resource_id",
        "stable_root_object_identity",
        "volume_identity",
        "filesystem_identity",
        "no_follow_reparse_status",
        "owning_instance_record_digest",
        "instance_binding_digest",
    }
    if (
        instance.get("selector_kind") != "stable_directory_object"
        or instance.get("descendant_policy") != "recursive_creation_and_mutation"
        or set(instance.get("identity_requirements", []))
        != required_instance_identity
    ):
        problems.append(
            "instance closure must bind one stable directory object, exact "
            "instance records, and recursive no-reparse descendant creation"
        )
    owners = {
        item.get("resource_id"): item.get("artifact_owner") for item in writable
    }
    if owners.get("operation.observer_artifacts") != "observer":
        problems.append("observer-artifacts must be exclusively observer-owned")
    if owners.get("operation.candidate_artifacts") != "runtime":
        problems.append("candidate-artifacts must be exclusively runtime-owned")
    if (
        owners.get("operation.observer_artifacts")
        == owners.get("operation.candidate_artifacts")
    ):
        problems.append("observer and candidate artifact ownership must be disjoint")

    protected = _validate_records(
        policy.get("protected_resources"), None, "protected resource", problems
    )
    protected_ids = _ids(protected, "resource_id", "protected resource ids", problems)
    _expect_exact(protected_ids, EXPECTED_PROTECTED_IDS, "protected resources", problems)
    for record in protected:
        resource_id = str(record.get("resource_id", ""))
        selector = str(record.get("logical_selector", ""))
        if any(marker in selector for marker in ("\\", "/", "*", "..")):
            problems.append(f"{resource_id}: protected selector is broad or path-based")
        if record.get("mutation_disposition") != "Fail":
            problems.append(f"{resource_id}: protected mutation must be Fail")
        if not str(record.get("comparison", "")).startswith("stable_"):
            problems.append(f"{resource_id}: protected resource lacks stable comparison")
    selected_install = next(
        (
            item
            for item in protected
            if item.get("resource_id") == "installation.selected"
        ),
        {},
    )
    if selected_install.get("comparison") != "stable_manifest":
        problems.append("selected installation must remain manifest-immutable")

    dispositions = _validate_records(
        policy.get("effect_dispositions"),
        schemas.get("disposition"),
        "effect disposition",
        problems,
    )
    disposition_ids = _ids(
        dispositions, "classification", "effect classifications", problems
    )
    _expect_exact(
        disposition_ids,
        set(EXPECTED_DISPOSITIONS),
        "effect disposition taxonomy",
        problems,
    )
    for record in dispositions:
        classification = str(record.get("classification", ""))
        expected = EXPECTED_DISPOSITIONS.get(classification)
        actual = (
            record.get("ownership"),
            record.get("permit_authorized"),
            record.get("pass_eligible"),
            record.get("verdict_impact"),
        )
        if expected and actual != expected:
            problems.append(f"{classification}: closed disposition semantics changed")

    disclosures = _validate_records(
        policy.get("external_effect_disclosures"),
        schemas.get("disclosure"),
        "external disclosure",
        problems,
    )
    disclosure_ids = _ids(disclosures, "effect_id", "disclosure ids", problems)
    _expect_exact(
        disclosure_ids, EXPECTED_DISCLOSURE_IDS, "external disclosures", problems
    )
    for record in disclosures:
        selector = str(record.get("target_selector", ""))
        combined = json.dumps(record, sort_keys=True).lower()
        if "*" in selector or selector in {"hklm", "hkcu", "registry", "filesystem"}:
            problems.append("external disclosure selector is broad or wildcarded")
        if "nvidia" in combined or "directinput" in combined:
            problems.append(
                "NVIDIA and DirectInput effects cannot be frozen as expected disclosures"
            )
        if record.get("permit_authorized") is not False or record.get(
            "permit_effects"
        ) != []:
            problems.append("external effects are observations, never permit resources")
        if record.get("mismatch_disposition") != "Fail":
            problems.append("external disclosure mismatch must be Fail")
    bam = disclosures[0] if len(disclosures) == 1 else {}
    if (
        bam.get("target_selector")
        != "HKLM\\SYSTEM\\CurrentControlSet\\Services\\bam\\State\\UserSettings\\{principal_sid}"
        or bam.get("value_selector") != "{exact_factorio_executable_native_path}"
        or bam.get("operation_kinds") != ["RegSetValue"]
    ):
        problems.append(
            "BAM disclosure must bind the exact domain, principal, executable value, "
            "and RegSetValue operation"
        )

    observations = _validate_records(
        policy.get("observation_scopes"),
        schemas.get("observation"),
        "observation",
        problems,
    )
    observer_ids = _ids(observations, "observer_id", "observer ids", problems)
    _expect_exact(
        observer_ids, EXPECTED_OBSERVER_IDS, "observation scope", problems
    )
    required_gaps = {
        "lost_events",
        "buffer_overflow",
        "unresolved_target",
        "attribution_gap",
        "provider_failure",
    }
    for record in observations:
        observer_id = str(record.get("observer_id", ""))
        if not required_gaps.issubset(set(record.get("gap_signals", []))):
            problems.append(f"{observer_id}: mandatory gap signals are incomplete")
        if record.get("gap_disposition") != "Inconclusive":
            problems.append(f"{observer_id}: every observation gap is Inconclusive")
        if (
            record.get("exact_target_resolution_required") is not True
            or record.get("successful_completion_required") is not True
        ):
            problems.append(
                f"{observer_id}: exact target and completion evidence are required"
            )

    verdicts = _validate_records(
        policy.get("verdict_criteria"),
        schemas.get("verdict"),
        "verdict",
        problems,
    )
    verdict_by_result = {str(item.get("result", "")): item for item in verdicts}
    if set(verdict_by_result) != {"Pass", "Fail", "Inconclusive"} or len(verdicts) != 3:
        problems.append("verdict law must contain exactly Pass, Fail, and Inconclusive")
    expected_verdict_dispositions = {
        "Pass": "eligible_for_separate_exact_route_promotion",
        "Fail": "bounded_repair_required",
        "Inconclusive": "improve_observation_and_repeat",
    }
    for result, disposition in expected_verdict_dispositions.items():
        record = verdict_by_result.get(result, {})
        if (
            record.get("requires_human_review") is not True
            or record.get("grants_authority") is not False
        ):
            problems.append(f"{result}: human review is required and grants no authority")
        if (
            record.get("observation_gaps_allowed") is not False
            or record.get("unresolved_effects_allowed") is not False
        ):
            problems.append(f"{result}: gaps or unresolved effects cannot be waived")
        if record.get("disposition") != disposition:
            problems.append(f"{result}: governance disposition changed")

    _expect_exact(
        set(policy.get("automated_negative_controls", [])),
        EXPECTED_NEGATIVE_CONTROLS,
        "negative controls",
        problems,
    )
    _expect_exact(
        set(policy.get("explicit_exclusions", [])),
        EXPECTED_EXCLUSIONS,
        "explicit exclusions",
        problems,
    )

    governance = policy.get("governance", {})
    required_governance = {
        "policy_implementation_review_required": True,
        "policy_closeout_review_required": True,
        "canonical_policy_promotion_before_candidate": True,
        "main_to_dev_ancestry_sync_before_candidate": True,
        "candidate_work_unit": "FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-CANDIDATE-01",
        "verdict_work_unit": "FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-VERDICT-01",
        "candidate_implementation_separate": True,
        "human_verdict_separate": True,
        "criteria_change_after_candidate_observation_forbidden": True,
        "frozen_hermetic_policy_mutation_forbidden": True,
    }
    if governance != required_governance:
        problems.append("policy governance sequence is not exact")

    authority = policy.get("authority_boundary", {})
    promoted = sorted(key for key, value in authority.items() if value is not False)
    if promoted:
        problems.append(f"policy-only artifact promotes forbidden authority: {promoted}")

    try:
        hermetic_bytes = HERMETIC_POLICY.read_bytes()
        hermetic_data = tomllib.loads(hermetic_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        problems.append(f"frozen hermetic policy cannot be read: {exc}")
    else:
        file_digest = hashlib.sha256(hermetic_bytes).hexdigest()
        if file_digest != HERMETIC_POLICY_FILE_SHA256:
            problems.append("canonical Gate 4A hermetic policy bytes changed")
        if hermetic_data.get("policy_digest") != HERMETIC_POLICY_DIGEST:
            problems.append("canonical Gate 4A hermetic policy digest changed")

    with (ROOT / "release/index/project_status.v2.toml").open("rb") as handle:
        status = tomllib.load(handle)
    product = status.get("product", {})
    if (
        product.get("truth_scope")
        != "dev_integrated_postrun_repair_proven_instance_isolated_policy_active"
    ):
        problems.append("project truth understates merged Verdict 03 repair integration")
    if product.get("canonical_main_promotion") is not False:
        problems.append("project truth must explicitly record no canonical main promotion")
    if "canonical_integration" in product:
        problems.append(
            "ambiguous product canonical_integration field must be replaced by "
            "canonical_main_promotion"
        )

    repair = status.get("gate4c_verdict03_postrun_repair", {})
    if repair.get("status") != "accepted_reviewed_dev_integration":
        problems.append("post-run repair truth must record accepted reviewed dev integration")

    policy_truth = status.get("windows_instance_isolated_play_policy", {})
    expected_truth = {
        "status": "frozen_criteria_review_pending",
        "work_unit": "FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-POLICY-01",
        "source_repair": "FACMAN-GATE4C-VERDICT03-POSTRUN-REPAIR-01",
        "source_verdict": "Inconclusive",
        "policy_path": (
            "contracts/policy/factorio/"
            "windows_instance_isolated_play_2_0_77_windows_x64.v1.toml"
        ),
        "policy_schema": "factorio.windows_instance_isolated_play_policy.v1",
        "policy_id": "facman.windows-instance-isolated-play.2.0.77.x64.v1",
        "policy_revision": "1",
        "canonicalization_version": "facman.sorted-json.v1",
        "policy_digest": recorded_digest,
        "claim_id": "factorio.windows_instance_isolated_process_tree.v1",
        "user_label": "Instance-isolated — Windows",
        "candidate_class": "Windows x64 Factorio 2.0.77 standalone non-Steam menu",
        "isolation_mode": "instance_isolated",
        "writable_boundary": "exact stable FacMan-owned instance directory object and descendants",
        "writable_resource_count": 7,
        "protected_resource_count": 12,
        "external_disclosure_count": 1,
        "expected_external_disclosures": [
            "windows.bam.factorio_process_execution.v1"
        ],
        "protected_software_roots_immutable": True,
        "os_driver_effects_observed_and_disclosed": True,
        "external_effects_are_permit_resources": False,
        "whole_host_immutability_claimed": False,
        "enforced_sandbox_claimed": False,
        "frozen_hermetic_policy_mutation_allowed": False,
        "runtime_mutation_allowed": False,
        "factorio_execution_allowed": False,
        "public_command": False,
        "product_permit_issuance": False,
        "canonical_main_promotion": False,
        "authority_promotion": False,
    }
    if policy_truth != expected_truth:
        problems.append(
            "Windows instance-isolated policy truth must bind the frozen policy "
            "candidate, resources, disclosure, and no-authority boundary"
        )

    if status.get("execution", {}).get("status") != "unavailable":
        problems.append("policy work cannot promote execution")
    return problems


def check() -> list[str]:
    try:
        policy = load_policy()
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [f"{POLICY.relative_to(ROOT)}: {exc}"]
    problems = validate_policy(policy)
    expected_canonical = canonical_policy_bytes(policy)
    try:
        actual_canonical = CANONICAL_POLICY.read_bytes()
    except OSError as exc:
        problems.append(f"{CANONICAL_POLICY.relative_to(ROOT)}: {exc}")
    else:
        if actual_canonical not in {expected_canonical, expected_canonical + b"\n"}:
            problems.append("canonical Windows instance-isolated policy mirror is absent or stale")
    return problems


def main() -> int:
    problems = check()
    if problems:
        for problem in problems:
            print(
                f"windows-instance-isolated-play-policy-check: {problem}",
                file=sys.stderr,
            )
        return 1
    policy = load_policy()
    print(
        "windows-instance-isolated-play-policy-check: ok "
        f"({len(policy['writable_resources'])} writable, "
        f"{len(policy['protected_resources'])} protected, "
        f"{len(policy['external_effect_disclosures'])} disclosed external; "
        f"digest {policy['policy_digest']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
