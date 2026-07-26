# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Operator-only coordinator for exact instance-isolated Play revalidation.

This module stages only remotely qualified candidate bytes and prepares fresh
evidence sessions.  It cannot issue a permit, start Factorio, record an
observation on behalf of a person, or promote product authority.
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

from tools import gate4c_verdict03_coordinator as COMMON
from tools import gate4c_verdict_evidence as EVIDENCE
from tools import gate4c_verdict_preflight as PREFLIGHT
from tools.play_verdict_route import (
    INSTANCE_ISOLATED_REVALIDATION as ROUTE,
    CandidateQualificationBinding,
    RouteBindingError,
    load_qualification_binding,
)


CONFIG_SCHEMA = "factorio.instance_isolated_verdict_coordinator_config.v1"
PREPARED_SCHEMA = "factorio.instance_isolated_prepared_launch.v1"
PLAN_APPROVAL_SCHEMA = "factorio.instance_isolated_exact_plan_approval.v1"
CONFIG_KEYS = {
    "schema",
    "task_root",
    "repository_root",
    "launcher_repository",
    "setup_repository",
    "qualification_binding",
    "qualification_digest",
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


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(path))


def _binding(path: Path) -> CandidateQualificationBinding:
    try:
        return load_qualification_binding(path, ROUTE)
    except RouteBindingError as exc:
        raise CoordinatorError(str(exc)) from exc


def _safe_path(path: Path, *, require_file: bool) -> None:
    audit = PREFLIGHT.audit_no_follow(path, require_file=require_file)
    if not audit["safe"]:
        raise CoordinatorError(f"unsafe configured path: {path}: {audit}")


def validate_config(
    path: Path,
) -> tuple[dict[str, Any], CandidateQualificationBinding]:
    value = COMMON.read_strict(path)
    if set(value) != CONFIG_KEYS or value.get("schema") != CONFIG_SCHEMA:
        raise CoordinatorError(
            "instance-isolated coordinator configuration is not closed"
        )
    task_root = _absolute(Path(value["task_root"]))
    if (
        task_root.name != ROUTE.work_unit
        or _absolute(path).parent != task_root / "operator"
        or _absolute(Path(value["workspace"])) != task_root / "workspace"
        or value["instance_id"] != ROUTE.instance_id
        or value["reviewer_id"]
        != f"windows:{os.environ.get('USERNAME', '')}"
    ):
        raise CoordinatorError(
            "instance-isolated coordinator configuration scope is not exact"
        )
    qualification_path = _absolute(Path(value["qualification_binding"]))
    qualification = _binding(qualification_path)
    if value["qualification_digest"] != qualification.qualification_digest:
        raise CoordinatorError("qualification binding digest changed")
    operations = [
        value["first_operation_id"],
        value["second_operation_id"],
    ]
    if (
        operations[0] == operations[1]
        or any(
            not isinstance(item, str)
            or not item.startswith(ROUTE.operation_prefix)
            or not item.replace("-", "").isalnum()
            or item.lower() != item
            for item in operations
        )
    ):
        raise CoordinatorError(
            "instance-isolated operation identities are not exact and unique"
        )
    directory_keys = {
        "task_root",
        "repository_root",
        "launcher_repository",
        "setup_repository",
        "workspace",
    }
    ignored = {
        "schema",
        "qualification_digest",
        "instance_id",
        "reviewer_id",
        "first_operation_id",
        "second_operation_id",
    }
    for key in CONFIG_KEYS - ignored:
        _safe_path(Path(value[key]), require_file=key not in directory_keys)
    return value, qualification


