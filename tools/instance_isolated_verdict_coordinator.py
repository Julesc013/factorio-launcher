# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Operator-only coordinator for exact instance-isolated Play revalidation.

This module stages only remotely qualified candidate bytes and prepares fresh
evidence sessions.  It records only explicit, interactively confirmed human
checks.  It cannot issue a permit, start Factorio, infer a human observation,
or promote product authority.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from argparse import Namespace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import gate4c_verdict03_coordinator as COMMON
from tools import gate4c_verdict_evidence as EVIDENCE
from tools import gate4c_verdict_preflight as PREFLIGHT
from tools import play_staged_candidate as STAGED
from tools.play_evidence_stable_io import (
    EvidenceIo,
    StableIoError,
    file_payload_sha256,
    file_payload_size,
)
from tools.play_verdict_route import (
    INSTANCE_ISOLATED_REVALIDATION as ROUTE,
    CandidateQualificationBinding,
    RouteBindingError,
    digest_value,
    parse_qualification_binding,
)


CONFIG_SCHEMA = "factorio.instance_isolated_verdict_coordinator_config.v2"
PREPARED_SCHEMA = "factorio.instance_isolated_prepared_launch.v1"
QUALIFICATION_BINDING_FILENAME = "qualification-binding.v4.json"
CONFIG_KEYS = {
    "schema",
    "task_root",
    "repository_root",
    "launcher_repository",
    "setup_repository",
    "qualification_binding",
    "qualification_digest",
    "staged_candidate_binding",
    "staged_candidate_digest",
    "artifact_manifest",
    "facman_artifact",
    "evidence_probe",
    "workspace",
    "instance_id",
    "factorio_executable",
    "source_artifact",
    "source_member_executable",
    "reviewer_principal",
    "first_operation_id",
    "second_operation_id",
}


class CoordinatorError(RuntimeError):
    pass


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(path))


def _binding(
    path: Path,
    evidence_io: EvidenceIo,
) -> CandidateQualificationBinding:
    try:
        result = evidence_io.read_json(path)
        return parse_qualification_binding(
            result["payload"]["document"], ROUTE
        )
    except RouteBindingError as exc:
        raise CoordinatorError(str(exc)) from exc


def _safe_path(path: Path, *, require_file: bool) -> None:
    audit = PREFLIGHT.audit_no_follow(path, require_file=require_file)
    if not audit["safe"]:
        raise CoordinatorError(f"unsafe configured path: {path}: {audit}")


def _validate_operation_ids(first: object, second: object) -> None:
    operations = [first, second]
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


