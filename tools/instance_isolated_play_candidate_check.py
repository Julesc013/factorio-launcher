# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.aide_evidence import resolve_task_file

POLICY = (
    ROOT
    / "contracts/policy/factorio/"
    "windows_instance_isolated_play_2_0_77_windows_x64.v1.toml"
)
CANONICAL = (
    ROOT
    / "contracts/generated-index/"
    "windows_instance_isolated_play_policy.v1.canonical.json"
)
EXPECTED_DIGEST = (
    "8d8189a9e8fc9ff7e479f7dda1adf0ea"
    "516bed2878046468022b2da8355e2432"
)
SCHEMAS = (
    "factorio_instance_isolated_play_candidate_plan.v1.schema.json",
    "factorio_instance_isolated_play_candidate_observation.v1.schema.json",
    "factorio_instance_isolated_play_candidate_packet.v1.schema.json",
)


def _load_json(path: Path, problems: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        problems.append(f"{path.relative_to(ROOT)}: {exc}")
        return {}
    if not isinstance(value, dict):
        problems.append(f"{path.relative_to(ROOT)}: expected JSON object")
        return {}
    return value


def check() -> list[str]:
    from tools.windows_instance_isolated_play_policy_check import (
        canonical_policy_bytes,
    )

    problems: list[str] = []
    try:
        with POLICY.open("rb") as handle:
            policy = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [f"{POLICY.relative_to(ROOT)}: {exc}"]
    expected = canonical_policy_bytes(policy)
    try:
        canonical = CANONICAL.read_bytes()
    except OSError as exc:
        problems.append(f"{CANONICAL.relative_to(ROOT)}: {exc}")
    else:
        if canonical not in {expected, expected + b"\n"}:
            problems.append(
                "candidate canonical mirror differs from the frozen "
                "instance-isolated policy"
            )

    schema_root = ROOT / "contracts/schema/factorio"
    loaded: dict[str, dict[str, Any]] = {}
    for name in SCHEMAS:
        schema = _load_json(schema_root / name, problems)
        loaded[name] = schema
        if schema.get("additionalProperties") is not False:
            problems.append(
                f"{name}: candidate contract must reject additional properties"
            )

    plan = loaded.get(
        "factorio_instance_isolated_play_candidate_plan.v1.schema.json", {}
    )
    core = plan.get("$defs", {}).get("plan_core", {}).get("properties", {})
    expected_plan_constants = {
        "policy_digest": EXPECTED_DIGEST,
        "operation": "instance.play",
        "launch_intent": "menu",
        "isolation_mode": "instance_isolated",
        "environment_revision": "factorio.menu-minimal.v2",
    }
    if not isinstance(core, dict):
        problems.append("instance-isolated candidate plan core is missing")
    else:
        for key, expected_value in expected_plan_constants.items():
            value = core.get(key, {})
            if not isinstance(value, dict) or value.get("const") != expected_value:
                problems.append(
                    f"instance-isolated plan must freeze {key}={expected_value!r}"
                )

    observation = loaded.get(
        "factorio_instance_isolated_play_candidate_observation.v1.schema.json",
        {},
    )
    gaps = observation.get("$defs", {}).get("gap_state", {})
    required_gaps = {
        "lost_events",
        "buffer_overflow",
        "unknown_process_identity",
        "unresolved_target",
        "delayed_events",
        "attribution_gap",
        "provider_failure",
        "missing_completion",
        "object_reuse_ambiguity",
        "baseline_incomplete",
        "postrun_incomplete",
        "packet_collision",
    }
    if (
        not isinstance(gaps, dict)
        or gaps.get("additionalProperties") is not False
        or set(gaps.get("properties", {})) != required_gaps
        or set(gaps.get("required", [])) != required_gaps
    ):
        problems.append(
            "instance-isolated observation does not close every policy gap signal"
        )
    effect = observation.get("$defs", {}).get("effect", {})
    classifications = (
        effect.get("properties", {})
        .get("classification", {})
        .get("enum", [])
    )
    expected_classifications = {
        "instance_owned",
        "operation_owned",
        "protected_software",
        "expected_external_disclosed",
        "unexpected_external",
        "unresolved",
        "observation_gap",
    }
    if set(classifications) != expected_classifications:
        problems.append(
            "instance-isolated effect taxonomy differs from the frozen policy"
        )

    packet = loaded.get(
        "factorio_instance_isolated_play_candidate_packet.v1.schema.json", {}
    )
    packet_properties = packet.get("properties", {})
    expected_packet_constants = {
        "policy_digest": EXPECTED_DIGEST,
        "human_verdict": "unset",
        "grants_authority": False,
        "product_route_available": False,
    }
    if not isinstance(packet_properties, dict):
        problems.append("instance-isolated candidate packet properties are missing")
    else:
        for key, expected_value in expected_packet_constants.items():
            value = packet_properties.get(key, {})
            if not isinstance(value, dict) or value.get("const") != expected_value:
                problems.append(
                    f"instance-isolated packet must freeze "
                    f"{key}={expected_value!r}"
                )

    paths = {
        "file_io_header": ROOT / "runtime/platform/fl_file_io.h",
        "file_io_source": ROOT / "runtime/platform/fl_file_io.cpp",
        "candidate_header": (
            ROOT
            / "runtime/factorio/launch/flb_factorio_hermetic_candidate.h"
        ),
        "candidate_source": (
            ROOT
            / "runtime/factorio/launch/flb_factorio_hermetic_candidate.cpp"
        ),
        "projection": (
            ROOT
            / "runtime/factorio/instance/flb_factorio_candidate_projection.cpp"
        ),
    }
    texts: dict[str, str] = {}
    for name, path in paths.items():
        try:
            texts[name] = path.read_text(encoding="utf-8")
        except OSError as exc:
            problems.append(str(exc))
            texts[name] = ""
    for anchor in (
        "class StableDirectoryObject",
        "validate_descendant",
        "revalidate",
    ):
        if anchor not in texts["file_io_header"]:
            problems.append(f"stable Instance object lacks anchor: {anchor}")
    for anchor in (
        "FILE_FLAG_OPEN_REPARSE_POINT",
        "FILE_SHARE_READ | FILE_SHARE_WRITE",
        "directory_object_path_identity_changed",
        "directory_descendant_reparse_refused",
    ):
        if anchor not in texts["file_io_source"]:
            problems.append(
                f"stable Instance implementation lacks anchor: {anchor}"
            )
    for anchor in (
        EXPECTED_DIGEST,
        'kInstanceIsolatedCandidateIsolation =',
        '"instance_isolated"',
        "public_issuance_available() noexcept { return false; }",
        "public_execution_available() noexcept { return false; }",
    ):
        if anchor not in texts["candidate_header"]:
            problems.append(f"candidate header lacks boundary anchor: {anchor}")
    for anchor in (
        "build_instance_isolated_candidate_plan",
        "candidate lacks a held no-follow Instance directory object",
        "launch.execute.instance_isolated",
        "windows.bam.factorio_process_execution.v1",
        "missing_completion",
        "object_reuse_ambiguity",
        "permit_resource_stale",
    ):
        if anchor not in texts["candidate_source"]:
            problems.append(f"candidate source lacks enforcement anchor: {anchor}")
    for anchor in (
        "project_instance_isolated_candidate_plan",
        '#include "facman/build_identity.hpp"',
        "open_no_follow(instance_root)",
        "instance_root_stable_object_identity",
        "exact_operation_resource_identities",
        "coordinator_integrity_medium",
        "observer_broker_integrity_high",
        "facman::build_identity::universal_launcher_revision",
        "facman::build_identity::universal_setup_revision",
        "reobserve_instance_isolated_candidate_context",
    ):
        if anchor not in texts["projection"]:
            problems.append(f"candidate projection lacks enforcement anchor: {anchor}")
    for stale_revision in (
        "7bd4425f0c35414f738159b45d8bec42edf70235",
        "3f8489275077347c2918f3bb03614ec6431362ff",
    ):
        if stale_revision in texts["projection"]:
            problems.append(
                "candidate projection embeds a historical first-party "
                f"revision literal: {stale_revision}"
            )

    catalog = _load_json(
        ROOT / "contracts/generated-index/command_catalog.v2.json", problems
    )
    command_ids = {
        str(command.get("command_id", ""))
        for command in catalog.get("commands", [])
        if isinstance(command, dict)
    }
    exposed = sorted(
        command_ids
        & {
            "instance.play",
            "instances.play",
            "permit.issue",
            "permits.issue",
            "operation_permit.issue",
        }
    )
    if exposed:
        problems.append(
            f"instance-isolated candidate exposes forbidden public commands: {exposed}"
        )

    try:
        with (ROOT / "release/index/project_status.v2.toml").open("rb") as handle:
            status = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        problems.append(f"project status unavailable: {exc}")
        status = {}
    if status.get("execution", {}).get("status") != "unavailable":
        problems.append("candidate project truth must keep real execution unavailable")
    permit_program = status.get("operation_permit_program", {})
    if permit_program.get("permit_issuance_authority") is not False:
        problems.append(
            "candidate project truth must keep product permit issuance unavailable"
        )
    policy_truth = status.get("windows_instance_isolated_play_policy", {})
    if policy_truth.get("policy_digest") != EXPECTED_DIGEST:
        problems.append(
            "candidate project truth does not retain the canonical policy digest"
        )
    for key in (
        "public_command",
        "product_permit_issuance",
        "factorio_execution_allowed",
        "runtime_mutation_allowed",
        "authority_promotion",
    ):
        if policy_truth.get(key) is not False:
            problems.append(
                f"candidate project truth promotes forbidden authority: {key}"
            )

    activation = resolve_task_file(
        "FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-CANDIDATE-01",
        "evidence/activation.md",
    )
    if activation is None:
        problems.append("instance-isolated candidate activation evidence is missing")
    return problems


def main() -> int:
    problems = check()
    if problems:
        for problem in problems:
            print(f"instance-isolated-play-candidate: {problem}", file=sys.stderr)
        return 1
    print("instance-isolated-play-candidate: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