def _copy_qualified_artifacts(
    source_build: Path,
    destination: Path,
    qualification: CandidateQualificationBinding,
) -> tuple[list[dict[str, Any]], dict[str, Path]]:
    records: list[dict[str, Any]] = []
    paths: dict[str, Path] = {}
    names: set[str] = set()
    for logical_name, artifact in qualification.artifacts:
        source = source_build / Path(artifact.relative_path)
        name = Path(artifact.relative_path).name
        if name in names:
            raise CoordinatorError("qualified artifact basenames collide")
        names.add(name)
        target = destination / name
        copied = COMMON.copy_exact(source, target, artifact.sha256)
        if copied["bytes"] != artifact.size:
            raise CoordinatorError(
                f"qualified artifact size changed: {logical_name}"
            )
        copied["logical_name"] = logical_name
        records.append(copied)
        paths[logical_name] = target
    return records, paths


def _qualified_source_paths(
    source_build: Path,
    qualification: CandidateQualificationBinding,
) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    basenames: set[str] = set()
    for logical_name, artifact in qualification.artifacts:
        source = source_build / Path(artifact.relative_path)
        name = Path(artifact.relative_path).name
        audit = PREFLIGHT.audit_no_follow(source, require_file=True)
        if (
            name in basenames
            or not audit["safe"]
            or source.stat().st_size != artifact.size
            or PREFLIGHT.sha256_file(source) != artifact.sha256
        ):
            raise CoordinatorError(
                f"qualified candidate source changed: {logical_name}"
            )
        basenames.add(name)
        paths[logical_name] = source
    return paths


def _exact_repository_inputs(
    repository_root: Path,
    launcher_repository: Path,
    setup_repository: Path,
    qualification: CandidateQualificationBinding,
) -> None:
    checks = (
        (
            "FacMan",
            repository_root,
            qualification.factorio_launcher,
        ),
        (
            "Universal Launcher",
            launcher_repository,
            qualification.universal_launcher,
        ),
        (
            "Universal Setup",
            setup_repository,
            qualification.universal_setup,
        ),
    )
    for name, path, binding in checks:
        identity = PREFLIGHT.git_identity(
            path,
            binding.revision,
            required_ref=binding.required_ref,
        )
        if not identity.get("valid"):
            raise CoordinatorError(
                f"{name} checkout differs from qualification: {identity}"
            )


def _validate_staged_candidate(
    *,
    facman: Path,
    workspace: Path,
    factorio_executable: Path,
    source_artifact: Path,
    source_member: Path,
    task_root: Path,
    qualification: CandidateQualificationBinding,
) -> None:
    factorio = PREFLIGHT.factorio_evidence(
        factorio_executable,
        qualification,
    )
    source = PREFLIGHT.source_evidence(
        source_artifact,
        factorio_executable,
        source_member_executable=source_member,
        task_root=task_root,
    )
    instance = PREFLIGHT.instance_evidence(
        facman,
        workspace,
        ROUTE.instance_id,
        qualification,
    )
    if (
        not factorio.get("valid")
        or not source.get("valid")
        or not instance.get("valid")
    ):
        raise CoordinatorError(
            "prequalified candidate state differs from its immutable binding"
        )


def _extract_authenticated_executable(
    source_artifact: Path,
    destination: Path,
    qualification: CandidateQualificationBinding,
) -> None:
    _safe_path(source_artifact, require_file=True)
    destination.parent.mkdir(parents=True, exist_ok=False)
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
            raise CoordinatorError(
                "source package does not contain one exact Factorio executable"
            )
        with archive.open(members[0], "r") as source, destination.open(
            "xb"
        ) as target:
            shutil.copyfileobj(source, target)
    if PREFLIGHT.sha256_file(destination) != qualification.factorio_sha256:
        raise CoordinatorError(
            "authenticated source member differs from qualification"
        )