def validate_config(
    path: Path,
) -> tuple[
    dict[str, Any],
    CandidateQualificationBinding,
    dict[str, Any],
]:
    absolute_path = _absolute(path)
    path_bound_task_root = absolute_path.parent.parent
    path_bound_probe = (
        path_bound_task_root
        / "artifacts"
        / "qualified-build"
        / "facman_evidence_probe.exe"
    )
    evidence_io = EvidenceIo(path_bound_probe)
    value = evidence_io.read_json(absolute_path)["payload"]["document"]
    if set(value) != CONFIG_KEYS or value.get("schema") != CONFIG_SCHEMA:
        raise CoordinatorError(
            "instance-isolated coordinator configuration is not closed"
        )
    task_root = _absolute(Path(value["task_root"]))
    if (
        task_root.name != ROUTE.work_unit
        or absolute_path.parent != task_root / "operator"
        or absolute_path.name != "instance-isolated-config.json"
        or _absolute(Path(value["evidence_probe"])) != path_bound_probe
        or _absolute(Path(value["workspace"])) != task_root / "workspace"
        or value["instance_id"] != ROUTE.instance_id
    ):
        raise CoordinatorError(
            "instance-isolated coordinator configuration scope is not exact"
        )
    current_principal = PREFLIGHT.windows_principal_identity()
    if (
        not PREFLIGHT.validate_windows_principal(
            value["reviewer_principal"]
        )
        or value["reviewer_principal"] != current_principal
        or current_principal.get("integrity") != "medium"
    ):
        raise CoordinatorError(
            "configured reviewer principal is not the current exact "
            "medium-integrity Windows token"
        )
    qualification_path = _absolute(Path(value["qualification_binding"]))
    qualification = _binding(qualification_path, evidence_io)
    if value["qualification_digest"] != qualification.qualification_digest:
        raise CoordinatorError("qualification binding digest changed")
    staged_candidate_path = _absolute(
        Path(value["staged_candidate_binding"])
    )
    if (
        staged_candidate_path
        != path_bound_task_root
        / "artifacts"
        / "qualified-build"
        / "staged-candidate-binding.v1.json"
    ):
        raise CoordinatorError(
            "staged candidate binding path is not exact"
        )
    try:
        staged_candidate = STAGED.parse_staged_candidate(
            evidence_io.read_json(staged_candidate_path)[
                "payload"
            ]["document"],
            task_root=task_root,
            qualification=qualification,
            route=ROUTE,
        )
    except STAGED.StagedCandidateError as exc:
        raise CoordinatorError(str(exc)) from exc
    if (
        value["staged_candidate_digest"]
        != staged_candidate["staged_candidate_digest"]
    ):
        raise CoordinatorError("staged candidate binding digest changed")
    probe_binding = qualification.artifact_mapping()["evidence_probe"]
    probe_result = evidence_io.inspect_file(evidence_io.probe)
    if (
        file_payload_sha256(probe_result) != probe_binding.sha256
        or file_payload_size(probe_result) != probe_binding.size
    ):
        raise CoordinatorError(
            "configured evidence probe differs from qualification"
        )
    _validate_operation_ids(
        value["first_operation_id"],
        value["second_operation_id"],
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
        "staged_candidate_digest",
        "instance_id",
        "reviewer_principal",
        "first_operation_id",
        "second_operation_id",
    }
    for key in CONFIG_KEYS - ignored:
        _safe_path(Path(value[key]), require_file=key not in directory_keys)
    return value, qualification, staged_candidate


def _copy_qualified_artifacts(
    source_build: Path,
    destination: Path,
    qualification: CandidateQualificationBinding,
    evidence_io: EvidenceIo,
) -> tuple[list[dict[str, Any]], dict[str, Path]]:
    destination.mkdir(parents=True, exist_ok=False)
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
        evidence_io.copy_file(
            source, target, maximum_bytes=max(artifact.size, 1)
        )
        inspected = evidence_io.inspect_file(target)
        copied = {
            "name": target.name,
            "bytes": file_payload_size(inspected),
            "sha256": file_payload_sha256(inspected),
        }
        if (
            copied["bytes"] != artifact.size
            or copied["sha256"] != artifact.sha256
        ):
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
    evidence_io: EvidenceIo,
) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    basenames: set[str] = set()
    for logical_name, artifact in qualification.artifacts:
        source = source_build / Path(artifact.relative_path)
        name = Path(artifact.relative_path).name
        inspected = evidence_io.inspect_file(source)
        if (
            name in basenames
            or file_payload_size(inspected) != artifact.size
            or file_payload_sha256(inspected) != artifact.sha256
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
    evidence_io: EvidenceIo,
) -> dict[str, Any]:
    factorio = PREFLIGHT.factorio_evidence(
        factorio_executable,
        qualification,
        evidence_io,
    )
    source = PREFLIGHT.source_evidence(
        source_artifact,
        factorio_executable,
        source_member_executable=source_member,
        task_root=task_root,
        evidence_io=evidence_io,
    )
    instance = PREFLIGHT.instance_evidence(
        facman,
        workspace,
        ROUTE.instance_id,
        qualification,
        allow_unbound_runtime_digests=True,
    )
    if (
        not factorio.get("valid")
        or not source.get("valid")
        or not instance.get("valid")
    ):
        raise CoordinatorError(
            "prequalified candidate state differs from its immutable binding"
        )
    return instance


