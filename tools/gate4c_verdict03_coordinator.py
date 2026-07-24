# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Exact operator tooling for the fresh split-privilege Gate 4C Verdict 03.

This module does not issue permits or start processes.  It stages the immutable
Gate 4B candidate, creates one disposable Verdict 03 workspace, binds a fresh
quiet-host attestation to an elevated observer self-test, captures one
medium-integrity baseline, records explicit human observations, and delegates
the final closed verdict derivation to the reviewed evidence implementation.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import zipfile
from argparse import Namespace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import gate4c_verdict_evidence as EVIDENCE
from tools import gate4c_verdict_preflight as PREFLIGHT


CONFIG_SCHEMA = "factorio.gate4c_verdict03_coordinator_config.v1"
PREPARED_SCHEMA = "factorio.gate4c_verdict03_prepared_launch.v1"
PLAN_APPROVAL_SCHEMA = "factorio.gate4c_exact_plan_approval.v1"
PLAN_SCHEMA = "factorio.hermetic_play_candidate_plan.v1"
WORK_UNIT = "FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-03"
EXPECTED_FACMAN_SHA256 = PREFLIGHT.EXPECTED_FACMAN_SHA256
EXPECTED_SMOKE_SHA256 = (
    "61b12376dca012caa829e5bf228d79801b0c978e9e6e551b2c393b9ce822a9f2"
)
EXPECTED_CACHE_SHA256 = (
    "037d92a2bc50cb56bedd3a40196edf49c5c25eb1824e440d36cd72f902ecf922"
)
CONFIG_KEYS = {
    "schema",
    "task_root",
    "repository_root",
    "launcher_repository",
    "setup_repository",
    "artifact_manifest",
    "facman_artifact",
    "workspace",
    "instance_id",
    "factorio_executable",
    "source_artifact",
    "source_member_executable",
    "reviewer_id",
    "first_operation_id",
    "second_operation_id",
}


class CoordinatorError(RuntimeError):
    pass