def _stage_workspace(
    workspace: Path,
    instance_id: str,
    factorio_executable: Path,
) -> None:
    instance_root = workspace / "instances" / instance_id
    for relative in (
        "accounts",
        "audit",
        "cache",
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
        f"instances/{instance_id}/state/userprofile",
        "modsets",
        "operations",
        "profiles",
        "saves",
        "temporary",
        "transactions",
    ):
        (workspace / relative).mkdir(parents=True, exist_ok=False)
    COMMON.write_new(
        workspace / "workspace.v1.json",
        {
            "schema": "facman.factorio.workspace.v1",
            "workspace_id": "31242429-b2f0-47a3-9dc9-c58239f66976",
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
        },
        compact=True,
    )
    installation_root = factorio_executable.parents[2]
    install_id = "instance-isolated-factorio-2-0-77"
    COMMON.write_new(
        workspace / "installs" / "refs" / f"{install_id}.json",
        {
            "schema": "factorio.install_ref.v1",
            "install_id": install_id,
            "candidate_id": install_id,
            "provider_id": "direct.inspect",
            "product_id": "factorio",
            "display_name": "Factorio instance-isolated 2.0.77",
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
            "side_by_side_safety": (
                "program_files_separate_but_registration_may_be_superseded"
            ),
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
        },
        compact=True,
    )
    COMMON.write_new(
        instance_root / "instance.v1.json",
        {
            "schema": "factorio.instance.v1",
            "instance_id": instance_id,
            "display_name": "Instance-Isolated Disposable 2.0.77",
            "install_ref": install_id,
            "factorio_version": "2.0.77",
            "local_data_root": str(instance_root),
            "profile": "gui",
            "modset": None,
            "template": "vanilla",
            "save_policy": {"mode": "instance-local"},
            "account_ref": None,
            "concurrency": {"single_writer": True},
            "export_policy": {"portable": True, "redact_secrets": True},
        },
        compact=True,
    )
    config = (
        "[path]\n"
        f"read-data={installation_root}\\data\n"
        f"write-data={instance_root}\n\n"
        "[other]\n"
        "check_updates=false\n"
    )
    (instance_root / "config" / "config.ini").write_text(
        config, encoding="utf-8", newline="\n"
    )
    lock = {
        "lockfile_version": 1,
        "schema": "factorio.modset_lock.v1",
        "instance_id": instance_id,
        "factorio_version": "2.0.77",
        "mods": [],
    }
    COMMON.write_new(
        instance_root / "mods" / "modset-lock.v1.json",
        lock,
        compact=True,
    )
    COMMON.write_new(
        workspace / "modsets" / f"{instance_id}.modset-lock.v1.json",
        lock,
        compact=True,
    )


