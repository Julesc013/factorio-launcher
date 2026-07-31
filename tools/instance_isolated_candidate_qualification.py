# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Produce the immutable instance-isolated candidate qualification binding.

The producer consumes a successful remote-only three-repository closure,
exact build outputs, and an authenticated Factorio 2.0.77 source. It stages
the disposable Instance once so file-object-bound Instance identities can be
derived without a bootstrap binding. It cannot issue a permit, start Factorio,
capture observer evidence, record a human verdict, or promote authority.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import gate4c_verdict03_coordinator as COMMON
from tools import gate4c_verdict_preflight as PREFLIGHT
from tools import instance_isolated_verdict_coordinator as COORDINATOR
from tools import json_contract
from tools.play_evidence_stable_io import (
    EvidenceIo,
    StableIoError,
    file_payload_sha256,
    file_payload_size,
)
from tools.play_verdict_route import (
    CANONICALIZATION,
    INSTANCE_ISOLATED_REVALIDATION as ROUTE,
    QUALIFICATION_SCHEMA,
    digest_value,
    parse_qualification_binding,
)


REPORT_SCHEMA = "facman.instance_isolated_candidate_qualification.v4"
QUALIFICATION_WORK_UNIT = (
    "FACMAN-WINDOWS-INSTANCE-ISOLATED-CANDIDATE-QUALIFICATION-05"
)
SOURCE_CLOSURE_SCHEMA = "facman.remote_source_closure.v1"
LOWERCASE_COMMIT = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_REPOSITORIES = frozenset(
    {"factorio-launcher", "universal-launcher", "universal-setup"}
)
EXPECTED_ARTIFACTS = {
    "facman": "facman.exe",
    "candidate_smoke": "facman_hermetic_play_candidate_smoke.exe",
    "verdict_harness": "facman_gate4c_verdict_harness.exe",
    "evidence_probe": "facman_evidence_probe.exe",
    "cmake_cache": "CMakeCache.txt",
}


class QualificationError(RuntimeError):
    """A required qualification fact could not be established."""


@dataclass(frozen=True)
class QualifiedSource:
    repo_id: str
    path: Path
    revision: str
    required_ref: str
    remote: str


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(path))