def _extract_authenticated_executable(
    source_artifact: Path,
    destination: Path,
    qualification: CandidateQualificationBinding,
    evidence_io: EvidenceIo,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=False)
    evidence_io.extract_exact_member(
        source_artifact,
        "Factorio_2.0.77/bin/x64/factorio.exe",
        destination,
    )
    if (
        file_payload_sha256(evidence_io.hash_file(destination))
        != qualification.factorio_sha256
    ):
        raise CoordinatorError(
            "authenticated source member differs from qualification"
        )


def _active_install_record(
    factorio_executable: Path,
    factorio_identity: dict[str, str],
) -> dict[str, Any]:
    """Create an active install record only from exact current file evidence."""

    if set(factorio_identity) != {"version", "sha256", "signer"}:
        raise CoordinatorError("Factorio installation identity is not closed")
    executable = _absolute(factorio_executable)
    audit = PREFLIGHT.audit_no_follow(executable, require_file=True)
    stable_identity = PREFLIGHT.stable_identity_digest(audit)
    actual_sha256 = (
        PREFLIGHT.sha256_file(executable) if audit.get("safe") else ""
    )
    if (
        not audit.get("safe")
        or stable_identity is None
        or factorio_identity["version"] != PREFLIGHT.EXPECTED_FACTORIO_VERSION
        or factorio_identity["signer"] != PREFLIGHT.EXPECTED_SIGNER
        or factorio_identity["sha256"] != actual_sha256
    ):
        raise CoordinatorError(
            "Factorio installation identity is not exact and current"
        )

    installation_root = executable.parents[2]
    install_id = "instance-isolated-factorio-2-0-77"
    verification_core = {
        "schema": "facman.instance_isolated_install_verification.v1",
        "install_id": install_id,
        "executable": str(executable),
        "executable_size": int(audit["size"]),
        "executable_sha256": actual_sha256,
        "stable_file_identity": stable_identity,
        "version": factorio_identity["version"],
        "signer": factorio_identity["signer"],
        "method": "no_follow_exact_authenticated_binary",
        "status": "pass",
    }
    verification_identity = digest_value(verification_core)
    record: dict[str, Any] = {
        "schema": "factorio.install_ref.v1",
        "install_id": install_id,
        "candidate_id": install_id,
        "provider_id": "direct.inspect",
        "product_id": "factorio",
        "display_name": "Factorio instance-isolated 2.0.77",
        "root": str(installation_root),
        "app_dir": str(installation_root),
        "executable": str(executable),
        "version": "2.0.77",
        "ownership": "imported",
        "source": "manual",
        "source_ref": f"wube-signed-binary-sha256:{actual_sha256}",
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
        "lifecycle_status": "active",
        "last_verification_identity": verification_identity,
        "executable_path_kind": "candidate",
        "app_dir_kind": "install_root",
        "diagnostic_code": "",
        "evidence": [
            "direct_inspection",
            "no_follow_exact_authenticated_binary",
        ],
        "setup_mutation_allowed": False,
        "verification": {
            **verification_core,
            "identity": verification_identity,
            "problems": [],
        },
        "discovery": {"read_only": True, "source_family": "manual"},
        "safe_actions": {"repair": False, "uninstall": False},
    }
    record["state_revision"] = digest_value(
        {
            "schema": "facman.instance_isolated_install_state.v1",
            "installation": record,
        }
    )
    return record