def stage(args: argparse.Namespace) -> dict[str, Any]:
    task_root = _absolute(args.task_root)
    if task_root.name != ROUTE.work_unit:
        raise CoordinatorError("stage root is not the exact revalidation root")
    _safe_path(task_root, require_file=False)
    if (task_root / "artifacts").exists():
        raise CoordinatorError("revalidation artifacts already exist")
    qualification_source = _absolute(args.qualification_binding)
    qualification = _binding(qualification_source)
    source_build = _absolute(args.candidate_build)
    _safe_path(source_build, require_file=False)
    source_paths = _qualified_source_paths(source_build, qualification)
    repository_root = _absolute(args.repository_root)
    launcher_repository = _absolute(args.launcher_repository)
    setup_repository = _absolute(args.setup_repository)
    _exact_repository_inputs(
        repository_root,
        launcher_repository,
        setup_repository,
        qualification,
    )
    source_artifact = _absolute(args.source_artifact)
    factorio_executable = _absolute(args.factorio_executable)
    source_member = (
        task_root / "source" / "portable-package-inspection" / "factorio.exe"
    )
    workspace = task_root / "workspace"
    prequalified = workspace.exists() or source_member.exists()
    if prequalified and not (workspace.is_dir() and source_member.is_file()):
        raise CoordinatorError(
            "prequalified candidate state is partial or malformed"
        )
    if not prequalified:
        _extract_authenticated_executable(
            source_artifact, source_member, qualification
        )
        _safe_path(factorio_executable, require_file=True)
        if (
            PREFLIGHT.sha256_file(factorio_executable)
            != qualification.factorio_sha256
        ):
            raise CoordinatorError("installed Factorio differs from qualification")
        _stage_workspace(workspace, ROUTE.instance_id, factorio_executable)
    _validate_staged_candidate(
        facman=source_paths["facman"],
        workspace=workspace,
        factorio_executable=factorio_executable,
        source_artifact=source_artifact,
        source_member=source_member,
        task_root=task_root,
        qualification=qualification,
    )
    artifact_root = task_root / "artifacts" / "qualified-build"
    artifacts, artifact_paths = _copy_qualified_artifacts(
        source_build, artifact_root, qualification
    )
    binding_copy = task_root / "artifacts" / "qualification-binding.v1.json"
    COMMON.copy_exact(
        qualification_source,
        binding_copy,
        PREFLIGHT.sha256_file(qualification_source),
    )
    manifest = {
        "schema": "facman.gate4c_artifact_binding.v1",
        "work_unit": ROUTE.work_unit,
        "source_candidate_revision": qualification.factorio_launcher.revision,
        "qualification_digest": qualification.qualification_digest,
        "source_checkout_clean": True,
        "copy_method": "literal_file_copy_after_no_reparse_path_audit",
        "copy_verified": True,
        "artifacts": artifacts,
        "notes": [
            "Only exact bytes from the remote-only qualification are staged.",
            "No historical verdict packet or observer artifact is reused.",
        ],
    }
    manifest_path = artifact_root / "artifact-binding.v1.json"
    COMMON.write_new(manifest_path, manifest)
    config = {
        "schema": CONFIG_SCHEMA,
        "task_root": str(task_root),
        "repository_root": str(repository_root),
        "launcher_repository": str(launcher_repository),
        "setup_repository": str(setup_repository),
        "qualification_binding": str(binding_copy),
        "qualification_digest": qualification.qualification_digest,
        "artifact_manifest": str(manifest_path),
        "facman_artifact": str(artifact_paths["facman"]),
        "workspace": str(workspace),
        "instance_id": ROUTE.instance_id,
        "factorio_executable": str(factorio_executable),
        "source_artifact": str(source_artifact),
        "source_member_executable": str(source_member),
        "reviewer_id": f"windows:{os.environ.get('USERNAME', '')}",
        "first_operation_id": args.first_operation_id,
        "second_operation_id": args.second_operation_id,
    }
    config_path = task_root / "operator" / "instance-isolated-config.json"
    COMMON.write_new(config_path, config)
    return {
        "config": str(config_path),
        "qualification_digest": qualification.qualification_digest,
        "manifest": str(manifest_path),
        "facman": str(artifact_paths["facman"]),
        "harness": str(artifact_paths["verdict_harness"]),
        "workspace": str(workspace),
        "source_member_executable": str(source_member),
    }


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    config_path = _absolute(args.config)
    config, qualification = validate_config(config_path)
    task_root = Path(config["task_root"])
    operation_id = args.operation_id
    if operation_id not in {
        config["first_operation_id"],
        config["second_operation_id"],
    }:
        raise CoordinatorError("operation is outside the exact two-launch set")
    harness = _absolute(args.harness)
    harness_binding = qualification.artifact_mapping()["verdict_harness"]
    if (
        PREFLIGHT.sha256_file(harness) != harness_binding.sha256
        or harness.stat().st_size != harness_binding.size
    ):
        raise CoordinatorError("verdict harness differs from qualification")
    observer_path = _absolute(args.observer_self_test)
    observer_record = COMMON.read_strict(observer_path)
    observer_digest = observer_record.get("self_test_digest")
    if not isinstance(observer_digest, str):
        raise CoordinatorError("observer self-test has no canonical digest")
    session = PREFLIGHT.host_session_identity()
    processes = PREFLIGHT.process_inventory()
    host_state = PREFLIGHT.host_state_digest(
        session, processes, observer_digest
    )
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
    COMMON.write_new(attestation_path, attestation)
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
    preflight = PREFLIGHT.build_preflight(
        preflight_args,
        route=ROUTE,
        qualification=qualification,
    )
    PREFLIGHT.write_record(preflight_path, preflight, task_root)
    if preflight["status"] != "ready" or preflight["blockers"]:
        raise CoordinatorError(
            f"fresh revalidation preflight is blocked: {preflight['blockers']}"
        )
    sessions = task_root / "evidence" / "sessions"
    prepared = EVIDENCE.prepare_session(
        Namespace(
            preflight=preflight_path,
            task_root=task_root,
            operation_id=operation_id,
            harness=harness,
            baseline_out=sessions / f"{operation_id}-baseline.json",
            classification_out=sessions / f"{operation_id}-roots.json",
            session_out=sessions / f"{operation_id}-session.json",
        ),
        route=ROUTE,
    )
    output = {
        "schema": PREPARED_SCHEMA,
        "work_unit": ROUTE.work_unit,
        "operation_id": operation_id,
        "qualification_digest": qualification.qualification_digest,
        "observer_self_test_path": str(observer_path),
        "observer_self_test_digest": observer_digest,
        "attestation_path": str(attestation_path),
        "preflight_path": str(preflight_path),
        "preflight_digest": preflight["preflight_digest"],
        "baseline_digest": prepared["baseline_bundle_sha256"],
        "session_path": str(
            sessions / f"{operation_id}-session.json"
        ),
        "session_digest": prepared["session_digest"],
    }
    output["prepared_digest"] = PREFLIGHT.digest_value(output)
    output_path = (
        task_root
        / "evidence"
        / "coordinator"
        / f"{operation_id}-prepared.json"
    )
    COMMON.write_new(output_path, output)
    output["output"] = str(output_path)
    return output


