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
POLICY = ROOT / "contracts/policy/factorio/hermetic_standalone_play_2_0_77_windows_x64.v1.toml"
CANONICAL = ROOT / "contracts/generated-index/hermetic_standalone_play_policy.v1.canonical.json"
EXPECTED_DIGEST = "6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2"
SCHEMAS = (
    "factorio_hermetic_play_candidate_plan.v1.schema.json",
    "factorio_play_candidate_observation.v1.schema.json",
    "factorio_play_candidate_protected_comparison.v1.schema.json",
    "factorio_play_candidate_stable_manifest.v1.schema.json",
    "factorio_play_candidate_evidence_packet.v1.schema.json",
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
    from tools.hermetic_play_policy_check import canonical_policy_bytes

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
            problems.append("candidate canonical policy mirror differs from frozen Gate 4A policy")

    schema_root = ROOT / "contracts/schema/factorio"
    loaded: dict[str, dict[str, Any]] = {}
    for name in SCHEMAS:
        schema = _load_json(schema_root / name, problems)
        loaded[name] = schema
        if schema.get("additionalProperties") is not False:
            problems.append(f"{name}: candidate contract must reject additional properties")
    packet = loaded.get("factorio_play_candidate_evidence_packet.v1.schema.json", {})
    packet_properties = packet.get("properties", {})
    if not isinstance(packet_properties, dict):
        problems.append("candidate packet properties are missing")
    else:
        expected_constants = {
            "policy_digest": EXPECTED_DIGEST,
            "human_verdict": "unset",
            "grants_authority": False,
            "product_route_available": False,
        }
        for key, expected_value in expected_constants.items():
            value = packet_properties.get(key, {})
            if not isinstance(value, dict) or value.get("const") != expected_value:
                problems.append(f"candidate packet must freeze {key}={expected_value!r}")
    observation = loaded.get("factorio_play_candidate_observation.v1.schema.json", {})
    gaps = observation.get("$defs", {}).get("gap_state", {}).get("properties", {})
    required_gaps = {
        "lost_events", "buffer_overflow", "unknown_process_identity",
        "unresolved_target", "delayed_events", "attribution_gap", "provider_failure",
    }
    if not isinstance(gaps, dict) or set(gaps) != required_gaps:
        problems.append("candidate observer contract does not expose every frozen gap signal")

    header_path = ROOT / "runtime/factorio/launch/flb_factorio_hermetic_candidate.h"
    source_path = ROOT / "runtime/factorio/launch/flb_factorio_hermetic_candidate.cpp"
    projection_path = ROOT / "runtime/factorio/instance/flb_factorio_candidate_projection.cpp"
    try:
        header = header_path.read_text(encoding="utf-8")
        source = source_path.read_text(encoding="utf-8")
        projection = projection_path.read_text(encoding="utf-8")
    except OSError as exc:
        problems.append(str(exc))
        header = source = projection = ""
    for anchor in (
        EXPECTED_DIGEST,
        'kHermeticCandidateOperation = "instance.play"',
        'kHermeticCandidateIntent = "menu"',
        'kHermeticCandidateIsolation = "hermetic"',
        "public_issuance_available() noexcept { return false; }",
        "public_execution_available() noexcept { return false; }",
        "class BoundArtifactCandidateEffectObserver final",
    ):
        if anchor not in header:
            problems.append(f"candidate header lacks boundary anchor: {anchor}")
    for anchor in (
        "candidate does not bind the exact 31 policy evidence requirements",
        "runtime writable scope must be a duplicate-free strict subset",
        "candidate permit resources do not exactly bind writable and execution effects",
        "plan_integrity_valid(reviewed_plan)",
        "independent observer was not active before process boundary",
        "eligible_for_human_verdict",
        'output.add_string("human_verdict", packet.human_verdict)',
        "packet_digest == sha256_text(packet_core)",
    ):
        if anchor not in source:
            problems.append(f"candidate source lacks enforcement anchor: {anchor}")
    for anchor in (
        "the frozen candidate is available only on Windows x64",
        "candidate executable is not inside selected installation",
        'request.workspace / "temporary" / request.operation_id / "process"',
        'instance_root / "state" / "userprofile"',
        "reobserve_hermetic_candidate_context",
        '"factorio.writable-root"',
    ):
        if anchor not in projection:
            problems.append(f"candidate projection lacks enforcement anchor: {anchor}")

    catalog = _load_json(
        ROOT / "contracts/generated-index/command_catalog.v2.json", problems
    )
    command_ids = {
        str(command.get("command_id", ""))
        for command in catalog.get("commands", [])
        if isinstance(command, dict)
    }
    forbidden_commands = {
        "instance.play", "instances.play", "permit.issue", "permits.issue",
        "operation_permit.issue",
    }
    exposed = sorted(command_ids & forbidden_commands)
    if exposed:
        problems.append(f"candidate exposes forbidden public commands: {exposed}")

    with (ROOT / "release/index/project_status.v2.toml").open("rb") as handle:
        status = tomllib.load(handle)
    if status.get("execution", {}).get("status") != "unavailable":
        problems.append("candidate project truth must keep real execution unavailable")
    permit_program = status.get("operation_permit_program", {})
    if permit_program.get("permit_issuance_authority") is not False:
        problems.append("candidate project truth must keep product permit issuance unavailable")
    policy_truth = status.get("hermetic_standalone_play_policy", {})
    if policy_truth.get("policy_digest") != EXPECTED_DIGEST:
        problems.append("candidate project truth does not retain the frozen policy digest")
    for key in (
        "public_command", "permit_issuance_authority", "real_factorio_execution",
        "setup_authority", "credential_authority", "network_authority",
        "authority_promotion", "playability_promotion", "signing", "publication",
    ):
        if policy_truth.get(key) is not False:
            problems.append(f"candidate project truth promotes forbidden authority: {key}")

    storage = ROOT / ".aide/queue/active/FACMAN-HERMETIC-STANDALONE-PLAY-CANDIDATE-01/evidence/task-storage.md"
    if not storage.is_file():
        problems.append("Gate 4B task-scoped storage record is missing")
    return problems


def main() -> int:
    problems = check()
    if problems:
        for problem in problems:
            print(f"hermetic-play-candidate: {problem}", file=sys.stderr)
        return 1
    print("hermetic-play-candidate: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