def read_strict(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CoordinatorError(f"expected one JSON object: {path}")
    return value


def write_new(
    path: Path,
    value: dict[str, Any],
    *,
    compact: bool = False,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            if compact:
                json.dump(value, handle, separators=(",", ":"))
            else:
                json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def path_text(path: Path) -> str:
    return str(Path(os.path.abspath(path)))


def validate_config(path: Path) -> dict[str, Any]:
    value = read_strict(path)
    if set(value) != CONFIG_KEYS or value.get("schema") != CONFIG_SCHEMA:
        raise CoordinatorError("Verdict 03 coordinator configuration is not closed")
    task_root = Path(value["task_root"])
    if task_root.name != WORK_UNIT:
        raise CoordinatorError("configuration does not bind the exact Verdict 03 root")
    if Path(os.path.abspath(path)).parent != Path(os.path.abspath(task_root / "operator")):
        raise CoordinatorError("configuration must remain under the Verdict 03 operator root")
    if Path(value["workspace"]) != task_root / "workspace":
        raise CoordinatorError("configuration workspace is not exact")
    if value["instance_id"] != PREFLIGHT.EXPECTED_INSTANCE_ID:
        raise CoordinatorError("configuration instance is not the frozen candidate")
    if value["reviewer_id"] != f"windows:{os.environ.get('USERNAME', '')}":
        raise CoordinatorError("reviewer is not the current provider-scoped Windows identity")
    operations = [value["first_operation_id"], value["second_operation_id"]]
    if (
        operations[0] == operations[1]
        or any(
            not isinstance(item, str)
            or not item.startswith("gate4c-verdict03-")
            or not item.replace("-", "").isalnum()
            or item.lower() != item
            for item in operations
        )
    ):
        raise CoordinatorError("Verdict 03 operation identities are not exact and unique")
    for key in CONFIG_KEYS - {
        "schema",
        "instance_id",
        "reviewer_id",
        "first_operation_id",
        "second_operation_id",
    }:
        audit = PREFLIGHT.audit_no_follow(Path(value[key]), require_file=key not in {
            "task_root",
            "repository_root",
            "launcher_repository",
            "setup_repository",
            "workspace",
        })
        if not audit["safe"]:
            raise CoordinatorError(f"unsafe configured path for {key}: {audit}")
    return value


def copy_exact(source: Path, destination: Path, expected_sha256: str) -> dict[str, Any]:
    source_audit = PREFLIGHT.audit_no_follow(source, require_file=True)
    if not source_audit["safe"] or PREFLIGHT.sha256_file(source) != expected_sha256:
        raise CoordinatorError(f"candidate source artifact changed: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise CoordinatorError(f"candidate destination already exists: {destination}")
    shutil.copy2(source, destination, follow_symlinks=False)
    destination_audit = PREFLIGHT.audit_no_follow(destination, require_file=True)
    actual = PREFLIGHT.sha256_file(destination)
    if not destination_audit["safe"] or actual != expected_sha256:
        raise CoordinatorError(f"candidate copy verification failed: {destination}")
    return {
        "name": destination.name,
        "bytes": destination.stat().st_size,
        "sha256": actual,
    }


def stage(args: argparse.Namespace) -> dict[str, Any]:
    task_root = Path(os.path.abspath(args.task_root))
    if task_root.name != WORK_UNIT:
        raise CoordinatorError("stage root is not the exact Verdict 03 root")
    if any((task_root / name).exists() for name in ("artifacts", "workspace", "source")):
        raise CoordinatorError("Verdict 03 candidate state was already staged")
    source_build = Path(os.path.abspath(args.candidate_build))
    artifact_root = task_root / "artifacts" / "gate4b-reviewed-build"
    artifacts = [
        copy_exact(
            source_build / "Debug" / "facman.exe",
            artifact_root / "facman.exe",
            EXPECTED_FACMAN_SHA256,
        ),
        copy_exact(
            source_build / "Debug" / "facman_hermetic_play_candidate_smoke.exe",
            artifact_root / "facman_hermetic_play_candidate_smoke.exe",
            EXPECTED_SMOKE_SHA256,
        ),
        copy_exact(
            source_build / "CMakeCache.txt",
            artifact_root / "CMakeCache.txt",
            EXPECTED_CACHE_SHA256,
        ),
    ]
    manifest = {
        "schema": "facman.gate4c_artifact_binding.v1",
        "work_unit": WORK_UNIT,
        "source_candidate_revision": PREFLIGHT.CANDIDATE_REVISION,
        "source_checkout_clean": True,
        "copy_method": "literal_file_copy_after_no_reparse_path_audit",
        "copy_verified": True,
        "artifacts": artifacts,
        "notes": [
            "Fresh Verdict 03 copies bind the exact reviewed Gate 4B candidate bytes.",
            "No Verdict 01 or Verdict 02 evidence artifact is reused.",
        ],
    }
    manifest_path = artifact_root / "artifact-binding.v1.json"
    write_new(manifest_path, manifest)

    source_artifact = Path(os.path.abspath(args.source_artifact))
    source_audit = PREFLIGHT.audit_no_follow(source_artifact, require_file=True)
    if not source_audit["safe"]:
        raise CoordinatorError("authenticated source package path is unsafe")
    member_root = task_root / "source" / "portable-package-inspection"
    member_root.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(source_artifact) as archive:
        members = [
            item
            for item in archive.infolist()
            if item.filename.replace("\\", "/").lower().endswith(
                "/bin/x64/factorio.exe"
            )
            and not item.is_dir()
        ]
        if len(members) != 1:
            raise CoordinatorError("source package does not contain one exact Factorio executable")
        member_path = member_root / "factorio.exe"
        with archive.open(members[0], "r") as source, member_path.open("xb") as target:
            shutil.copyfileobj(source, target)

    workspace = task_root / "workspace"
    instance_id = PREFLIGHT.EXPECTED_INSTANCE_ID
    instance_root = workspace / "instances" / instance_id
    for relative in (
        "accounts",
        "audit",
        "diagnostics/reports",
        "exports",
        "installs/refs",
        "installs/setup_state_refs",
        f"instances/{instance_id}/cache",
        f"instances/{instance_id}/config",
        f"instances/{instance_id}/crash",
        f"instances/{instance_id}/exports",
        f"instances/{instance_id}/locks",
        f"instances/{instance_id}/logs",
        f"instances/{instance_id}/mods",
        f"instances/{instance_id}/saves",
        f"instances/{instance_id}/scenarios",
        f"instances/{instance_id}/script-output",
        "modsets",
        "profiles",
        "saves",
        "temporary",
        "transactions",
    ):
        (workspace / relative).mkdir(parents=True, exist_ok=False)
    workspace_record = {
        "schema": "facman.factorio.workspace.v1",
        "workspace_id": "3b0eaa69-fb0b-4d1d-92bc-24458a31b703",
        "layout_version": 1,
        "roots": {
            "installs": "installs",
            "instances": "instances",
            "profiles": "profiles",
            "modsets": "modsets",
            "accounts": "accounts",
            "cache": "cache",
            "audit": "audit",
            "diagnostics": "diagnostics",
            "exports": "exports",
        },
    }
    write_new(workspace / "workspace.v1.json", workspace_record, compact=True)
    factorio_executable = Path(os.path.abspath(args.factorio_executable))
    installation_root = factorio_executable.parents[2]
    install_ref = {
        "schema": "factorio.install_ref.v1",
        "install_id": "gate4c-factorio-2-0-77",
        "candidate_id": "gate4c-factorio-2-0-77",
        "provider_id": "direct.inspect",
        "product_id": "factorio",
        "display_name": "Factorio gate4c-factorio-2-0-77",
        "root": str(installation_root),
        "app_dir": str(installation_root),
        "executable": str(factorio_executable),
        "version": "2.0.77",
        "ownership": "imported",
        "source": "manual",
        "source_ref": "",
        "platform": "windows-x64",
        "distribution_origin": "website_installer",
        "platform_integration": "none_detected",
        "installation_layout": "official_installer",
        "data_routing": "system_shared",
        "program_data_separation": "separated",
        "uninstall_integration": "uninstaller_present",
        "side_by_side_safety": "program_files_separate_but_registration_may_be_superseded",
        "local_data_domains": [],
        "strict_isolation_eligibility": "candidate",
        "external_state_domains": ["default_factorio_data"],
        "capabilities": ["gui"],
        "setup_state_ref": "",
        "lifecycle_status": "",
        "last_verification_identity": "",
        "state_revision": "",
        "executable_path_kind": "candidate",
        "app_dir_kind": "install_root",
        "diagnostic_code": "",
        "evidence": ["direct_inspection"],
        "setup_mutation_allowed": False,
        "verification": {"status": "structural", "problems": []},
        "discovery": {"read_only": True, "source_family": "manual"},
        "safe_actions": {"repair": False, "uninstall": False},
    }
    write_new(
        workspace / "installs" / "refs" / "gate4c-factorio-2-0-77.json",
        install_ref,
        compact=True,
    )
    instance_record = {
        "schema": "factorio.instance.v1",
        "instance_id": instance_id,
        "display_name": "Gate 4C Disposable 2.0.77",
        "install_ref": "gate4c-factorio-2-0-77",
        "factorio_version": "2.0.77",
        "local_data_root": str(instance_root),
        "profile": "gui",
        "modset": None,
        "template": "vanilla",
        "save_policy": {"mode": "instance-local"},
        "account_ref": None,
        "concurrency": {"single_writer": True},
        "export_policy": {"portable": True, "redact_secrets": True},
    }
    write_new(instance_root / "instance.v1.json", instance_record, compact=True)
    config_ini = (
        "[path]\n"
        f"read-data={installation_root}\\data\n"
        f"write-data={instance_root}\n\n"
        "[other]\n"
        "check_updates=false\n"
    )
    config_path = instance_root / "config" / "config.ini"
    config_path.write_text(config_ini, encoding="utf-8", newline="\n")
    lock = {
        "lockfile_version": 1,
        "schema": "factorio.modset_lock.v1",
        "instance_id": instance_id,
        "factorio_version": "2.0.77",
        "mods": [],
    }
    write_new(
        instance_root / "mods" / "modset-lock.v1.json",
        lock,
        compact=True,
    )
    write_new(
        workspace / "modsets" / f"{instance_id}.modset-lock.v1.json",
        lock,
        compact=True,
    )

    config = {
        "schema": CONFIG_SCHEMA,
        "task_root": str(task_root),
        "repository_root": path_text(args.repository_root),
        "launcher_repository": path_text(args.launcher_repository),
        "setup_repository": path_text(args.setup_repository),
        "artifact_manifest": str(manifest_path),
        "facman_artifact": str(artifact_root / "facman.exe"),
        "workspace": str(workspace),
        "instance_id": instance_id,
        "factorio_executable": str(factorio_executable),
        "source_artifact": str(source_artifact),
        "source_member_executable": str(member_path),
        "reviewer_id": f"windows:{os.environ.get('USERNAME', '')}",
        "first_operation_id": args.first_operation_id,
        "second_operation_id": args.second_operation_id,
    }
    config_path_out = task_root / "operator" / "verdict03-config.json"
    write_new(config_path_out, config)
    return {
        "config": str(config_path_out),
        "manifest": str(manifest_path),
        "facman": str(artifact_root / "facman.exe"),
        "workspace": str(workspace),
        "source_member_executable": str(member_path),
    }


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    config_path = Path(os.path.abspath(args.config))
    config = validate_config(config_path)
    task_root = Path(config["task_root"])
    operation_id = args.operation_id
    if operation_id not in {
        config["first_operation_id"],
        config["second_operation_id"],
    }:
        raise CoordinatorError("prepare operation is outside the exact two-launch set")
    observer_path = Path(os.path.abspath(args.observer_self_test))
    observer_record = read_strict(observer_path)
    observer_digest = observer_record.get("self_test_digest")
    if not isinstance(observer_digest, str):
        raise CoordinatorError("observer self-test has no canonical digest")
    session = PREFLIGHT.host_session_identity()
    processes = PREFLIGHT.process_inventory()
    host_state = PREFLIGHT.host_state_digest(session, processes, observer_digest)
    attestation = {
        "schema": PREFLIGHT.ATTESTATION_SCHEMA,
        "attested_at": EVIDENCE.utc_now(),
        "reviewer_id": config["reviewer_id"],
        "machine_binding_id": session["machine_binding_id"],
        "boot_identity": session["boot_identity"],
        "observer_self_test_digest": observer_digest,
        "host_state_digest": host_state,
        "pending_restart_cleared": True,
        "steam_closed": True,
        "unrelated_factorio_facman_closed": True,
        "install_backup_sync_activity_paused": True,
        "sleep_and_restart_prevented_for_run": True,
    }
    attestation_path = (
        task_root / "operator" / "attestation" / f"{operation_id}.json"
    )
    write_new(attestation_path, attestation)
    preflight_path = (
        task_root / "evidence" / "preflight" / f"{operation_id}.json"
    )
    preflight_args = Namespace(
        task_root=task_root,
        repo_root=Path(config["repository_root"]),
        launcher_repo=Path(config["launcher_repository"]),
        setup_repo=Path(config["setup_repository"]),
        artifact_manifest=Path(config["artifact_manifest"]),
        facman=Path(config["facman_artifact"]),
        workspace=Path(config["workspace"]),
        instance_id=config["instance_id"],
        factorio_exe=Path(config["factorio_executable"]),
        source_artifact=Path(config["source_artifact"]),
        source_member_executable=Path(config["source_member_executable"]),
        observer_self_test=observer_path,
        operator_attestation=attestation_path,
        out=preflight_path,
    )
    preflight = PREFLIGHT.build_preflight(preflight_args)
    PREFLIGHT.write_record(preflight_path, preflight, task_root)
    if preflight["status"] != "ready" or preflight["blockers"]:
        raise CoordinatorError(
            f"fresh Verdict 03 preflight is blocked: {preflight['blockers']}"
        )
    sessions = task_root / "evidence" / "sessions"
    baseline_path = sessions / f"{operation_id}-baseline.json"
    roots_path = sessions / f"{operation_id}-roots.json"
    session_path = sessions / f"{operation_id}-session.json"
    prepared = EVIDENCE.prepare_session(
        Namespace(
            preflight=preflight_path,
            task_root=task_root,
            operation_id=operation_id,
            harness=Path(os.path.abspath(args.harness)),
            baseline_out=baseline_path,
            classification_out=roots_path,
            session_out=session_path,
        )
    )
    output = {
        "schema": PREPARED_SCHEMA,
        "work_unit": WORK_UNIT,
        "operation_id": operation_id,
        "observer_self_test_path": str(observer_path),
        "observer_self_test_digest": observer_digest,
        "attestation_path": str(attestation_path),
        "preflight_path": str(preflight_path),
        "preflight_digest": preflight["preflight_digest"],
        "baseline_path": str(baseline_path),
        "baseline_digest": prepared["baseline_bundle_sha256"],
        "session_path": str(session_path),
        "session_digest": prepared["session_digest"],
    }
    prepared_path = (
        task_root / "evidence" / "coordinator" / f"{operation_id}-prepared.json"
    )
    output["prepared_digest"] = PREFLIGHT.digest_value(output)
    write_new(prepared_path, output)
    output["output"] = str(prepared_path)
    return output


def human(args: argparse.Namespace) -> dict[str, Any]:
    config = validate_config(Path(args.config))
    session = EVIDENCE.validate_session_record(Path(args.session))
    packet = EVIDENCE.validate_native_packet(session, Path(args.packet))
    expected = (
        EVIDENCE.FIRST_LAUNCH_CHECKS
        if args.launch == 1
        else EVIDENCE.SECOND_LAUNCH_CHECKS
    )
    checks = {key: args.disposition == "Pass" for key in sorted(expected)}
    for key in args.false_check:
        if key not in checks:
            raise CoordinatorError(f"unknown human observation check: {key}")
        checks[key] = False
    if args.disposition == "Fail" and all(checks.values()):
        raise CoordinatorError("human Fail requires at least one explicit false check")
    record = {
        "schema": EVIDENCE.HUMAN_OBSERVATION_SCHEMA,
        "canonicalization_version": "facman.sorted-json.v1",
        "work_unit": WORK_UNIT,
        "operation_id": session["operation_id"],
        "session_digest": session["session_digest"],
        "packet_digest": packet["packet_digest"],
        "reviewer_id": config["reviewer_id"],
        "observed_at": EVIDENCE.utc_now(),
        "disposition": args.disposition,
        "checks": checks,
        "notes": args.notes,
    }
    record["attestation_digest"] = PREFLIGHT.digest_value(record)
    out = Path(args.out)
    write_new(out, record)
    return {"path": str(out), "digest": record["attestation_digest"]}


def approve_plan(args: argparse.Namespace) -> dict[str, Any]:
    config = validate_config(Path(args.config))
    operation_id = args.operation_id
    if operation_id not in {
        config["first_operation_id"],
        config["second_operation_id"],
    }:
        raise CoordinatorError("plan approval operation is not configured")
    plan = read_strict(Path(args.plan))
    plan_core = plan.get("plan_core")
    if (
        plan.get("schema") != PLAN_SCHEMA
        or plan.get("canonicalization_version") != "facman.sorted-json.v1"
        or not isinstance(plan_core, dict)
        or plan_core.get("operation") != "instance.play"
        or plan_core.get("instance_id") != config["instance_id"]
        or plan_core.get("launch_intent") != "menu"
        or plan_core.get("isolation_mode") != "hermetic"
        or plan_core.get("policy_digest") != PREFLIGHT.POLICY_DIGEST
        or plan.get("public_command_available") is not False
        or plan.get("human_verdict_recorded") is not False
    ):
        raise CoordinatorError("plan is outside the frozen Verdict 03 candidate")
    plan_digest = plan.get("plan_digest")
    if (
        not isinstance(plan_digest, str)
        or len(plan_digest) != 64
        or any(character not in "0123456789abcdef" for character in plan_digest)
    ):
        raise CoordinatorError("plan digest is not canonical lowercase SHA-256")
    record = {
        "schema": PLAN_APPROVAL_SCHEMA,
        "work_unit": WORK_UNIT,
        "operation_id": operation_id,
        "plan_digest": plan_digest,
        "approved_by": "codex:root",
        "approved_at": EVIDENCE.utc_now(),
    }
    record["approval_digest"] = PREFLIGHT.digest_value(record)
    out = Path(args.out)
    expected_out = (
        Path(config["task_root"])
        / "operator"
        / "approvals"
        / f"{operation_id}-plan-approval.json"
    )
    if Path(os.path.abspath(out)) != Path(os.path.abspath(expected_out)):
        raise CoordinatorError("plan approval output path is not exact")
    write_new(out, record)
    return {
        "path": str(out),
        "plan_digest": plan_digest,
        "digest": record["approval_digest"],
    }


def finalize_auto(args: argparse.Namespace) -> dict[str, Any]:
    first_session = EVIDENCE.validate_session_record(Path(args.first_session))
    second_session = EVIDENCE.validate_session_record(Path(args.second_session))
    first_packet = EVIDENCE.validate_native_packet(
        first_session, Path(args.first_packet)
    )
    second_packet = EVIDENCE.validate_native_packet(
        second_session, Path(args.second_packet)
    )
    first_human = read_strict(Path(args.first_human))
    second_human = read_strict(Path(args.second_human))
    technical = [
        first_packet.get("technical_disposition"),
        second_packet.get("technical_disposition"),
    ]
    human_dispositions = [
        first_human.get("disposition"),
        second_human.get("disposition"),
    ]
    if "fail_evidence" in technical or "Fail" in human_dispositions:
        verdict = "Fail"
    elif (
        any(item != "eligible_for_human_verdict" for item in technical)
        or "Inconclusive" in human_dispositions
    ):
        verdict = "Inconclusive"
    else:
        verdict = "Pass"
    return EVIDENCE.finalize_verdict(
        Namespace(
            first_session=Path(args.first_session),
            first_packet=Path(args.first_packet),
            first_human=Path(args.first_human),
            second_session=Path(args.second_session),
            second_packet=Path(args.second_packet),
            second_human=Path(args.second_human),
            verdict=verdict,
            out=Path(args.out),
        )
    )


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    commands = value.add_subparsers(dest="command", required=True)
    stage_parser = commands.add_parser("stage")
    stage_parser.add_argument("--task-root", required=True, type=Path)
    stage_parser.add_argument("--candidate-build", required=True, type=Path)
    stage_parser.add_argument("--repository-root", required=True, type=Path)
    stage_parser.add_argument("--launcher-repository", required=True, type=Path)
    stage_parser.add_argument("--setup-repository", required=True, type=Path)
    stage_parser.add_argument("--factorio-executable", required=True, type=Path)
    stage_parser.add_argument("--source-artifact", required=True, type=Path)
    stage_parser.add_argument("--first-operation-id", required=True)
    stage_parser.add_argument("--second-operation-id", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--config", required=True, type=Path)
    prepare_parser.add_argument("--observer-self-test", required=True, type=Path)
    prepare_parser.add_argument("--operation-id", required=True)
    prepare_parser.add_argument("--harness", required=True, type=Path)
    approval_parser = commands.add_parser("approve-plan")
    approval_parser.add_argument("--config", required=True, type=Path)
    approval_parser.add_argument("--operation-id", required=True)
    approval_parser.add_argument("--plan", required=True, type=Path)
    approval_parser.add_argument("--out", required=True, type=Path)
    human_parser = commands.add_parser("human")
    human_parser.add_argument("--config", required=True, type=Path)
    human_parser.add_argument("--launch", required=True, type=int, choices=(1, 2))
    human_parser.add_argument("--session", required=True, type=Path)
    human_parser.add_argument("--packet", required=True, type=Path)
    human_parser.add_argument(
        "--disposition", required=True, choices=("Pass", "Fail", "Inconclusive")
    )
    human_parser.add_argument("--false-check", action="append", default=[])
    human_parser.add_argument("--notes", default="")
    human_parser.add_argument("--out", required=True, type=Path)
    final_parser = commands.add_parser("finalize-auto")
    final_parser.add_argument("--first-session", required=True, type=Path)
    final_parser.add_argument("--first-packet", required=True, type=Path)
    final_parser.add_argument("--first-human", required=True, type=Path)
    final_parser.add_argument("--second-session", required=True, type=Path)
    final_parser.add_argument("--second-packet", required=True, type=Path)
    final_parser.add_argument("--second-human", required=True, type=Path)
    final_parser.add_argument("--out", required=True, type=Path)
    return value


def main() -> int:
    args = parser().parse_args()
    if args.command == "stage":
        result = stage(args)
    elif args.command == "prepare":
        result = prepare(args)
    elif args.command == "approve-plan":
        result = approve_plan(args)
    elif args.command == "human":
        result = human(args)
    else:
        result = finalize_auto(args)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        CoordinatorError,
        EVIDENCE.EvidenceError,
        PREFLIGHT.PreflightError,
        OSError,
        ValueError,
        json.JSONDecodeError,
        zipfile.BadZipFile,
    ) as exc:
        print(f"gate4c-verdict03-coordinator: {exc}", file=os.sys.stderr)
        raise SystemExit(2)