def approve_plan(args: argparse.Namespace) -> dict[str, Any]:
    config, _ = validate_config(args.config)
    if args.operation_id not in {
        config["first_operation_id"],
        config["second_operation_id"],
    }:
        raise CoordinatorError("plan approval operation is not configured")
    plan = COMMON.read_strict(args.plan)
    core = plan.get("plan_core")
    if (
        plan.get("schema") != ROUTE.plan_schema
        or plan.get("canonicalization_version") != "facman.sorted-json.v1"
        or not isinstance(core, dict)
        or core.get("operation") != "instance.play"
        or core.get("instance_id") != ROUTE.instance_id
        or core.get("launch_intent") != "menu"
        or core.get("isolation_mode") != ROUTE.isolation_mode
        or core.get("policy_digest") != ROUTE.policy_digest
        or plan.get("public_command_available") is not False
        or plan.get("human_verdict_recorded") is not False
    ):
        raise CoordinatorError(
            "plan is outside the frozen instance-isolated candidate"
        )
    plan_digest = plan.get("plan_digest")
    if (
        not isinstance(plan_digest, str)
        or len(plan_digest) != 64
        or any(character not in "0123456789abcdef" for character in plan_digest)
    ):
        raise CoordinatorError("plan digest is not lowercase SHA-256")
    record = {
        "schema": PLAN_APPROVAL_SCHEMA,
        "work_unit": ROUTE.work_unit,
        "operation_id": args.operation_id,
        "plan_digest": plan_digest,
        "approved_by": config["reviewer_id"],
        "approved_at": EVIDENCE.utc_now(),
        "permit_issued": False,
        "process_started": False,
    }
    record["approval_digest"] = PREFLIGHT.digest_value(record)
    expected = (
        Path(config["task_root"])
        / "operator"
        / "approvals"
        / f"{args.operation_id}-plan-approval.json"
    )
    if _absolute(args.out) != _absolute(expected):
        raise CoordinatorError("plan approval output path is not exact")
    COMMON.write_new(args.out, record)
    return {
        "path": str(args.out),
        "plan_digest": plan_digest,
        "digest": record["approval_digest"],
    }