def _stage_workspace(
    workspace: Path,
    instance_id: str,
    factorio_executable: Path,
    factorio_identity: dict[str, str],
) -> None:
    install_record = _active_install_record(
        factorio_executable,
        factorio_identity,
    )
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
        install_record,
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
    reviewer_principal = PREFLIGHT.windows_principal_identity()
    if (
        not PREFLIGHT.validate_windows_principal(reviewer_principal)
        or reviewer_principal.get("integrity") != "medium"
    ):
        raise CoordinatorError(
            "stage requires an observed medium-integrity Windows principal"
        )
    if (task_root / "artifacts").exists():
        raise CoordinatorError("revalidation artifacts already exist")
    _validate_operation_ids(
        args.first_operation_id,
        args.second_operation_id,
    )
    qualification_source = _absolute(args.qualification_binding)
    source_build = _absolute(args.candidate_build)
    _safe_path(source_build, require_file=False)
    bootstrap_probe = (
        source_build / args.configuration / "facman_evidence_probe.exe"
    )
    evidence_io = EvidenceIo(bootstrap_probe)
    qualification = _binding(qualification_source, evidence_io)
    source_paths = _qualified_source_paths(
        source_build, qualification, evidence_io
    )
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
            source_artifact, source_member, qualification, evidence_io
        )
        _safe_path(factorio_executable, require_file=True)
        if (
            PREFLIGHT.sha256_file(factorio_executable)
            != qualification.factorio_sha256
        ):
            raise CoordinatorError("installed Factorio differs from qualification")
        _stage_workspace(
            workspace,
            ROUTE.instance_id,
            factorio_executable,
            {
                "version": qualification.factorio_version,
                "sha256": qualification.factorio_sha256,
                "signer": qualification.factorio_signer,
            },
        )
    staged_instance = _validate_staged_candidate(
        facman=source_paths["facman"],
        workspace=workspace,
        factorio_executable=factorio_executable,
        source_artifact=source_artifact,
        source_member=source_member,
        task_root=task_root,
        qualification=qualification,
        evidence_io=evidence_io,
    )
    artifact_root = task_root / "artifacts" / "qualified-build"
    artifacts, artifact_paths = _copy_qualified_artifacts(
        source_build, artifact_root, qualification, evidence_io
    )
    staged_io = EvidenceIo(artifact_paths["evidence_probe"])
    binding_copy = task_root / "artifacts" / QUALIFICATION_BINDING_FILENAME
    binding_hash = file_payload_sha256(
        evidence_io.hash_file(qualification_source)
    )
    staged_io.copy_file(
        qualification_source,
        binding_copy,
        maximum_bytes=64 * 1024 * 1024,
    )
    if (
        file_payload_sha256(staged_io.hash_file(binding_copy))
        != binding_hash
    ):
        raise CoordinatorError(
            "staged qualification binding changed during native copy"
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
    staged_io.write_new_json(manifest_path, manifest)
    try:
        staged_candidate = STAGED.build_staged_candidate(
            staged_instance,
            workspace=workspace,
            qualification=qualification,
            route=ROUTE,
        )
    except STAGED.StagedCandidateError as exc:
        raise CoordinatorError(str(exc)) from exc
    staged_candidate_path = (
        artifact_root / "staged-candidate-binding.v1.json"
    )
    staged_io.write_new_json(staged_candidate_path, staged_candidate)
    config = {
        "schema": CONFIG_SCHEMA,
        "task_root": str(task_root),
        "repository_root": str(repository_root),
        "launcher_repository": str(launcher_repository),
        "setup_repository": str(setup_repository),
        "qualification_binding": str(binding_copy),
        "qualification_digest": qualification.qualification_digest,
        "staged_candidate_binding": str(staged_candidate_path),
        "staged_candidate_digest": staged_candidate[
            "staged_candidate_digest"
        ],
        "artifact_manifest": str(manifest_path),
        "facman_artifact": str(artifact_paths["facman"]),
        "evidence_probe": str(artifact_paths["evidence_probe"]),
        "workspace": str(workspace),
        "instance_id": ROUTE.instance_id,
        "factorio_executable": str(factorio_executable),
        "source_artifact": str(source_artifact),
        "source_member_executable": str(source_member),
        "reviewer_principal": reviewer_principal,
        "first_operation_id": args.first_operation_id,
        "second_operation_id": args.second_operation_id,
    }
    config_path = task_root / "operator" / "instance-isolated-config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    staged_io.write_new_json(config_path, config)
    return {
        "config": str(config_path),
        "qualification_digest": qualification.qualification_digest,
        "staged_candidate_binding": str(staged_candidate_path),
        "staged_candidate_digest": staged_candidate[
            "staged_candidate_digest"
        ],
        "manifest": str(manifest_path),
        "facman": str(artifact_paths["facman"]),
        "harness": str(artifact_paths["verdict_harness"]),
        "evidence_probe": str(artifact_paths["evidence_probe"]),
        "workspace": str(workspace),
        "source_member_executable": str(source_member),
    }


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    config_path = _absolute(args.config)
    config, qualification, staged_candidate = validate_config(config_path)
    task_root = Path(config["task_root"])
    evidence_io = EvidenceIo(Path(config["evidence_probe"]))
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
    current_principal = PREFLIGHT.windows_principal_identity()
    if current_principal != config["reviewer_principal"]:
        raise CoordinatorError(
            "reviewer principal changed after candidate staging"
        )
    pending_restart = PREFLIGHT.pending_restart_observation()
    operator_claims = _named_booleans(
        args.operator_attestation,
        expected=PREFLIGHT.INSTANCE_OPERATOR_CLAIMS,
        context="operator attestation",
    )
    if not all(operator_claims.values()):
        raise CoordinatorError(
            "every explicit operator attestation must be true before "
            "preflight preparation"
        )
    attestation = PREFLIGHT.build_instance_operator_attestation(
        attested_at=EVIDENCE.utc_now(),
        reviewer_principal=current_principal,
        machine_binding_id=session["machine_binding_id"],
        boot_identity=session["boot_identity"],
        observer_self_test_digest=observer_digest,
        host_state_digest_value=host_state,
        processes=processes,
        pending_restart=pending_restart,
        operator_claims=operator_claims,
    )
    attestation_path = (
        task_root / "operator" / "attestation" / f"{operation_id}.json"
    )
    attestation_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_io.write_new_json(attestation_path, attestation)
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
        evidence_probe=Path(config["evidence_probe"]),
        operation_id=operation_id,
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
        staged_candidate=staged_candidate,
    )
    PREFLIGHT.write_record(
        preflight_path, preflight, task_root, evidence_io
    )
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
            evidence_probe=Path(config["evidence_probe"]),
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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_io.write_new_json(output_path, output)
    output["output"] = str(output_path)
    return output


