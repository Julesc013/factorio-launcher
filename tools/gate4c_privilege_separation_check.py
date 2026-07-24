# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY_DIGEST = "6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2"
SCHEMAS = (
    "factorio_gate4c_observer_broker_request.v1.schema.json",
    "factorio_gate4c_observer_broker_response.v1.schema.json",
    "factorio_gate4c_privilege_boundary.v1.schema.json",
    "factorio_gate4c_process_integrity.v1.schema.json",
    "factorio_gate4c_observer_recovery_required.v1.schema.json",
    "factorio_gate4c_privilege_probe.v1.schema.json",
    "factorio_gate4c_observer_abort.v1.schema.json",
)


def required_anchors(
    path: Path, anchors: tuple[str, ...], problems: list[str]
) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        problems.append(f"{path.relative_to(ROOT)}: {exc}")
        return
    for anchor in anchors:
        if anchor not in text:
            problems.append(f"{path.relative_to(ROOT)} lacks boundary anchor: {anchor}")


def check() -> list[str]:
    problems: list[str] = []
    schema_root = ROOT / "contracts/schema/factorio"
    for name in SCHEMAS:
        path = schema_root / name
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"{path.relative_to(ROOT)}: {exc}")
            continue
        if schema.get("additionalProperties") is not False:
            problems.append(f"{name}: contract must reject additional properties")

    required_anchors(
        ROOT / "tests/native/gate4c_observer_broker_windows.cpp",
        (
            "PIPE_REJECT_REMOTE_CLIENTS",
            "FILE_FLAG_FIRST_PIPE_INSTANCE",
            "ConvertStringSecurityDescriptorToSecurityDescriptorW",
            "GetNamedPipeClientProcessId",
            "GetNamedPipeServerProcessId",
            'execute.lpVerb = L"runas"',
            "peer.user_sid != current.user_sid",
            "peer.windows_session_id != current.windows_session_id",
            "!is_high_integrity(peer)",
            "!is_exact_medium_integrity(peer)",
            'broker_mode != L"--observer-broker"',
            'broker_mode != L"--observer-broker-probe"',
        ),
        problems,
    )
    required_anchors(
        ROOT / "tests/native/gate4c_verdict_harness.cpp",
        (
            "Gate 4C coordinator must run at medium integrity",
            "observer broker start request binding is invalid",
            "observer broker independently rejected the frozen policy",
            '"observer-status"',
            '"observer-abort"',
            "capture_session_digest",
            "broker_resource_binding_digest",
            "validate_before_resume",
            "factorio.gate4c_process_integrity.v1",
            "observer-recovery-required.json",
            "product authority promoted: false",
        ),
        problems,
    )
    required_anchors(
        ROOT / "runtime/platform/fl_process_supervisor_windows.cpp",
        (
            "CREATE_SUSPENDED",
            "request.validate_before_resume",
            "refused before primary-thread resume",
            "ResumeThread",
        ),
        problems,
    )
    required_anchors(
        ROOT / "runtime/platform/fl_process_supervisor_posix.cpp",
        (
            "request.validate_before_resume",
            "pre-resume process validation is unavailable on this platform",
        ),
        problems,
    )
    required_anchors(
        ROOT / "tools/gate4c_verdict_session.py",
        (
            'sub.add_parser("observer-status")',
            'sub.add_parser("observer-abort")',
            "WPR remained active after fail-closed abort",
            "WPR is not active for the bound capture",
        ),
        problems,
    )

    with (ROOT / "release/index/project_status.v2.toml").open("rb") as handle:
        status = tomllib.load(handle)
    repair = status.get("gate4c_privilege_separation_repair", {})
    if repair.get("frozen_policy_digest") != POLICY_DIGEST:
        problems.append("privilege repair truth changed the frozen policy digest")
    for key in (
        "public_command",
        "product_permit_issuance",
        "privileged_broker_authority",
        "real_factorio_execution",
        "setup_authority",
        "credential_authority",
        "network_authority",
        "host_mutation_authority",
        "authority_promotion",
        "playability_promotion",
        "signing",
        "publication",
    ):
        if repair.get(key) is not False:
            problems.append(f"privilege repair truth promotes forbidden authority: {key}")
    return problems


def main() -> int:
    problems = check()
    if problems:
        for problem in problems:
            print(f"gate4c-privilege-separation: {problem}", file=sys.stderr)
        return 1
    print(
        "gate4c-privilege-separation: ok "
        "(medium coordinator/game, high observer, closed IPC)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