def human(args: argparse.Namespace) -> dict[str, Any]:
    config, _ = validate_config(args.config)
    session = EVIDENCE.validate_session_record(args.session, ROUTE)
    packet = EVIDENCE.validate_native_packet(session, args.packet, ROUTE)
    expected = (
        EVIDENCE.FIRST_LAUNCH_CHECKS
        if args.launch == 1
        else EVIDENCE.SECOND_LAUNCH_CHECKS
    )
    if args.disposition == "Inconclusive":
        checks: dict[str, bool | None] = {
            key: None for key in sorted(expected)
        }
    else:
        checks = {
            key: args.disposition == "Pass" for key in sorted(expected)
        }
    for key in args.false_check:
        if key not in checks:
            raise CoordinatorError(f"unknown human observation check: {key}")
        checks[key] = False
    record = {
        "schema": EVIDENCE.HUMAN_OBSERVATION_SCHEMA,
        "canonicalization_version": "facman.sorted-json.v1",
        "work_unit": ROUTE.work_unit,
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
    COMMON.write_new(args.out, record)
    return {
        "path": str(args.out),
        "digest": record["attestation_digest"],
    }


def finalize_auto(args: argparse.Namespace) -> dict[str, Any]:
    first_session = EVIDENCE.validate_session_record(
        args.first_session, ROUTE
    )
    second_session = EVIDENCE.validate_session_record(
        args.second_session, ROUTE
    )
    first_packet = EVIDENCE.validate_native_packet(
        first_session, args.first_packet, ROUTE
    )
    second_packet = EVIDENCE.validate_native_packet(
        second_session, args.second_packet, ROUTE
    )
    first_human = COMMON.read_strict(args.first_human)
    second_human = COMMON.read_strict(args.second_human)
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
        any(
            item != "eligible_for_human_verdict"
            for item in technical
        )
        or "Inconclusive" in human_dispositions
    ):
        verdict = "Inconclusive"
    else:
        verdict = "Pass"
    return EVIDENCE.finalize_verdict(
        Namespace(
            first_session=args.first_session,
            first_packet=args.first_packet,
            first_human=args.first_human,
            second_session=args.second_session,
            second_packet=args.second_packet,
            second_human=args.second_human,
            verdict=verdict,
            out=args.out,
        ),
        route=ROUTE,
    )


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    commands = value.add_subparsers(dest="command", required=True)
    stage_parser = commands.add_parser("stage")
    stage_parser.add_argument("--task-root", required=True, type=Path)
    stage_parser.add_argument("--candidate-build", required=True, type=Path)
    stage_parser.add_argument(
        "--qualification-binding", required=True, type=Path
    )
    stage_parser.add_argument("--repository-root", required=True, type=Path)
    stage_parser.add_argument(
        "--launcher-repository", required=True, type=Path
    )
    stage_parser.add_argument("--setup-repository", required=True, type=Path)
    stage_parser.add_argument(
        "--factorio-executable", required=True, type=Path
    )
    stage_parser.add_argument("--source-artifact", required=True, type=Path)
    stage_parser.add_argument("--first-operation-id", required=True)
    stage_parser.add_argument("--second-operation-id", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--config", required=True, type=Path)
    prepare_parser.add_argument(
        "--observer-self-test", required=True, type=Path
    )
    prepare_parser.add_argument("--operation-id", required=True)
    prepare_parser.add_argument("--harness", required=True, type=Path)
    approval_parser = commands.add_parser("approve-plan")
    approval_parser.add_argument("--config", required=True, type=Path)
    approval_parser.add_argument("--operation-id", required=True)
    approval_parser.add_argument("--plan", required=True, type=Path)
    approval_parser.add_argument("--out", required=True, type=Path)
    human_parser = commands.add_parser("human")
    human_parser.add_argument("--config", required=True, type=Path)
    human_parser.add_argument(
        "--launch", required=True, type=int, choices=(1, 2)
    )
    human_parser.add_argument("--session", required=True, type=Path)
    human_parser.add_argument("--packet", required=True, type=Path)
    human_parser.add_argument(
        "--disposition",
        required=True,
        choices=("Pass", "Fail", "Inconclusive"),
    )
    human_parser.add_argument(
        "--false-check", action="append", default=[]
    )
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
        OSError,
        ValueError,
        json.JSONDecodeError,
        zipfile.BadZipFile,
    ) as exc:
        print(f"instance-isolated-verdict-coordinator: {exc}", file=sys.stderr)
        raise SystemExit(2)