def _strict_json(path: Path, context: str) -> dict[str, Any]:
    audit = PREFLIGHT.audit_no_follow(path, require_file=True)
    if not audit.get("safe"):
        raise QualificationError(f"{context} path is unsafe: {audit}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QualificationError(f"{context} is unreadable: {exc}") from exc
    if not isinstance(value, dict):
        raise QualificationError(f"{context} is not a JSON object")
    return value


def _run_git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=path,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != 0:
        raise QualificationError(
            f"{path.name}: git {' '.join(args)} failed: {result.stdout.strip()}"
        )
    return result.stdout.strip()


def _git_code(path: Path, *args: str) -> int:
    return subprocess.run(
        ["git", *args],
        cwd=path,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode


def _origin_ref(required_ref: str) -> str:
    prefix = "refs/heads/"
    if not isinstance(required_ref, str) or not required_ref.startswith(prefix):
        raise QualificationError("source closure contains a non-canonical ref")
    branch = required_ref.removeprefix(prefix)
    if not branch or ".." in branch or branch.startswith("/") or branch.endswith("/"):
        raise QualificationError("source closure contains an unsafe branch ref")
    return f"origin/{branch}"


def validate_remote_closure(
    report_path: Path,
    *,
    factorio_repository: Path,
    launcher_repository: Path,
    setup_repository: Path,
    candidate_build: Path,
) -> tuple[dict[str, QualifiedSource], dict[str, Any]]:
    """Validate the report and its live exact checkouts without network access."""

    report_path = _absolute(report_path)
    report = _strict_json(report_path, "remote source closure report")
    closure_schema = (
        ROOT
        / "contracts"
        / "schema"
        / "release"
        / "remote_source_closure.v1.schema.json"
    )
    closure_problems = json_contract.validate(
        report,
        json_contract.load_schema(closure_schema),
    )
    if closure_problems:
        raise QualificationError(
            "remote source closure report violates its schema: "
            + "; ".join(closure_problems)
        )
    if (
        report.get("schema") != SOURCE_CLOSURE_SCHEMA
        or report.get("status") != "pass"
        or report.get("claim") != "remote_source_closure_proven"
        or report.get("authority_promotion") is not False
        or report.get("factorio_execution") is not False
        or report.get("permit_issuance") is not False
        or report.get("publication") is not False
    ):
        raise QualificationError("remote source closure report is not an exact PASS")
    clone_policy = report.get("clone_policy")
    if not isinstance(clone_policy, dict) or clone_policy != {
        "alternates": False,
        "detached_exact_checkouts": True,
        "empty_directories": True,
        "git_clone_no_local": True,
        "https_remotes_only": True,
        "preexisting_objects": False,
    }:
        raise QualificationError("remote source closure policy is not exact")
    workspace = report.get("workspace")
    if (
        not isinstance(workspace, dict)
        or workspace.get("paths_are_local_observations") is not True
        or workspace.get("source_worktrees_clean_after_validation") is not True
    ):
        raise QualificationError("remote source closure workspace is not clean")
    clone_root = _absolute(Path(str(workspace.get("clone_root", ""))))
    build_root = _absolute(Path(str(workspace.get("build_root", ""))))
    expected_build = build_root / "factorio-launcher"
    if _absolute(candidate_build) != expected_build:
        raise QualificationError(
            "candidate build is not the reported FacMan remote-only build"
        )

    actual_paths = {
        "factorio-launcher": _absolute(factorio_repository),
        "universal-launcher": _absolute(launcher_repository),
        "universal-setup": _absolute(setup_repository),
    }
    if any(actual_paths[name] != clone_root / name for name in EXPECTED_REPOSITORIES):
        raise QualificationError(
            "repository paths are not the report's exact remote-only clones"
        )
    repositories = report.get("repositories")
    if not isinstance(repositories, list):
        raise QualificationError("remote source closure repository list is missing")
    records = {
        str(item.get("id", "")): item
        for item in repositories
        if isinstance(item, dict)
    }
    if set(records) != EXPECTED_REPOSITORIES or len(repositories) != 3:
        raise QualificationError("remote source closure repository set is not exact")

    result: dict[str, QualifiedSource] = {}
    for repo_id in sorted(EXPECTED_REPOSITORIES):
        item = records[repo_id]
        revision = item.get("pin")
        required_ref = item.get("required_ref")
        remote = item.get("remote")
        if (
            not isinstance(revision, str)
            or LOWERCASE_COMMIT.fullmatch(revision) is None
            or item.get("head") != revision
            or item.get("detached") is not True
            or item.get("clean") is not True
            or item.get("alternates") is not False
            or item.get("local_clone") is not False
            or item.get("canonical_ref_contains_pin") is not True
            or not isinstance(remote, str)
            or not remote.startswith("https://")
        ):
            raise QualificationError(f"{repo_id}: closure record is not exact")
        origin_ref = _origin_ref(str(required_ref))
        repo_path = actual_paths[repo_id]
        identity = PREFLIGHT.git_identity(
            repo_path,
            revision,
            required_ref=origin_ref,
        )
        if not identity.get("valid"):
            raise QualificationError(
                f"{repo_id}: live checkout differs from closure: {identity}"
            )
        if _git_code(repo_path, "symbolic-ref", "-q", "HEAD") == 0:
            raise QualificationError(f"{repo_id}: qualification checkout is not detached")
        if _run_git(repo_path, "remote", "get-url", "origin") != remote:
            raise QualificationError(f"{repo_id}: origin differs from closure")
        alternates = Path(_run_git(repo_path, "rev-parse", "--git-path", "objects/info/alternates"))
        if not alternates.is_absolute():
            alternates = (repo_path / alternates).resolve()
        if alternates.exists():
            raise QualificationError(f"{repo_id}: checkout unexpectedly uses alternates")
        result[repo_id] = QualifiedSource(
            repo_id=repo_id,
            path=repo_path,
            revision=revision,
            required_ref=origin_ref,
            remote=remote,
        )

    package = report.get("package")
    expected_revisions = {
        "factorio_launcher": result["factorio-launcher"].revision,
        "universal_launcher": result["universal-launcher"].revision,
        "universal_setup": result["universal-setup"].revision,
    }
    if (
        not isinstance(package, dict)
        or package.get("source_revisions") != expected_revisions
        or package.get("required_package_skips") != 0
        or package.get("runtime_smoke") != "pass"
        or package.get("archive_runtime_smoke") != "pass"
        or package.get("provenance_verification") != "pass"
        or package.get("installed_sdk_proof") is not True
    ):
        raise QualificationError(
            "remote source closure package proof is incomplete or stale"
        )
    return result, report


def resolve_artifacts(
    candidate_build: Path,
    configuration: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Path]]:
    if os.name != "nt":
        raise QualificationError("instance-isolated qualification requires Windows")
    if (
        not isinstance(configuration, str)
        or not configuration
        or Path(configuration).name != configuration
        or configuration in {".", ".."}
    ):
        raise QualificationError("candidate configuration is unsafe")
    root = _absolute(candidate_build)
    paths = {
        "facman": root / configuration / EXPECTED_ARTIFACTS["facman"],
        "candidate_smoke": root
        / configuration
        / EXPECTED_ARTIFACTS["candidate_smoke"],
        "verdict_harness": root
        / configuration
        / EXPECTED_ARTIFACTS["verdict_harness"],
        "evidence_probe": root
        / configuration
        / EXPECTED_ARTIFACTS["evidence_probe"],
        "cmake_cache": root / EXPECTED_ARTIFACTS["cmake_cache"],
    }
    evidence_io = EvidenceIo(paths["evidence_probe"])
    records: dict[str, dict[str, Any]] = {}
    for name, path in paths.items():
        inspected = evidence_io.inspect_file(path)
        relative = path.relative_to(root).as_posix()
        records[name] = {
            "relative_path": relative,
            "size": file_payload_size(inspected),
            "sha256": file_payload_sha256(inspected),
        }
    return records, paths


def _extract_source_member(
    source_artifact: Path,
    destination: Path,
    evidence_io: EvidenceIo,
) -> None:
    """Use the native bounded exact-member extraction before validation."""

    destination.parent.mkdir(parents=True, exist_ok=False)
    evidence_io.extract_exact_member(
        source_artifact,
        "Factorio_2.0.77/bin/x64/factorio.exe",
        destination,
    )


def factorio_identity(
    factorio_executable: Path,
    source_artifact: Path,
    source_member: Path,
    task_root: Path,
    evidence_io: EvidenceIo,
) -> tuple[dict[str, str], dict[str, Any]]:
    factorio_executable = _absolute(factorio_executable)
    source_artifact = _absolute(source_artifact)
    installed = PREFLIGHT.audit_no_follow(factorio_executable, require_file=True)
    if not installed.get("safe"):
        raise QualificationError(f"installed Factorio is unsafe: {installed}")
    source = PREFLIGHT.source_evidence(
        source_artifact,
        factorio_executable,
        source_member_executable=source_member,
        task_root=task_root,
        evidence_io=evidence_io,
    )
    if not source.get("valid"):
        raise QualificationError(
            f"Factorio source authentication did not pass: {source.get('reason')}"
        )
    signature = source.get("source_member", {}).get("signature", {})
    sha256 = file_payload_sha256(
        evidence_io.hash_file(factorio_executable)
    )
    signer_subject = str(signature.get("signer_subject") or "")
    if (
        sha256 != source.get("source_member", {}).get("sha256")
        or sha256
        != source.get("installed_executable_comparison", {}).get("sha256")
        or PREFLIGHT.EXPECTED_SIGNER not in signer_subject
        or not PREFLIGHT.exact_factorio_version(signature)
    ):
        raise QualificationError("Factorio executable identity is not exact")
    return (
        {
            "version": PREFLIGHT.EXPECTED_FACTORIO_VERSION,
            "sha256": sha256,
            "signer": PREFLIGHT.EXPECTED_SIGNER,
        },
        source,
    )


def derive_instance_identity(
    facman: Path,
    workspace: Path,
) -> tuple[dict[str, str], dict[str, Any]]:
    prefix = [str(facman), "--workspace", str(workspace)]
    instance_id = ROUTE.instance_id
    inspection = PREFLIGHT.run_json(
        prefix + ["instances", "inspect", instance_id, "--json"]
    )
    description = PREFLIGHT.run_json(
        prefix
        + ["instances", "describe", instance_id, "--intent", "menu", "--json"]
    )
    readiness = PREFLIGHT.run_json(
        prefix
        + ["instances", "readiness", instance_id, "--intent", "menu", "--json"]
    )
    launch = PREFLIGHT.run_json(
        prefix + ["launch", "plan", instance_id, "--preflight", "--json"]
    )
    digests = {
        "instance_id": instance_id,
        "spec_digest": str(
            description.get("instance_spec", {}).get("spec_digest", "")
        ),
        "binding_digest": str(
            description.get("instance_binding", {}).get("binding_digest", "")
        ),
        "readiness_digest": str(readiness.get("readiness_digest", "")),
    }
    blockers = {
        str(item.get("code"))
        for item in readiness.get("blockers", [])
        if isinstance(item, dict)
    }
    if (
        inspection.get("instance_id") != instance_id
        or inspection.get("factorio_version") != PREFLIGHT.EXPECTED_FACTORIO_VERSION
        or inspection.get("modset_status") != "present"
        or inspection.get("save_count") != 0
        or any(re.fullmatch(r"[0-9a-f]{64}", value) is None for value in digests.values() if value != instance_id)
        or blockers != {"real_play_gate_not_passed"}
        or readiness.get("execution_started") is not False
        or readiness.get("permit_issued") is not False
        or launch.get("status") != "pass"
        or launch.get("started") is not False
    ):
        raise QualificationError(
            "staged Instance did not produce the exact non-executing candidate projection"
        )
    return digests, {
        "inspection": inspection,
        "description": description,
        "readiness": readiness,
        "launch_preflight": launch,
    }


def qualification_value(
    sources: dict[str, QualifiedSource],
    artifacts: dict[str, dict[str, Any]],
    factorio: dict[str, str],
    instance: dict[str, str],
) -> dict[str, Any]:
    core: dict[str, Any] = {
        "schema": QUALIFICATION_SCHEMA,
        "canonicalization_version": CANONICALIZATION,
        "route_id": ROUTE.route_id,
        "work_unit": ROUTE.work_unit,
        "source_binding": {
            "factorio_launcher": {
                "revision": sources["factorio-launcher"].revision,
                "required_ref": sources["factorio-launcher"].required_ref,
            },
            "universal_launcher": {
                "revision": sources["universal-launcher"].revision,
                "required_ref": sources["universal-launcher"].required_ref,
            },
            "universal_setup": {
                "revision": sources["universal-setup"].revision,
                "required_ref": sources["universal-setup"].required_ref,
            },
        },
        "artifacts": artifacts,
        "factorio": factorio,
        "instance": instance,
    }
    return {**core, "qualification_digest": digest_value(core)}


def _validate_schema(
    value: dict[str, Any],
    filename: str,
    context: str,
) -> None:
    schema_path = (
        ROOT
        / "contracts"
        / "schema"
        / "factorio"
        / filename
    )
    problems = json_contract.validate(
        value,
        json_contract.load_schema(schema_path),
    )
    if problems:
        raise QualificationError(
            f"{context} violates its schema: {'; '.join(problems)}"
        )


def qualify(args: argparse.Namespace) -> dict[str, Any]:
    task_root = _absolute(args.task_root)
    candidate_build = _absolute(args.candidate_build)
    if task_root.name != QUALIFICATION_WORK_UNIT:
        raise QualificationError(
            "qualification root is not the exact qualification-05 root"
        )
    parent_audit = PREFLIGHT.audit_no_follow(
        task_root.parent,
        require_file=False,
    )
    if not parent_audit.get("safe"):
        raise QualificationError(
            f"qualification parent is unsafe: {parent_audit}"
        )
    if task_root.exists():
        root_audit = PREFLIGHT.audit_no_follow(
            task_root,
            require_file=False,
        )
        if not root_audit.get("safe"):
            raise QualificationError(
                f"qualification root is unsafe: {root_audit}"
            )
    if task_root.exists() and any(task_root.iterdir()):
        raise QualificationError("qualification root must be empty")

    sources, closure = validate_remote_closure(
        args.remote_source_closure,
        factorio_repository=args.repository_root,
        launcher_repository=args.launcher_repository,
        setup_repository=args.setup_repository,
        candidate_build=candidate_build,
    )
    artifacts, artifact_paths = resolve_artifacts(
        candidate_build,
        args.configuration,
    )
    evidence_io = EvidenceIo(artifact_paths["evidence_probe"])
    stable_closure = evidence_io.read_json(
        _absolute(args.remote_source_closure)
    )["payload"]["document"]
    if stable_closure != closure:
        raise QualificationError(
            "remote source closure changed during qualification"
        )
    factorio_executable = _absolute(args.factorio_executable)
    source_artifact = _absolute(args.source_artifact)
    task_root.mkdir(exist_ok=True)
    source_member = (
        task_root / "source" / "portable-package-inspection" / "factorio.exe"
    )
    _extract_source_member(source_artifact, source_member, evidence_io)
    factorio, source_evidence = factorio_identity(
        factorio_executable,
        source_artifact,
        source_member,
        task_root,
        evidence_io,
    )
    workspace = task_root / "workspace"
    COORDINATOR._stage_workspace(  # pylint: disable=protected-access
        workspace,
        ROUTE.instance_id,
        factorio_executable,
        factorio,
    )
    instance, projections = derive_instance_identity(
        artifact_paths["facman"],
        workspace,
    )
    value = qualification_value(
        sources,
        artifacts,
        factorio,
        instance,
    )
    _validate_schema(
        value,
        "play_candidate_qualification_binding.v4.schema.json",
        "qualification binding",
    )
    qualification_path = (
        task_root / "qualification" / "qualification-binding.v4.json"
    )
    qualification_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_io.write_new_json(qualification_path, value)
    loaded_result = evidence_io.read_json(qualification_path)
    loaded = parse_qualification_binding(
        loaded_result["payload"]["document"], ROUTE
    )
    if loaded.qualification_digest != value["qualification_digest"]:
        raise QualificationError("qualification binding did not reload exactly")

    report_core: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "canonicalization_version": CANONICALIZATION,
        "status": "pass",
        "route_id": ROUTE.route_id,
        "work_unit": ROUTE.work_unit,
        "qualification_work_unit": QUALIFICATION_WORK_UNIT,
        "remote_source_closure": {
            "path": str(_absolute(args.remote_source_closure)),
            "sha256": file_payload_sha256(
                evidence_io.hash_file(_absolute(args.remote_source_closure))
            ),
            "observed_at_utc": closure.get("observed_at_utc"),
        },
        "qualification_binding": {
            "path": str(qualification_path),
            "sha256": file_payload_sha256(
                evidence_io.hash_file(qualification_path)
            ),
            "qualification_digest": loaded.qualification_digest,
        },
        "source_binding": value["source_binding"],
        "artifacts": artifacts,
        "factorio": {
            **factorio,
            "source_artifact_sha256": file_payload_sha256(
                evidence_io.hash_file(source_artifact)
            ),
            "authentication_evidence_digest": source_evidence.get(
                "authentication_evidence_digest"
            ),
        },
        "instance": instance,
        "projection_digests": {
            "inspection": digest_value(projections["inspection"]),
            "description": digest_value(projections["description"]),
            "readiness": digest_value(projections["readiness"]),
            "launch_preflight": digest_value(projections["launch_preflight"]),
        },
        "authority_promotion": False,
        "factorio_execution": False,
        "permit_issuance": False,
        "observer_capture": False,
        "human_verdict": False,
    }
    report = {
        **report_core,
        "report_digest": digest_value(report_core),
    }
    _validate_schema(
        report,
        "instance_isolated_candidate_qualification.v4.schema.json",
        "qualification report",
    )
    report_path = task_root / "qualification" / "qualification-report.v4.json"
    evidence_io.write_new_json(report_path, report)
    return {
        "status": "pass",
        "qualification_binding": str(qualification_path),
        "qualification_digest": loaded.qualification_digest,
        "qualification_report": str(report_path),
        "workspace": str(workspace),
        "source_member_executable": str(source_member),
        "factorio_execution": False,
        "permit_issuance": False,
        "authority_promotion": False,
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--task-root", required=True, type=Path)
    value.add_argument("--remote-source-closure", required=True, type=Path)
    value.add_argument("--candidate-build", required=True, type=Path)
    value.add_argument("--configuration", default="Debug")
    value.add_argument("--repository-root", required=True, type=Path)
    value.add_argument("--launcher-repository", required=True, type=Path)
    value.add_argument("--setup-repository", required=True, type=Path)
    value.add_argument("--factorio-executable", required=True, type=Path)
    value.add_argument("--source-artifact", required=True, type=Path)
    return value


def main() -> int:
    result = qualify(parser().parse_args())
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        QualificationError,
        COORDINATOR.CoordinatorError,
        PREFLIGHT.PreflightError,
        StableIoError,
        OSError,
        ValueError,
    ) as exc:
        print(f"instance-isolated-candidate-qualification: {exc}", file=sys.stderr)
        raise SystemExit(2)