def _split_named_values(
    raw: list[str],
    *,
    expected: set[str] | frozenset[str],
    context: str,
    allow_empty: bool = False,
) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in raw:
        name, separator, value = item.partition("=")
        if (
            not separator
            or name not in expected
            or name in values
            or (not allow_empty and not value)
        ):
            raise CoordinatorError(
                f"{context} must provide each exact name once"
            )
        values[name] = value
    if set(values) != set(expected):
        missing = sorted(set(expected) - set(values))
        raise CoordinatorError(
            f"{context} is incomplete; missing: {', '.join(missing)}"
        )
    return values


def _named_booleans(
    raw: list[str],
    *,
    expected: set[str] | frozenset[str],
    context: str,
) -> dict[str, bool]:
    values = _split_named_values(
        raw, expected=expected, context=context
    )
    if any(value not in {"true", "false"} for value in values.values()):
        raise CoordinatorError(
            f"{context} values must be exactly true or false"
        )
    return {name: value == "true" for name, value in values.items()}


def _derive_human_disposition(
    checks: dict[str, bool | None],
) -> str:
    if any(value is False for value in checks.values()):
        return "Fail"
    if any(value is None for value in checks.values()):
        return "Inconclusive"
    return "Pass"


def human(
    args: argparse.Namespace,
    *,
    input_fn: Any = input,
    output_fn: Any = print,
) -> dict[str, Any]:
    config, _, _ = validate_config(args.config)
    session = EVIDENCE.validate_session_record(args.session, ROUTE)
    packet = EVIDENCE.validate_native_packet(session, args.packet, ROUTE)
    expected = (
        EVIDENCE.FIRST_LAUNCH_CHECKS
        if args.launch == 1
        else EVIDENCE.SECOND_LAUNCH_CHECKS
    )
    expected_operation = (
        config["first_operation_id"]
        if args.launch == 1
        else config["second_operation_id"]
    )
    if session["operation_id"] != expected_operation:
        raise CoordinatorError(
            "human observation launch sequence and operation do not match"
        )
    raw_checks = _split_named_values(
        args.check,
        expected=expected,
        context="human observation checks",
    )
    if any(
        value not in {"true", "false", "unknown"}
        for value in raw_checks.values()
    ):
        raise CoordinatorError(
            "human checks must be exactly true, false, or unknown"
        )
    checks: dict[str, bool | None] = {
        name: (
            True
            if value == "true"
            else False if value == "false" else None
        )
        for name, value in raw_checks.items()
    }
    raw_notes = _split_named_values(
        args.check_note,
        expected=expected,
        context="human observation check notes",
        allow_empty=True,
    )
    for name, value in checks.items():
        if value is not True and not raw_notes[name].strip():
            raise CoordinatorError(
                f"human check {name} requires a false/unknown note"
            )
    disposition = _derive_human_disposition(checks)
    record = {
        "schema": ROUTE.human_observation_schema,
        "canonicalization_version": "facman.sorted-json.v1",
        "work_unit": ROUTE.work_unit,
        "operation_id": session["operation_id"],
        "launch_sequence": args.launch,
        "session_digest": session["session_digest"],
        "packet_digest": packet["packet_digest"],
        "reviewer_principal": config["reviewer_principal"],
        "observed_at": EVIDENCE.utc_now(),
        "disposition": disposition,
        "checks": dict(sorted(checks.items())),
        "check_notes": dict(sorted(raw_notes.items())),
        "notes": args.notes,
    }
    record["attestation_digest"] = PREFLIGHT.digest_value(record)
    expected_out = (
        Path(config["task_root"])
        / "evidence"
        / "human"
        / f"{session['operation_id']}-launch-{args.launch}.json"
    )
    if _absolute(args.out) != _absolute(expected_out):
        raise CoordinatorError(
            "human observation output path is not operation/launch exact"
        )
    output_fn(
        f"Human observation for {session['operation_id']} launch "
        f"{args.launch}:"
    )
    for name in sorted(checks):
        state = (
            "unknown" if checks[name] is None else str(checks[name]).lower()
        )
        output_fn(f"  {name}={state} note={raw_notes[name]}")
    phrase = (
        "RECORD HUMAN OBSERVATION "
        f"{session['operation_id']} LAUNCH {args.launch} "
        f"{record['attestation_digest']}"
    )
    output_fn(f"Type exactly:\n{phrase}")
    if input_fn("> ") != phrase:
        raise CoordinatorError(
            "human observation confirmation did not match"
        )
    evidence_io = EvidenceIo(Path(config["evidence_probe"]))
    expected_out.parent.mkdir(parents=True, exist_ok=True)
    evidence_io.write_new_json(expected_out, record)
    return {
        "path": str(expected_out),
        "digest": record["attestation_digest"],
        "disposition": disposition,
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
    first_human = EVIDENCE.validate_human_observation(
        args.first_human,
        operation_id=first_session["operation_id"],
        session_digest=first_session["session_digest"],
        packet_digest=first_packet["packet_digest"],
        expected_checks=EVIDENCE.FIRST_LAUNCH_CHECKS,
        route=ROUTE,
        launch_sequence=1,
        task_root=Path(first_session["task_root"]),
    )
    second_human = EVIDENCE.validate_human_observation(
        args.second_human,
        operation_id=second_session["operation_id"],
        session_digest=second_session["session_digest"],
        packet_digest=second_packet["packet_digest"],
        expected_checks=EVIDENCE.SECOND_LAUNCH_CHECKS,
        route=ROUTE,
        launch_sequence=2,
        task_root=Path(second_session["task_root"]),
    )
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
    stage_parser.add_argument("--configuration", default="Debug")
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
    prepare_parser.add_argument(
        "--operator-attestation", action="append", default=[]
    )
    human_parser = commands.add_parser("human")
    human_parser.add_argument("--config", required=True, type=Path)
    human_parser.add_argument(
        "--launch", required=True, type=int, choices=(1, 2)
    )
    human_parser.add_argument("--session", required=True, type=Path)
    human_parser.add_argument("--packet", required=True, type=Path)
    human_parser.add_argument("--check", action="append", default=[])
    human_parser.add_argument(
        "--check-note", action="append", default=[]
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
        StableIoError,
    ) as exc:
        print(f"instance-isolated-verdict-coordinator: {exc}", file=sys.stderr)
        raise SystemExit(2)
